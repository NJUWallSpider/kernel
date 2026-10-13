# Actual test35 all-binary affine elimination

All four complete integer/LP affine-bijection claims are **VERIFIED**, and all four deliberate mutations are **INVALID**. The actual model decreases from 4,456 variables and 1,667 rows to 3,510 binaries and 675 rows.

The certificate restores 810 fixed variables and 136 affine definitions, including the objective variable. Every defining equality is checked from the actual source; dependent definitions are composed explicitly. Original lower/upper bounds follow from the target binary box, and integer coefficients establish every removed integer domain. Forty-five removed normalization equations follow from exact combinations of retained target equalities. Both full inverse compositions, every retained coordinate, every original row and exact objective equality are checked. No path-only or independent-network interpretation is imposed.

The proof has 74,490 obligations, 611,616 work units and no branches. RPX size is 1,459,018 bytes, SHA-256 `436f7d514a771be8a9ce6d04b9d777da4914dc25123a55523d3b7c708236606c`. Preparation took 1.13 seconds; one recorded verification executed in 36.2 ms (46.7 ms including read/decode). These are case receipts, not isolated benchmarks.

Mutations omit an affine-definition premise, corrupt a removed coordinate's recovery, drop a normalization premise and omit a full inverse coordinate. All are rejected.

```sh
python3 tools/prepare_test35.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds all actual input/output/preparer/kernel/artifact files by hash and records the complete commands/results. Corpus files remain read-only.
