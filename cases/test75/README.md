# test75: complete affine-component bijections

The actual source and final MPS have passed four complete claims: affine
bijections in both integer directions and both continuous-relaxation directions.
Every retained original coordinate is preserved, every original variable bound
and constraint is checked, and both full compositions equal the identity. The
zero objective is checked explicitly.

The source has 48,950 variables and 98,021 constraints; the target has 38,001
variables and 72,968 constraints. Exact source equations or pairs of opposite
inequalities establish 9,578 affine relations. Their 2,146 connected components
supply signed affine reconstructions, including the 12 components forced to a
constant by member bounds. Original fixed-column bounds prove the other
constants. The 35 eliminated integer leaf sums are proved from their actual
defining rows after all required affine substitutions.

The forward certificate substitutes proved equalities into every actual target
row. Reverse recovery checks every original domain using the final variable
boxes, every retained original row by exact target-row identity, and each
removed row as an identity or an exact box consequence. The same scalar proofs
are valid over real coordinates, which also establishes the LP bijections.

`preparation.json` binds the original files, complete request, canonical models,
RPA and RPX to successful kernel verification. Four mutations are rejected:
using the same inequality for both sides of equality antisymmetry, an incorrect
affine recovery constant, an omitted term in a leaf sum, and an omitted full
inverse coordinate. No audit PASS or graph traversal is a trusted acceptance
condition; all resulting facts are checked by ordinary kernel rules.

Reproduce from the workspace:

```
python3 tools/prepare_test75.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```
