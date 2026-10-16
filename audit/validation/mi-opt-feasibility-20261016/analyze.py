"""Research-only MI_OPT classification and small semantic experiments.

Run after tools/run_acceptance.py --label mi-opt-feasibility-20261016.
This is an audit script, not a production acceptance authority.
"""
import collections
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python"))
from kernel_compiler import Expr, Model, Proof, Variable
from kernel_compiler.backend import Kernel


def directions(request):
    claims = request if isinstance(request, list) else request.get("claims", [])
    return {
        direction: [i for i, c in enumerate(claims)
                    if c["reverse"] is reverse
                    and c["input_integers"] is True
                    and c["output_integers"] is True
                    and c["objective"] in ("Equal", "NonIncreasing")
                    and c.get("input_objective_level") is None
                    and c.get("input_halfspace") is None]
        for direction, reverse in (("forward", False), ("reverse", True))
    }


replay = json.loads((OUT / "run.json").read_text())
results = {entry["case"]: entry for entry in replay["replayed"]}
records = []
counts = collections.Counter()
for case in json.loads((ROOT / "audit/acceptance.json").read_text())["cases"]:
    name = case["case_id"]
    request_path = ROOT / "cases" / name / (
        "combined-request.json" if name == "test46" else "request.json")
    request_bytes = request_path.read_bytes()
    request = json.loads(request_bytes)
    claims = request if isinstance(request, list) else request["claims"]
    selected = directions(request)
    eligible = all(selected.values())
    relations = [claims[selected[d][0]]["objective"] for d in selected] if eligible else []
    counts["/".join(relations) if eligible else "not_covered"] += 1
    result = results[name]
    verified = result["exit_code"] == 0 and result["result"]["status"] == "VERIFIED"
    records.append({"case": name, "request": str(request_path.relative_to(ROOT)),
                    "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
                    "unrestricted_mi_directions": selected, "objectives": relations,
                    "covers_mi_opt_by_direct_maps": eligible,
                    "fresh_complete_request_verified": verified,
                    "proof_pieces": len(result.get("pieces", [None]))})

kernel_path = ROOT / "target/validation-mi-opt-feasibility-20261016/release/rpx"
kernel = Kernel(kernel_path)
x = Expr.var(0)

# The user's dominated-point deletion is accepted using both NonIncreasing maps.
source = Model("binary_source", [Variable("x", integer=True, lower=0, upper=1)], objective=x)
target = Model("zero_target", [Variable("x", integer=True, lower=0, upper=0)], objective=x)
proof = Proof(source, target, kernel=kernel)
f, r = proof.correspondence({"x": 0}, "identity", reverse_objective="NonIncreasing")
f.complete()
r.le([(r.upper("x"), 1)], constant=-1)
r.complete()
deletion = proof.verify(OUT / "dominated_point_deletion")

# Strict improvement plus a face correspondence does NOT preserve unboundedness.
# Source: min -x, integer x >= 0. Target: x = 0, min -x.
# On x > 0, x -> x+1 saves 1 but never reaches the face x <= 0.
source = Model("unbounded_source", [Variable("x", integer=True, lower=0)], objective=-x)
target = Model("bounded_target", [Variable("x", integer=True, lower=0, upper=0)], objective=-x)
proof = Proof(source, target, kernel=kernel)
proof.claim(mapping="identity", objective="Equal", input_halfspace=x).complete()
proof.claim(reverse=True, mapping="identity", objective="Equal").complete()
improvement = proof.improvement(x, margin={"Constant": 1}, mapping={"x": x+1})
improvement.le([(improvement.lower("x"), 1)], constant=-1)
improvement.complete()
counterexample = proof.verify(OUT / "strict_improvement_unbounded_counterexample")

# Existing request matching is syntactic: logical weakening is not automatic.
original_path = OUT / "strict_improvement_unbounded_counterexample/request.json"
weakened = json.loads(original_path.read_text())
weakened["claims"][1]["objective"] = "NonIncreasing"
weakened_path = OUT / "weakened_request.json"
weakened_path.write_text(json.dumps(weakened, indent=2) + "\n")
base = original_path.parent
mismatch = kernel.verify(base / "source.mcm", base / "target.mcm", base / "proof.rpx", weakened_path)

report = {
    "scope": "Complete existing requests imply MI_OPT; no production MI_OPT API was added.",
    "kernel_sha256": hashlib.sha256(kernel_path.read_bytes()).hexdigest(),
    "replay": "run.json",
    "cases": len(records), "proof_pieces": sum(r["proof_pieces"] for r in records),
    "relation_counts": dict(counts),
    "all_covered_and_replayed": all(r["covers_mi_opt_by_direct_maps"] and r["fresh_complete_request_verified"] for r in records),
    "case_results": records,
    "experiments": {
        "dominated_point_deletion": {"status": deletion["status"], "mi_opt_directions": directions(json.loads((OUT / "dominated_point_deletion/request.json").read_text()))},
        "strict_improvement_counterexample": {"status": counterexample["status"], "source_infimum": "-infinity", "target_infimum": "0", "mi_opt_directions": directions(proof.request()), "interpretation": "The accepted narrow contract is true, but does not imply MI_OPT. This is not a kernel soundness failure."},
        "weakened_request_against_unchanged_certificate": mismatch,
    },
}
(OUT / "mi_opt_analysis.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "case_results"}, indent=2))
