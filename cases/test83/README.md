# Actual test83: minimum preservation, recovery, and all-optimizer exclusion

Status: VERIFIED under the **unfrozen V10 working draft**. Actual source and
target identities, all exact artifact hashes, executions and negative tests are
in `preparation.json`. The original V5 submission is preserved under
`attempts/submitted-v5-2026-10-11/`.

The two original integer directional maps remain: complete source-to-target
NonIncreasing dominance map, and complete target-to-source Equal recovery, with
all 152 affine observations. They establish minimum preservation and optimal
solution recovery, but alone do not state that every source optimizer excludes
all 61 dominated columns.

The added caller-bound improvement request takes P to be the sum of exactly
those 61 original binary coordinates. For any source feasible x with P>0, the
proof returns one complete source tuple: each removed coordinate becomes zero;
each retained replacement coordinate becomes itself plus all removed columns
assigned to it. Singleton coordinates are retained in this source tuple. Exact
disjoint-support identities preserve every source partition equality. Shared
ordinary Lin proofs establish all aggregated binary bounds; every original
domain and all 100 original rows are checked.

The exact objective difference is `-sum(delta_i*x_i)` with every delta_i>0.
The certified minimum saving is `161497/1000000`. Predicate margin qP therefore
gives strict decrease whenever P>0, including arbitrarily small positive real
values under the generic rule. In this case the requested domain also retains
the actual integer predicates. Consequently every attained source optimizer
has all 61 dominated coordinates zero. No numeric optimum or existence of an
optimizer is claimed.

The new improvement has 183 ordinary steps and 197,597 complete output/objective
obligations. The combined RPX is 95,477,870 bytes. Its receipt records 37,741,826
total work units. Preparation and verification timings were functional runs
with other work present, not an isolated performance comparison.

Reproduction, from the repository root:

```
python3 tools/complete_test83.py --kernel target/next-contracts-initial/release/rpx
```

That fixed initial V10 draft binary has SHA-256
`a0875d7e7f7577bf328c2a6a7cb8db4b7bd8e0aaa6c3dc673dc067ceebaba875`.
The preparer uses the archived original directional RPA and independently
checks all actual support/cost identities before emitting the new improvement.
It regenerates both actual models, assembles twice byte-identically and repeats
verification with identical non-timing statistics.

Eight new negative mutations reject: zero margin, lost replacement contributor,
missing partition premise, wrong saving multiplier, incomplete source tuple,
false positive-domain refutation, changed caller predicate and omitted caller
improvement. Four original directional mutations remain documented in the old
receipt, explicitly distinguished from the eight newly executed checks. Root's
independent regeneration/replay is in
`audit/validation/completed-46-62-83-independent.json`.
