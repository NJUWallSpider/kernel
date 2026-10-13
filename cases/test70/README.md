# Actual test70 aggregate-gate tightening

The frozen V7 rational kernel returned **VERIFIED** for the complete source and final target, followed by **INVALID** for four deliberate proof mutations. Both models contain 48,417 binary variables and 2,187 rows. The actual artifact changes 1,975 negative control coefficients and preserves all other model content.

The request proves the full same-coordinate integer feasible-set bijection, exact objective equality and both complete affine inverse identities. It also proves objective-preserving inclusion of the target continuous relaxation into the source relaxation. It does not claim strict global LP containment.

Every packing fact comes from an actual source equality (and, for two activation rows, the actual activation upper bound). Each gate support is partitioned among its stated packing supports. A restricted packing bound is derived from the smallest previously proved containing support by explicitly adding nonnegativity facts. Shared 64-coordinate subset facts are ordinary checked linear combinations. The disjoint restricted bounds sum to the requested gate bound. A local binary case split proves each stronger gate row; reverse inclusion uses the actual control lower bound. All output domains, rows, objective, original-coordinate observations and requested inverse coordinates are checked.

The accepted proof has 190,770 forward steps, 1,975 branches, 635,985 obligations, 23,271,589 linear terms and 83,954,707 charged work units. The binary proof is 61,393,184 bytes, SHA-256 `66c7844d71949193213178666b149fd3cb72615949ca2b6d4fb4f301d1ddc270`. Preparation took 52.67 seconds; this single verification run executed in 2.909 seconds (3.775 seconds including reads/decoding). These timings are case receipts, not isolated benchmarks.

Negative checks remove a restricted-support premise, omit the active-branch assumption, remove the LP reverse nonnegativity premise, and omit a requested inverse obligation. All four are rejected as INVALID.

## Preserved development evidence

`preparation.naive-interrupted.json` and `tools/prepare_test70_naive.py` retain the initial generator interruption, which occurred before a complete proof was written. `preparation.subset-global-resource-limit.json`, `proof.subset-global.rpa`, `proof.subset-global.rpx` and `tools/prepare_test70_subset_global.py` retain the next complete attempt: it assembled successfully but exhausted the unchanged kernel work limit. That result is a resource gap, not evidence against the transformation. The accepted version reduces repeated expansion of large packing rows without changing claims, raising limits or adding trusted rules.

## Reproduce

From the repository root:

```sh
python3 tools/prepare_test70.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the actual input/output files, exact preparer, kernel binary, canonical models, request and accepted proof by hash, and records the complete commands, verification output and mutation results. The corpus files remain read-only.
