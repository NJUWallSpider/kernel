# Actual test43 projected reduction

The complete source/final-target pair is **VERIFIED**, and all four deliberate mutations are **INVALID**. The actual model shrinks from 33,242 to 26,625 variables and from 49,565 to 37,573 rows.

Four complete integer/LP directions establish identical feasible projections onto all retained coordinates and exact objective preservation. The proof covers 5,663 aliases, 477 fixed-zero variables, 477 unused zero-cost binary variables, 6,323 bound-implied rows and six duplicate rows. No bijection is claimed: the original unused binaries may have either value and are reconstructed as zero.

Actual source equalities prove the alias substitutions and actual paired domain bounds prove fixed zeros. Forward rows and objective are exact linear combinations of those facts and the original rows. Reverse reconstruction checks every original domain and row, using target bounds for redundant rows and actual retained witnesses for duplicates. Objective-only positive-cost retained coordinates remain present.

The proof has 506,270 obligations, 6,630,010 work units and no branching. RPX size is 9,488,836 bytes, SHA-256 `134e2908ae4cee305bd24b054731b5100deafce0a87fb9b381760ed4dccd6e7e`. Preparation took 13.66 seconds; the recorded single verification executed in 693 ms (844 ms including read/decode). These are case receipts, not controlled benchmarks.

Mutations omit an alias premise, alter a retained-coordinate mapping, corrupt a fixed-zero equality's bound premise and omit a retained-coordinate observation. Every mutation is INVALID.

```sh
python3 tools/prepare_test43.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the actual source, target, preparer, kernel and generated artifacts by hash and records complete commands and results. Corpus files remain read-only.
