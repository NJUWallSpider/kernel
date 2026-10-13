# test16: complete forced-zero closure and zero-extension bijections

The actual source and final MPS have passed four complete integer/LP affine
bijection claims. The source has 228,350 variables and 126,512 rows; the target
has 198,848 variables and 100,518 rows. Every retained original coordinate and
the exact objective are preserved, and both complete compositions equal the
identity. The retained fixed-one objective column is included unchanged.

The certificate proves every one of 29,502 eliminated variables zero, following
25,842 ordered source-row witnesses. Each upper-zero inequality is an explicit
linear combination of the actual witness row, earlier proved zero equalities
and the other variables' nonnegative lower bounds. Its opposite is the original
variable lower bound, so equality antisymmetry establishes the zero fact.

Every target row follows by cancelling only those proved zero terms. Reverse
recovery inserts zero and checks every original domain, every retained row,
25,933 removed tautologies and 61 removed box-implied inequalities. The full
objective difference uses all 28,810 removed objective terms; no nonzero fixed
coordinate or objective constant is silently discarded. The same arguments
apply to continuous relaxations.

The complete certificate has 3,365,868 terminal obligations and 72,419,456 RPX
bytes. `preparation.json` binds all actual model and proof artifacts to the
successful kernel replay. Four mutations are rejected: a missing zero-proof
row, a nonzero recovery for a proved-zero coordinate, an omitted objective term,
and an omitted inverse coordinate. These failures reject the modified proofs,
not the actual reformulation.

Reproduce from the workspace:

```
python3 tools/prepare_test16.py --kernel target/validation-checkpoint-v7-rational/release/rpx
python3 tools/prepare_affine.py --acceptance
```
