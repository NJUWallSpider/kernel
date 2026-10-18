#!/usr/bin/env python3
"""Build, assemble and verify cases through the native kernel API only.

This is the current case pipeline. It has no LP parser, historical model
dictionaries, per-case proof scripts, subprocess calls, or certificate JSON.
A case is one source MCM, one target MCM, one RPA 12 source, and one RPX 11
proof. The native core owns verification and RPA/RPX conversion.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from kernel_compiler import Kernel, KernelError, Model, Proof  # noqa: E402

ARTIFACTS = ("source.mcm", "target.mcm", "proof.rpa", "proof.rpx", "delivery.json")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def case_paths(root):
    root = Path(root).resolve()
    paths = {"root": root}
    paths.update({name: root / name for name in ARTIFACTS})
    missing = [name for name in ("source.mcm", "target.mcm", "proof.rpa", "proof.rpx")
               if not paths[name].is_file()]
    if missing:
        raise FileNotFoundError(f"{root}: missing {', '.join(missing)}")
    return paths


def delivery_audit(paths):
    delivery = paths["root"] / "delivery.json"
    if not delivery.is_file():
        return {"status": "MISSING"}
    document = json.loads(delivery.read_text())
    records = document.get("artifacts", {})
    aliases = {"source.mcm": ("source.mcm", "source"),
               "target.mcm": ("target.mcm", "target"),
               "proof.rpa": ("proof.rpa", "rpa"),
               "proof.rpx": ("proof.rpx", "proof")}
    mismatches = []
    for name in ("source.mcm", "target.mcm", "proof.rpa", "proof.rpx"):
        record = next((records.get(key) for key in aliases[name] if records.get(key)), None)
        if record is None:
            mismatches.append({"artifact": name, "reason": "not listed"})
            continue
        actual = digest(paths["root"] / name)
        if actual != record.get("sha256"):
            mismatches.append({"artifact": name, "expected": record.get("sha256"), "actual": actual})
    return {"status": "MATCHED" if not mismatches else "MISMATCH", "mismatches": mismatches}


def verify_case(root, *, audit=True):
    paths = case_paths(root)
    kernel = Kernel()
    report = kernel.verify(paths["source.mcm"], paths["target.mcm"], paths["proof.rpx"])
    result = {
        "case": paths["root"].name,
        "status": report.get("status"),
        "guarantee": report.get("guarantee"),
        "obligations": report.get("statistics", {}).get("obligations"),
    }
    if audit:
        result["delivery"] = delivery_audit(paths)
    return result


def assemble_case(root, *, write=False):
    paths = case_paths(root)
    with tempfile.TemporaryDirectory(dir=paths["root"], prefix=".assemble-") as temporary:
        candidate = Path(temporary) / "proof.rpx"
        report = Kernel().call("assemble", paths["proof.rpa"], candidate)
        expected = digest(paths["proof.rpx"])
        actual = digest(candidate)
        if expected != actual:
            raise ValueError(f"{paths['root'].name}: assembled RPX differs from proof.rpx "
                             f"({expected} != {actual})")
        if write:
            candidate.replace(paths["proof.rpx"])
        return {"case": paths["root"].name, "status": "MATCHED",
                "artifact": "proof.rpx", "sha256": actual,
                "reported": report}


def disassemble_case(root, *, write=False):
    paths = case_paths(root)
    with tempfile.TemporaryDirectory(dir=paths["root"], prefix=".disassemble-") as temporary:
        candidate = Path(temporary) / "proof.rpa"
        report = Kernel().call("disassemble", paths["proof.rpx"], candidate)
        expected = digest(paths["proof.rpa"])
        actual = digest(candidate)
        if expected != actual:
            raise ValueError(f"{paths['root'].name}: disassembled RPA differs from proof.rpa "
                             f"({expected} != {actual})")
        if write:
            candidate.replace(paths["proof.rpa"])
        return {"case": paths["root"].name, "status": "MATCHED",
                "artifact": "proof.rpa", "sha256": actual,
                "reported": report}


def check_case(root, *, write=False):
    verified = verify_case(root)
    assembled = assemble_case(root)
    disassembled = disassemble_case(root)
    return {"case": verified["case"], "status": verified["status"],
            "guarantee": verified["guarantee"], "obligations": verified["obligations"],
            "delivery": verified["delivery"], "assemble": assembled["status"],
            "disassemble": disassembled["status"]}


def _recipe(path):
    spec = importlib.util.spec_from_file_location("case_recipe", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load recipe {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build = getattr(module, "build", None)
    if not callable(build):
        raise ValueError("Recipe must export build(source: Model, target: Model) -> Proof")
    return build


def compile_recipe(*, source, target, recipe, out):
    source = Model.load(source)
    target = Model.load(target)
    proof = _recipe(recipe)(source, target)
    if not isinstance(proof, Proof):
        raise TypeError("Recipe build() must return Proof")
    report = proof.verify(out)
    return {"case": Path(out).resolve().name, "status": report.get("status"),
            "guarantee": report.get("guarantee"),
            "obligations": report.get("statistics", {}).get("obligations")}


def case_dirs(values):
    if values:
        return [Path(value) for value in values]
    return sorted(path for path in (ROOT / "cases").iterdir()
                  if path.is_dir() and (path / "source.mcm").is_file())


def run_cases(action, roots, *, jobs=1):
    results = []
    errors = []
    if jobs <= 1 or len(roots) <= 1:
        for root in roots:
            try:
                results.append(action(root))
            except (OSError, ValueError, KeyError, TypeError, KernelError) as error:
                errors.append({"case": Path(root).name, "error": str(error)})
        return results, errors
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        pending = {pool.submit(action, root): Path(root) for root in roots}
        for future in as_completed(pending):
            root = pending[future]
            try:
                results.append(future.result())
            except (OSError, ValueError, KeyError, TypeError, KernelError) as error:
                errors.append({"case": root.name, "error": str(error)})
    results.sort(key=lambda item: item["case"])
    errors.sort(key=lambda item: item["case"])
    return results, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="verify MCM + RPX through the native kernel")
    verify.add_argument("cases", nargs="*", type=Path)
    verify.add_argument("--jobs", type=int, default=1)
    verify.add_argument("--no-audit", action="store_true", help="skip delivery.json hashes")

    for name, help_text in (("assemble", "RPA 12 -> RPX 11"), ("disassemble", "RPX 11 -> RPA 12")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("cases", nargs="*", type=Path)
        command.add_argument("--jobs", type=int, default=1)
        command.add_argument("--write", action="store_true", help="replace the artifact atomically on a match")

    check = sub.add_parser("check", help="verify and check both conversions against hashes")
    check.add_argument("cases", nargs="*", type=Path)
    check.add_argument("--jobs", type=int, default=1)

    compile_case = sub.add_parser("compile", help="compile a native Python recipe")
    compile_case.add_argument("--source", type=Path, required=True)
    compile_case.add_argument("--target", type=Path, required=True)
    compile_case.add_argument("--recipe", type=Path, required=True)
    compile_case.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "compile":
            result = compile_recipe(source=args.source, target=args.target,
                                    recipe=args.recipe, out=args.out)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["status"] == "VERIFIED" else 1
        roots = case_dirs(args.cases)
        if args.command == "verify":
            action = lambda root: verify_case(root, audit=not args.no_audit)
        elif args.command == "assemble":
            action = lambda root: assemble_case(root, write=args.write)
        elif args.command == "disassemble":
            action = lambda root: disassemble_case(root, write=args.write)
        else:
            action = lambda root: check_case(root, write=False)
        results, errors = run_cases(action, roots, jobs=args.jobs)
        for item in results:
            print(json.dumps(item, sort_keys=True))
        for item in errors:
            print(json.dumps(item, sort_keys=True), file=sys.stderr)
        failed = [item for item in results if item.get("status") != "VERIFIED"] \
            if args.command in ("verify", "check") else []
        for item in results:
            if args.command == "check" and (item.get("delivery", {}).get("status") != "MATCHED"
                                            or item.get("assemble") != "MATCHED"
                                            or item.get("disassemble") != "MATCHED"):
                failed.append(item)
        return 0 if not errors and not failed else 1
    except (OSError, ValueError, KeyError, TypeError, KernelError) as error:
        print(json.dumps({"status": "ERROR", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
