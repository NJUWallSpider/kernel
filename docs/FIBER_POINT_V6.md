# Fiber strictness: point-side implementation and independent checks

`FORMAT_V6.md` defines the complete versioned statement, proof language and wire
layout. `point.rs` implements the point-side binding; `verify_lp_refutation` in
`verify.rs` checks the resulting LP contradiction. The old V3 complete-permutation
strictness rule is unchanged.

The full request verifier first proves every requested inclusion claim. For a
FiberStrictness witness, the point checker then checks the complete actual output
LP point and binds the referenced claim's direction. Both domain flags must be
LP mode. Coordinate observations are validated against the original variable
dimensions; both sides of every affine observation are likewise validated before
any fiber model is built.

The entire actual input model is copied, including all variable bounds, declared
domains, rows and objective. Existing indices are preserved. Every coordinate
observation is appended first, then every affine observation, in request order.
For observation `(a,b)` the row is the full expression a with the exactly
evaluated scalar b(y) on both bounds. Its affine constant is retained. No supplied
witness data can replace a row, select a subset of observations or alter a
variable domain. Generated names cannot collide with existing row names.

A fresh LP refutation then establishes infeasibility of this **entire** fiber.
It has no access to live facts or assumptions from an inclusion proof, prior
point witness or sibling branch. LP refutation ignores integer declarations for
inference; a half-integral point in an integer-declared variable remains a valid
LP possibility. Every terminal leaf must be Absurd, with ordinary exhaustive
Split branches and the existing scalar/local Cases rules. A supplied Return or
existential-extension terminator is rejected. Missing refutations on this point
variant and surplus refutations on other point variants are rejected.

The proof establishes that b(y) belongs to the output observation image while no
input point has all those same observations. Along with the earlier checked
inclusion, that establishes strict inclusion of observation images. Neither
observation injectivity nor equal model dimensions is needed. In particular,
unused input variables remain in the fiber and cannot be silently fixed. Empty
observation lists work precisely through the same rule: the actual input must
be proved empty, and the output point must be feasible.

## Resource accounting

Every output coordinate is checked before use. Output row and affine-observation
evaluation checks every rational product and partial sum against the common bit
budget. Fiber row/term counts use checked addition and respect `MAX_ROWS` and
`MAX_TERMS`. Prefix copying and generated rows are charged before allocation;
vectors, strings and row-name indices use fallible reservation. The copy metric
is twice the sum of input names/metadata/coefficients, 33 units per coordinate
observation, and 32 plus input coefficient count per affine observation. Expression
validation, observation evaluation and name-collision visits are charged separately.

Point feasibility, observation evaluation, fiber copying and refutation execution
all draw from the same remaining request-wide work budget. The refutation receives
only the remainder after point-side work and its returned work is added back to
`PointStatistics.work`. `coefficient_terms` continues to count point and
observation evaluation visits; it is not presented as a count of all arithmetic
inside the refutation. Each refutation starts at proof depth one and obeys the
ordinary bounded depth and live-fact limits. Model validation remains subject to
the shared structural and scalar limits.

`verify_points` by itself assumes the inclusion proofs have already succeeded;
it does not re-run them. Use `verify_request` for the complete acceptance result.
The tests explicitly reject a full request whose separator is valid but whose
inclusion proof is false.

## Executed evidence

`cargo test -p kernel-core --test fiber_points` passes eleven tests covering
non-injective input observations, combined coordinate/affine fibers, retained
affine constants on both sides, reverse direction, infeasible output points,
missing observations, empty observation spaces, fresh refutation state, sibling
isolation, disabled LP integer inference, missing/surplus proofs, wrong indices,
original-dimension validation, intermediate rational limits and exact shared-work
thresholds.

`audit/generate_fiber_oracle.py` independently computes affine images of rational
boxes using Python `fractions.Fraction`. For each coefficient sign it selects the
appropriate box endpoint to obtain the attained minimum and maximum. Points
outside that range are separating; the chosen midpoint of the range has the
explicit common preimage given by all box-coordinate midpoints. This checks
non-injective projections without a solver or the Rust implementation.

Seed 1179206226 generates 120 cases in `tests/vectors/fiber_oracle.json`: 80 strict
and 40 non-strict. The Rust tests construct and verify a genuine total inclusion
map for every case, then try an ordinary linear LP fiber refutation. Constants,
positive/negative/zero coefficients, fixed coordinates and several input
dimensions vary. All decisions match the independent oracle. Reproduce the
fixture with `python3 audit/generate_fiber_oracle.py`.

These checks supplement the separate refutation and binary-format attack suites.
They provide executable evidence and a mathematical rule argument, not a formal
proof of the Rust implementation.
