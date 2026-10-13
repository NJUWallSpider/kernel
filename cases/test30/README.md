# Actual test30 complete projected reformulation

All four complete integer/LP projection claims are **VERIFIED**; all four deliberate proof mutations are **INVALID**. The actual model decreases from 35,378 variables and 16,516 rows to 32,337 variables and 14,717 rows.

The proof preserves every retained coordinate and exact objective value. It covers 930 free absolute-value auxiliaries, 31 nonnegative auxiliaries, 620 equality aliases and 1,460 private binary variables. No bijection is claimed.

Each reverse direction uses one joint IntervalLift. Actual target rows prove both lower expressions are below the upper expression for all 930 independent continuous auxiliaries. Generated interval bounds then prove every original incident row. Actual source equality paths establish aliases. Each private-binary row is projected using all removed-variable lower bounds; reverse reconstruction assigns its deficit to one private binary and zero to the others, explicitly checking its bounds and integrality. All original domains, rows, duplicates, objective and observations are included.

The proof has 525,092 obligations, 6,663,662 work units and no branches. RPX size is 10,418,378 bytes, SHA-256 `78cc75a8b5403328ec6f417e6c72b68780bcc62c4dd63984d3480d8e7aedb671`. Preparation took 6.69 seconds; the recorded single verification executed in 172.8 ms (241.5 ms including reads/decoding). These are case receipts, not controlled benchmarks.

Mutations remove an alias premise, alter an interval endpoint without its premise, omit a private-variable nonnegativity premise and omit a retained-coordinate observation. All are rejected.

```sh
python3 tools/prepare_test30.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the actual source/final artifact, preparer, kernel and generated files by hash and records the complete commands/results. The input corpus remains read-only.
