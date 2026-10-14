#!/usr/bin/env python3
"""Supplied C3 test16 proof diagnosis, explicitly never Agent acceptance.

Replay only archived, supplied mathematical selections in a fresh pinned
workspace. Replace the failed immutable Eq-residual loop with the public
Builder.substitution helper. Do not discover a map, row, pivot or reformulation.
The supervisor enforces a 1,500 s wall budget and sampled 8 GiB process-tree RSS.
Heavy input/model/certificate artifacts remain outside the Git checkout.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "audit/compiler-agent/C3-test16-failure"
SOURCE = ROOT.parent / "reform_test/runs/test16-compiler-compiler-batch-C3-20261015/input/model.mps"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def memory():
    unit = 1 if platform.system() == "Darwin" else 1024
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"python_max_rss_bytes": own.ru_maxrss * unit,
            "native_child_max_rss_bytes": child.ru_maxrss * unit}


SPARSE_FILL = '''def fill_missing(b, definitions=None, box=False):
    domain = "MI" if b.integers else "LP"
    direction = "forward" if definitions is not None else "reverse"
    prefix = domain + "." + direction
    missing = diagnostic_phase(prefix + ".missing", b.missing)
    diagnostic_event("missing_goals", claim=b.index, domain=domain,
                     count=len(missing), kinds=dict(Counter(g.kind for g in missing)),
                     first_labels=[g.label for g in missing[:3]])
    if definitions is not None:
        equality_goals = [g.expression for g in missing if g.kind == "Eq"]
        # Use the public base Builder method with only these explicit goals.
        # ClaimBuilder's convenience override additionally inspects the full
        # plan; this diagnostic retains the original compact missing-goal set.
        generated = diagnostic_phase(prefix + ".sparse_substitution",
            lambda: Builder.substitution(b, definitions, goals=equality_goals))
        diagnostic_event("substitution_facts", claim=b.index, count=len(generated))
        del generated
    def assign_given_goals():
        for g in missing:
            if g.kind == "Eq" and definitions is not None:
                fact = b.find("Eq", g.expression)
                assert fact is not None, (g.label, "supplied pivot reduction did not prove equality")
                b.check(g.label, fact)
            elif g.kind == "Le" and box:
                b.check(g.label, box_fact(b, g.expression))
            else:
                raise AssertionError(("Unsupported proof obligation", g.label, g.kind, str(g.expression)))
    diagnostic_phase(prefix + ".assign_supplied_goals", assign_given_goals)
    diagnostic_phase(prefix + ".complete", b.complete)
'''


def worker(workdir, record_path):
    workdir, record_path = Path(workdir).resolve(), Path(record_path).resolve()
    identity = json.loads((workdir / "diagnostic/identity.json").read_text())
    record = {**identity, "status": "RUNNING", "phases": [], "events": [],
              "native_calls": [], "started_utc": datetime.now(timezone.utc).isoformat()}
    phase_name = "reconstruct_supplied_prefix"
    total_start = time.monotonic()

    def save():
        record["worker_wall_seconds"] = time.monotonic() - total_start
        record["memory_high_water"] = memory()
        record_path.write_text(json.dumps(record, indent=2) + "\n")

    def event(event_name, **values):
        entry = {"event": event_name, "phase": phase_name,
                 "elapsed_seconds": time.monotonic() - total_start, **values}
        record["events"].append(entry)
        save()
        print(json.dumps(entry), flush=True)

    def phase(name, callback):
        nonlocal phase_name
        previous, phase_name = phase_name, name
        start = time.monotonic()
        event("phase_start", name=name)
        try:
            result = callback()
            record["phases"].append({"name": name, "seconds": time.monotonic() - start,
                                     "memory_high_water": memory()})
            event("phase_done", name=name, seconds=time.monotonic() - start)
            return result
        finally:
            phase_name = previous

    try:
        sys.path.insert(0, str(workdir / "compiler/python"))
        os.environ["KERNEL_RPX"] = str(workdir / "compiler/bin/rpx")
        from kernel_compiler.backend import Kernel
        original_call = Kernel.call

        def tracked_call(kernel, *command, **options):
            start = time.monotonic()
            entry = {"phase": phase_name, "command": list(map(str, command))}
            try:
                result = original_call(kernel, *command, **options)
                entry["result"] = {key: result[key] for key in
                    ("status", "obligations", "missing", "statistics", "version", "rpx_bytes", "total_us") if key in result}
                return result
            except BaseException as error:
                entry["error"] = str(error)
                raise
            finally:
                entry["seconds"] = time.monotonic() - start
                record["native_calls"].append(entry)
                save()

        Kernel.call = tracked_call
        spec = importlib.util.spec_from_file_location("supplied_prefix", ARCHIVE / "reconstruct-prefix.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        namespace = phase("reconstruct_supplied_prefix", lambda: module.reconstruct(workdir))
        record["prefix"] = json.loads((workdir / "diagnostic/prefix.json").read_text())
        record["mathematical_selections"] = {
            "events": len(namespace["events"]), "initial_eliminations": len(namespace["elim"]),
            "aggregate_order": len(namespace["agg_order"]), "all_replacements": len(namespace["allrepl"]),
            "box_redundant_rows": len(namespace["box_redundant"]),
            "modelA": namespace["modelA"].stats(), "source": namespace["source"].stats()}
        event("prefix_ready", **record["mathematical_selections"])
        archive = ast.parse((ARCHIVE / "failed-cell.py").read_text())
        original_helpers = ast.literal_eval(archive.body[0].value)
        beginning = original_helpers.index("def fill_missing(")
        ending = original_helpers.index("def exact_stage_proof(", beginning)
        helpers = original_helpers[:beginning] + SPARSE_FILL + "\n" + original_helpers[ending:]
        record["proof_change"] = {
            "scope": "Only fill_missing Eq residual loop; original maps, targets, events, definitions, box proofs and exact_stage_proof preserved",
            "old_helpers_sha256": hashlib.sha256(original_helpers.encode()).hexdigest(),
            "new_helpers_sha256": hashlib.sha256(helpers.encode()).hexdigest(),
            "public_helper": "Builder.substitution(builder, supplied_definitions, goals=supplied_missing_equality_expressions)",
            "no_new_equations_pivots_maps_or_search": True}
        (workdir / "diagnostic/supplied-proof-with-sparse-fill.py").write_text(helpers)
        namespace.update(diagnostic_event=event, diagnostic_phase=phase)
        exec(compile(helpers, "supplied-proof-with-sparse-fill.py", "exec"), namespace)
        proof = phase("author_exact_stage_four_claims", lambda: namespace["exact_stage_proof"](
            *[namespace[name] for name in ("source", "modelA", "events", "elim", "agg_order", "agg_rows", "allrepl", "box_redundant")]))
        record["claims"] = [{"index": c.index,
            "contract": {**c.claim, "projection": {"kind": "unchanged supplied retained-coordinate pairs",
                "count": len(c.claim["projection"]), "sha256": hashlib.sha256(json.dumps(c.claim["projection"], separators=(",", ":")).encode()).hexdigest()}},
            "steps": len(c.steps)} for c in proof.claims]
        output = workdir / "output"
        output.mkdir(exist_ok=True)
        target = phase("write_preserved_modelA", lambda: namespace["modelA"].write_mcm(output / "modelA.mcm"))
        artifacts = phase("compile_four_claims", lambda: proof.compile(output / "proofA", committed_model=target))
        verification = phase("kernel_verify_four_claims", lambda: proof.kernel.verify(
            artifacts["source"], artifacts["target"], artifacts["proof"], artifacts["request"]))
        record["verification"] = verification
        if verification["status"] != "VERIFIED" or len(proof.claims) != 4:
            raise AssertionError("Four supplied MI/LP directional claims were not VERIFIED")
        record["artifacts"] = {key: {"path": str(path), "bytes": path.stat().st_size,
                                              "sha256": digest(path)} for key, path in artifacts.items()}
        record["artifacts"]["certificate"] = {"path": str(output / "proofA/certificate.json"),
            "bytes": (output / "proofA/certificate.json").stat().st_size,
            "sha256": digest(output / "proofA/certificate.json")}
        record["target_formulation"] = {"path": str(target), "sha256": digest(target),
                                        "statistics": namespace["modelA"].stats()}
        record["status"] = "VERIFIED_SUPPLIED_PROOF_DIAGNOSTIC"
        record["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    except BaseException as error:
        record["status"] = "FAILED_SUPPLIED_PROOF_DIAGNOSTIC"
        record["error"] = str(error)
        record["traceback"] = traceback.format_exc()
        save()
        raise


def tree_rss(pid):
    rows = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss="], text=True).splitlines()
    processes = {int(a): (int(b), int(c) * 1024) for a, b, c in (row.split() for row in rows)}
    selected = {pid}
    while True:
        children = {child for child, (parent, _) in processes.items() if parent in selected}
        if children <= selected:
            break
        selected |= children
    return sum(processes[child][1] for child in selected if child in processes), sorted(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--record", type=Path, default=Path(__file__).with_name("record.json"))
    args = parser.parse_args()
    if args.worker:
        worker(args.workdir, args.record)
        return
    workdir = args.workdir.resolve()
    if workdir.exists() or args.record.exists():
        raise ValueError("Preserve old observations: choose fresh workspace/record")
    started = time.monotonic()
    (workdir / "input").mkdir(parents=True)
    (workdir / "compiler/bin").mkdir(parents=True)
    (workdir / "diagnostic").mkdir()
    shutil.copy2(SOURCE, workdir / "input/model.mps")
    shutil.copy2(ROOT / "target/release/rpx", workdir / "compiler/bin/rpx")
    shutil.copytree(ROOT / "python", workdir / "compiler/python",
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))
    package = sorted((workdir / "compiler/python/kernel_compiler").glob("*.py"))
    identity = {"schema": "kernel-supplied-proof-performance-rescue-1", "case": "test16",
        "diagnostic_only": True, "autonomous_agent_acceptance": False,
        "recipe": "Provided C3 first exact stage source -> modelA; four unchanged MI/LP equal affine bijection claims",
        "workdir": str(workdir), "source": {"path": str(SOURCE), "sha256": digest(SOURCE)},
        "kernel": {"path": str(workdir / "compiler/bin/rpx"), "sha256": digest(workdir / "compiler/bin/rpx")},
        "package": {p.name: digest(p) for p in package}, "script_sha256": digest(__file__),
        "archives": {name: digest(ARCHIVE / name) for name in
                     ("reconstruct-prefix.py", "trajectory-python-cells.json", "failed-cell.py")},
        "python": {"executable": sys.executable, "version": sys.version},
        "guard": {"wall_seconds": 1500, "sampled_process_tree_rss_bytes": 8 * 2**30,
                  "sample_interval_seconds": 1, "memory_note": "ps RSS summed over live worker/native descendants; shared pages may be counted twice; a sampled bound is not an OS memory limit"},
        "cache_condition": "Fresh process and workspace, warm filesystem; concurrent fresh Agent runs may contend"}
    (workdir / "diagnostic/identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    log_path = args.record.with_name("worker.log")
    peak, stopped = 0, None
    with log_path.open("w") as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", "--workdir", str(workdir),
                                    "--record", str(args.record.resolve())], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        while process.poll() is None:
            rss, pids = tree_rss(process.pid)
            peak = max(peak, rss)
            elapsed = time.monotonic() - started
            if rss > identity["guard"]["sampled_process_tree_rss_bytes"]:
                stopped = "8 GiB sampled process-tree RSS guard"
            elif elapsed > identity["guard"]["wall_seconds"]:
                stopped = "1500 s total wall guard"
            if stopped:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                break
            time.sleep(1)
    record = json.loads(args.record.read_text()) if args.record.exists() else identity
    record["supervisor"] = {"exit_code": process.returncode, "total_wall_seconds": time.monotonic() - started,
        "sampled_process_tree_peak_rss_bytes": peak, "guard_stopped": stopped, "worker_log": str(log_path.resolve())}
    if stopped:
        record["status"] = "RESOURCE_LIMIT_SUPPLIED_PROOF_DIAGNOSTIC"
    args.record.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": record.get("status"), "supervisor": record["supervisor"]}, indent=2))
    if process.returncode:
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
