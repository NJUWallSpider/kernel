# Proposed independent interval extension (not implemented yet)

Actual test23 eliminates 2,467 continuous variables through independent interval
intersections. Its retained signed quantity is t=v-w, so simple coordinate
projection alone cannot state its full contract. This document proposes a later
version after the V4 flow feature is frozen; it is not accepted functionality.

`Claim.affine_projection` is an optional array of `(input Expr, output Expr)`.
Both expressions are validated against the actual original model dimensions before
entering any extension. Every Return proves `EQ(output Expr(map) - input Expr)`
after ordinary coordinate projections and before inverse composition. Empty is the
old-version default. This adds explicit requested affine observations, not a new
inference rule. Source/target direction and integer modes retain their meaning.

`End::IntervalLift { intervals, body }` has a list of independent intervals. Each
has `lower: Vec<Expr>`, `upper: Vec<Expr>`, and `checks: Vec<Ref>`. Every expression
depends only on the current input coordinates, never another new interval
coordinate. The exact required checks are all LE(lower[i]-upper[j]), in lower-major
order. Their number is exactly lower.len()*upper.len(); every pair is checked.
Missing, repeated-out-of-order, or surplus obligation witnesses reject as for a
Return (the same reference may legitimately prove identical expressions).

The helper appends one continuous, initially free variable z per interval. For
each lower expression it appends `z-lower[i]>=0`; for each upper it appends
`z-upper[j]<=0`. Rows are ordered interval, all lowers, then all uppers. Original
variables, rows and objective remain a prefix and unchanged. All intervals extend
the same input point simultaneously. The child proof verifies every actual output
bound, row, integrality, objective, coordinate and affine observation. It cannot
borrow choices from incompatible separate witnesses.

The total deterministic construction is immediate: if any lower exists choose
their maximum; every checked pair ensures it is below every upper. If no lower
exists but an upper does, choose their minimum. If neither exists choose zero.
Finite maxima/minima are attained, including with real input coordinates. No
integrality is inferred for appended variables. An integer output must still have
its INT obligation proved by ordinary rules. No graph search or optimization runs.

As with FlowLift, all premises use the parent input/live/path context, all generated
facts are child-local, affine inverse contracts reject a non-affine terminator,
and model dimension/name/count budgets apply to the complete extension. Charge
the checked pair product before allocating or evaluating, generated terms, copied
input, and nested body depth. Each temporary rational remains exact and bounded.

Required evidence: independently construct intervals over Fraction points, including
empty/one-sided/free cases and multiple independent choices; reject an absent or
false middle pair; check constant signs; reject INT of arbitrary new continuous
coordinates and extra coupled target rows; check branch isolation; test affine
observation dimensions against original, not appended, models; reject wrong signed
relations. Actual test23 must preserve all claimed y/other coordinates, signed
observations t=v-w, and pointwise objective in both integer and relaxed directions.
