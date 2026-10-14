# Independent interval extension in V5

The `IntervalLift` terminator checks a simultaneous extension by real interval
coordinates. Its bounded preparation helper is `crates/core/src/interval.rs`.
It returns an `UncheckedIntervalExtension`: every returned premise must first be
proved in the parent input/fact/assumption scope. Preparation alone does not
establish those premises. The helper's premise formulas and generated model are
trusted implementations of the joint-existence lemma below; no independent
runtime checker proves that lemma. The ordinary child proof checks the complete
actual output model and caller-requested contract conditional on this extension.

## Witness, premises and generated layout

Each `IntervalWitness` has `lower: Vec<Expr>`, `upper: Vec<Expr>` and
`checks: Vec<Ref>`. The affine expressions must be canonical and reference only
the input coordinates available before this terminator. None may refer to a
coordinate newly introduced by this same extension. There is no restriction
that different intervals use different parent coordinates.

The required premises are precisely `LE(lower[i]-upper[j])` for all pairs, in
lower-major order. The number of supplied checks must equal the checked product
`lower.len()*upper.len()`. Every pair is emitted; a false or out-of-order premise
cannot be hidden in a middle position. Reusing a fact reference is legitimate
when it proves the actual required expressions. Empty lower or upper lists need
no pair premises.

The original model name, variable and row prefixes, domains and affine objective
are preserved. One free continuous variable is appended per interval in witness
order. It has no intrinsic finite bounds and is never declared integer. For an
input with N variables, interval k uses coordinate N+k. Generated names are fresh
even when an actual input already uses an internal naming prefix.

Rows are appended interval by interval, first every lower bound in list order,
then every upper bound:

- Lower row: expression `z-lower[i]`, lower bound zero, no upper bound.
- Upper row: expression `z-upper[j]`, no lower bound, upper bound zero.

Thus the expression constant is the negative of the bound's affine constant,
the original coefficients are negated, and the new coordinate has coefficient
one. Each row is canonical without sorting because the new coordinate follows
every allowed input coordinate. An empty list of intervals is a valid identity
extension. A free interval still adds its continuous variable even though it
adds no rows or premises.

## Constructive soundness and scope

Fix any actual input point satisfying the checked premises, including current
branch assumptions. All affine bounds have finite real values. If a lower bound
exists, choose their attained maximum for z. Every pairwise premise ensures this
maximum is at most every upper bound. If there is no lower but an upper exists,
choose the minimum upper value. With no bounds choose zero. This explicitly
constructs one value satisfying all bounds of each interval. Since all bound
expressions use only the same fixed parent point, all choices can be made
simultaneously. The argument applies to real input coordinates, not only rational
sample points; it uses no solver, search or approximation.

The parent may be infeasible; in that case the extension property is vacuous.
Otherwise all generated rows and bounds hold for the same extended point. The
child must prove every actual output variable bound, row, requested integrality,
objective relation and observation using those facts. Extra constraints coupling
new coordinates are not granted by this rule; if they cannot be derived, the
certificate is rejected. Likewise no integer fact is inferred for a newly
introduced interval coordinate.

The rule is child-local. Its laws cannot be used while proving its own premises
and cannot leak into siblings. Facts and assumptions about old coordinates remain
valid because those coordinates and their model prefix are unchanged. Nested
extensions are bounded by the existing block-depth limit. A non-affine extension
cannot be used as an affine inverse map.

V5 also permits caller-requested affine observations through
`Claim.affine_projection`, an ordered list of `(input Expr, output Expr)`.
Both sides are validated against the actual original directional model dimensions
before entering any extension. Every returned map must prove
`EQ(output Expr(map)-input Expr)` using the ordinary proof rules. This is an
additional explicit obligation; it does not relax complete model checking or
change the interval theorem. It expresses, for example, preservation of a signed
quantity t=v-w in actual test23. The legacy V3 `Strictness` variant retains its
complete-coordinate-bijection requirement. V6 `FiberStrictness` supports partial
coordinate/affine observation images through a complete LP fiber refutation;
see [FIBER_POINT_V6.md](FIBER_POINT_V6.md). Both indexed strictness variants
require an unrestricted LP inclusion, with neither an objective-level nor a
halfspace restriction.

## Exact arithmetic and resources

All model and witness expressions and scalars are validated. Pair subtraction is
one linear merge of two canonical sparse expressions. Every difference of
constants or coincident coefficients is checked against the shared rational bit
limit before it can be used. An oversized temporary result is RESOURCE_LIMIT
even if another proof step could later cancel it.

Count addition and multiplication are checked. The expanded model respects
`MAX_VARS` and `MAX_ROWS`; total pair count is bounded by `MAX_ROWS`. A conservative
count of copied input, generated model and unmerged pair terms is bounded by
`MAX_TERMS`. The Cartesian product is counted and charged before any pair vector
allocation or evaluation. Controlled vectors, strings and name tables use
fallible reservation.

Preparation work charges input validation and full prefix copying, interval and
bound scans, pair visits and expanded storage/arithmetic. Storage charges are
32 units per generated variable or row, four per generated/unmerged premise
coefficient and four per premise, with name-collision checks charged separately.
Statistics expose total preparation work and generated variable, row and model
coefficient counts. The caller charges this work to the shared remaining request
budget before checking premises and entering the child. These deterministic units
bound work and allocation; they are not a bit-complexity or machine-instruction
claim. Arbitrary-precision arithmetic still has its bounded operand-size cost.

## Executed independent evidence

`audit/generate_interval_oracle.py` independently evaluates bounds and constructs
all choices with Python `fractions.Fraction`, without Rust or solver imports.
Seed 1229870166 produces 241 cases: 121 consistent and 120 inconsistent families.
They vary dimension, signs, affine coefficients and constants, bound counts,
multiple simultaneous intervals, free/one-sided cases and an empty family. The
fixture records every lower-major pair value and a complete choice vector in
`tests/vectors/interval_oracle.json`.

`crates/core/tests/interval_builder.rs` checks each emitted pair against those
independently computed values and checks the entire extended vector against all
generated bounds and rows. Additional tests cover all pair positions, row signs,
input-prefix/domain/objective preservation, new-coordinate reference attacks,
missing/surplus checks, malformed rational values, large intermediate scalar
differences, pair-product and work budgets, and generated-name collisions.

Reproduce with `python3 audit/generate_interval_oracle.py` and
`cargo test -p kernel-core --test interval_builder`. Full proof-engine integration
tests additionally check scope isolation, complete output obligations, affine
observation binding and versioned wire behavior. These executable checks support
the rule argument; they do not constitute a machine-checked proof of Rust code.

## Actual signed-coordinate recovery

[test23](../cases/test23/README.md) recovers 2,467 continuous variables through
independent interval intersections. Its complete contract preserves retained
coordinates, signed affine observations `t=v-w` and the pointwise objective
in both integer and relaxed directions. The affine observations express that
contract; interval existence alone does not prove those relations. The case
record and [delivery report](../audit/FINAL_DELIVERY_REPORT.md) locate the full
replay evidence.
