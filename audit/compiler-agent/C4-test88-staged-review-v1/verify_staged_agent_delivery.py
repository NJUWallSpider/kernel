#!/usr/bin/env python3
"""Versioned post-run review of an ordered chain; preserve strict assessments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_compiler_agents import (ROOT, canonical_model, digest, kernel_call,
                                normalized_model, path_inside, shape, write_json)

VERSION = "staged-agent-review-v1"
OBJECTIVES = {"Equal": 0, "NonIncreasing": 1, "None": 2}
RESTRICTIONS = ("input_objective_level", "input_halfspace")
KNOWN_CLAIM_FIELDS = {"reverse", "input_integers", "output_integers", "objective",
                      "inverse", "projection", "affine_projection", "input_objective_lower", *RESTRICTIONS}


def eligible(claim, *, integers, reverse):
    return (not set(claim) - KNOWN_CLAIM_FIELDS
            and claim.get("reverse") is reverse
            and claim.get("input_integers") is integers
            and claim.get("output_integers") is integers
            and not any(claim.get(field) is not None for field in RESTRICTIONS)
            and claim.get("objective") in OBJECTIVES)


def choose_claim(claims, *, integers, reverse):
    choices = [(OBJECTIVES[c["objective"]], index, c) for index, c in enumerate(claims)
               if eligible(c, integers=integers, reverse=reverse)]
    if not choices:
        return None
    _, index, claim = min(choices, key=lambda item: item[:2])
    return index, claim


def projection_relation(claim, source, target):
    input_model, output_model = (target, source) if claim["reverse"] else (source, target)
    return {(input_model["variables"][left]["name"], output_model["variables"][right]["name"])
            for left, right in claim.get("projection", [])}


def compose_relations(left, right, *, max_pairs=1_000_000):
    outgoing = {}
    for middle, end in right:
        outgoing.setdefault(middle, set()).add(end)
    result = set()
    for start, middle in left:
        for end in outgoing.get(middle, ()):
            result.add((start, end))
            if len(result) > max_pairs:
                raise ValueError("composed observation relation exceeds reviewer limit")
    return result


def compose_direction(pieces, *, integers, reverse):
    order = list(range(len(pieces)))
    if reverse:
        order.reverse()
    selections, relation, objective = [], None, "Equal"
    for index in order:
        piece = pieces[index]
        selected = choose_claim(piece["claims"], integers=integers, reverse=reverse)
        if selected is None:
            return {"composable": False, "missing_piece": index,
                    "reason": "no unrestricted claim with exactly matching integer domains"}
        claim_index, claim = selected
        # All observations here belong to this one map. Never union unrelated
        # claims' projections into an invented jointly preserving map.
        edge = projection_relation(claim, piece["source_model"], piece["target_model"])
        relation = edge if relation is None else compose_relations(relation, edge)
        if OBJECTIVES[claim["objective"]] > OBJECTIVES[objective]:
            objective = claim["objective"]
        selections.append({"piece": index, "claim": claim_index,
                           "objective": claim["objective"], "projection_count": len(edge),
                           "uncomposed_affine_projection_count": len(claim.get("affine_projection", []))})
    return {"composable": True, "input_integers": integers, "output_integers": integers,
            "objective": objective, "selected_claims": selections,
            "observation_relation": sorted(relation or set()),
            "observation_count": len(relation or set())}


def compose_domain(pieces, *, integers):
    forward = compose_direction(pieces, integers=integers, reverse=False)
    reverse = compose_direction(pieces, integers=integers, reverse=True)
    complete = forward["composable"] and reverse["composable"]
    common = (set(map(tuple, forward["observation_relation"]))
              & {(right, left) for left, right in reverse["observation_relation"]}) if complete else set()
    optimal = complete and all(direction["objective"] in ("Equal", "NonIncreasing")
                               for direction in (forward, reverse))
    return {"domain": "mixed_integer" if integers else "continuous_relaxation",
            "forward": forward, "reverse": reverse,
            "feasibility_correspondence": complete,
            "equal_optimal_infima": optimal,
            "attainment_transfers_if_optimum_exists": optimal,
            "bidirectionally_preserved_observations": sorted(common),
            "bidirectionally_preserved_observation_count": len(common),
            "full_model_bijection_inferred": False,
            "affine_inverse_inferred": False}


def review(batch, case, output):
    metadata = json.loads((batch / "batch.json").read_text())
    run = batch.parent / f"{case}-compiler-{batch.name}"
    if not (run / "execution.json").is_file() or not (run / "assessment.json").is_file():
        raise ValueError("agent must finish and strict assessment must exist before staged review")
    output.mkdir(parents=True, exist_ok=False)
    strict = run / "assessment.json"
    expected = metadata["input_sha256"][case]
    report = {"reviewer_version": VERSION, "batch": str(batch), "run": str(run),
              "reviewer_sha256": digest(__file__),
              "model_comparison_sha256": digest(ROOT / "tools/run_compiler_agents.py"),
              "checkpoint": metadata["git_head"], "strict_assessment": str(strict),
              "strict_assessment_sha256": digest(strict), "strict_assessment_preserved": True,
              "expected_pristine_input_sha256": expected, "pieces": [], "errors": [],
              "all_pieces_kernel_verified": False, "composed_claims": []}
    try:
        binary = batch / "kernel/rpx"
        if digest(binary) != metadata["kernel_sha256"]:
            raise ValueError("pinned verifier binary changed")
        report["kernel_sha256"] = digest(binary)
        if digest(run / "input/model.mps") != expected:
            raise ValueError("original input changed since trusted launch snapshot")
        original = canonical_model(binary, run / "input/model.mps", output / "pristine.mcm")
        manifest = run / "output/delivery.json"
        delivery = json.loads(manifest.read_text())
        report.update(manifest=str(manifest), manifest_sha256=digest(manifest),
                      declared_relation=delivery.get("relation"))
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
                     for key in ("source", "target", "proof", "request")}
            source = canonical_model(binary, paths["source"], output / f"source-{index}.mcm")
            target = canonical_model(binary, paths["target"], output / f"target-{index}.mcm")
            request = json.loads(paths["request"].read_text())
            if not isinstance(request, dict):
                raise ValueError("staged reviewer requires structured Request objects; legacy arrays are unsupported")
            verification = kernel_call(binary, "verify", output / f"source-{index}.mcm", output / f"target-{index}.mcm",
                                       paths["proof"], paths["request"])
            record = {"index": index, "paths": {key: str(value) for key, value in paths.items()},
                      "sha256": {key: digest(value) for key, value in paths.items()},
                      "source_shape": shape(source), "target_shape": shape(target),
                      "claims": request.get("claims", []),
                      "points": request.get("points", []),
                      "improvements": request.get("improvements", []),
                      "bijections": request.get("bijections", []), "verification": verification}
            report["pieces"].append(record)
            pieces.append({"source_model": source, "target_model": target,
                           "claims": record["claims"]})
        report["all_pieces_kernel_verified"] = all(p["verification"]["exit_code"] == 0
            and p["verification"]["result"].get("status") == "VERIFIED" for p in report["pieces"])
        if not report["all_pieces_kernel_verified"]:
            raise ValueError("at least one staged RPX/request failed its own endpoint verification")
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
        report["composed_claims"] = [compose_domain(pieces, integers=domain) for domain in (True, False)]
        if not report["composed_claims"][0]["equal_optimal_infima"]:
            raise ValueError("chain does not establish full integer-domain optimal-value correspondence")
        report["status"] = "VERIFIED_CHAIN"
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
        report["status"] = "REVIEW_FAILED"
    if digest(strict) != report["strict_assessment_sha256"]:
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
