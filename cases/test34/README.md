# Actual test34: complete one-hot weighted aggregation

The actual source and target are certified for equality of their mixed-integer feasible sets in all 53,593 original coordinates, exact objective equality, and reciprocal full identity inverses. Target LP inclusion and a complete source-feasible fractional point rejected by the target prove **strict LP strengthening**. Every feasible objective value is preserved; the proof does not restrict the continuous objective variable to a minimum.

All 231 original binary one-hot groups are covered, including every one of their 53,361 choices. A balanced tree branches on integer subset sums. Each branch proves that its unchosen sibling has zero sum and therefore zero weighted contribution, then combines a checked bound on the selected subtree. The depth is at most eight; conclusions contain only their local subtree coefficients. Leaves cite actual original individual inequalities or the actual nonnegative bound on z. This is an explicit composition of ordinary `Lin`, `EqPair`, and `Cases`, not a trusted one-hot aggregation theorem.

The reverse proof successively subtracts nonnegative weighted sibling sums from each actual aggregate, recovering every original individual inequality. The 231 redundant zero-distance rows follow from z's lower bound. Every unchanged row, domain, objective coefficient, projection and inverse coordinate is checked. The full 53,593-coordinate strictness point is checked against all actual source rows and bounds, then against the target.

Observed result: **VERIFIED**, 964,439 obligations, 53,130 branches, 46,977,300 work units, 116,032,429 RPX bytes. Preparation took 35.606 seconds. The recorded verification took 11.177 seconds execution and 12.552 seconds complete. These are single observations, not benchmark distributions.

Five corruptions returned **INVALID**: weakened subset integrality, missing weighted zero-sibling premise, missing reverse nonnegativity premise, infeasible strictness point, and missing inverse obligation. Large mutated files are removed after exact hashes and results are recorded; deterministic mutation recipes remain in the preparer.

Reproduce from the repository root:

```sh
python3 tools/prepare_test34.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the unchanged corpus models, untrusted audit/row manifest/generator, complete RPA/RPX, canonical models, request, binary, and actual execution receipts by exact hashes.
