# Actual test22 ranged-row projection and equal-cost aggregation

All four complete integer/LP projection claims are **VERIFIED**; all four deliberate mutations are **INVALID**. The actual model has 397 source variables and 213 target variables, with 171 source equalities represented by 171 target ranged rows.

The request preserves all 211 retained original coordinates, the exact aggregate observation `x142 + x145 = agg107`, and every corresponding objective value. It checks both lower and upper endpoints of every actual target ranged row, all original domains/equalities, 171 private pivot reconstructions, 13 fixed-zero integers, and the fixed objective-offset column. No bijection is claimed because aggregation discards the split between two equal-cost columns.

The reverse map splits the aggregate equally (`g/2`, `g/2`); its [0,8] bounds imply both original [0,4] bounds. Pivot coordinates follow their actual defining equalities. A small untrusted parser wrapper records the actual positive G-row ranges; the trusted canonicalizer independently imports the untouched actual MPS. Both range endpoints participate in the kernel proof. The encoded tiny nonzero RHS is preserved exactly, as is the offset `-3397586999999310018947800000094739/1000000000000000000000000000`.

The proof has 4,647 obligations, 51,683 work units and no branches. RPX size is 156,556 bytes, SHA-256 `2571a3d13b13c9cafa85811f99cd0fb0e6cfc9410dde8afe1d4af5dadc0c865c`. Preparation took 0.124 seconds; the single recorded verification executed in 4.90 ms (6.24 ms including read/decode). These are case receipts, not controlled benchmarks.

Mutations corrupt the fixed offset mapping, omit a pivot-bound premise, alter a pivot reconstruction and omit the aggregate observation. All are rejected.

```sh
python3 tools/prepare_test22.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds all actual input/output/preparer/kernel/artifact files by hash and records full commands/results. Corpus files remain read-only.
