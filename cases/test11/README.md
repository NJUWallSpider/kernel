# Actual test11 alias elimination

The frozen V7 rational kernel returned **VERIFIED** for all four complete integer/LP directions and **INVALID** for all four deliberate mutations. The actual model decreases from 62,529 to 40,488 variables and from 121,161 to 90,561 rows.

The request proves affine bijections of both integer and continuous feasible sets, with all retained coordinates, exact objective equality and both complete inverse compositions. Actual homogeneous two-variable equalities establish all 22,041 eliminated continuous aliases. Every target row is checked as an exact substitution of its source row. In reverse, 6,543 removed rows follow from actual target bounds and 2,016 follow from retained target dominance rows plus nonnegativity. Every original domain and every original row is included; the positive-cost isolated variables intentionally retained by the source transformation remain present.

The proof has 1,123,132 obligations and 13,004,302 charged work units, with no branching. Its RPX is 27,215,640 bytes, SHA-256 `457d2a4b4efa1e3fe2d2af494be71247b0b80f83779305f4088c33e68ab749f9`. Preparation took 31.66 seconds. The recorded single verification executed in 2.216 seconds, or 2.637 seconds including read/decode; these are case receipts rather than isolated performance results.

The negative checks omit an alias premise, change an eliminated variable's reconstruction, omit a dominance-row premise and omit a requested inverse coordinate. Every mutation is INVALID.

Reproduce from the repository root:

```sh
python3 tools/prepare_test11.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` records exact source/final-target/preparer/kernel/artifact hashes, the full request, complete verification command/output and mutation results. Corpus files are read-only. Exploratory local cost-facet observations are not prerequisites or extra claims of this transformation certificate.
