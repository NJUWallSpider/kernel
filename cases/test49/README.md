# Actual test49: integer identity and strict LP strengthening

The original and committed final MPS files both contain 2,013 variables. The
target removes one dependent balance equation and adds twenty integer-rounded
capacity inequalities, changing 233 rows to 252. The files are unchanged.

The complete RPA3/RPX certificate proves all integer feasible vectors and every
objective value are identical, using coordinate permutations with both affine
inverse identities. It separately proves target-LP inclusion in source-LP and
strictness using one complete 2,013-coordinate rational source point. The point
has capacity 449/2 in the source cut, below the required 225. Every original row
and bound is checked on this same vector. Two additional integer points, including
one containing a circulation of 2,000, are checked on both actual models. These
feasibility points do not claim an optimal objective or improved LP bound.

Each rounded inequality is an ordinary exact linear combination of actual
capacity rows, one balance equality and nonnegative-flow bounds, divided by six.
Its integer expression is derived from actual integer-domain premises and then
rounded by the existing `Round` rule. The deleted balance equality is recovered
as minus the other 49 balances. No network theorem or external PASS is trusted.

Reproduce from the repository root:

```sh
python3 tools/prepare_test49.py --kernel target/validation-checkpoint-v7/release/rpx
```

`preparation.json` binds the original models, audit hints, input point file,
preparer, executable, full caller request, RPA and RPX, and records every command.
The fresh V7 executable returns VERIFIED with 25,060 terminal obligations,
212,771 work units and five complete point checks. Five mutations are INVALID:
continuous-variable integrality, a wrong cut multiplier, a missing middle bound
obligation, a nonseparating point and a changed mapped coordinate. The first
complete run took 52.038 ms of execution and 58.637 ms internally; this overlapping
single observation is not part of a controlled benchmark distribution.
