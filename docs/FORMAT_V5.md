# RPX / RPA 5: independent interval lifting and affine observations

Version 5 adds `End::IntervalLift` and caller-requested affine projection equalities. MCM remains version 1. All earlier RPX/RPA versions retain their layouts and meanings. An old certificate decodes with an empty affine-projection list. The writer chooses V5 whenever any such observation or interval endpoint occurs, including a deeply nested child; V1–V4 headers reject the new logic.

Actual test23 motivates the extension. It removes 2,467 continuous variables whose feasible choices are intersections of independent intervals. It also replaces a signed quantity `t` by a difference `v-w`, so equality of retained coordinates alone cannot state the complete requested relation. The interval rule introduces a simultaneous feasible tuple only after all lower/upper comparisons have been proved. The affine observations explicitly retain the signed values and are ordinary output obligations, rather than a new inference shortcut.

## Affine observations

Claim has optional field `affine_projection`, defaulting to an empty list. Its entries are ordered pairs `[input Expr, output Expr]`. Each expression is exact and canonical and is validated against that direction's **original** input/output model dimensions before any proof execution. Thus a requested input observation cannot refer to a variable introduced by a later flow or interval lift.

At every Return, after the coordinate-projection obligations and before inverse-composition obligations, the checker generates one EQ obligation per entry:

```
output Expr(map) - input Expr = 0.
```

The single complete Return map is used for all output observations. Constants and signs are included exactly. Objective relations remain separate. Duplicate observation expressions are permitted, but each list entry generates its own ordered witness obligation. The complete Claim, including these expressions, must equal the caller's separately supplied request; a certificate cannot remove a signed observation to obtain acceptance. A contradiction endpoint is vacuously valid only after an ordinary checked contradiction.

The full Return order in V5 is: all output domains and rows; objective relation; coordinate projection; affine projection; affine inverse composition; optional input-objective lower bound. V1–V4 have an empty affine list, so their original obligation order is unchanged. The supplementary strictness point rule still requires its complete coordinate bijection; general affine observations do not enlarge that strictness rule's domain.

## Independent interval theorem

```
IntervalWitness = { "lower": Expr[], "upper": Expr[], "checks": Ref[] }
End = prior variants
    | { "IntervalLift": { "intervals": IntervalWitness[], "body": Block } }
```

Every expression depends only on current parent input coordinates, including already-established extension coordinates if the endpoint is nested. It cannot mention any variable being introduced by this IntervalLift. A witness with `p` lowers and `q` uppers requires exactly `p*q` references, in lower-major/upper-minor order. The checker constructs every premise itself:

```
for i in 0..p:
    for j in 0..q:
        LE(lower[i] - upper[j])
```

Every premise must be justified by its corresponding Ref using ordinary exact fact matching in the old input/live/path scope. Exact is allowed only under the usual tautology rules. An equal expression may legitimately reuse the same reference; omitting a middle comparison, replacing it with an unrelated witness, or supplying a surplus reference rejects. Scalar differences and coefficients are exact and bounded before they affect acceptance.

For each interval append one new free **continuous** variable `z`. Append rows in interval order, all lower rows followed by all upper rows:

- Each lower: `z - lower[i] >= 0`.
- Each upper: `z - upper[j] <= 0`.

The row expression stores the negated bound constant, negated bound coefficients, and coefficient `+1` for the new coordinate. A lower row has lower bound zero and no upper bound; an upper row has upper bound zero and no lower bound. The variable itself has neither direct bound; only these generated rows restrict it. All original model variables, rows, names, domains and objective remain unchanged as prefixes. Empty interval lists, empty-sided intervals and completely free intervals are well-defined. New internal names avoid collisions with actual model names but have no mathematical authority.

The child gets this one simultaneous extended model, the same complete actual output model, requested claim, live facts and assumptions. All premise checks finish before any extension row is usable. At Return the child must prove every actual output bound, row, required integrality, objective and projection. It cannot combine incompatible choices for different target constraints. New interval variables are never assumed integer. The endpoint is terminal, with no return to its parent scope, and extension facts cannot leak to a sibling. Affine inverse contracts still require root Return endpoints and therefore reject IntervalLift, FlowLift or a non-affine Split.

### Total joint construction and proof

Fix a point satisfying the current parent domain and assumptions. All bound expressions have finite real values. For an interval with at least one lower bound choose the maximum of its finitely many lowers. Every checked pair ensures that maximum is no greater than each upper. If there is no lower but at least one upper, choose the minimum upper. If both sides are empty, choose zero. These choices satisfy every generated row. Finite maxima/minima are attained, so the argument applies to real input points, not merely rational samples.

Every interval's expressions use only the same fixed old point, so the choices are independent and can be made simultaneously. The complete tuple extends that point without changing any old variable or objective. The child proof is valid for every tuple satisfying the extension laws, so it in particular provides one legal complete actual output for the constructed tuple. This proves a total existence relation; it does not assert a unique lift, an affine inverse, or any unproved coupling between the new choices. For nested lifts, the same argument composes on the jointly existing preceding extension.

Production checks the exact pair premises and generates the algebraic laws. It performs no interval optimization, search or external solver call. The maximum/minimum construction defines the mathematical mapping and is executed independently in the test oracle.

## Binary layout

The common RPX header version is `05 00`. V5 Claim is the exact V3/V4 Claim payload, followed by `array<(Expr input,Expr output)> affine_projection` **after** the optional input-objective-lower scalar. The older inverse field still precedes that optional scalar. Claims in V1–V4 contain no affine-list count. The trailing V3 point array remains present in V5.

End tag 4 encodes:

```
tag(4)
array<IntervalWitness> intervals
Block body
```

Each IntervalWitness is, in order, `array<Expr> lower`, `array<Expr> upper`, `array<Ref> checks`. Tags, reserved bytes, little-endian integers, canonical Q, expression ordering and array count rules are unchanged. V1–V4 reject End tag 4 before using its payload. All branches and nested children are decoded independently of semantic reachability; unknown tags, malformed optional fields, truncation and trailing bytes reject.

Entering the body increments the same root-at-one depth counter as Split, Cases and FlowLift. The decoder's shared maximum is 64. Encoder/version discovery also traverses all nested bodies; a V5 affine observation cannot be downgraded merely because a FlowLift appears elsewhere.

RPA 5 is exact header `RPA 5\n` followed by strict JSON. The schema above uses existing exact Expr/Ref representations; coefficient and constant values are scalar strings. Older text headers reject any nonempty affine list or IntervalLift. The assembler remains a syntax-to-bytes converter with no proof authority.

## Implementation, limits and evidence

`proof.rs` holds IntervalWitness, the endpoint and affine Claim field. `interval::prepare_unchecked_extension` validates structural counts, original-scope expressions, all scalar differences and complete candidate model layout; it returns explicit `IntervalPremise` records plus an **unchecked** extended model. `verify.rs` proves every premise before entering the child. Original-dimension observation validation happens at the top-level requested-claim boundary. Affine observation substitution uses the same exact sparse arithmetic and final fact checking as objective and coordinate obligations.

The helper bounds expanded dimensions and combined old/generated/uncanonicalized premise support by shared model limits. Cartesian pair counts use checked multiplication and are charged before allocation/evaluation; supplied reference length must match exactly. It copies and validates the whole input prefix with charged work. Pair expressions use a linear merge of sorted sparse supports. Generated support and names use checked counts and fallible reservations; name-collision probes and arithmetic/copy/storage work are charged to the remaining request budget. New-variable/row/term statistics are separate from physical file size and consumed work. Standard dependency allocations retain the limitations documented in TRUST_REPORT.md; these deterministic work counts are not a hard wall-clock guarantee.

Eight integration tests in `crates/core/tests/interval_lift.rs` were executed successfully: exact signed-coordinate and objective preservation; missing/false/misordered pair witnesses and new-scope references; original observation dimensions and caller binding; integer and coupled-output attacks; free/one-sided/multiple choices; sibling isolation, inverse rejection and nested lifts; affine-only version selection and unchanged V1–V4 bytes; all adjusted-header truncations, four byte substitutions at every payload position, and a shared work-budget boundary. Builder/oracle tests additionally check independent exact interval constructions; their details are in [INTERVAL_V5.md](INTERVAL_V5.md).

The separate Python writer in `tests/vectors/generate_vectors.py` produces `interval-v5.rpx` (457 bytes), with a singleton interval, exact antisymmetry, a proved output lower bound, and a requested affine observation of the new target coordinate. Rust verifies it against independently encoded actual source/target MCMs and a separately constructed request. `invalid-v5-terminal-v4.rpx` (383 bytes) has a genuine V4 Claim layout and rejects specifically for its V5 terminal. Test success and this semantic argument remain bounded evidence rather than a formal implementation proof.

Actual test23 completed its V5 replay: four integer/relaxed directional claims,
181,296 terminal obligations, 4,934 generated variables and 19,736 generated rows
across the two reverse lifts, about 11.85 MB of physical RPX, and about 4.516 million
charged work units. All four targeted corruptions were INVALID.
`cases/test23/preparation.json` preserves exact byte/work/timing measurements;
this receipt does not certify the remaining corpus cases.
