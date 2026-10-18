Choose premises explicitly; inspect their normalized expressions before combining them.

## Linear rules
Eq facts assert E=0; Le facts assert E<=0; Int facts assert E integral. `scope.lower(x)` is lower-x<=0, and upper(x) is x-upper<=0. `2*a-b-1` is a LinCombination. Derive.le permits nonnegative inequality multipliers, signed equality multipliers, and a nonpositive constant. Derive.eq requires equality contributions and zero constant. Derive.int requires integer coefficients on Int premises and an integer constant; equality premises can have arbitrary exact coefficients. Zero terms are removed before lowering. `scope.prove(label, by=combination)` additionally requires the exact goal kind and expression.

## Selected helper navigation
Use Derive.round with a matching integrality witness; eqpair for opposite inequalities; box_le for model-box expansion; eq_on_fixed for equality on fixed coordinates. rewrite and rewrite_many use ordered equality definitions. substitution and substitution_fact use author-selected elimination definitions and residuals. zero_sum extracts selected zeros; parity_fix uses a chosen equality; subset_bounds bounds omitted coordinates; plotkin expands chosen codewords and clique facts. Inspect each exact signature with `python -m rpx help Derive.NAME`.

## Example
In the quickstart, `f.prove("objective.non_increasing", by=-f.row("balance"))` is the selected equality witness. `fact.expression` is useful for diagnosis but is not a replacement for the fact's proof ownership.
