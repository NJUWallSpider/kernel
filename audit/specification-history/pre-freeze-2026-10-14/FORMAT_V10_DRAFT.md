# Consolidated working V10 draft

Status: **implemented working draft, not frozen or released**. V8 remains the
last frozen protocol. V9 objective-level semantics remain unchanged. This one
draft groups caller-bound strict improvement, exact complete-point image
exclusion, a joint demand-bounded subflow lift, and an explicit affine input
restriction for conditional directional claims. It does not register a V11 protocol, a generic
theorem registry, a solver callback, or a new scalar arithmetic rule.

The inherited byte and text grammar is [CURRENT_FORMAT.md](CURRENT_FORMAT.md).
This document defines every V10 addition; [SUBFLOW_DRAFT.md](SUBFLOW_DRAFT.md)
gives the separate subflow lemma and builder correspondence. Historical
`audit/CAPABILITY_PROPOSAL_NOTES.md` alternatives are proposals, not wire schemas.

## Strict improvement contract

The separately supplied request gains `improvements: [ImprovementClaim]`, default
empty. A claim has exactly `target: bool`, `integers: bool`, and `positive: Expr`.
Let S be the complete actual model selected by `target`, with the requested
integer predicates, normalized minimization objective f, and P=`positive`.
Acceptance means

`for every x in S with P(x)>0, there exists one y in S with f(y)<f(x)`.

P is canonical and uses only original coordinates of that selected actual model.
There is no implicit objective-level restriction. The certificate has the same
ordered number of `ImprovementWitness {claim, block}` records; all claim fields
must exactly match the caller. Each block starts with fresh facts and assumptions.
Assumption 0 is the weak fact `LE(-P)`. Later Split/Cases assumptions start at 1.
The strict condition P>0 remains in the immutable improvement context, not in
the scalar fact language. It cannot be borrowed by ordinary claims or siblings.

`ImproveReturn {map, checks, margin}` supplies one complete tuple y in the SAME
actual model. It checks all actual output variable bounds, requested integrality,
and row sides in the ordinary Return order, followed by one objective obligation
`LE(f(y)-f(x)+h(x))`. The proof witness `margin` is one of:

- `Constant(q)`: h=q, with an exact, bit-bounded q>0;
- `Predicate(q)`: h=qP, with an exact, bit-bounded q>0.

No zero or negative q is valid. The second form handles arbitrarily small P>0
without presuming a positive minimum gap. Missing/surplus output expressions or
obligation references reject. Both objectives include their actual constants.
There are no projection/inverse/level restrictions in this contract. Its tuple
may use current lift coordinates; P always keeps its original-coordinate meaning.

`PositiveRefutation {fact}` closes a leaf only in an improvement block, after
checking `LE(P)` exactly. This contradicts that block's strict root domain. It
does not claim infeasibility of the weak closure P>=0. Ordinary Absurd may close
an inconsistent weak domain. Ordinary Return is invalid in an improvement block;
both new endpoints are invalid in ordinary mapping and fiber-refutation contexts.
All exhaustive branches still execute, including boundary branches. Local Cases
export only ordinary facts and have no strict-improvement endpoints.

Soundness follows by the existing scalar/scope induction: each feasible point in
the strict root domain lies in an exhaustive branch, extends jointly through
each trusted lift, and either contradicts a checked leaf condition or receives
one feasible y with positive h and f(y)<=f(x)-h. Empty, unbounded and nonattaining
domains are allowed. The result implies P(x)<=0 at every attained minimizer; it
does not assert existence or value of a minimizer. If P is a sum of known
nonnegative coordinates, each such coordinate is zero at every minimizer. Ordinary
directional claims remain necessary for any source/target minimum relation.

## Explicit affine input restriction

Directional `Claim` gains `input_halfspace: Expr|null`, default absent. With
`input_halfspace=H`, the claim's input domain is the complete actual model
intersected with `H(x)<=0`. H is canonical and validated against the ORIGINAL
input coordinates before any domain row or lift is constructed. It does not
declare H globally valid, identify an optimal face, or assert nonemptiness.
All output bounds, rows, integer predicates, objective and requested projection
equalities still require the ordinary complete Return proof.

The domain constructor preserves the complete original model, then appends the
optional V9 objective-level equality followed by the optional halfspace LE row.
For r original rows, H has row ID r when no level is present and r+1 otherwise;
its upper side is zero and its lower side is absent. Thus `RowUpper` denotes H,
and `RowEq` cannot directly assume H=0. The conjunction of both restrictions is
permitted. Original variables and objective remain unchanged. Names are generated
without collisions, dimensions and terms are bounded, and construction work is
charged to the same verification budget. Each claim starts from its own actual
input model; no restriction leaks to another direction or improvement block.

`input_objective_lower` is conditional when either restriction is present.
Existing whole-model V7 bijections and indexed Strictness/FiberStrictness reject
restricted directions. For this draft, legacy `inverse` rejects if either its
current or referenced opposing claim has a halfspace; inverse composition alone
would not prove membership in the opposing restricted domain. Existing V9-only
inverse membership checks are unchanged. Feasible point and image-exclusion
claims continue to refer to their complete actual models.

This adds a caller-declared conditional domain, not an existence theorem. Its
soundness obligation is exact construction of the stated intersection followed
by the existing proof induction. In particular, a strict-improvement contract
for P>0 excludes that region from attained minimizers. A separately checked
direction on P<=0 with explicit retained-coordinate projection then applies to
every original minimizer. Together with complete objective/recovery directions,
these statements can establish an optimal-projection relation. Neither request
alone may be relabeled as the whole compound statement. The actual test36 uses
this combination; its model-specific external structure checks do not substitute
for the conditional projection obligations.

## Exact complete-image exclusion

`PointClaim::ImageExclusion {point_in_target: bool, map: [Expr]}` binds a complete
affine image in the caller request. The ordinary point witness supplies all
coordinates of a point in the selected actual model, in LP mode. `map` has exactly
one expression per coordinate of the opposite actual model, expressed solely in
the selected model's original coordinates.

The checker validates all point scalars and map expressions, checks full input
LP feasibility, evaluates every image coordinate with checked exact intermediate
products and sums, and requires an actual opposite-model bound or row violation.
Integer declarations on either side are relaxed; a fractional value alone cannot
establish exclusion. A surplus refutation block rejects. Early return upon a
violated row is allowed only after complete expression/image validation.

This is one separating image, not global containment, strict inclusion, an
objective comparison, or the impossibility of all completions of a partial map.
There is no requested inclusion index. Existing Strictness/FiberStrictness
contracts and their inclusion prerequisites are unchanged. The exact number of
violated rows is auxiliary data, not part of this claim.

## Joint subflow endpoint

`SubflowLift {witness: SubflowWitness, body: Block}` has
`SubflowWitness {nodes: u32, arcs: [(u32,u32)], groups: [SubflowGroup]}` and
`SubflowGroup {source: u32, demands: [(u32,Q)], flows: [Expr],
nonnegative: [Ref], balances: [Ref]}`. The exact graph, premise, domain and layout
rules are in [SUBFLOW_DRAFT.md](SUBFLOW_DRAFT.md). Every group uses the common
pre-extension scope. All premises execute there before the child receives any
appended variable or row. The endpoint is valid in LP or MI ordinary/improvement
blocks, but not in the existing restricted fiber-refutation language. Legacy
affine `inverse` requires root Return and cannot silently accept this endpoint.

## Complete V10 wire delta

MCM stays version 1. RPA header `RPA 10` and RPX header version 10 are accepted.
RPA otherwise uses the existing strict JSON schema and exact rational strings.
Unknown fields/tags, nonzero reserved fields, unsupported versions, noncanonical
rationals and trailing bytes reject. Existing count/depth/byte limits apply.
Below `tag`, `array`, Q, Expr, Ref and Block have their existing meanings.

V10 directional Claim records retain the V9 layout, with the following optional
extension: Claim flags bit 3 means a halfspace is present, and exactly one Expr
is appended immediately after that claim's `input_objective_level` option. There
is no additional option byte. Bits 4–7 remain zero; versions 1–9 reject bit 3.
If absent, no flag or payload byte changes, including for previously valid V10
certificates. The addition assigns previously invalid flag encodings and does
not reinterpret any previously valid byte sequence. A present halfspace selects
version 10 even when no other V10 feature occurs.

After the complete V9 outer certificate arrays (claims, blocks, points,
bijections), append:

```
array<ImprovementWitness>
ImprovementWitness = u8 flags; u8 0; u16 0; Expr positive; Block
flags bit 0 = target; bit 1 = integers; all other bits zero
```

The new point claim record is:

```
tag(3); u8 flags; u8 0; u16 0; array<Expr> map
flags bit 0 = point_in_target; all other bits zero
```

It is followed by the existing point-witness value array and optional refutation
record, whose presence the semantic checker rejects for ImageExclusion.

The new block endpoint records, after the existing block step array, are:

```
tag(7); u32 nodes; array<(u32 tail,u32 head)> arcs;
        array<SubflowGroup>; Block body
SubflowGroup = u32 source; array<(u32 sink,Q demand)>;
               array<Expr> flows; array<Ref> nonnegative; array<Ref> balances

tag(8); array<Expr> map; array<Ref> checks; Margin
Margin = tag(0); Q          // Constant
       | tag(1); Q          // Predicate

tag(9); Ref fact            // PositiveRefutation
```

All three endpoint tags and the new point tag require version>=10 even inside
semantically forbidden or infeasible branches. Minimum-record byte preflights are
20 per subflow group and 33 per improvement witness; nested counts independently
check remaining bytes and aggregate item limits. The version scan visits every
new body, improvement block and point refutation before encoding. Any new record
requires V10; without new records the lowest previously required version remains
unchanged, including byte-for-byte old encodings. Empty V10 outer improvement
arrays are present whenever another V10 feature selects the header.

## Limits, diagnostics and trust

All new work shares the same request budget with directional claims, bijections
and points. Improvements execute last, with no work reset. Every lift depth,
live-fact bound and exact arithmetic constraint still applies. JSON adds
`improvements` only when requested, and nonzero statistics `improvements`,
`subflow_lifts`, `subflow_generated_variables`, `subflow_generated_rows`,
`subflow_generated_terms`, `halfspace_domains`, `halfspace_generated_rows`,
`halfspace_generated_terms`; zero new counters are omitted so old receipts keep
their complete non-timing statistics unchanged. No resource default is raised
for this draft.

The strict and conditional root-domain handling and image evaluation join the existing trusted
checker. The subflow builder is trusted inference code: checking its old-scope
premises does not independently prove that its generated extension is jointly
satisfiable. The mathematical lemma, independent construction oracle, adversarial
tests and source review are separate evidence. Neither these tests nor successful
actual cases formally verify the Rust implementation.

Freeze remains conditional on complete actual-case contracts, independent review,
new-record byte/limit attacks, old-byte compatibility, a fresh complete corpus
replay, and controlled preparation/size/runtime measurements. Working test and
case receipts must identify the precise source and binary used.
