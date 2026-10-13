# Actual test20: affine demand elimination

The complete actual models contain 13,873 → 13,849 variables and 3,202 → 3,138
rows. The target eliminates 24 demand variables using proved supply offsets,
removes their definitions and dominated thresholds, fifteen duplicates, and one
dependent degree equality. Both original files remain unchanged.

Four complete RPA1 claims prove integer and LP affine bijections, pointwise
objective equality, every retained coordinate and both inverse identities in
each domain. Each offset is an exact combination of actual supply, demand,
aggregate-flow and balance rows. All recovered demand bounds and original rows
are checked, including nonzero offsets of both signs. Only 69 original variables
are integer; no integrality is inferred from a variable name or its unit bound.

```sh
python3 tools/prepare_test20.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds all inputs, proof files and the original V7 executable.
The merged arithmetic checkpoint separately replays the unchanged bytes in
`audit/validation/checkpoint-v7-rational/test20-late.json`. The full certificate
checks 181,410 obligations with 2,499,882 work units and no branches. Five attacks
return INVALID: wrong reconstruction offset, a corrupted middle balance term,
missing original-row obligation, integer inference in the LP direction, and a
weakened objective declaration that disagrees with the caller request.
