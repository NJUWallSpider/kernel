#!/usr/bin/env python3
"""Regression replay of previously VERIFIED shipped case certificates.

Existing proof.rpa files are fixture containers only: remove their version
header, pass the raw Certificate JSON directly to compile, compare frozen RPX
bytes, and independently verify the caller-bound complete request. This is not
an Agent experiment or evidence of newly discovered reformulations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from case_delivery import load_delivery, sha  # noqa: E402


def run(binary, *args):
    started = time.perf_counter()
    result = subprocess.run([str(binary), *map(str, args)], capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = {"status": "EXECUTION_FAILED", "stdout": result.stdout}
    return {"exit_code": result.returncode, "seconds": time.perf_counter() - started,
            "result": report, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=ROOT / "target/release/rpx")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--cases", type=int, nargs="*", help="Default: all existing VERIFIED deliveries")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = sorted((ROOT / "cases").glob("test*/preparation.json"),
                   key=lambda path: int(path.parent.name[4:]))
    if args.cases:
        cases = [path for path in cases if int(path.parent.name[4:]) in args.cases]
    cases = [path for path in cases if json.loads(path.read_text()).get("status") == "VERIFIED"]
    started = time.perf_counter()
    source_identity = {str(path.relative_to(ROOT)): sha(path)
                       for path in sorted((ROOT / "crates/core/src").rglob("*.rs"))}
    source_identity["Cargo.lock"] = sha(ROOT / "Cargo.lock")
    source_hash = hashlib.sha256(json.dumps(source_identity, sort_keys=True).encode()).hexdigest()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    records = []
    with tempfile.TemporaryDirectory(prefix="kernel-compiler-corpus-") as directory:
        temp = Path(directory)
        binary = temp / "rpx"
        shutil.copy2(args.kernel.resolve(), binary)
        binary.chmod(0o500)
        binary_hash = sha(binary)
        metadata = {"format": "compiler-shipped-corpus-replay-1", "git_head": head,
                    "started_at_utc": datetime.now(timezone.utc).isoformat(),
                    "release_binary_sha256": binary_hash, "source_tree_sha256": source_hash,
                    "source_files": source_identity, "selected_cases": [path.parent.name for path in cases],
                    "method": "existing VERIFIED fixture -> raw Certificate JSON -> direct compile -> byte parity -> independent complete Request verification",
                    "scope": "regression of shipped artifacts; not autonomous Agent acceptance"}
        (args.output / "identity.json").write_text(json.dumps(metadata, indent=2) + "\n")
        with (args.output / "results.jsonl").open("w") as log:
            for preparation in cases:
                case = preparation.parent
                delivery = load_delivery(case)
                for piece in delivery["pieces"]:
                    item_started = time.perf_counter()
                    raw = temp / "certificate.json"
                    compiled = temp / "compiled.rpx"
                    with Path(piece["rpa"]).open("rb") as source, raw.open("wb") as destination:
                        header = source.readline(32)
                        if not header.startswith(b"RPA ") or not header.endswith(b"\n"):
                            raise ValueError(f"Unexpected fixture header: {piece['rpa']}")
                        shutil.copyfileobj(source, destination, length=4 * 1024 * 1024)
                    compilation = run(binary, "compile", raw, compiled)
                    hashes = {role: {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                                     "sha256": sha(path)} for role, path in
                              (("source", delivery["source"]), ("target", delivery["target"]),
                               ("proof", Path(piece["rpx"])), ("request", Path(piece["request"])))}
                    same_rpx = compilation["exit_code"] == 0 and sha(compiled) == hashes["proof"]["sha256"]
                    verification = run(binary, "verify", delivery["source"], delivery["target"],
                                       compiled, piece["request"]) if compilation["exit_code"] == 0 else None
                    old_stats = piece["result"]["statistics"]
                    new_stats = verification["result"].get("statistics", {}) if verification else {}
                    # Newly introduced zero statistics may be omitted by serde.
                    same_stats = all(old_stats.get(key, 0) == new_stats.get(key, 0)
                                     for key in old_stats.keys() | new_stats.keys())
                    status = "PASS" if (same_rpx and verification and verification["exit_code"] == 0
                                         and verification["result"].get("status") == "VERIFIED") else "FAIL"
                    record = {"case": case.name, "piece": piece["id"], "delivery_kind": delivery["kind"],
                              "status": status, "artifacts": hashes, "raw_json_bytes": raw.stat().st_size,
                              "raw_json_sha256": sha(raw), "compilation": compilation,
                              "rpx_byte_identity": same_rpx, "verification": verification,
                              "historical_receipt_statistics_identity": same_stats,
                              "elapsed_seconds": time.perf_counter() - item_started}
                    records.append(record)
                    log.write(json.dumps(record, separators=(",", ":")) + "\n")
                    log.flush()
                    print(json.dumps({"case": case.name, "piece": piece["id"], "status": status,
                                      "compile_seconds": compilation["seconds"],
                                      "verify_seconds": verification["seconds"] if verification else None}), flush=True)
        versions = Counter(str(item["compilation"]["result"].get("version")) for item in records)
        summary = {"status": "PASS" if records and all(item["status"] == "PASS" for item in records) else "FAIL",
                   "case_count": len(cases), "piece_count": len(records),
                   "passed_pieces": sum(item["status"] == "PASS" for item in records),
                   "wire_versions": dict(sorted(versions.items())),
                   "elapsed_seconds": time.perf_counter() - started,
                   "compile_seconds": sum(item["compilation"]["seconds"] for item in records),
                   "verify_seconds": sum(item["verification"]["seconds"] for item in records if item["verification"]),
                   "raw_json_bytes": sum(item["raw_json_bytes"] for item in records),
                   "max_raw_json_bytes": max(item["raw_json_bytes"] for item in records),
                   "rpx_bytes": sum(item["artifacts"]["proof"]["bytes"] for item in records),
                   "release_binary_sha256": binary_hash, "binary_identity_unchanged": sha(binary) == binary_hash,
                   "source_tree_sha256": source_hash, "results_sha256": sha(args.output / "results.jsonl"),
                   "historical_receipt_statistics_differences": [item["case"] for item in records if not item["historical_receipt_statistics_identity"]],
                   "pre_compiler_baseline_check": "PENDING (run baseline.py)",
                   "failures": [{"case": item["case"], "piece": item["piece"]} for item in records if item["status"] != "PASS"],
                   "scope": "regression of shipped artifacts; not autonomous Agent acceptance"}
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2), flush=True)
        return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
