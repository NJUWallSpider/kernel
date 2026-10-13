# Actual test14 cleanup and binary-conflict disaggregation

The complete actual transformation is **VERIFIED**, and all four deliberate mutations are **INVALID**. The source has 1,166 variables and 2,295 rows; the target has 1,046 variables and 1,804 rows.

The request proves the full integer affine bijection, all retained-coordinate observations, exact objective equality and both inverse identities. A third claim proves target-LP inclusion into the source LP. Strict global LP containment is not claimed.

Actual singleton rows and domains establish 120 continuous zeros and 118 folded upper bounds. For each of 246 new conflicts, a local binary-center split proves the pair inequality from its original aggregate and neighbor bounds. Reverse restoration of each deleted small aggregate uses one-quarter of its conflict rows and the remaining center upper-bound weight. All larger aggregates remain checked directly. The certificate also covers every box-implied and duplicate row, every variable domain and every retained original row.

The proof has 246 branches, 19,973 obligations and 434,761 work units. RPX size is 409,517 bytes, SHA-256 `b341ac27de11af6dc808aad71784d672cf33e56c17f131ee8b94df6d4549daa3`. Preparation took 0.84 seconds; the recorded single kernel execution took 20.0 ms (27.7 ms including read/decode). These are case receipts, not controlled benchmarks.

Mutations remove split integrality, omit a neighbor bound, omit an LP-restoration center bound and omit a full inverse coordinate. Every mutation is rejected.

```sh
python3 tools/prepare_test14.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` records actual source/final-artifact/preparer/kernel/proof hashes, complete commands and results. Corpus files remain read-only. Exploratory weighted-covering observations are not used to delete additional rows or asserted by this request.
