# test50: complete identity correspondence with implied integrality

The actual source and final MPS have passed all four integer/LP identity mapping
claims, with all 28,926 original coordinates and the objective preserved. Both
complete compositions are checked. Every original and final variable bound and
row is included. The final artifact is the actual `model_reformulated.mps`.

In the integer reverse direction the certificate proves all 11,935 variables
whose declarations were relaxed are nevertheless integer-valued. For each of
11,200 u variables, a local Cases step splits on its retained binary control x
and concludes INT(u). If x=0, the actual balance equality and nonnegative bounds
force u=0. If x=1, the actual count equality, balance equality, every other lower
link and the control's bounds give u equal to its source-variable sum. A linear
integer fact then uses the retained binary source variables. The 735 remaining
variables use their actual unit-coefficient defining equations.

The row proofs check all 320 opposite-inequality pairs, all ten aggregate
equality combinations and all 2,940 deleted empty tautologies. These row changes
also preserve the full continuous relaxation geometry; no fractional point is
silently excluded by invoking the integer-only arguments in an LP claim.

The full receipt is `preparation.json`. Four mutations are rejected: a relaxed
continuous coordinate used as an integer split premise, an omitted active-case
balance equality, an invalid opposite-row pair, and a missing inverse
coordinate. The certificate does not trust the independent corpus auditor's
PASS; all conditional integer facts are executed and checked by the kernel.

Reproduce from the workspace:

```
python3 tools/prepare_test50.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```
