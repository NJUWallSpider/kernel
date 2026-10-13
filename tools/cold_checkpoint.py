#!/usr/bin/env python3
"""Save immutable kernel/spec/test inputs and cold-build/test a locked candidate.

This records build evidence only. Corpus scope and every request are checked
separately by check_delivery.py, run_acceptance.py and the acceptance ledger.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]

def identity(path):
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.label):
        raise SystemExit("Invalid label")
    source = ROOT / "audit/checkpoints" / (args.label + "-source")
    manifest_path = source.with_suffix(".json")
    build = ROOT / "target" / ("validation-" + args.label)
    report_path = ROOT / "audit/validation" / (args.label + "-cold-build.json")
    if any(p.exists() for p in [source, manifest_path, build, report_path]):
        raise SystemExit("Use a fresh label; immutable evidence already exists")
    files = [ROOT / x for x in ["Cargo.toml", "Cargo.lock", "README.md",
                              "audit/subflow-next/fixtures/oracle.json"]]
    for folder in ["crates", "tests", "docs"]:
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                     and not set(p.parts).intersection({"target", "__pycache__", ".build"})
                     and p.name != ".DS_Store")
    entries = {}
    for path in sorted(set(files)):
        relative = path.relative_to(ROOT)
        before = identity(path)
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        if identity(path) != before or identity(destination) != before:
            raise RuntimeError(f"Source changed while snapshotting: {relative}")
        entries[str(relative)] = before
    manifest_path.write_text(json.dumps({
        "status": "IMMUTABLE_KERNEL_CHECKPOINT_NOT_PROTOCOL_FREEZE",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files": entries,
    }, indent=2) + "\n")
    report = {"status": "RUNNING", "driver": identity(Path(__file__)),
              "source_root": str(source), "source_manifest": str(manifest_path),
              "source_manifest_identity": identity(manifest_path), "commands": []}
    for kind, extra in [("release", ["build", "--release"]), ("tests", ["test"])]:
        command = ["cargo", *extra, "--manifest-path", str(source / "Cargo.toml"),
                   "-p", "kernel-core", "--locked", "--target-dir", str(build)]
        start = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = report_path.with_name(args.label + "-cold-" + kind + ".log")
        log.write_text(result.stdout + result.stderr)
        record = {"command": command, "exit_code": result.returncode,
                  "seconds": time.perf_counter() - start, "log": str(log), **identity(log)}
        if kind == "tests":
            record["tests_passed"] = sum(map(int, re.findall(r"test result: ok\. (\d+) passed", result.stdout)))
        report["commands"].append(record)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(kind, result.returncode, flush=True)
        if result.returncode:
            report["status"] = "FAILED"
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            raise SystemExit(result.returncode)
    binary = build / "release/rpx"
    report.update(status="PASS", binary={"path": str(binary), **identity(binary)})
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(report_path, flush=True)

if __name__ == "__main__":
    main()
