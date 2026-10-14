#!/usr/bin/env python3
"""Compare completed direct-compiler replays with pre-compiler c16fdaf.

Historical preparation receipts span earlier accounting implementations. Build
the explicit pre-compiler revision and check all current work and
obligation counters against that baseline, keeping historical drift visible.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time

from replay import ROOT, run, sha


def main():
    directory = Path(__file__).resolve().parent
    identity_path = directory / "identity.json"
    identity = json.loads(identity_path.read_text())
    records_path = directory / "results.jsonl"
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    baseline_commit = subprocess.run(["git", "rev-parse", "c16fdaf"], cwd=ROOT,
                                     capture_output=True, text=True, check=True).stdout.strip()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="kernel-compiler-baseline-") as temporary:
        source = Path(temporary)
        archive = subprocess.run(["git", "archive", baseline_commit, "Cargo.toml", "Cargo.lock", "crates"],
                                 cwd=ROOT, capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as files:
            for member in files.getmembers():
                if not (source / member.name).resolve().is_relative_to(source.resolve()) or member.issym() or member.islnk():
                    raise ValueError("Unexpected path/link in the trusted git source archive")
            files.extractall(source)
        build = subprocess.run(["cargo", "build", "--release", "--manifest-path", str(source / "Cargo.toml"),
                                "--target-dir", str(source / "target")],
                               capture_output=True, text=True)
        (directory / "baseline-build.log").write_text(build.stdout + build.stderr)
        if build.returncode:
            raise RuntimeError("Baseline build failed; see baseline-build.log")
        binary = source / "target/release/rpx"
        binary_hash = sha(binary)
        identity["baseline"] = {"git_head": baseline_commit, "binary_sha256": binary_hash,
                                "method": "git archive c16fdaf (pre-compiler), separate temporary release build"}
        identity_path.write_text(json.dumps(identity, indent=2) + "\n")
        for item in records:
            paths = {role: ROOT / item["artifacts"][role]["path"] for role in ("source", "target", "proof", "request")}
            baseline = run(binary, "verify", *(paths[role] for role in ("source", "target", "proof", "request")))
            current = item["verification"]["result"].get("statistics", {}) if item["verification"] else {}
            old = baseline["result"].get("statistics", {})
            same = baseline["exit_code"] == 0 and all(old.get(k, 0) == current.get(k, 0) for k in old.keys() | current.keys())
            item["historical_receipt_statistics_identity"] = item.pop("frozen_statistics_identity", item.get("historical_receipt_statistics_identity"))
            item["baseline_verification"] = baseline
            item["pre_compiler_statistics_identity"] = same
            item["status"] = "PASS" if (item["rpx_byte_identity"] and item["verification"]
                and item["verification"]["exit_code"] == 0 and item["verification"]["result"]["status"] == "VERIFIED" and same) else "FAIL"
            print(json.dumps({"case": item["case"], "piece": item["piece"], "status": item["status"],
                              "pre_compiler_statistics_identity": same}), flush=True)
    records_path.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in records))
    summary_path = directory / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary.update({"status": "PASS" if all(item["status"] == "PASS" for item in records) else "FAIL",
                    "passed_pieces": sum(item["status"] == "PASS" for item in records),
                    "historical_receipt_statistics_differences": [item["case"] for item in records if not item["historical_receipt_statistics_identity"]],
                    "pre_compiler_statistics_identical_pieces": sum(item["pre_compiler_statistics_identity"] for item in records),
                    "pre_compiler_baseline_check": "PASS" if all(item["pre_compiler_statistics_identity"] for item in records) else "FAIL",
                    "baseline_binary_sha256": binary_hash, "baseline_git_head": baseline_commit,
                    "baseline_build_and_verify_seconds": time.perf_counter() - started,
                    "results_sha256": sha(records_path),
                    "failures": [{"case": item["case"], "piece": item["piece"]} for item in records if item["status"] != "PASS"]})
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
