# Actual test27 — signed flow with shared activation

The full original 3,040-coordinate, 1,920-row model and actual 1,520-coordinate,
1,919-row target are certified by two complete mixed-integer contracts. Every
source point has a target point with nonincreasing objective; every target point
has a source lift with equal objective. All 760 signed-flow observations are
explicitly preserved in both directions. This proves equal feasibility status
and extended infima. It does not preserve dominated original objective levels
or assert a bijection of full feasible-point sets.

The forward proof chooses 760 independent real intervals for the OR of paired
binary activations, then proves their integrality using 2,280 ordinary local
Cases. Exact capacity combinations and unchanged balances prove every target
constraint. The reverse proof uses V8 SignedLift with every original-scope premise
proved from actual target bounds and capacity rows. It jointly produces positive
and negative flows with one paid binary activation, including at zero flow.
The deleted balance is recovered as the negative sum of all retained balances.
All original constraints, bounds, integer domains and objective terms are checked.

The complete receipt has 13,721 output obligations and 1,173,116 work units.
Six targeted corruptions are INVALID: missing capacity premise, altered capacity,
self-justifying generated-domain reference, dropped activation, missing balance
and altered caller observation. Preparation and verification times in the receipt
are single diagnostic observations, not controlled benchmark measurements.

```sh
cargo build -p kernel-core --release --locked
python3 tools/prepare_test27.py --kernel target/release/rpx
```

The original audit supplies candidates only. The new rule's exact statement,
construction, versioned format, tests and resource limits are in
[FORMAT_V8.md](../../docs/FORMAT_V8.md); the independent implementation review is
[V8_REVIEW.md](../../audit/V8_REVIEW.md).
