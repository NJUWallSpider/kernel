# Actual test26 — implied integrality and binary gate rounding

The complete actual models have 11,717 coordinates and 10,460 rows each. The target
relaxes 4,502 integer declarations and replaces exactly 38 gate inequalities.
Three complete requested contracts verify: identity of all mixed-integer feasible
assignments with both inverse identities and equal objective values, and complete
target-LP inclusion into source LP with all coordinates and objective preserved.
Neither equality nor strictness of the LP sets is asserted.

The reverse integer proof recovers each relaxed declaration from an actual unit
pivot equality and previously checked integer dependencies. The forward proof
uses 38 ordinary local binary Cases: when the gate is zero its bound combines
with the original inequality; when it is one ordinary exact Round proves the
integer sum bound. Reverse LP inclusion uses the actual gate lower bound and
nonnegative scalar combinations. No tree, gate or model-specific trusted theorem
is added. Every bound, row, integrality, map, objective, projection and requested
inverse obligation is checked against actual canonical model data.

`preparation.json` records VERIFIED for 179,202 obligations, 38 branches and
2,573,631 work units, plus six INVALID corruptions: continuous pivot, missing
integer dependency, unequal Round witness, omitted middle obligation, LP borrowing
integrality, and changed coordinate. The verifier timings are single diagnostic
observations, not a controlled benchmark.

Reproduce from the original inputs with:

```sh
python3 tools/prepare_test26.py --kernel target/release/rpx
```

The original audit only supplies proof candidates. The Rust canonicalizer and
verifier retain all mathematical acceptance responsibility.
