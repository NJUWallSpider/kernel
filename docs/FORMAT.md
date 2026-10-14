# Frozen MCM 1 and RPX/RPA 1–10 specification

MCM 1 and RPX/RPA 1–10 are implemented and frozen. V9 and V10 were frozen by
explicit project decision on **2026-10-14**, with their existing bytes and
mathematical acceptance conditions unchanged. V10 is the highest frozen proof
version. This document replaces all ten FORMAT increments and CURRENT_FORMAT;
it is the single authoritative wire/text and contract reference. Incompatible
changes to these layouts or meanings require a new version, not reinterpretation
of a frozen record. Resource policies and informational diagnostics are identified
separately below.

The [freeze record](../audit/PROTOCOL_V9_V10_FREEZE.md) binds the implementation
and validation evidence. [Original hash-pinned specifications](../audit/specification-history/README.md)
and historical receipts retain their at-the-time draft status. Rule arguments
linked below supplement this specification; corpus receipts and design proposals
are evidence, not additional schemas or acceptance authorities.

Implementation correspondence: `crates/core/src/{model,proof,codec,rpa,verify}.rs`,
plus the static `flow`, `interval`, `menu`, `signed`, `subflow`, `point`,
`injectivity` and `level` modules; improvement checking is in `verify.rs`.

## Primitive notation and framing

All integer fields are unsigned little-endian at the stated width. Definitions
list fields in wire order. There is no padding, alignment, implicit terminator,
pointer, offset table or native Rust layout. Counts are items, not byte lengths.
`[field] // version >= N` means physical absence before N.

```
tag(k)    = u8 k; u8 0; u16 0
array<T>  = u32 n; T[n]
option<T> = u8 0 | u8 1; T
name      = u32 byte_count; byte[byte_count]
header    = byte[4] magic; u16 version; u16 0; u64 total_file_bytes
```

MCM magic is `4d 43 4d 00`; RPX magic is `52 50 58 00`. The 16-byte header's
length includes itself and must equal the actual file length. MCM accepts only
version 1; RPX accepts 1–10. Every reserved field is zero. Unknown versions,
tags, flags, option discriminants and trailing bytes reject; unknown extensions
are never skipped. The entire proof, including both sides of every branch, is
decoded before execution. Contradictory branches cannot hide malformed records.

Names are length-delimited UTF-8 in the codec. Actual model validation requires
nonempty ASCII names, no control bytes, at most 1,024 bytes, with uniqueness
separately within the variable and row vectors. Names are metadata.

### Exact rationals and expressions

```
Q = tag(sign); u32 numerator_bytes; u32 denominator_bytes;
    byte[numerator_bytes] numerator_magnitude;
    byte[denominator_bytes] denominator_magnitude
Expr = Q constant; array<(u32 coordinate, Q coefficient)>
```

Sign 0 is nonnegative; sign 1 is negative. Magnitudes are base-256 little-endian
without high zero bytes. Denominators are positive and nonzero; numerator and
denominator are coprime. Zero has sign 0, no numerator bytes, and denominator
bytes `[1]`. Negative zero, `0/7` and `2/4` reject in binary. The smallest Q is
13 bytes; a nonzero Q needs at least 14. For example, −1/2 is:

```
01 00 00 00 01 00 00 00 01 00 00 00 01 02
```

An Expr means `constant + sum(coefficient * coordinate)`. Terms have strictly
increasing distinct coordinate IDs and nonzero coefficients. The codec does not
sort or merge them. Every expression is checked against its applicable actual
model or current scope dimension. A zero Expr is 17 bytes. Stored coefficients
are rational; continuous coordinates have real semantics.

## MCM 1: complete models

```
MCM = header; name model_name; array<Var>; array<Row>; Expr objective
Var = name; tag(domain); option<Q> lower; option<Q> upper
Row = name; Expr expression; option<Q> lower; option<Q> upper
```

Domain 0 is continuous and 1 is integer. An absent bound is infinite. Each row
means `lower <= expression <= upper` for its present sides. Equal finite sides
mean equality. Contradictory bounds are valid and may describe an empty domain;
they are not repaired. The objective includes its constant and is minimized.
Maximization import negates the entire objective. The trusted input dialects,
defaults, binary domains and ranges are specified in [MPS](MPS_V1.md) and
[LP](LP_V1.md).

RPX contains no model hash or source/target subset that permits skipping actual
constraints. Verification receives two complete MCMs and an independent Request.
Every accepted statement refers to those actual models.

## RPX outer layout and version selection

```
RPX = header; array<Claim>; array<Block>;
      [array<PointWitness>]       // >= 3
      [array<BijectionWitness>]   // >= 7
      [array<ImprovementWitness>] // >= 10
```

There is exactly one ordered Block per Claim. Each requested point, bijection
and improvement has exactly one ordered matching witness. Version-required arrays
are present even when empty. Claims are not witnesses for unrequested properties.

| Minimum version | Added capability / version trigger |
|---:|---|
| 1 | Whole-model affine directions; Lin, Round, Drop; Return, Split, Absurd |
| 2 | EqPair or Cases |
| 3 | Plotkin, a present objective lower bound, or point records |
| 4 | FlowLift |
| 5 | IntervalLift or nonempty affine observations |
| 6 | FiberStrictness or a present point-refutation payload |
| 7 | MenuLift or bijection records |
| 8 | SignedLift |
| 9 | A present input objective level |
| 10 | A present input halfspace, ImageExclusion, improvement records, SubflowLift, ImproveReturn or PositiveRefutation |

All versions in this table are frozen. The encoder chooses the lowest necessary
version. It scans every claim and every syntactic proof subtree, including local
Cases, point refutations, injectivity steps, improvement blocks and both sides of
branches. A later lower-version feature cannot lower the requirement. A high-version
file may contain only older features; re-encoding then may select a lower version
and omit empty version-specific fields. Absent new features preserve the earlier
canonical encoding. No new MCM version is introduced.

There is one codec/verifier with explicit feature gates. This layout has no dynamic
theorem registry, host callback, generic batch instruction or shared expression/map
DAG. A header from before a feature's minimum version rejects that feature.

## Directional contracts

```
Claim = u8 flags; u8 objective_relation; u16 0;
        array<(u32 input_coordinate, u32 output_coordinate)> projection;
        option<u32> inverse_claim;
        [option<Q> input_objective_lower]                // >= 3
        [array<(Expr input, Expr output)> affine_projection] // >= 5
        [option<Q> input_objective_level]                // >= 9
        [Expr input_halfspace]                          // >= 10, flags bit 3 set
```

Flags: bit 0 reverse, bit 1 input integer mode, bit 2 output integer mode;
bit 3 announces the halfspace in V10 only. All remaining bits are zero. The
halfspace has **no option byte**: when its flag is set, its Expr immediately
follows the objective-level option. Before V10 bit 3 rejects.

Forward means source to target, reverse target to source. Integer mode enforces
the selected model's declared integer coordinates; LP mode removes integrality
while retaining every bound and row. Objective tags are 0=None, 1=Equal,
2=NonIncreasing, comparing full normalized objectives including constants.
NonIncreasing requires `f_output(map(x)) - f_input(x) <= 0`.

A direction supplies a total construction of one complete feasible output tuple
for **every** feasible input in its stated domain. Coordinate observations require
`x_i=map_j(x)`. Affine observations require `a(x)=b(map(x))`, using the original
input/output dimensions. Duplicate coordinate pairs reject; distinct pairs may
share coordinates. Affine observations remain ordered and may repeat. Unobserved
coordinates and constraints still require the complete output proof.

Two unrestricted Equal directions preserve the attainable objective-value sets
and extended infima. Two unrestricted NonIncreasing directions preserve extended
infima and nonemptiness, including empty, unbounded or nonattaining cases. Neither
statement alone asserts a bijection or existence of an attained minimizer.
Restricted directions apply only to their declared intersections.

### Objective-level and halfspace domains

A present `input_objective_level=L` restricts the complete actual input to
`f_input(x)=L`. A present `input_halfspace=H` also requires `H(x)<=0`. Both may
coexist. They assert neither global validity, nonemptiness, attainment nor
optimality. H uses original coordinates, validated before domain preparation.

The constructor keeps the entire original model, its variable prefix and
objective. For r original rows it appends the level equality at row r, when
present, then H's upper-zero/lower-absent row at r or r+1. `RowUpper` therefore
reads H, while `RowEq` cannot directly assume H=0. Objective constants are retained
in the equality. Fresh generated names have no theorem authority.

Each direction prepares its own domain; restrictions never leak to siblings,
points or improvements. Lifts may operate inside restricted domains under their
usual rules. A requested `input_objective_lower` is conditional if either
restriction is present. A global lower bound requires a separate unrestricted
claim; an actual-model Feasible point can independently establish attainment.
An empty restricted domain may close by Absurd and establishes no minimum.

Legacy inverse rejects if either selected direction has a halfspace. V7 bijection
pairs and indexed Strictness/FiberStrictness reject either restriction. Feasible
and ImageExclusion points continue to use whole actual models.

### Legacy affine inverse

`inverse` selects a distinct opposing claim with compatible input/output modes.
Both roots must be affine Return endpoints, excluding Split and lifts. For the
current map F and opposing map G, each current Return proves `G(F(x))=x` in every
input coordinate. The reciprocal identity requires a reciprocal requested inverse.

If the opposing claim has objective level L, the current Return additionally
proves `f_output(F(x))=L`, even when its objective relation is None. Composition
alone cannot prove that F(x) lies in G's restricted domain. With both opposing
domain-membership checks and reciprocal identities, the maps yield a bijection
of the stated restricted domains. This mechanism is distinct from V7 pairs.

## Facts, references and scopes

Kinds are four-byte `tag(0)=Le`, `tag(1)=Eq`, `tag(2)=Int`, meaning `e<=0`, `e=0`
and integer-valued e. Every Ref starts with the same four-byte tag primitive.

| Tag | Ref | Payload | Raw fact |
|---:|---|---|---|
| 0 | VarLower | u32 i | LE(lower_i − x_i), finite lower required |
| 1 | VarUpper | u32 i | LE(x_i − upper_i), finite upper required |
| 2 | VarInt | u32 i | INT(x_i), declared integer and input integer mode required |
| 3 | RowLower | u32 i | LE(lower_i − row_i), finite lower required |
| 4 | RowUpper | u32 i | LE(row_i − upper_i), finite upper required |
| 5 | RowEq | u32 i | EQ(row_i − bound_i), equal finite sides required |
| 6 | Local | u32 id | Visible checked local definition |
| 7 | Assumption | u32 i | Current path assumption, 0 is oldest |
| 8 | Exact | none | Narrow checker-supplied proposition discharge |

Exact has no u32 payload and creates no fact. It discharges constant true LE/EQ,
or an integral affine expression with integral constant and coefficients over
enabled declared integer input coordinates. Constant integers also work in LP
mode. It cannot assert nonconstant LP integrality or arbitrary inequalities.
Exact works only when a checker supplies the target proposition: Return,
ImproveReturn, PositiveRefutation, injectivity, lift premises, or Derivation
Witness checks. It cannot be read by Lin even at zero multiplier, Round, EqPair,
Plotkin, a Split/Cases integer operand or Absurd. A checked EQ of the exact same
expression can discharge a requested LE or INT; raw instruction operands still
obey their own kind rules.

Local IDs are mutable u32 registers. Defining a live ID rejects; Drop removes
visibility and permits later reuse. Children have isolated writes and deletion
masks; they cannot leak redefinitions, drops or arbitrary facts into siblings or
parents. Old facts remain valid through extensions. References are not offsets.

## Sequential steps and local derivations

```
Steps = array<Step>
Derivation = Steps; DerivationEnd
DerivationEnd = tag(0); Ref witness | tag(1); Ref absurd
```

| Tag | Step | Payload after tag | Min version |
|---:|---|---|---:|
| 0 | Lin | u32 id; Kind; Q constant; array<(Ref, Q multiplier)> | 1 |
| 1 | Round | u32 id; Ref le; Ref integer | 1 |
| 2 | Drop | array<u32> ids | 1 |
| 3 | EqPair | u32 id; Ref positive; Ref negative | 2 |
| 4 | Cases | u32 id; Kind; Expr expression; Expr split; option<Ref> integer; Derivation left; Derivation right | 2 |
| 5 | Plotkin | u32 id; u32 bits; u32 distance; array<(u32 coordinate, u64 label)> variables; array<Ref> cliques | 3 |

Lin checks every reference and type, even zero-weight operands. Its output is
`constant + sum(multiplier * fact_expression)`:

- Le: constant <=0; LE multipliers nonnegative; EQ multipliers arbitrary; no INT.
- Eq: constant zero; all operands EQ with arbitrary rational multipliers.
- Int: integral constant and integral multipliers for INT; arbitrary rational
  multiples of zero EQ; no LE operands.

Round requires raw LE(a) and INT(z) with identical nonconstant terms. For
`d=a.constant-z.constant`, it derives `LE(z+ceil(d))`, using exact ceiling also
for negative d. EqPair requires raw LE(e) and LE(−e), including exact opposite
constants, and yields EQ(e). Drop permits an empty list, but duplicate or absent
IDs reject. [Current semantics](SEMANTICS.md) gives the invariant argument.

Cases proves one fixed `kind/expression` in two isolated derivations. Without an
integer reference its guards are `split<=0` and `-split<=0`, overlapping at zero.
With raw INT(split), they are `split<=0` and `1-split<=0`, exhaustive on integers.
Each child proves the same target or a contradiction. The common fact is then
published at id in the parent. Derivations have no maps and cannot replace output
obligations. Contradictions are checked variable-free positive LE or nonzero EQ;
INT and Exact do not establish Absurd.

### Plotkin

Input integer mode is required. `1<=bits,distance<=64` and `2*distance>bits`.
Selected coordinates are distinct declared integers with finite lower >=0 and
upper <=1. u64 labels fit the stated bit width (all bits permitted for width 64).
Each clique reference must be raw LE of `sum(x_i)-1` with unit coefficients.
Every clique coordinate has a finite nonnegative lower, including any unselected
coordinates; those extra coordinates need not be binary.

Every selected pair with label Hamming distance below `distance` must occur
together in at least one checked clique. Duplicate labels are allowed if covered.
Labels and cliques never grant facts without these checks. The output is
`LE(sum(selected x)-floor(2d/(2d-b)))` for d=distance, b=bits. Empty selections
or clique lists are valid when no required pair is uncovered.

For k active selected bits, uncovered close pairs are forbidden by the cliques,
so each pair differs in at least d positions. Double counting gives
`d*k*(k-1)/2 <= sum_h a_h*(k-a_h) <= b*k*k/4`, hence the bound. The actual
binary domains and coverage checks are part of the trusted static theorem.

## Blocks and complete endpoints

```
Block = Steps; End
```

| Tag | End | Payload after tag | Min version |
|---:|---|---|---:|
| 0 | Return | array<Expr> map; array<Ref> checks | 1 |
| 1 | Split | Expr expression; option<Ref> integer; Block left; Block right | 1 |
| 2 | Absurd | Ref fact | 1 |
| 3 | FlowLift | FlowWitness witness; Block body | 4 |
| 4 | IntervalLift | array<IntervalWitness> intervals; Block body | 5 |
| 5 | MenuLift | array<MenuWitness> menus; Block body | 7 |
| 6 | SignedLift | array<SignedWitness> decompositions; Block body | 8 |
| 7 | SubflowLift | SubflowWitness witness; Block body | 10 |
| 8 | ImproveReturn | array<Expr> map; array<Ref> checks; ImprovementMargin | 10 |
| 9 | PositiveRefutation | Ref fact | 10 |

Step, End and DerivationEnd tags are distinct namespaces. Split uses the same
exhaustive real/integer guards as Cases. Both children execute and each proves a
complete output construction or contradiction. There is no post-Split continuation
merging incomplete obligations. Absurd reads a checked constant positive LE or
nonzero EQ, never Exact or INT.

### Return obligation order

Map has exactly one affine expression per actual output variable, in coordinate
order. All map expressions validate before checks; every obligation uses this
same tuple. Missing or surplus expressions/references reject. Checks are ordered:

1. Each output variable: finite lower, finite upper, required integrality.
2. Each output row: one EQ for equal finite sides, otherwise finite lower then
   finite upper. Absent sides add nothing.
3. Requested objective relation, unless None.
4. Coordinate observations, then affine observations, in their request orders.
5. Legacy inverse identities for every original input coordinate.
6. Opposing inverse objective-level membership, when present.
7. Requested input objective lower bound, when present.
8. Bijection compositions selecting this reverse direction, in pair-request order,
   each in the forward map's complete output-coordinate order. The original
   reverse input coordinates remain available through lifts.

Equal variable bounds still produce two LE obligations. An EQ check may discharge
a matching LE/INT as specified above. Facts proving different existential tuples
cannot be assembled into a Return.

## Joint existence extensions

All witnesses use the **pre-extension** scope. Every premise for every item/group
passes there before any generated coordinate or row is visible. The old variables,
rows and objective remain complete prefixes. Nesting can use previously established
extensions, but items in one lift cannot reference each other's new coordinates.
Generated names avoid collisions. Copying, dimension/support validation, exact
intermediates and generated terms share the remaining work budget.

Each lift's simultaneous-existence lemma and Rust builder are trusted inference
code. Premise checking, model validation and a complete child proof do not
independently prove the existence lemma. The child still proves all actual output
obligations with one tuple. [Lift trust review](../audit/LIFT_TRUST_REVIEW.md)
explains this boundary. No production search or solver callback supplies authority.

Flow/Interval/Subflow work in LP or integer input modes and generate continuous
coordinates. Menu/Signed require integer input mode, including empty item lists.
Legacy inverse forbids lifts at its affine root; V7 reverse proofs may lift but
retain every composition and the independent injectivity proof. LP/fiber refutation
blocks permit only Split/Absurd endpoints, with scalar/Cases steps and no integrality
or existence lifts. Improvement blocks permit the lifts under their usual rules.

### FlowLift

```
FlowWitness = u32 nodes; array<(u32 tail, u32 head)> arcs; array<FlowGroup> groups
FlowGroup = u32 source; array<(u32 sink, Q demand)> commodities;
            array<Expr> flows; array<Ref> nonnegative; array<Ref> balances
```

There is at least one node, group and commodity per group. Endpoints are in range
and demands nonnegative. Zero demands, repeated sinks, source=sink, parallel arcs,
self-loops and zero arcs are allowed. For m arcs and n nodes, each group supplies
m flows, m nonnegative refs and n balance refs. With divergence outflow minus
inflow, `b_v=sum_k d_k*(1[v=source]-1[v=sink_k])`, premises are m `LE(-F_e)`
then n `EQ(div_v(F)-b_v)`, in group order.

For k commodities append k*m nonnegative continuous variables z with no finite
upper bounds, ordered commodity then arc. Append k*n equality rows for each
commodity's node balances, then m equalities `sum_k z_ke=F_e`. Groups are ordered
as given. Self-loops cancel in divergence but retain their coordinates and arc-total
rows. All arc totals and circulation are preserved.

Finite positive path extraction serves the demands; a commodity whose source is
its sink has zero divergence and needs no path. Extraction needs at most m+k
path operations; remaining circulation goes to the first commodity. This gives
one joint tuple. It grants no additional capacities or flow integrality.
[Full constructive argument and builder order](FLOW_V4.md).

### IntervalLift

```
IntervalWitness = array<Expr> lower; array<Expr> upper; array<Ref> checks
```

For p lowers and q uppers, exactly p*q refs prove `LE(lower_i-upper_j)` in
lower-major/upper-minor order, retaining duplicates and zero propositions. Each
item adds one continuous variable z with no intrinsic bounds, then lower rows
`z-lower_i>=0`, followed by upper rows `z-upper_j<=0`. Empty item lists are identity;
free and one-sided intervals are allowed.

At a fixed old point choose max(lower) when present, otherwise min(upper),
otherwise zero. All choices coexist since every bound uses the old tuple.
This grants no coupled existence or integrality.
[Full argument](INTERVAL_V5.md).

### MenuLift

```
MenuWitness = u32 maximum_index; Expr activation; Expr index; array<Ref> checks
```

For K=maximum_index, A=activation, I=index, exactly six premises are
`LE(-A), LE(A-1), INT(A), LE(-I), LE(I-K*A), INT(I)` in that order.
Append K+1 integer [0,1] variables z_j, j=0..K, then equality rows
`sum_j z_j-A=0` and `sum_j j*z_j-I=0`. For K=0 both rows remain, including
`-I=0`. Empty menus are identity subject to integer mode and depth requirements.

If A=0, I=0 and all z are zero. If A=1, choose z_I=1 and the others zero.
The choices coexist and are locally unique; this alone proves no whole-model
bijection. [Full argument and independent bijection conditions](MENU_V7.md).

### SignedLift

```
SignedWitness = Q capacity; Expr flow; Expr activation; array<Ref> checks
```

For C=capacity, F=flow, Z=activation, C is canonical and nonnegative. Exactly five
premises are `LE(-Z), LE(Z-1), INT(Z), LE(F-C*Z), LE(-F-C*Z)`.
For each item append p,n continuous >=0 without finite uppers, then u,v integer
[0,1], and these four rows:

```
p-n-F = 0
u+v-Z = 0
p-C*u <= 0
n-C*v <= 0
```

Order is item then p,n,u,v, and item then the listed rows. C=0 keeps both capacity
rows with zero terms omitted. Empty lists are identity under the usual mode/depth
rules. If Z=0 then F=0 and choose all zero. If Z=1 and F>=0 choose
`(p,n,u,v)=(F,0,1,0)`; if F<0 choose `(0,-F,0,1)`. Capacity premises suffice.
Active zero flow retains u+v=1. All choices coexist; F need not be integral.

### SubflowLift

```
SubflowWitness = u32 nodes; array<(u32 tail, u32 head)> arcs; array<SubflowGroup> groups
SubflowGroup = u32 source; array<(u32 sink, Q demand)> demands;
               array<Expr> flows; array<Ref> nonnegative; array<Ref> balances
```

There is at least one node and group. A group's demand list may be empty. Every
sink differs from its source, including for zero demand; repeated sinks and
nonnegative demands are allowed. Arcs may be parallel, self-loops or empty.
Let B=sum(demands), b_source=B and each other b_v=−sum(demands at v).
Each group checks m `LE(-F_e)` then n `EQ(div_v(F)-b_v)` in the old scope.

Each group adds m continuous g_e in [0,B], followed by n equality rows
`div_v(g)=b_v` and m upper-zero rows `g_e-F_e<=0`. With N old variables and R
old rows, group j starts at coordinate N+j*m and row R+j*(n+m). For B=0
all g are zero. Groups' choices coexist over the same old point.

Add a supersink and extract simple positive source-to-demand paths; at most
m+k positive-demand path operations suffice. Their aggregate g keeps the requested
balances, satisfies `0<=g_e<=F_e` and `g_e<=B`, and discards residual circulation.
It preserves demanded balance, unlike FlowLift's preservation of every arc total.
No integer flow follows. Extra objectives/side conditions remain child obligations.
[Full constructive lemma, edge cases and builder](SUBFLOW_V10.md).

## Complete point witnesses

```
PointWitness = PointClaim; array<Q> values;
               [option<Block> refutation] // >= 6
PointClaim = tag(0); u8 flags; u8 0; u16 0; option<Q> objective // Feasible
           | tag(1); u32 inclusion_claim                     // Strictness
           | tag(2); u32 inclusion_claim                     // FiberStrictness, >=6
           | tag(3); u8 flags; u8 0; u16 0; array<Expr> map  // ImageExclusion, >=10
```

Feasible flags are bit 0 target and bit 1 integers; others zero. ImageExclusion
uses only bit 0 point_in_target. Values cover every original coordinate of the
selected actual model, never a restricted or generated model. Surplus refutations
reject except for FiberStrictness, which requires one.

- **Feasible:** checks every actual bound and row, requested integrality and,
  when supplied, equality to the complete objective value. It proves no optimum
  alone and inherits no directional level/halfspace.
- **Strictness:** indexes an unrestricted LP-to-LP inclusion with a complete
  coordinate projection bijection. A full feasible output point is pulled back
  through the inverse permutation and must violate an actual input bound/row.
  This proves proper inclusion in the common permutation space. Fractionality
  alone is insufficient. [Point argument](POINT_V3.md).
- **FiberStrictness:** indexes an unrestricted LP-to-LP inclusion. Over the whole
  actual input LP, append equalities fixing every coordinate observation, then
  every affine observation, to its value at the complete feasible output point.
  Constants remain in the formulas. A fresh LP refutation proves this entire
  fiber empty; unobserved coordinates are not fixed. Only Split/Absurd endpoints
  and ordinary scalar/Cases steps are allowed. With no observations, the actual
  input must be empty. [Full fiber argument](FIBER_POINT_V6.md).
- **ImageExclusion:** checks a full feasible LP point on the chosen actual side
  and its caller-specified complete affine image in the opposite actual model.
  All image expressions validate and the entire tuple evaluates before an actual
  opposite bound/row violation establishes exclusion. It is not integer separation,
  an indexed inclusion, global containment or exclusion of all possible completions.

## Complete-domain bijection witnesses

```
BijectionWitness = u32 forward_claim; u32 reverse_claim;
                   Steps injectivity_steps; array<Ref> injectivity_checks
```

The two indices are distinct, valid, opposing and mode-compatible; duplicate
ordered pairs reject. Neither direction may have a level or halfspace. The
forward proof has root affine Return F. Every reverse Return G, including through
Split/lifts, checks `F(G(y))=y` for every original reverse input coordinate.

Independent injectivity uses a fresh paired model containing two complete copies
x,x' of the actual forward input, all original bounds/domains/rows and then
`F_j(x)-F_j(x')=0` for every coordinate of the same F. Rows are first original,
then shifted original, then map equalities. Its objective is zero; it adds no
objective equality constraint. Forward input integer mode applies to both copies.
Steps and checks prove `EQ(x_i-x'_i)` for every original coordinate. Injectivity
plus reverse surjectivity yields a full bijection, including empty domains.
Selected observations or menu-local uniqueness cannot replace it. Objective
relationships remain those separately requested. [Argument](MENU_V7.md).

## Strict improvements

```
ImprovementWitness = u8 flags; u8 0; u16 0; Expr positive; Block
ImprovementMargin = tag(0); Q constant | tag(1); Q predicate
```

Flags bit 0 selects target, bit 1 enables integers; all others zero. The independent
ImprovementClaim has `target`, `integers`, `positive`. For the complete selected
actual model M, normalized objective f and original-coordinate P=positive,
acceptance means:

`for every feasible x in M with P(x)>0, there exists feasible y in M with f(y)<f(x)`.

Each block has fresh facts and assumption 0 `LE(-P)`. Later branch assumptions
start at 1. The strict P>0 condition remains in immutable improvement context,
not as a scalar fact. It cannot be exported or borrowed by ordinary directions,
local Cases or siblings. There is no implicit objective-level restriction.

ImproveReturn gives one full tuple in the **same** actual model. Checks are the
ordinary variable and row feasibility obligations, followed by
`LE(f(y)-f(x)+h(x))`. Margin Constant(q) gives h=q; Predicate(q) gives h=q*P.
Both require canonical bit-bounded q>0. No zero/negative margin is accepted.
Both objectives include constants. Missing/surplus expressions or checks reject;
no projection, inverse, level or input-lower obligations are added. Lift coordinates
may appear in y; P keeps its original meaning.

PositiveRefutation checks `LE(P)` against the root's strict P>0 condition. A matching
EQ or the narrow Exact rule may discharge it. This closes that strict branch,
not the entire weak closure P>=0. Ordinary Absurd closes an inconsistent weak
branch. Ordinary Return is forbidden in improvements; ImproveReturn and
PositiveRefutation are forbidden in ordinary mapping/refutation contexts. Split
and the usual lifts are allowed; all branches execute, including boundaries.

The existing scalar/scope induction, exhaustive branches and trusted joint lifts
ensure every strict-domain point either contradicts its leaf or receives one
feasible tuple with positive decrease. Consequently every attained minimizer has
P<=0. Empty, unbounded and nonattaining domains are allowed; the contract asserts
no minimum's existence or value. A separate direction on P<=0 can cover all
original minimizers. Combined with complete objective/recovery directions and
explicit retained observations, this may establish an optimal-projection relation;
no single component request silently asserts that compound conclusion.

## RPA text and independent Request schema

RPA begins with exact UTF-8 bytes `RPA N\n`, N=1..10, then one JSON Certificate.
The header accepts no BOM, CRLF, extra spaces or comments. Ordinary JSON whitespace,
including CRLF, is permitted in the body. Unknown fields/variants, duplicate
record fields, trailing commas and extra top-level values reject. Variant names
are case-sensitive. The header must permit all used features; assembling selects
the lowest required RPX version rather than preserving N.

All mathematical scalars are strings: signed integers, integer fractions, exact
decimals and scientific notation using e/E/d/D. Negative denominators normalize;
all arithmetic is exact. JSON floats/numeric scalar literals reject. Rational text
normalizes before semantic equality; Expr terms still must be ordered and nonzero,
including after normalization. IDs, graph nodes, bit counts and indices are JSON
u32 integers, labels u64; booleans are true/false.

The following is schema notation; actual JSON keys are quoted:

```
Certificate = { claims: Claim[], blocks: Block[], points?: PointWitness[],
                bijections?: BijectionWitness[], improvements?: ImprovementWitness[] }
Request = { claims: Claim[], points?: PointClaim[], bijections?: BijectionClaim[],
            improvements?: ImprovementClaim[] } | Claim[]
Claim = { reverse: bool, input_integers: bool, output_integers: bool,
          objective: "None"|"Equal"|"NonIncreasing", projection: [u32,u32][],
          inverse?: u32|null, input_objective_lower?: scalar|null,
          affine_projection?: [Expr,Expr][], input_objective_level?: scalar|null,
          input_halfspace?: Expr|null }
Expr = { constant: scalar, terms: [u32,scalar][] }
Block = { steps: Step[], end: End }
Derivation = { steps: Step[], end: DerivationEnd }
PointWitness = { claim: PointClaim, values: scalar[], refutation?: Block|null }
BijectionClaim = { forward_claim: u32, reverse_claim: u32 }
BijectionWitness = { claim: BijectionClaim,
                     injectivity: { steps: Step[], checks: Ref[] } }
ImprovementClaim = { target: bool, integers: bool, positive: Expr }
ImprovementWitness = { claim: ImprovementClaim, block: Block }
```

`scalar` above means a scalar string. Optional arrays default to empty, optional
scalars/inverse/refutation/halfspace to null; other fields shown are required.
Kind is `"Le"|"Eq"|"Int"`. Ref is `"Exact"` or an externally tagged object such
as `{"VarLower":0}`, `{"Local":7}` or `{"Assumption":0}`.

Steps/Ends use externally tagged records, with exactly these JSON payload fields:

| Variant | Payload fields |
|---|---|
| Lin | id, kind, constant, terms (`[Ref,scalar][]`) |
| Round | id, le, integer (required Ref) |
| Drop | ids |
| EqPair | id, positive, negative |
| Cases | id, kind, expression, split, integer (omitted/null/Ref), left, right |
| Plotkin | id, bits, distance, variables (`[u32,u64][]`), cliques |
| Return | map, checks |
| Split | expression, integer (omitted/null/Ref), left, right |
| Absurd | fact |
| FlowLift / SubflowLift | witness, body |
| IntervalLift | intervals, body |
| MenuLift | menus, body |
| SignedLift | decompositions, body |
| ImproveReturn | map, checks, margin |
| PositiveRefutation | fact |

Witness field names match their binary definitions: FlowGroup uses commodities;
SubflowGroup uses demands; MenuWitness uses maximum_index; all remaining names
are as listed. Demands/commodities are `[u32,scalar][]`. Margin is
`{"Constant":"q"}` or `{"Predicate":"q"}`. DerivationEnd is
`{"Witness":Ref}` or `{"Absurd":Ref}`; the ordinary End Absurd instead uses
`{"Absurd":{"fact":Ref}}`.

Point variants are `{"Feasible":{"target":bool,"integers":bool,"objective":scalar|null}}`
(objective may be omitted), `{"Strictness":{"inclusion_claim":u32}}`,
`{"FiberStrictness":{"inclusion_claim":u32}}`, and
`{"ImageExclusion":{"point_in_target":bool,"map":Expr[]}}`.

The separately supplied Request must equal all certificate contract arrays in
order and every field, including point maps, restrictions and improvement P.
This is parsed structural equality, not literal JSON-byte equality. Requests have
no proof witnesses; a certificate cannot weaken the caller's requirement. An
empty Request rejects. A legacy Claim array requests no other contract types.

Verification validates the actual models and contract indices/modes first, then
all directional proofs, independent bijection injectivity, points/fiber refutations
and improvements. All share one work budget, without resets for independent scopes.

A complete minimal identity certificate, for identical one-variable models with
continuous x>=0, no rows and zero objective, is:

```json
RPA 1
{"claims":[{"reverse":false,"input_integers":false,"output_integers":false,
 "objective":"Equal","projection":[[0,0]]}],
 "blocks":[{"steps":[],"end":{"Return":{
 "map":[{"constant":"0","terms":[[0,"1"]]}],
 "checks":[{"VarLower":0},"Exact","Exact"]}}}]}
```

The independent request is the same claims array. Complete runnable bidirectional
LP/RPA/Request examples are in [rpx/examples](rpx/examples/) and checked by
`tools/check_rpx_manual.py`. [Current RPA tutorial](RPA.md) gives additional lexical
examples without extending the schema. Disassembly/reassembly preserves semantics
and canonical lowest-version encoding; arbitrary high-version input bytes are
not promised to round-trip unchanged.

## Resource policies, reports and trust boundary

These are current implementation limits, distinct from frozen mathematical
meanings. Controlled count arithmetic and minimum-remaining-byte checks precede
allocation; applicable model/proof/theorem limits may be stricter.

| Layer | Current limit |
|---|---:|
| CLI owned file read | 512 MiB per file |
| RPA / Request text | 256 MiB; serde nesting capacity 128 |
| Binary codec file | 1 GiB, subject to CLI limit |
| One array / cumulative counted items | 10,000,000 / 20,000,000 |
| Binary numerator / denominator magnitude | 1,700 bytes each (13,600 bits) |
| Binary name preflight / actual model name | 1 MiB / 1,024 bytes |
| Proof nesting | 64; root depth 1; Split/Cases/lifts increment |
| Model variables / rows / combined terms | 2,000,000 / 2,000,000 / 20,000,000 |
| Arithmetic intermediate numerator / denominator | 65,536 bits |
| Decimal digits / absolute and effective exponent | 4,096 / 4,096; exponent digits <=6 |
| Scalar text length | 8,192+32 bytes |
| Default verification work / live facts / depth | 1,000,000,000 / 1,000,000 / 64 |
| Plotkin membership matrix | 8,000,000 u64 cells; pair work also charged |
| Point records / total point values | 1,000,000 / 20,000,000 |

Minimum bytes per counted record used by codec preflight:

| Record | Minimum bytes |
|---|---:|
| Expr term / Lin term / sink-demand / Expr / Q point value | 17 / 17 / 17 / 17 / 13 |
| Step / graph arc / projection pair / Ref / Drop ID | 8 / 8 / 8 / 4 / 4 |
| MCM Var / Row; Claim / Block / PointWitness | 10 / 23; 9 / 12 / 12 |
| Affine observation pair / Plotkin variable-label pair | 34 / 12 |
| Flow or Subflow group / IntervalWitness / MenuWitness / SignedWitness | 20 / 12 / 42 / 51 |
| BijectionWitness / ImprovementWitness | 16 / 33 |

Text depth is not proof depth. Exact intermediate overflow rejects before
cancellation; it is not rounded away. Owned parsing/models are not streaming or
mmap; logical live-fact peak is not physical RSS. Standard library and bigint
internal allocation limitations remain in the trusted boundary.

The verify CLI permits `--work <u64>` and `--live-facts <usize>` after the command;
depth is not configurable. Reports include effective limits. Historical benchmarks
using 100,000,000 work retain that original policy. A RESOURCE_LIMIT outcome may
reject a mathematically valid proof and asserts no model relation.

Verification outcomes: VERIFIED exit 0, INVALID 2, RESOURCE_LIMIT 3, IO_ERROR 4.
Auxiliary CANONICALIZED, ASSEMBLED, DISASSEMBLED, INSPECTED and EXPORTED outcomes
also use exit 0 but prove no mathematical relationship. API report schemas and
informational diagnostic `code`/`location` are specified in [API](API.md); their
vocabulary is not frozen as proof protocol.

`obligations` counts complete mapped-output obligations, excluding lift premises,
local Witness checks and point/refutation checks. Work includes all checks and
builders. Fiber subchecks contribute shared work but do not aggregate their branch,
linear-term or peak counters into ordinary directional counters. Point evaluations
charge examined terms. Zero-valued newer V10 counters may be omitted to retain
older non-timing JSON. Statistics are not optimality or feasibility assertions.

The trusted boundary includes parsers/importers, exact arithmetic, expression and
scope algebra, obligation builders, point/injectivity checkers, static theorem and
joint-lift implementations, and the compiler/runtime/OS. Python preparers, solvers,
case names, labels, manifests and hashes grant no mathematical facts. Independent
oracles, adversarial byte vectors, source reviews and complete corpus replay are
supporting evidence, not formal verification of the Rust implementation.
