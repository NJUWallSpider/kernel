# Actual test28: simultaneous common-source flow lifting

The source has 47 continuous commodities on a common directed graph with 19
nodes and 50 arcs. The actual target aggregates them into 14 groups sharing a
source. It retains all 150 integer capacity coordinates and removes 50 auxiliary
aggregate coordinates. Source and target have respectively 2,550 / 850 variables
and 1,062 / 302 rows. Exact immutable artifact identities are in
`preparation.json`; `flow_witness.json` binds every structural item to actual
model indices.

The requested contract preserves every feasible assignment to the 150 integer
coordinates and every attainable objective value for each assignment. It does
not assert a bijection between the continuous feasible points.

The forward affine map sums the commodity flows in each group. The reverse
`FlowLift` extension checks every grouped arc's nonnegativity and all 19 node
balances, including the omitted balance reconstructed as a linear combination.
It then introduces all commodity flows simultaneously, together with every
commodity balance and every per-arc total equality. Its deterministic
construction extracts source-to-sink paths until all demands are met, then
assigns the entire remaining circulation to one commodity in each group.
Discarding this circulation would fail the required preservation of all arc
totals and all objective values.

The extension introduces 2,350 continuous nonnegative coordinates and 1,593
equalities. Ordinary proof instructions then establish every actual source
variable bound, integer condition, row, objective equality and requested
projection. Source aggregate variables are mapped to sums of the grouped flows.
Source capacities and linking rows follow from the new per-arc equalities;
commodity balances follow from the new conservation equalities. The theorem
does not approve the actual output model directly or bypass its obligations.

The source detailed commodity flows have no individual upper bounds or other
commodity-specific capacity constraints. Flow costs agree across commodities
on each arc, aggregate variables have zero cost, and all integer coordinates
keep their domains and costs. These are independently audited observations;
the ordinary complete-output proof is also responsible for accepting only the
actual encoded domains, constraints and objective.

`tools/audit_test28.py` independently reconstructs both complete matrices and
executes a separate Fraction-based joint lifting algorithm on two persisted
grouped points. The reconstructed points satisfy all actual source and target
constraints with objectives `17501` and `118681/7`. Residual circulation arc
totals of `1176` and `2488/7` are preserved. The second deterministic path
decomposition differs from the legacy report, as expected for nonunique lifts.
This independent evidence alone is not a universal kernel certificate.

Reproduce from the workspace root with a V4-enabled kernel:

```sh
python3 tools/audit_test28.py
python3 tools/prepare_test28.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

The proof preparer also requires rejection of a missing middle node premise, an
incorrect commodity demand, missing middle arc nonnegativity, and a reverse map
that discards a required flow coordinate. `preparation.json` records the latest
actual execution status. RPA generation alone is not certification.
