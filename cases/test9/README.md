# test9: affine exit elimination with the actual objective-offset column

The actual source and final MPS have passed complete affine bijections for both
integer points and continuous relaxations. The source has 2,298 variables and
1,026 rows; the target has 1,536 variables and 846 rows. Every retained original
coordinate is preserved, every original bound and row is checked, and both
complete mapping compositions equal the identity.

Each of 763 eliminated nonnegative continuous exits has one actual defining
equality and a unique affine reconstruction. Its projected inequality follows
from that equality and its original nonnegative bound. In reverse, the actual
target inequality proves that bound; for 180 removed projected rows, the
retained variable's lower bound does so directly. All other rows remain checked
against their actual model coefficients.

The target's `OBJCONST` column is fixed to one and carries coefficient
`-77180001/1000000`. Forward objective equality is proved using all eliminated
defining equations. Reverse objective equality and the full reverse composition
explicitly use both actual fixed-column bounds. The constant is never inferred
from a conventional objective-offset encoding or omitted from a contract.

`preparation.json` binds the exact original files and all certificate artifacts
to the successful kernel replay. Four mutations are rejected: an incorrect
fixed offset, an omitted nonnegative-bound premise, an incorrect exit recovery,
and an omitted inverse coordinate. The deliberately uncommitted cost-dominance
reductions in the corpus report are not applied.

Reproduce from the workspace:

```
python3 tools/prepare_test9.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```
