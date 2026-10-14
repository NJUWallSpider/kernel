#!/usr/bin/env python3
"""Independent, serial, post-commit MIP/LP quality measurements for fresh agents.

No measurements are written into agent workspaces or sent back to agents.
Numerical solves measure formulation quality; they do not replace RPX proofs.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import time
from zoneinfo import ZoneInfo

from run_compiler_agents import ROOT, canonical_model, digest, normalized_model, shape, write_json


def parse_highs(text):
    result = {}
    pattern = r"^(?:MIP|LP|QP) \S+ has (\d+) rows?; (\d+) cols?; (\d+) nonzeros?"
    hits = re.findall(pattern, text, re.M)
    if hits:
        rows, variables, nonzeros = hits[-1]
        result.update(rows=int(rows), variables=int(variables), nonzeros=int(nonzeros))
    patterns = {
        "status": r"^\s*(?:Model )?[Ss]tatus\s*:?\s+(.+?)\s*$",
        "primal_objective": r"^\s*(?:Primal bound|Objective value)\s*:?\s+(\S+)\s*$",
        "dual_bound": r"^\s*Dual bound\s+(\S+)\s*$",
        "gap": r"^\s*Gap\s+(\S+)",
        "solver_seconds": r"^\s*(?:Timing|HiGHS run time)\s*:?\s+(\S+)\s*$",
        "nodes": r"^\s*Nodes\s+(\d+)\s*$",
        "simplex_iterations": r"^\s*Simplex\s+iterations\s*:\s*(\d+)\s*$",
    }
    for field, expression in patterns.items():
        hits = re.findall(expression, text, re.M)
        if hits:
            result[field] = hits[-1].strip()
    for field in ("primal_objective", "dual_bound", "solver_seconds"):
        if field in result:
            try:
                result[field] = float(result[field])
            except ValueError:
                pass
    for field in ("nodes", "simplex_iterations"):
        if field in result:
            result[field] = int(result[field])
    if result.get("status") == "Optimal" and "dual_bound" not in result:
        result["dual_bound"] = result.get("primal_objective")
    result["optimal"] = result.get("status") == "Optimal"
    return result


def solve(binary, model, options, destination, *, hard_timeout):
    command = [str(binary), "--options_file", str(options), str(model)]
    started = time.monotonic()
    load = os.getloadavg()
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=hard_timeout)
        text, code, timed_out = process.stdout + process.stderr, process.returncode, False
    except subprocess.TimeoutExpired as error:
        out = error.stdout or b""
        err = error.stderr or b""
        text = (out.decode(errors="replace") if isinstance(out, bytes) else out) + (
            err.decode(errors="replace") if isinstance(err, bytes) else err)
        code, timed_out = None, True
    destination.write_text(text)
    result = {"command": command, "exit_code": code, "timed_out": timed_out,
              "wall_seconds": round(time.monotonic() - started, 6),
              "load_average_at_start": list(load), "log": str(destination),
              **parse_highs(text)}
    write_json(destination.with_suffix(".json"), result)
    return result


def options_file(path, *, relaxation, time_limit):
    path.write_text("\n".join(("parallel = off", "threads = 1", "random_seed = 0",
        f"time_limit = {time_limit}", f"solve_relaxation = {'true' if relaxation else 'false'}")) + "\n")


def solver_probe(binary, output):
    """Check the actual hidden relaxation option using a generic known optimum."""
    model = output / "solver-probe.lp"
    model.write_text("Minimize\n obj: x\nSubject To\n r: 2 x >= 1\nBounds\n 0 <= x <= 1\nBinary\n x\nEnd\n")
    results = {}
    for mode in ("mip", "lp"):
        options = output / f"probe-{mode}.options"
        options_file(options, relaxation=mode == "lp", time_limit=5)
        results[mode] = solve(binary, model, options, output / f"probe-{mode}.log", hard_timeout=15)
    if not (results["mip"].get("optimal") and results["lp"].get("optimal")
            and results["mip"].get("primal_objective") == 1
            and results["lp"].get("primal_objective") == 0.5):
        raise ValueError("HiGHS did not establish the known integer/LP probe optima; do not compare relaxations")
    return results


def claim_coverage(assessment):
    claims = []
    points = []
    for piece in assessment.get("pieces", []):
        for claim in piece.get("claims", []):
            claims.append({key: value for key, value in claim.items()
                           if key not in ("projection", "affine_projection")}
                          | {"projection_count": len(claim.get("projection", [])),
                             "affine_projection_count": len(claim.get("affine_projection", []))})
        points += piece.get("points", [])
    return {"kernel_verified": assessment.get("kernel_verified"),
            "relation": assessment.get("relation"), "claims": claims, "points": points,
            "manual_coverage_review_required": True}


def measurements(binary, variants, options, output, *, mode, args):
    collected = {name: [] for name in variants}
    for index, (name, model) in enumerate(variants.items()):
        record = solve(binary, model, options, output / f"{mode}-{name}-0.log",
                       hard_timeout=args.time_limit + 60)
        collected[name].append(record)
        print(json.dumps({"mode": mode, "variant": name, "repeat": 0,
            "status": record.get("status"), "objective": record.get("primal_objective"),
            "wall_seconds": record["wall_seconds"]}), flush=True)
    # Repeats stay matched. Do not selectively repeat only the fastest variant.
    repeatable = all(records[0].get("optimal") and records[0]["wall_seconds"] <= args.repeat_threshold
                     for records in collected.values())
    order = list(variants)
    if repeatable:
        for repeat in range(1, args.repeats):
            shifted = order[repeat % len(order):] + order[:repeat % len(order)]
            for name in shifted:
                collected[name].append(solve(binary, variants[name], options,
                    output / f"{mode}-{name}-{repeat}.log", hard_timeout=args.time_limit + 60))
    summaries = {}
    for name, samples in collected.items():
        summaries[name] = {"samples": samples, "sample_count": len(samples),
            "repeat_policy_eligible": repeatable,
            "median_wall_seconds": statistics.median(s["wall_seconds"] for s in samples),
            "median_solver_seconds": statistics.median(s["solver_seconds"] for s in samples
                if isinstance(s.get("solver_seconds"), (int, float)))
                if any(isinstance(s.get("solver_seconds"), (int, float)) for s in samples) else None,
            "all_optimal": all(s.get("optimal") for s in samples),
            "first_primal_objective": samples[0].get("primal_objective"),
            "first_dual_bound": samples[0].get("dual_bound")}
    return summaries


def compare(case_result):
    mip, lp = case_result["mip"], case_result["lp"]
    mip_objectives = [entry["first_primal_objective"] for entry in mip.values()]
    result = {"mip_optimality_complete": all(entry["all_optimal"] for entry in mip.values()),
              "objective_values_are_numerical_quality_evidence_not_correctness_proof": True}
    if result["mip_optimality_complete"] and all(isinstance(v, (int, float)) for v in mip_objectives):
        result["matched_mip_objectives"] = all(math.isclose(value, mip_objectives[0], rel_tol=1e-8, abs_tol=1e-6)
                                                for value in mip_objectives)
    if all(entry["all_optimal"] for entry in lp.values()):
        result["lp_objective_compiler_minus_nomf"] = lp["compiler"]["first_primal_objective"] - lp["nomf"]["first_primal_objective"]
        result["lp_objective_compiler_minus_source"] = lp["compiler"]["first_primal_objective"] - lp["source"]["first_primal_objective"]
    if mip["compiler"]["sample_count"] > 1 and mip["nomf"]["sample_count"] > 1:
        result["mip_median_wall_ratio_compiler_to_nomf"] = mip["compiler"]["median_wall_seconds"] / max(1e-9, mip["nomf"]["median_wall_seconds"])
    result["scope_note"] = "LP deltas use raw standard-artifact objective senses; inspect any original MAX model separately. No timed-out incumbent proves equivalence."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--cases", default="")
    parser.add_argument("--highs", type=Path, default=Path.home() / ".local/bin/highs")
    parser.add_argument("--time-limit", type=float, default=120)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--repeat-threshold", type=float, default=10)
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label) or args.time_limit <= 0 or args.repeats < 1:
        parser.error("label must be path-safe; time limit and repeats must be positive")
    if not args.highs.is_file():
        parser.error("existing HiGHS binary missing; this evaluator installs nothing")
    batch = json.loads((args.batch / "batch.json").read_text())
    cases = args.cases.split(",") if args.cases else batch["cases"]
    if set(cases) - set(batch["cases"]):
        parser.error("selected cases are not present in the fresh batch")
    runs_root = args.batch.parent
    run_pairs = {}
    if not args.probe_only:
        for case in cases:
            run_pairs[case] = {}
            for arm in ("compiler", "nomf"):
                run = runs_root / f"{case}-{arm}-{args.batch.name}"
                if not (run / "execution.json").is_file() or not (run / "assessment.json").is_file():
                    parser.error(f"agent has not finished; no solver may run yet: {run}")
                run_pairs[case][arm] = run
    output = ROOT / "audit/compiler-agent" / args.label
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"created": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "batch": str(args.batch), "host": platform.node(), "platform": platform.platform(),
        "solver": str(args.highs), "solver_sha256": digest(args.highs),
        "solver_version": subprocess.run([str(args.highs), "--version"], capture_output=True, text=True).stdout.strip(),
        "evaluator_sha256": digest(__file__), "model_comparison_sha256": digest(ROOT / "tools/run_compiler_agents.py"),
        "options": {"parallel": "off", "threads": 1, "random_seed": 0,
            "time_limit": args.time_limit, "repeats": args.repeats,
            "repeat_threshold_seconds": args.repeat_threshold},
        "solves_serial": True, "feedback_to_agents": False, "cases": {}}
    write_json(output / "quality.json", metadata)
    metadata["solver_probe"] = solver_probe(args.highs, output)
    if args.probe_only:
        write_json(output / "quality.json", metadata)
        print(output / "quality.json")
        return 0
    kernel = args.batch / "kernel/rpx"
    for case, runs in run_pairs.items():
        directory = output / case
        directory.mkdir()
        assessments = {arm: json.loads((run / "assessment.json").read_text()) for arm, run in runs.items()}
        variants = {"source": runs["compiler"] / "input/model.mps"}
        for arm, run in runs.items():
            assessment = assessments[arm]
            if "model" not in assessment:
                raise ValueError(f"no independently selected committed artifact for {case} {arm}")
            model = (run / assessment["model"]).resolve()
            if not model.is_relative_to(run.resolve()) or not model.is_file():
                raise ValueError("selected model escapes its agent workspace")
            if digest(model) != assessment["model_sha256"]:
                raise ValueError("committed artifact changed after independent assessment")
            variants[arm] = model
        canonical = {name: canonical_model(kernel, model, directory / f"{name}.mcm")
                     for name, model in variants.items()}
        entry = {"artifacts": {name: {"path": str(model), "sha256": digest(model),
                     "shape": shape(canonical[name])} for name, model in variants.items()},
                 "compiler_claim_coverage": claim_coverage(assessments["compiler"]),
                 "compiler_and_nomf_named_models_identical": normalized_model(canonical["compiler"]) == normalized_model(canonical["nomf"])}
        for mode in ("mip", "lp"):
            options = directory / f"{mode}.options"
            options_file(options, relaxation=mode == "lp", time_limit=args.time_limit)
            entry[mode] = measurements(args.highs, variants, options, directory, mode=mode, args=args)
        entry["comparison"] = compare(entry)
        metadata["cases"][case] = entry
        write_json(output / "quality.json", metadata)
    print(output / "quality.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
