# Actual test78 certificate

Status: **VERIFIED** on the complete original and final MPS models, using the frozen V7 rational-arithmetic kernel. This case introduces no trusted rule.

The original model has 3,472 binary variables and 4,633 rows. Its actual target has 2,720 variables and 3,881 rows: 768 single-implication choices are pooled into 16 continuous counts, and 1,280 retained choices are continuous. All 1,424 auxiliary binary decisions remain present.

The caller requests two complete mixed-integer maps. The forward map sums the removed members into each pool and preserves the objective exactly. The reverse map preserves every auxiliary decision and does not increase the objective. Every bound, integer domain, row, objective and auxiliary-coordinate projection is checked. This establishes feasibility and minimum-value preservation; it does not claim an LP bijection, preservation of every original choice, or a numerical optimum.

The reverse proof first constructs each choice's binary availability as an AND of its actual auxiliary requirements, using ordinary IntervalLift and exhaustive local Cases. For each capacity group, prefix availability sums are represented by MenuLift. The reconstructed choices are the consecutive differences of the prefix counts capped at nine. Ordinary exact linear arithmetic, integer Round and Cases prove each difference is binary, nonnegative and bounded by its availability. Their sum is at most nine and at least the target group's original total. All reconstructions coexist in one extended input domain before the complete Return check.

Reproduce from the repository root:

```sh
python3 tools/prepare_test78.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

The binary certificate is 92,054,445 bytes and checks 28,644 terminal obligations, with 11,344 local branches and 55,606,781 charged work units. The reverse extension uses 1,280 continuous availability coordinates and 133,280 menu binaries. The recorded single run took 3.072 seconds for execution and 3.621 seconds in total; these are receipts, not an isolated performance comparison.

Preparation took 201.17 seconds of wall time, including an intentional approximately 98-second stopped interval for an unrelated isolated benchmark. The precise observed pause endpoints are in `audit/test78_preparation_pause.json`. Do not interpret that wall interval as an uninterrupted preparation benchmark.

Six deliberate mutations were rejected as INVALID: omitted pool member, continuous variable used as an integer witness, missing interval compatibility premise, altered prefix menu size, missing reconstructed original choice, and changed objective claim against the unchanged caller request.

`preparation.json` records actual model, preparer, dependency, kernel and artifact hashes, all canonicalization/assembly/verification results and the six attack results. `proof.rpa` is the full reviewable RPA7 proof; `proof.rpx`, `source.mcm`, `target.mcm` and `request.json` are the actual kernel inputs. `audit/test78_plan.md` records the independent proof construction rationale. The preparer and trajectory audit are untrusted; only complete kernel acceptance certifies the relation.
