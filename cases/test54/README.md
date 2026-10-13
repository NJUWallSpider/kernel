# test54: complete coordinate projection and attainable objective values

The actual source and final MPS have passed four complete mapping claims: both
integer directions and both continuous-relaxation directions. The source has
48,738 variables and 21,732 rows; the target has 32,793 variables and 20,252 rows.
Every retained original coordinate and every attainable objective value is
preserved. No feasible-point bijection is claimed: 14,589 zero-cost monotone
auxiliaries are reconstructed at favorable endpoints rather than asserted fixed.

The forward proof derives all 920 forced-zero equalities from the original
bounds and 784 ordered source-row witnesses, then derives the 414 binary-copy
identities and 22 continuous definitions. It discharges each actual target row
by those equalities and the appropriate original lower or upper bounds for
endpoint replacements. The reverse affine recovery restores every original
coordinate. All its bounds, required integrality, retained rows, removed box
rows, aggregate inequalities, defining equalities and objective are checked.
These arguments use exact linear combinations and equality antisymmetry; they
do not rely on a trusted presolver or on the corpus audit's success message.

The complete certificate contains 619,558 terminal obligations, no case splits,
and 13,491,092 RPX bytes. `preparation.json` binds both actual model files, the
canonical models, full request, RPA and RPX to the successful kernel result.
Four mutations are rejected: a wrong endpoint recovery, a missing forced-zero
row premise, a missing coordinate observation, and a missing term in the
objective correspondence proof. These failures reject the mutated certificates;
they are not counterexamples to the actual reformulation.

Reproduce from the workspace:

```
python3 tools/prepare_test54.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

The preparation script reads the original corpus files without changing them.
The full request includes every model constraint and bound in each direction;
the forward endpoint argument preserves the entire set of retained coordinates,
and the reverse section supplies one feasible original representative.
