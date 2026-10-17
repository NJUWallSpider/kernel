#!/usr/bin/env python3
"""Exact test71 point/Plotkin fixture, not a native MI-OPT certificate.

The native compiler exposes the Plotkin inference rule itself
(``Builder.plotkin(bits=..., distance=..., variables=..., cliques=...)``).
The case's RPA 3 contract is not expressible through native ``Proof``: it
additionally asserts a universal input objective lower bound, LP
strictness/inclusion point claims, and a continuous reverse direction.
Native ``Proof`` carries only the two MI-OPT directions with their actual
integer declarations, so those extra claims are reported as unsupported
instead of being silently dropped.

This module retains the exact point evaluator used by the other preparers and
emits independent witness evidence only.  It writes no RPA, request, or
subprocess invocation and never claims verification.
"""
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps
from prepare_test40 import sha


def evaluate(model,point,integer):
    assert len(point)==len(model['vars']);violations=[]
    for i,(v,x) in enumerate(zip(model['vars'],point)):
        if v['lower'] is not None and x<v['lower']:violations.append({'kind':'VarLower','index':i,'residual':str(v['lower']-x)})
        if v['upper'] is not None and x>v['upper']:violations.append({'kind':'VarUpper','index':i,'residual':str(x-v['upper'])})
        if integer and v['integer'] and x.denominator!=1:violations.append({'kind':'VarInt','index':i})
    for i,row in enumerate(model['rows']):
        activity=sum(c*point[j] for j,c in row['terms'].items());rhs=row['rhs']
        if row['sense'] in ('L','E') and activity>rhs:violations.append({'kind':'RowUpper','index':i,'residual':str(activity-rhs)})
        if row['sense'] in ('G','E') and activity<rhs:violations.append({'kind':'RowLower','index':i,'residual':str(rhs-activity)})
    objective=model['objective'][0]+sum(c*point[i] for i,c in model['objective'][1].items())
    return {'objective':str(objective),'violations':violations,'checked_variables':len(model['vars']),'checked_rows':len(model['rows'])}


UNSUPPORTED = [
    "input_objective_lower: native MI-OPT Return obligations require only a "
    "nonincreasing objective; there is no named universal objective-bound claim.",
    "points: native Proof has no Feasible/Strictness/inclusion point contract.",
    "continuous reverse direction: native verification uses the actual integer "
    "declarations in both directions, so the LP-mode reverse claim is not expressible.",
    "projection/right-inverse lists: the MI-OPT map is implicit in the certificate.",
]


def analyse(run):
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    geometry_path = run / "output/geometry_certificate.json"
    geometry = json.loads(geometry_path.read_text())
    a = parse_mps(source)
    b = parse_mps(target)
    assert len(a["vars"]) == len(b["vars"]) == 1024 and len(a["rows"]) == 1024 and len(b["rows"]) == 1025
    assert a["var_index"] == b["var_index"] and a["vars"] == b["vars"] and a["objective"] == b["objective"]
    assert a["objective"] == (F(0), {i: F(-1) for i in range(1024)})
    assert all(v["integer"] and v["lower"] == 0 and v["upper"] == 1 for v in a["vars"])
    for row in a["rows"]:
        assert row == b["rows"][b["row_index"][row["name"]]]
    new = [row for row in b["rows"] if row["name"] not in a["row_index"]]
    assert len(new) == 1
    assert new[0]["sense"] == "L" and new[0]["rhs"] == 12 and new[0]["terms"] == {i: F(1) for i in range(1024)}
    assert set(geometry["variables"]) == set(a["var_index"])
    labels = [geometry["variables"][v["name"]] for v in a["vars"]]
    assert len(set(labels)) == 1024 and all(0 <= v < 2**11 for v in labels)
    incidence = [set() for _ in range(1024)]
    for i, row in enumerate(a["rows"]):
        assert row["sense"] == "L" and row["rhs"] == 1 and len(row["terms"]) == 56
        assert all(c == 1 for c in row["terms"].values())
        for j in row["terms"]:
            incidence[j].add(i)
    histogram = Counter()
    bad_pairs = 0
    for i in range(1024):
        for j in range(i + 1, 1024):
            d = bin(labels[i] ^ labels[j]).count("1")
            histogram[d] += 1
            if d < 6:
                assert incidence[i] & incidence[j]
                bad_pairs += 1
    uniform = [F(1, 56)] * 1024
    chosen = set(geometry["optimal_binary_witness"])
    assert len(chosen) == 12 and chosen <= set(a["var_index"])
    integer = [F(int(v["name"] in chosen)) for v in a["vars"]]
    evidence = {
        "source_relaxed_uniform": evaluate(a, uniform, False),
        "target_relaxed_uniform": evaluate(b, uniform, False),
        "source_integer_optimal": evaluate(a, integer, True),
        "target_integer_optimal": evaluate(b, integer, True),
        "target_relaxed_optimal": evaluate(b, integer, False),
    }
    assert evidence["source_relaxed_uniform"]["violations"] == []
    assert evidence["source_relaxed_uniform"]["objective"] == "-128/7"
    new_index = b["row_index"][new[0]["name"]]
    assert evidence["target_relaxed_uniform"]["violations"] == [
        {"kind": "RowUpper", "index": new_index, "residual": "44/7"}]
    for name in ("source_integer_optimal", "target_integer_optimal", "target_relaxed_optimal"):
        assert evidence[name]["violations"] == [] and evidence[name]["objective"] == "-12"
    witness = {
        "kind": "plotkin_cardinality", "bits": 11, "distance": 6,
        "variables": [[i, label] for i, label in enumerate(labels)],
        "clique_rows": [{"RowUpper": i} for i in range(1024)],
        "expected_conclusion": {"constant": "-12", "terms": [[i, "1"] for i in range(1024)]},
    }
    points = {
        "schema": "test71-exact-point-evidence-v1",
        "source_relaxed": {"coordinates": [str(x) for x in uniform], "integer": False, "objective": "-128/7"},
        "source_integer": {"coordinates": [str(x) for x in integer], "integer": True, "objective": "-12"},
        "target_integer": {"coordinates": [str(x) for x in integer], "integer": True, "objective": "-12"},
        "target_relaxed": {"coordinates": [str(x) for x in integer], "integer": False, "objective": "-12"},
        "separation": {"source_point": "source_relaxed", "map": "identity",
                       "target_violation": {"RowUpper": new_index}, "positive_residual": "44/7"},
        "lower_bounds": {
            "source_integer": {"value": "-12", "fact": "plotkin_cardinality"},
            "target_relaxed": {"value": "-12", "fact": {"RowUpper": new_index}},
        },
        "trust": "Input witnesses only; native MI-OPT does not certify these point/strictness claims.",
    }
    independent = {
        "status": "INDEPENDENT_CHECKED_NOT_KERNEL_CERTIFIED",
        "checks": evidence,
        "hamming_distance_pair_histogram": dict(sorted(histogram.items())),
        "all_pairs_examined": sum(histogram.values()),
        "low_distance_pairs_with_actual_common_row": bad_pairs,
    }
    return a, b, geometry, witness, points, independent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test71-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test71"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    a, b, geometry, witness, points, independent = analyse(run)
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    geometry_path = run / "output/geometry_certificate.json"
    (out / "plotkin_witness.json").write_text(json.dumps(witness, indent=2) + "\n")
    (out / "points.json").write_text(json.dumps(points, indent=2) + "\n")
    (out / "independent_exact_checks.json").write_text(json.dumps(independent, indent=2) + "\n")
    record = {
        "case_id": "test71",
        "status": "BLOCKED_NATIVE_MI_OPT",
        "source": {"path": str(source), "sha256": sha(source)},
        "target": {"path": str(target), "sha256": sha(target)},
        "geometry": {"path": str(geometry_path), "sha256": sha(geometry_path)},
        "proof_preparer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__))},
        "native_plotkin_rule_available": True,
        "case_contract_compatible": False,
        "unsupported_claims": UNSUPPORTED,
        "counts": {
            "source_variables": 1024, "target_variables": 1024,
            "source_rows": 1024, "target_rows": 1025,
            "all_label_pairs": sum(independent["hamming_distance_pair_histogram"].values()),
            "low_distance_pairs": independent["low_distance_pairs_with_actual_common_row"],
            "point_witnesses": 3,
        },
        "preparation_seconds": time.perf_counter() - started,
        "artifacts": ["plotkin_witness.json", "points.json", "independent_exact_checks.json"],
    }
    (out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test71", "status": record["status"],
                      "unsupported_claims": len(UNSUPPORTED)}))


if __name__ == "__main__":
    main()
