#!/usr/bin/env python3
"""Versioned post-run review of an ordered chain; preserve strict assessments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_compiler_agents import (ROOT, canonical_model, digest, kernel_call,
                                normalized_model, path_inside, shape, write_json)

VERSION = "staged-agent-review-mi-opt-v1"
REVIEWER_SOURCE_SHA256 = digest(__file__)
MODEL_COMPARISON_SHA256 = digest(ROOT / "tools/run_compiler_agents.py")


def inspect_delivery(run, binary, output, *, expected_input_sha256,
                     expected_kernel_sha256=None):
    """Independently anchor and check stages; never trust package receipts."""
    output.mkdir(parents=True, exist_ok=False)
    report = {"reviewer_version": VERSION, "run": str(run),
              "reviewer_sha256": REVIEWER_SOURCE_SHA256,
              "model_comparison_sha256": MODEL_COMPARISON_SHA256,
              "expected_pristine_input_sha256": expected_input_sha256,
              "pieces": [], "errors": [],
              "all_pieces_kernel_verified": False}
    try:
        if expected_kernel_sha256 is not None and digest(binary) != expected_kernel_sha256:
            raise ValueError("pinned verifier binary changed")
        report["kernel_sha256"] = digest(binary)
        if digest(run / "input/model.mps") != expected_input_sha256:
            raise ValueError("original input changed since trusted launch snapshot")
        original = canonical_model(binary, run / "input/model.mps", output / "pristine.mcm")
        manifest = run / "output/delivery.json"
        delivery = json.loads(manifest.read_text())
        report.update(manifest=str(manifest), manifest_sha256=digest(manifest),
                      declared_relation=delivery.get("relation"),
                      declared_composition=delivery.get("composition"))
        committed = path_inside(run, delivery["committed_model"], output=True)
        if committed.suffix.lower() not in (".mps", ".lp"):
            raise ValueError("committed solver artifact must be LP or MPS")
        final = canonical_model(binary, committed, output / "committed.mcm")
        report.update(committed_model=str(committed), committed_model_sha256=digest(committed),
                      committed_shape=shape(final))
        pieces = []
        if not delivery.get("pieces"):
            raise ValueError("empty proof chain")
        for index, declared in enumerate(delivery["pieces"]):
            paths = {key: path_inside(run, declared[key], output=True)
                     for key in ("source", "target", "proof")}
            source = canonical_model(binary, paths["source"], output / f"source-{index}.mcm")
            target = canonical_model(binary, paths["target"], output / f"target-{index}.mcm")
            verification = kernel_call(binary, "verify", output / f"source-{index}.mcm", output / f"target-{index}.mcm",
                                       paths["proof"])
            record = {"index": index, "paths": {key: str(value) for key, value in paths.items()},
                      "sha256": {key: digest(value) for key, value in paths.items()},
                      "source_shape": shape(source), "target_shape": shape(target),
                      "verification": verification}
            report["pieces"].append(record)
            pieces.append({"source_model": source, "target_model": target})
        report["all_pieces_kernel_verified"] = all(p["verification"]["exit_code"] == 0
            and p["verification"]["result"].get("status") == "VERIFIED"
            and p["verification"]["result"].get("guarantee") == "MI_OPT" for p in report["pieces"])
        if not report["all_pieces_kernel_verified"]:
            raise ValueError("at least one staged MI_OPT proof failed its own endpoint verification")
        if normalized_model(pieces[0]["source_model"]) != normalized_model(original):
            raise ValueError("first source differs from the pristine named formulation")
        if normalized_model(pieces[-1]["target_model"]) != normalized_model(final):
            raise ValueError("last target differs from the committed named formulation")
        boundaries = []
        for index in range(len(pieces)-1):
            if normalized_model(pieces[index]["target_model"]) != normalized_model(pieces[index+1]["source_model"]):
                raise ValueError(f"unlinked named formulation at boundary {index}->{index+1}")
            boundaries.append({"left_piece": index, "right_piece": index+1,
                               "exact_named_formulation_match": True,
                               "byte_identical": report["pieces"][index]["sha256"]["target"] == report["pieces"][index+1]["sha256"]["source"]})
        report.update(first_source_pristine_match=True, final_target_artifact_match=True,
                      boundaries=boundaries)
        report["guarantee"] = "MI_OPT"
        report["status"] = "VERIFIED_CHAIN"
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
        report["status"] = "REVIEW_FAILED"
    write_json(output / "staged-review.json", report)
    return report


def review(batch, case, output):
    """Post-run versioned review; retain the original strict assessment."""
    metadata = json.loads((batch / "batch.json").read_text())
    run = batch.parent / f"{case}-compiler-{batch.name}"
    if not (run / "execution.json").is_file() or not (run / "assessment.json").is_file():
        raise ValueError("agent must finish and strict assessment must exist before staged review")
    strict = run / "assessment.json"
    strict_hash = digest(strict)
    report = inspect_delivery(run, batch / "kernel/rpx", output,
                              expected_input_sha256=metadata["input_sha256"][case],
                              expected_kernel_sha256=metadata["kernel_sha256"])
    report.update(batch=str(batch), checkpoint=metadata["git_head"],
                  strict_assessment=str(strict), strict_assessment_sha256=strict_hash,
                  strict_assessment_preserved=True)
    if digest(strict) != strict_hash:
        raise RuntimeError("original strict assessment changed during staged review")
    write_json(output / "staged-review.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = review(args.batch, args.case, args.output)
    print(json.dumps({"status": report["status"], "errors": report["errors"],
                      "report": str(args.output / "staged-review.json")}))
    return 0 if report["status"] == "VERIFIED_CHAIN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
