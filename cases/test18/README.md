# Actual test18: saturation and strict projected LP containment

The actual source has 20,617 variables and 2,147 rows. The actual final target
has 1,146 binary variables and 929 rows. Its retained coordinates are the active
`X` binaries. The transformation eliminates 18,467 continuous edge coordinates,
1,000 `Y` binaries, and four zero-cost budget-only binaries. Removing the last
four makes the coordinate projection noninjective.

The requested complete certificate has three mapping claims: integer source to
target, integer target to source, and relaxed target to source. All preserve the
1,146 retained coordinates and objective. A fourth, supplementary point claim
proves strict containment of the target LP in the projected source LP. No equality
of the LP relaxations or strict objective-bound improvement is asserted.

For each source equality `sum(z)=d*x`, `x` is binary and all incident `z` have
domain `[0,1]`. Each of the 18,467 equations `z=x` is proved with ordinary local
cases at `x=0` and `x=1`, exact linear combinations and antisymmetry. Degree-one
equations are already source equalities. The resulting identities derive each
`Y=sum(X)` relation, every retained packing row and the transformed objective.
The reverse affine map copies each retained `X`, sets every incident edge to
that `X`, every `Y` to its support sum, and the four budget-only coordinates to
zero. Complete source bounds and rows are checked, including the packing
implications from retained superset rows.

For projected LP strictness, the full 20,617-coordinate source witness has
`C18473=18/35`, `C18501=8/15`, specified incident edges at `3/5`, and other values
defined in `projection_witness.json`. Every actual source LP bound and row is
checked. The projected target point violates the actual retained row `R2035`:
its activity is `22/21`, whereas its upper bound is `1`.

The kernel creates every observation-fixing equality in a fresh copy of the
actual target LP. Adding `R2035` to the negative of the corresponding fixing
equalities yields the constant-positive inequality `1/21 <= 0`; an `Absurd` leaf
refutes the entire fiber. This proves that no target point has the same observed
coordinates, rather than merely testing one arbitrary target reconstruction.
The source witness objective is `-243`; the projected target objective is
`-23596/105`. They need not agree for this LP separation witness. Integer
objective preservation is established separately by the complete mapping proofs.

`audit_test18.py` independently verifies the full actual structural inventory,
reverse substitution identities, complete source LP point, target violation,
and exact fiber contradiction. It is an evidence preparer, not kernel authority.

Reproduce from the workspace root with a V6-enabled kernel:

```sh
python3 tools/audit_test18.py
python3 tools/prepare_test18.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

The initial scalar certificate retains all saturation facts to expose the real
cost of copying branch state. The original implementation returned RESOURCE_LIMIT;
`preparation.naive-resource-baseline.json` preserves the actual outcome, complete
model/proof/request identities, command and binary hash. It is not a refutation
of the transformation.

The shared-scope V6 implementation replayed **the identical RPX, RPA, models and
request** and returned VERIFIED. `scope_replay.json` binds that direct replay to
the original hashes. The full deterministic preparer then reproduced identical
artifacts and all five mutated proofs were rejected. The complete certificate has
18,444 local case splits, 96,720 terminal obligations and one strict fiber point
claim. The latest executed acceptance and attack records are in `preparation.json`.
