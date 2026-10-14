#!/usr/bin/env python3
"""Measure authoring plumbing on fresh explicit identity proofs, without a solver.

No historical proof, preparer, target, or Agent transcript is replayed. These
records measure API scalability; they are not reformulation-quality acceptance.
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
        lines.append(f" x{i} row{(i+1) % size} 1")
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
    import kernel_compiler.session as session_module
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
    record = {"schema": "kernel-compiler-api-performance-1", "case": args.worker,
              "mode": "compact_complete" if args.compact_only else "full_plan_inspection",
              "status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
              "purpose": "Fresh same-model MI identity bijection plumbing; not Agent quality or reformulation acceptance",
              "source": {"path": str(source), "bytes": source.stat().st_size, "sha256": digest(source)},
              "kernel": {"path": str(args.kernel.resolve()), "sha256": digest(args.kernel)},
              "python": {"executable": sys.executable, "version": sys.version},
              "platform": platform.platform(), "package_hashes": code_hashes,
              "script_sha256": digest(__file__), "phases": [], "native_calls": [],
              "cache_condition": "Fresh Python worker, warm filesystem; no cache flushing; concurrent Agent runs may contend",
              "rss_note": "Python/native-child individual process high-water marks; not their sum or a sampled process-tree peak"}
    phase_name, json_events, mcm_events, wire_counts = "setup", [], [], {}
    original_dumps, original_mcm, original_wire = json.dumps, Model.write_mcm, session_module.wire

    def tracked_dumps(value, *positional, **kwargs):
        caller = sys._getframe(1)
        start = time.perf_counter_ns()
        text = original_dumps(value, *positional, **kwargs)
        json_events.append({"phase": phase_name, "caller": Path(caller.f_code.co_filename).name + ":" + caller.f_code.co_name,
                            "characters": len(text), "wall_ns": time.perf_counter_ns() - start})
        return text

    def tracked_mcm(model, path):
        start = time.perf_counter_ns()
        result = original_mcm(model, path)
        mcm_events.append({"phase": phase_name, "bytes": result.stat().st_size,
                           "wall_ns": time.perf_counter_ns() - start})
        return result

    def tracked_wire(value):
        counts = wire_counts.setdefault(phase_name, {"calls": 0, "container_calls": 0})
        counts["calls"] += 1
        counts["container_calls"] += isinstance(value, (dict, list, tuple))
        return original_wire(value)

    class MeasuredKernel(Kernel):
        def call(self, *command, **kwargs):
            start = time.perf_counter_ns()
            entry = {"phase": phase_name, "command": list(map(str, command))}
            try:
                result = super().call(*command, **kwargs)
                entry["result"] = result
                return result
            except Exception as error:
                entry["error"] = str(error)
                raise
            finally:
                entry["wall_ns"] = time.perf_counter_ns() - start
                entry["memory_high_water"] = memory()
                record["native_calls"].append(entry)

    def save():
        record["json_serializations"] = json_events
        record["mcm_serializations"] = mcm_events
        record["wire_lowering_counts"] = wire_counts
        record["memory_high_water"] = memory()
        record_path.write_text(original_dumps(record, indent=2) + "\n")

    def phase(name, callback):
        nonlocal phase_name
        phase_name = name
        before = (len(record["native_calls"]), len(json_events), len(mcm_events))
        start = time.perf_counter_ns()
        result = callback()
        entry = {"name": name, "wall_ns": time.perf_counter_ns() - start,
                 "native_calls": len(record["native_calls"]) - before[0],
                 "json_serializations": len(json_events) - before[1],
                 "mcm_serializations": len(mcm_events) - before[2], "memory_high_water": memory()}
        entry["wire_lowering"] = wire_counts.get(name, {"calls": 0, "container_calls": 0}).copy()
        record["phases"].append(entry)
        save()
        print(original_dumps({"case": args.worker, "phase": name, "seconds": entry["wall_ns"] / 1e9,
                              "python_rss_mib": entry["memory_high_water"]["python_max_rss_bytes"] / 2**20}), flush=True)
        if entry["memory_high_water"]["python_max_rss_bytes"] > args.max_rss_gib * 2**30:
            raise MemoryError("Benchmark exceeded its Python process high-water guard")
        return result

    json.dumps, Model.write_mcm, session_module.wire = tracked_dumps, tracked_mcm, tracked_wire
    try:
        kernel = MeasuredKernel(args.kernel)
        model = phase("model_load", lambda: Model.load(source, kernel=kernel))
        record["model_shape"] = model.stats()
        proof = phase("proof_construction", lambda: Proof(model, model, kernel=kernel))
        forward, reverse = phase("claim_construction", lambda: proof.bijection("identity", "identity", integers=True,
                                                                             projection="retained", objective="Equal"))
        record["claims"] = [{**c.claim, "projection": {"kind": "complete_name_identity", "count": len(c.claim["projection"])}}
                            for c in (forward, reverse)]
        record["obligations"] = []
        for name, claim in (("forward", forward), ("reverse", reverse)):
            if not args.compact_only:
                goals = phase(name + "_plan", claim.plan)
                record["obligations"].append(len(goals))
                cached = phase(name + "_plan_cached", claim.plan)
                cache_phase = record["phases"][-1]
                if cached is not goals or any(cache_phase[key] for key in ("native_calls", "mcm_serializations")) or cache_phase["wire_lowering"]["container_calls"]:
                    raise AssertionError("Cached plan performed native work, serialized a model, or lowered a map again")
                record.setdefault("plan_cache_checks", []).append({"claim": name, "same_list_object": True,
                    "additional_native_calls": 0, "additional_map_lowerings": 0, "additional_mcm_serializations": 0,
                    "contract_fingerprint_json": [e for e in json_events if e["phase"] == name + "_plan_cached"]})
            phase(name + "_complete", claim.complete)
            check_count = len(claim.end["Return"]["checks"])
            if args.compact_only:
                record["obligations"].append(check_count)
                calls = [e for e in record["native_calls"] if e["phase"] == name + "_complete" and e["command"][0] == "resolve-return"]
                if len(calls) != 1 or calls[0]["result"]["obligations"] != check_count or calls[0]["result"]["missing"] != 0:
                    raise AssertionError("Compact completion did not resolve every native obligation exactly once")
            elif check_count != record["obligations"][-1]:
                raise AssertionError("Complete checks differ from the full native plan count")
        if args.compact_only:
            completion_mcm = [e for e in mcm_events if e["phase"] in ("forward_complete", "reverse_complete")]
            if len(proof._model_cache) != 1 or len(completion_mcm) != 1:
                raise AssertionError("Same immutable Model was not serialized exactly once for completion")
            record["model_cache_check"] = {"models": 1, "owned_model_files": len(proof._model_cache),
                                           "completion_mcm_serializations": len(completion_mcm)}
            before_checks = [c.end["Return"]["checks"] for c in (forward, reverse)]
            def inspect_certificate_cache():
                certificate = proof.certificate()
                counts = [len(b["end"]["Return"]["checks"]) for b in certificate["blocks"]]
                if counts != record["obligations"]:
                    raise AssertionError("Certificate lost completed checks")
                return {"check_counts": counts, "completed_checks_same_object":
                        all(c.end["Return"]["checks"] is checks for c, checks in zip((forward, reverse), before_checks))}
            cache_result = phase("certificate_cache", inspect_certificate_cache)
            cache_phase = record["phases"][-1]
            if not cache_result["completed_checks_same_object"] or cache_phase["native_calls"] or cache_phase["mcm_serializations"]:
                raise AssertionError("Unchanged completion was recomputed while creating the Certificate")
            record["completion_cache_check"] = {**cache_result, "additional_native_calls": 0,
                                                 "additional_mcm_serializations": 0}
        artifacts = phase("compile", lambda: proof.compile(output / "delivery"))
        if args.compact_only:
            calls = record["native_calls"]
            surfaces = [e["command"][0] for e in calls]
            if surfaces.count("resolve-return") != 2 or "plan-return" in surfaces:
                raise AssertionError("Compact benchmark unexpectedly inspected full goals or recomputed completed returns")
            record["native_surface_check"] = {"resolve_return_calls": 2, "plan_return_calls": 0,
                                              "resolve_calls_during_compile": sum(e["phase"] == "compile" and e["command"][0] == "resolve-return" for e in calls)}
        verification = phase("verify", lambda: kernel.verify(artifacts["source"], artifacts["target"],
                                                             artifacts["proof"], artifacts["request"]))
        record["verification"] = verification
        if verification["status"] != "VERIFIED":
            raise AssertionError(f"Identity proof was not VERIFIED: {verification}")
        if list((output / "delivery").glob("*.rpa")):
            raise AssertionError("Direct compilation unexpectedly produced RPA")
        def artifact_record():
            return {key: {"path": str(value), "bytes": value.stat().st_size, "sha256": digest(value)}
                    for key, value in {**artifacts, "certificate": output / "delivery/certificate.json"}.items()}
        record["artifacts"] = phase("artifact_audit", artifact_record)
        record["package_hashes_after"] = {str(p.relative_to(ROOT)): digest(p) for p in source_files}
        record["kernel_sha256_after"] = digest(args.kernel)
        if record["package_hashes_after"] != code_hashes or record["kernel_sha256_after"] != record["kernel"]["sha256"]:
            raise AssertionError("Benchmark code/binary changed during the observation")
        record["status"] = "VERIFIED"
        record["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    except BaseException as error:
        record["status"] = "FAILED"
        record["error"] = str(error)
        record["traceback"] = traceback.format_exc()
        save()
        raise
    finally:
        json.dumps, Model.write_mcm, session_module.wire = original_dumps, original_mcm, original_wire


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=ROOT / "target/release/rpx")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["synthetic-1000", "test9", "test16"])
    parser.add_argument("--max-rss-gib", type=float, default=6)
    parser.add_argument("--compact-only", action="store_true", help="Call complete directly; do not request full plan/obligation expressions")
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
    pinned = output / "kernel.rpx"
    shutil.copy2(args.kernel, pinned)
    summary = {"schema": "kernel-compiler-api-performance-suite-1", "status": "RUNNING",
               "mode": "compact_complete" if args.compact_only else "full_plan_inspection",
               "kernel_sha256": digest(pinned), "cases": [], "note": "One fresh worker observation per case, not repeated latency distributions"}
    for case in args.cases:
        if case not in ["synthetic-1000", *SOURCES]:
            raise ValueError(f"Unknown case {case!r}")
        command = [sys.executable, str(Path(__file__).resolve()), "--worker", case, "--kernel", str(pinned),
                   "--output", str(output / case), "--max-rss-gib", str(args.max_rss_gib)]
        if args.source:
            command.extend(["--source", str(args.source.resolve())])
        if args.compact_only:
            command.append("--compact-only")
        result = subprocess.run(command)
        record_path = output / case / "record.json"
        summary["cases"].append({"case": case, "record": str(record_path), "exit_code": result.returncode,
                                 "sha256": digest(record_path) if record_path.is_file() else None})
        if result.returncode:
            summary["status"] = "FAILED"
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            raise SystemExit(result.returncode)
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    summary["status"] = "VERIFIED"
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
