# test58 — complete network reduction

**VERIFIED**, with the working unified RPA/RPX 10 implementation. This is not a
protocol-freeze announcement. The actual source has 2,500 variables and 1,750
rows; the actual target has 607 variables and 785 rows. Identities and complete
run receipts are in `preparation.json`.

The complete requested contract is certified in both directions:

- Every source mixed-integer feasible point has one complete target feasible
  image with nonincreasing objective.
- Every target mixed-integer feasible point has one complete source lift with
  exactly equal objective, including activated paths carrying zero flow.

These give minimum preservation and exact recovery. There is no LP-equivalence
or full feasible-set bijection claim.

The forward proof checks all original cut identities and forces the necessary
bridge activation costs by exact integer rounding. Their fixed contribution is
205, matching the actual target `OBJFIX` coordinate. Joint interval families
construct 426 edge activation ORs, 91 nontrivial path ANDs and two parallel-path
ORs. Ordinary exhaustive cases prove their integrality and the path capacities;
the longest original path has four edges. Every path cost is compared with the
cost of all its original edges.

The existing SignedLift creates all 305 pairs of nonnegative directional flows
together. After the two dominated parallel paths merge into their cheaper
partners, the new SubflowLift produces one common 606-arc flow on 180 nodes,
preserving every balance while bounding each retained arc by both its supplied
flow and total demand 82. All target flows, activations, capacities, node rows,
bounds, integer designations and objective are then checked explicitly. The
reverse retains the previously established 303-path SignedLift proof.

The actual RPX has 1,321,388 bytes; its RPA has 2,073,459 bytes. The complete run
checked 8,448 terminal obligations, 1,068 local branches and 2,029,879 work units.
The saved functional run took 18.906 ms to execute and 27.251 ms in total;
preparation took 3.162 s and assembly 21.547 ms. These are single functional
measurements with other work possibly concurrent, not isolated benchmarks.

All eight complete-certificate mutations returned `INVALID`: missing middle
node balance, wrong supply node, new coordinate used in an old-scope premise,
missing inactive-branch justification, wrong bridge offset, omitted objective
cost premise, incomplete forward tuple and incorrect reverse signed recovery.
The independently supplied original request remains fixed for every attack.

Reproduce from the repository root with a kernel supporting the unified draft:

```sh
python3 tools/prepare_test58_full.py --kernel target/subflow-production/release/rpx
```

The recorded executable SHA-256 is
`5cb441c3b38ab7b3aea01ca880ef720207001cad9e253b5256b714946c9b1c38`.
Its dedicated core suite passed 250 tests, including 14 Subflow tests and 983
independent Fraction construction/field cases. Build/test/source identities are
recorded in `audit/subflow-next/production-receipt.json`.

`attempts/` preserves the original reverse-only acceptance, rejected local merge,
and exact circulation counterexample. None is overwritten or counted as a
separate complete case. The old failure showed that local clipping/merging did
not prove capacity; it was not a counterexample to the committed reformulation.
