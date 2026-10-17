#!/usr/bin/env python3
"""Measure native authoring, completion, compilation, and verification.

No historical proof or solver is replayed. These records measure the current
native Python API; they are not reformulation-quality acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REFORM = ROOT.parent / "reform_test"
SOURCES = {
    "test9": REFORM / "runs/test9-nomf-20261004-004349/input/model.mps",
    "test16": REFORM / "runs/test16-nomf-B1/input/model.mps",
    "test10": REFORM / "runs/test10-nomf-B1/input/model.mps",
}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def memory():
    unit = 1 if platform.system() == "Darwin" else 1024
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"python_max_rss_bytes": own.ru_maxrss * unit,
            "native_child_max_rss_bytes": child.ru_maxrss * unit,
            "python_user_seconds": own.ru_utime, "python_system_seconds": own.ru_stime,
            "child_user_seconds": child.ru_utime, "child_system_seconds": child.ru_stime}


def synthetic(path, size=1000):
    lines = ["NAME synthetic_identity", "ROWS", " N objective"]
    lines.extend(f" L row{i}" for i in range(size))
    lines.append("COLUMNS")
    for i in range(size):
        lines.append(f" x{i} objective 0.125")
        lines.append(f" x{i} row{i} 1")
        lines.append(f" x{i} row{(i + 1) % size} 1")
    lines.append("RHS")
    lines.extend(f" rhs row{i} 1" for i in range(size))
    lines.append("BOUNDS")
    lines.extend(f" BV bound x{i}" for i in range(size))
    lines.append("ENDATA")
    path.write_text("\n".join(lines) + "\n")
    return path


def worker(args):
    sys.path.insert(0, str(ROOT / "python"))
    from kernel_compiler import Kernel, Model, Proof
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    record_path = output / "record.json"
    if record_path.exists():
        raise ValueError("Refusing to overwrite a preserved benchmark record")
    source = Path(args.source).resolve() if args.source else SOURCES.get(args.worker)
    if args.worker == "synthetic-1000":
        source = synthetic(output / "synthetic.mps")
    if source is None or not source.is_file():
        raise ValueError(f"No pristine source for {args.worker!r}")
    source_files = sorted((ROOT / "python/kernel_compiler").glob("*.py"))
    source_files.append(ROOT / "python/pyproject.toml")
    code_hashes = {str(p.relative_to(ROOT)): digest(p) for p in source_files}
    record = {"schema": "kernel-compiler-api-performance-2", "case": args.worker,
              "status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
              "source": {"path": str(source), "bytes": source.stat().st_size, "sha256": digest(source)},
              "python": {"executable": sys.executable, "version": sys.version},
              "platform": platform.platform(), "package_hashes": code_hashes,
              "script_sha256": digest(__file__), "phases": [], "native_calls": [],
              "rss_note": "Python process high-water mark; native work is in-process"}

    class MeasuredKernel(Kernel):
        def call(self, *command, **kwargs):
            start = time.perf_counter_ns()
            entry = {"command": list(map(str, command))}
            try:
                result = super().call(*command, **kwargs)
                entry["result"] = result
                return result
            finally:
                entry["wall_ns"] = time.perf_counter_ns() - start
                record["native_calls"].append(entry)

    def save():
        record["memory_high_water"] = memory()
        record_path.write_text(json.dumps(record, indent=2) + "\n")

    def phase(name, callback):
        start = time.perf_counter_ns()
        before = len(record["native_calls"])
        result = callback()
        entry = {"name": name, "wall_ns": time.perf_counter_ns() - start,
                 "native_calls": len(record["native_calls"]) - before,
                 "memory_high_water": memory()}
        record["phases"].append(entry)
        save()
        print(json.dumps({"case": args.worker, "phase": name, "seconds": entry["wall_ns"] / 1e9,
                          "python_rss_mib": entry["memory_high_water"]["python_max_rss_bytes"] / 2**20}), flush=True)
        if entry["memory_high_water"]["python_max_rss_bytes"] > args.max_rss_gib * 2**30:
            raise MemoryError("Benchmark exceeded its Python process high-water guard")
        return result

    try:
        kernel = MeasuredKernel()
        model = phase("model_load", lambda: Model.load(source, kernel=kernel))
        record["model_shape"] = model.stats()
        proof = phase("proof_construction", lambda: Proof(model, model, kernel=kernel))
        forward, reverse = proof.forward, proof.reverse
        phase("map_complete_forward", lambda: forward.map("identity").complete())
        phase("map_complete_reverse", lambda: reverse.map("identity").complete())
        record["obligations"] = [len(proof.certificate()["forward"]["end"]["Return"]["checks"]),
                                 len(proof.certificate()["reverse"]["end"]["Return"]["checks"])]
        artifacts = phase("compile", lambda: proof.compile(output / "delivery"))
        if not (artifacts["proof"].parent / "proof.rpa").is_file():
            raise AssertionError("native compile did not preserve RPA 12")
        if (artifacts["proof"].parent / "certificate.json").exists():
            raise AssertionError("native compile unexpectedly produced certificate.json")
        verification = phase("verify", lambda: kernel.verify(artifacts["source"], artifacts["target"], artifacts["proof"]))
        record["verification"] = verification
        if verification["status"] != "VERIFIED":
            raise AssertionError(f"Identity proof was not VERIFIED: {verification}")
        record["artifacts"] = {key: {"path": str(value), "bytes": value.stat().st_size, "sha256": digest(value)}
                               for key, value in artifacts.items()}
        record["package_hashes_after"] = {str(p.relative_to(ROOT)): digest(p) for p in source_files}
        if record["package_hashes_after"] != code_hashes:
            raise AssertionError("Benchmark code changed during the observation")
        record["status"] = "VERIFIED"
        record["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    except BaseException as error:
        record["status"] = "FAILED"
        record["error"] = str(error)
        record["traceback"] = traceback.format_exc()
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["synthetic-1000", "test9", "test16"])
    parser.add_argument("--max-rss-gib", type=float, default=6)
    parser.add_argument("--compact-only", action="store_true", help="accepted for existing invocations; native path is always compact")
    parser.add_argument("--worker", choices=["synthetic-1000", *SOURCES])
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Choose a fresh output directory; preserved records are never overwritten")
    output.mkdir(parents=True)
    summary = {"schema": "kernel-compiler-api-performance-suite-2", "status": "RUNNING",
               "cases": [], "note": "One fresh worker observation per case"}
    for case in args.cases:
        if case not in ["synthetic-1000", *SOURCES]:
            raise ValueError(f"Unknown case {case!r}")
        command = [sys.executable, str(Path(__file__).resolve()), "--worker", case,
                   "--output", str(output / case), "--max-rss-gib", str(args.max_rss_gib)]
        if args.source:
            command.extend(["--source", str(args.source.resolve())])
        result = subprocess.run(command)
        record_path = output / case / "record.json"
        summary["cases"].append({"case": case, "record": str(record_path), "exit_code": result.returncode})
    summary["status"] = "COMPLETE"
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
