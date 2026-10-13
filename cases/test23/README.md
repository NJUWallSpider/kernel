# Actual test23: signed differences and independent interval lifts

The actual source has 24,793 variables and 10,112 rows; its final target has
5,826 variables and 5,177 rows. The transformation removes 16,500 fixed-zero
coordinates, replaces 2,467 pairs `(v,w)` by their signed difference `t=v-w`,
and removes one dependent equality. Exact artifact identities and the latest
kernel execution status are recorded in `preparation.json`.

`proof.rpa` requests four complete directional claims: forward and reverse with
integer domains, then forward and reverse with relaxed domains. Each preserves
3,359 unchanged coordinates, 2,467 explicitly requested affine observations
`t=v-w`, and the objective. It does not claim a continuous feasible-point
bijection. The target reuses the name `v` for `t`; name equality alone would not
be an adequate projection contract.

For each original pair, the complete inspected constraints are

```
a*y <= v <= M*y
b*(1-y) <= w <= c*(1-y)
0 <= v <= M, 0 <= w <= c, 0 <= y <= 1
```

with `0<a<=M` and `0<b<=c`. The target replaces the four rows by the interval
for `t`. The reverse construction introduces one continuous `z` per pair with

```
max(a*y, t+b*(1-y)) <= z <= min(M*y, t+c*(1-y))
v=z, w=z-t.
```

All four lower-to-upper inequalities are checked against actual target facts.
In lower-major order, their proofs use `(M-a)*lower(y)`, the first target row,
the second target row, and `(c-b)*upper(y)`. These 2,467 choices depend only on
the original target coordinates, so they coexist. No integrality is inferred
for the new real variables. The body separately proves every original bound,
row, integrality requirement, objective, and requested observation.

Every external coupling row is an equality with opposite columns on `v,w`, so
substitution cancels every new `z`. The only inequalities are the disjoint local
four-row blocks, and paired variables have zero objective coefficients. The
removed equality follows from the recorded signed row combination. The forward
proof uses both bounds of fixed-zero variables as needed without creating
16,500 persistent equality facts.

`audit_test23.py` independently checks every actual model field and all external
occurrences, all 9,868 interval compatibility identities, and 37,005 exact local
endpoint/interior lifts. These checks provide independent evidence; they are not
the universal kernel proof.

Reproduce from the workspace root with a V5-enabled kernel:

```sh
python3 tools/audit_test23.py
python3 tools/prepare_test23.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

Negative proofs omit a middle compatibility pair, change a lower bound, change
the sign of a reconstructed coordinate, or alter a requested affine relation.
RPA generation without successful verification is not certification.
