#!/usr/bin/env python3
"""Rebuild and verify the manual's complete examples using the current CLI.

This is an untrusted documentation replay, not an additional acceptance authority.
All MCM/RPX and mutation files are created in a temporary directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "docs/rpx/examples"
EXPECTED = {"redundant": 9, "elimination": 9, "piecewise": 9}
REVERSE_MAPS = {
    "redundant": ("ret (x0)", "ret (1 + x0)"),
    "elimination": ("ret (1 - x0, x0)", "ret (-x0, x0)"),
    "piecewise": ("ret (x0)", "ret (1 + x0)"),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matching_paren(text, start):
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == ";":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise RuntimeError("unterminated parenthesized list")


def remove_last_forward_check(text):
    """Remove the last check from the first ret's second list in .forward."""
    forward = text.index(".forward")
    match = re.search(r"(?m)^\s*ret\b", text[forward:])
    if match is None:
        raise RuntimeError("missing forward ret")
    ret = forward + match.start()
    first_open = text.index("(", ret)
    first_close = matching_paren(text, first_open)
    second_open = text.index("(", first_close + 1)
    second_close = matching_paren(text, second_open)

    position = text.rfind("\n", 0, second_close) + 1
    while position > second_open:
        previous_end = position - 1
        previous_start = text.rfind("\n", 0, previous_end) + 1
        content = text[previous_start:previous_end].split(";", 1)[0].strip()
        if content and content != ")":
            return text[:previous_start] + text[position:]
        position = previous_start
    raise RuntimeError("checks list has no removable check line")


def replace_reverse_map(text, name):
    old, new = REVERSE_MAPS[name]
    reverse = text.index(".reverse")
    head, tail = text[:reverse], text[reverse:]
    if old not in tail:
        raise RuntimeError(f"{name}: reverse map not found")
    return head + tail.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=ROOT / "target/release/rpx")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    kernel = args.kernel.resolve()
    commands = []

    def run(arguments, status, exit_code=0):
        proc = subprocess.run([str(kernel), *map(str, arguments)],
                              text=True, capture_output=True, check=False)
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"CLI did not return JSON: {proc.stdout!r} {proc.stderr!r}") from exc
        if proc.returncode != exit_code or report.get("status") != status:
            raise RuntimeError(f"unexpected CLI result: {arguments}: {proc.returncode}: {report}")
        commands.append({"operation": arguments[0], "status": status, "exit": proc.returncode})
        return report

    results = []
    with tempfile.TemporaryDirectory(prefix="rpx-manual-") as tmp:
        temporary = Path(tmp)
        for name, obligations in EXPECTED.items():
            fixture = FIXTURES / name
            work = temporary / name
            work.mkdir()
            source, target = work / "source.mcm", work / "target.mcm"
            proof = work / "proof.rpx"
            for model, output in (("source", source), ("target", target)):
                run(["canonical", fixture / f"{model}.lp", output], "CANONICALIZED")
            run(["assemble", fixture / "proof.rpa", proof], "ASSEMBLED")
            success = run(["verify", source, target, proof], "VERIFIED")
            if success["statistics"]["obligations"] != obligations:
                raise RuntimeError(f"{name}: obligation count changed: {success}")

            recovered, encoded = work / "recovered.rpa", work / "recovered.rpx"
            run(["disassemble", proof, recovered], "DISASSEMBLED")
            run(["assemble", recovered, encoded], "ASSEMBLED")
            if encoded.read_bytes() != proof.read_bytes():
                raise RuntimeError(f"{name}: disassembly/reassembly changed RPX bytes")
            run(["verify", source, target, encoded], "VERIFIED")

            canonical = (fixture / "proof.rpa").read_text(encoding="utf-8")
            missing_text, missing_binary = work / "missing.rpa", work / "missing.rpx"
            missing_text.write_text(remove_last_forward_check(canonical), encoding="utf-8")
            run(["assemble", missing_text, missing_binary], "ASSEMBLED")
            missing_result = run(["verify", source, target, missing_binary], "INVALID", 2)
            if "missing obligation" not in missing_result["message"]:
                raise RuntimeError(f"{name}: unexpected missing-obligation failure: {missing_result}")

            legacy_text, legacy_binary = work / "legacy.rpa", work / "legacy.rpx"
            legacy_text.write_text("RPA 11\n{}\n", encoding="utf-8")
            legacy_result = run(["assemble", legacy_text, legacy_binary], "INVALID", 2)

            wrong_text, wrong_binary = work / "wrong.rpa", work / "wrong.rpx"
            wrong_text.write_text(replace_reverse_map(canonical, name), encoding="utf-8")
            run(["assemble", wrong_text, wrong_binary], "ASSEMBLED")
            wrong_result = run(["verify", source, target, wrong_binary], "INVALID", 2)
            if not any(message in wrong_result["message"] for message in
                       ("obligation mismatch", "non-tautological exact obligation")):
                raise RuntimeError(f"{name}: unexpected recovery failure: {wrong_result}")

            budget = run(["verify", "--work", "0", source, target, proof], "RESOURCE_LIMIT", 3)
            results.append({
                "example": name,
                "files": {file: digest(fixture / file)
                          for file in ("source.lp", "target.lp", "proof.rpa")},
                "rpx_sha256": digest(proof), "rpx_bytes": proof.stat().st_size,
                "guarantee": success["guarantee"], "statistics": success["statistics"],
                "roundtrip": "byte-identical and VERIFIED",
                "negative_results": {"missing_obligation": missing_result,
                                     "legacy_header": legacy_result,
                                     "wrong_recovery": wrong_result,
                                     "zero_work": budget},
            })
    receipt = {"kernel_sha256": digest(kernel), "examples": results,
               "commands": commands, "result": "PASS"}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "examples": len(results),
                      "negative_checks": 12, "cli_commands": len(commands)}, sort_keys=True))


if __name__ == "__main__":
    main()
