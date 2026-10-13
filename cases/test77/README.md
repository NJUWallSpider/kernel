# Actual test77: complete affine equivalence

The actual source `input/model.mps` and committed target
`output/reformulated.mps` are under
`/Users/bhz/Code/reform_test/runs/test77-nomf-B1`. The source has 1,536 variables
and 351 rows; the target has 1,486 variables and 259 rows. These complete models,
including bounds, integer declarations and objective, are the checker inputs.

**VERIFIED:** four complete requested directions establish an objective-preserving
affine bijection for both the mixed-integer models and their continuous
relaxations. Every retained coordinate is explicitly preserved. Both inverse
identities cover every input coordinate, including all 50 removed continuous
start variables. No feasibility or numeric optimum is claimed; 171 is used only
as an implied lower bound when recovering constraints.

The certificate uses RPA/RPX 1 and ordinary exact linear combinations. It adds
no production theorem or trusted preparer. Each start is reconstructed from its
actual defining equality as a weighted sum of its choice variables. The actual
choice equality says their nonnegative values sum to one, so their weighted sum
lies between the smallest and largest coefficient. This proves both original
start bounds. Forward row substitutions subtract the defining equalities with
their exact original coefficients.

The reverse proof restores all 42 deleted completion inequalities. A retained
completion inequality and its group's minimum weighted start prove the common
lower bound 171 on the objective coordinate. Each deleted completion expression
has a group maximum at most 171, certified by its actual choice equality and
nonnegative bounds. These facts yield each missing inequality pointwise.

The proof also derives all 201 resource-state identities by prefix sums of the
actual recurrence equalities. For 50 removed upper bounds, per-group maximum
active coefficients sum to at most 25. The choice equalities and nonnegativity
prove that sum bound. For the other eight, the exact active coefficient vector
is componentwise contained in one with a retained upper bound. Differences of
the two recurrence identities plus nonnegative bounds establish the implication.
Every restored bound remains a terminal obligation on the actual source model.

`tools/prepare_test77.py` checks every generated expression using Python Fraction
before serialization. Names select candidate facts; the exact coefficient
identities and subsequent model-bound Rust verification establish acceptance.
Historical audit or solver outcomes are not premises.

The actual path checked 27,748 terminal obligations, 122,718 linear terms and
33,836 substitution terms, charging 482,960 work units. The proof is 858,244 RPX
bytes, with no branches. On the new independently built kernel, one replay took
30.339 ms including decoding and 25.122 ms in execution. This is a preparation
receipt, not an isolated benchmark. `preparation.json` records every input,
request, proof, preparer dependency and binary hash, all commands and results.
`preparation.v7-baseline.json` preserves the previous kernel replay; both produced
identical proof bytes and mathematical statistics.

All six targeted attacks were rejected as INVALID on both binaries: a missing
terminal obligation, shifted reconstructed start, incorrect simplex multiplier,
missing recurrence equation, wrong containment witness and incorrect completion
combination. Their exact broken requirements, output messages and proof hashes
are in the receipts.

Reproduce the whole path and rejection checks from the repository root:

```sh
python3 tools/prepare_test77.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```
