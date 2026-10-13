# Actual test53: integer load bounds on continuous epigraphs

The actual models are certified for equality of their mixed-integer feasible sets in all 156 original coordinates, with equal objectives and both complete identity inverses. Target LP inclusion and a complete original-feasible rational point outside the target establish **strict LP strengthening**. No claim about either LP optimum is made.

All 26 epigraph coordinates are continuous. Their strengthened lower bounds are proved without treating them as integers: the certificate branches on each of five integer load expressions. A load at least the rounded threshold implies the epigraph bound directly; if every load is below it, their actual fixed-sum equality gives a positive constant contradiction. This uses ordinary `Lin`, integer facts, and depth-five `Cases`; no new pigeonhole theorem is trusted. All 130 sparse epigraph replacements are signed combinations with actual column-total equalities, and the removed assignment equality is reconstructed from retained equalities.

Every original and target bound, integer declaration, row, objective, observation, and inverse coordinate is checked. The complete 156-coordinate strictness witness is checked against all original bounds/rows before the actual target violation is confirmed.

Observed result: **VERIFIED**, 2,461 obligations, 130 branches, 155,335 work units, 251,774 RPX bytes. Preparation took 0.163 seconds; the recorded verification took 10.0 ms execution and 12.1 ms complete. These are single observations, not benchmark distributions.

Five corruptions returned **INVALID**: weakened integer load split, missing fixed-sum premise, incorrect epigraph row multiplier, infeasible strictness point, and missing inverse obligation.

Reproduce from the repository root:

```sh
python3 tools/prepare_test53.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds unchanged corpus inputs, the untrusted generator, complete RPA/RPX, canonical models, request, verifier binary, and actual executions by exact hashes.
