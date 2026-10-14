# Optional integer menus and complete paired domains

The V7 model builders are implemented in `crates/core/src/menu.rs` and
`crates/core/src/injectivity.rs`. They perform exact structural preparation; they
do not accept a menu premise, an injectivity claim or a bijection themselves.
The complete request, proof execution and binary layout are specified in
[FORMAT.md](FORMAT.md#complete-domain-bijection-witnesses). This document explains
the implemented builders, the complete bijection argument and their tests.

## Menu extension

`menu::prepare_unchecked_extension(input, menus, limits)` returns an
`UncheckedMenuExtension { model, premises, statistics }`. Each MenuWitness has
`maximum_index: u32`, `activation: Expr`, `index: Expr` and exactly six references.
The corresponding MenuPremise records carry `kind`, `expression` and `reference`,
in menu order, then this order:

1. LE(-A)
2. LE(A-1)
3. INT(A)
4. LE(-I)
5. LE(I-K*A)
6. INT(I)

Every expression is validated against the *old* input dimension. The proof engine
must require its integer input mode and prove every premise in the old live/path
scope before exposing the candidate model. The helper intentionally can return a
false premise or invalid Ref: preparation does not establish those premises.
Its premise formulas and generated model nevertheless belong to the trusted
inference implementation; checking the premises does not independently prove
the joint-existence lemma. In particular A=2,I=1
can admit two selected options in the candidate model; only the required A<=1
premise makes using that extension sound.

The input model's name, variable/row prefixes, domains and complete objective are
preserved. For each menu append K+1 integer variables with exact bounds [0,1],
in index order, then two equality rows in this order:

```
sum(j=0..K) z[j] - A = 0
sum(j=0..K) j*z[j] - I = 0.
```

Both bounds on each row are zero. Constants are retained in the expression as
-A.constant and -I.constant. A singleton K=0 still has both rows; its second row
is -I=0, with no coefficient for z[0]. Generated names avoid all original names;
their spelling has no proof significance. All menus extend the same original
point simultaneously. An empty family returns the original model unchanged.

At a point satisfying the premises, A is 0 or 1. If A=0, I=0 and all z are zero.
If A=1, the integer I is in [0,K], and z[I]=1 with all other z zero. This proves
total simultaneous existence over arbitrary real old coordinates. Binary domain
and the two equations also make this menu vector unique. That local uniqueness
does not independently establish any inverse of the complete actual model map.
Every actual output domain, row, objective and contract obligation still belongs
to the ordinary proof engine.

The helper preflights sum(K+1), row/reference counts, model dimensions and combined
old/generated/premise support with checked arithmetic. It charges copying and
expression work before reserving expanded buffers, uses fallible reservations,
checks all rational intermediates (including K*A before subtraction), and validates
the final model. Premise and link differences use sorted sparse merging, not
repeated whole-expression accumulation. `MenuStatistics` records `work`,
`generated_variables`, `generated_rows` and `generated_terms`; terms count actual
new row terms after zero-coefficient removal. These are logical counters, not
measured physical allocation sizes or a wall-clock guarantee.

## Complete bijection contract

A caller-requested `BijectionClaim { forward_claim, reverse_claim }` binds two
distinct, independently verified opposing directions with matching integer
modes. The forward root must be an affine Return map F. The reverse construction
G may branch or use admitted joint extensions; every reverse Return must prove
F(G(t))=t on every original target coordinate using that same complete tuple.
Duplicate ordered pairs reject. Neither direction may carry an objective-level
or halfspace restriction. Legacy affine `Claim.inverse` is a separate mechanism.

A fresh paired-domain equality proof also establishes that F is injective on
the complete actual forward input. For any s, both s and G(F(s)) belong to that
input domain and have the same F value, so injectivity gives G(F(s))=s. The
checked right inverse gives surjectivity. Together these prove a full bijection,
including empty domains, without assuming menu-local uniqueness is a complete
model inverse. Pointwise objective preservation must still be requested and
proved by the constituent directions.

The pair contract and its independent proof must match the caller's ordered
request. All reverse composition checks, paired-domain construction and equality
proof execution share the request-wide remaining work budget. Injectivity starts
with fresh live facts and assumptions at depth one and cannot borrow directional
or sibling proof facts.

## Paired domain for injectivity

`injectivity::prepare_domain(input, output, forward_map, limits)` returns
`InjectivityDomain { model, equalities, statistics }`. Both actual models are
validated. The affine map must have exactly one expression for every actual
output coordinate and use only original input indices. The public helper cannot
bind the map to a certificate; its caller must obtain it from the same verified
indexed forward root Return used by the requested bijection pair.

For n input variables and r input rows, generated variables are two complete
copies in order: x[0..n), then x'[0..n). Every lower bound, upper bound and declared
integer flag is copied exactly. The proof engine must use the original input's
integer mode for both copies, rather than activating integrality during an LP
claim. Generated names are fresh and unique. Rows are:

1. all r actual input rows, including full constants and both finite sides;
2. all r rows again, with every variable index shifted by n;
3. for each forward coordinate j, `F[j](x)-F[j](x')=0`.

Observation constants cancel because the same complete expression is evaluated
twice. Its left coefficients are copied and its right coefficients negated.
Repeated, constant and empty-support observations are retained as rows. The
synthetic model objective is zero: an objective is not a domain constraint and
the directional contracts separately check objective preservation.

The returned equality goals are exactly `x[i]-x'[i]`, i=0,...,n-1. The proof
engine must establish every goal as EQ in fresh state using ordinary rules.
There is no special exemption for continuous auxiliaries, variables missing from
the map, infeasible domains or duplicate resource columns. A noninjective map
still has a legitimate paired domain; successful preparation never asserts that
the goals hold. Nonempty fibers containing different points must prevent a valid
equality proof.

All counts, doubled dimensions, shifted index widths, copied source/model data,
map support and equality-goal support are preflighted. Construction uses bounded
fallible allocations and the caller's remaining work budget. Generated domain
validation includes every copied rational and coefficient. `InjectivityStatistics`
uses the same four field names as menu statistics, but `generated_variables`,
`generated_rows` and `generated_terms` count the **entire synthetic paired model**.
Its goals are charged separately as work/support; they are not model rows and
are not included in generated row-term counts.

## Executed independent evidence

The test-only `audit/generate_menu_oracle.py` uses Python Fraction, imports no
kernel or case preparer, and writes both fixtures with seed `0x4D454E55`:

- `tests/vectors/menu_oracle.json`: 241 simultaneous families, 121 satisfying all
  premises and 120 violating one or more, with exact affine constants and negative
  coefficients. Separately the writer enumerates 16,382 binary vectors across
  K=0..12 and identifies exactly 104 feasible activation/index states, each with
  one binary vector.
- `tests/vectors/injectivity_oracle.json`: 80 complete input models, including
  ranged/one-sided/equality rows with nonzero constants, and 640 candidate point
  pairs. Independent construction records every expected generated row, every
  coordinate difference, and feasibility in both integer and relaxed modes.

Six tests in `crates/core/tests/menu_builder.rs` passed. They check exact ordered
premises and generated equations, all valid inactive/active/index-zero/singleton
states through K=12, preservation of the original model/objective and name
collisions, rejection of malformed dimensions/counts/rationals, u32::MAX K,
intermediate bit overflow and the precise preparation-work boundary. A Rust
exhaustive check evaluates every binary candidate against each valid state's
generated model, independently of the closed-form chosen vector.

Six tests in `crates/core/tests/injectivity_builder.rs` passed. They compare all
copied domains and row fields, canceled affine constants, observation and goal
ordering, and all independent oracle rows/point pairs. Regressions preserve a
free unobserved continuous coordinate with two possible values and the genuine
fractional menu collision `(0,1,0)` versus `(1/2,0,1/2)`. Empty dimensions,
constant observations, contradictory bounds, wrong map dimensions, invalid
scalars and shared-work boundaries are covered.

Reproduce with:

```
python3 audit/generate_menu_oracle.py
cargo test -p kernel-core --test menu_builder --test injectivity_builder --locked
```

The integrated request-binding, reverse-composition, fresh injectivity, scope and
complete-output attacks are in `crates/core/tests/menu_bijection.rs`; run them
with `cargo test -p kernel-core --test menu_bijection --locked`. Builder preparation
alone never replaces these checks. Mathematical arguments and finite tests are
evidence, not a formal correctness proof of the implementation.

## Actual optional-menu models

[test59](../cases/test59/README.md) and [test60](../cases/test60/README.md) request
complete integer-domain bijections as well as equality of the specified LP
observation images. A menu's affine aggregation records activation
`A=sum_j x[j]` and moment `I=sum_j j*x[j]`; resource and objective coefficients
that are affine in j can then be expressed in A and I. The ordinary proofs still
check all actual options, continuous definitions, packing rows and bounds.

For K>=2 the relaxed aggregation is generally noninjective: option 1 alone and
half of each endpoint option 0 and 2 have A=1,I=1. Thus LP observation equivalence
must not be reported as an LP bijection. The case records and
[delivery report](../audit/FINAL_DELIVERY_REPORT.md) locate the full replay evidence.
