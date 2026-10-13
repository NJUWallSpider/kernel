# Current MCM, RPX and RPA reference

This is the single layout reference for the implemented codec. It consolidates
the V1–V8 increments without changing their bytes or declaring a new version.
V8 remains the last frozen protocol. The final section describes the implemented
but **unfrozen V9 objective-level draft** separately. The additional implemented
**unfrozen V10 draft** is specified in [FORMAT_V10_DRAFT.md](FORMAT_V10_DRAFT.md),
including SubflowLift, strict improvement, complete-image exclusion and explicit
affine input restrictions. No
FlowPrune endpoint is registered. The older `rpx-manual.pdf` and `rpx/` material describe unimplemented
D0 ideas and are not this format.

The source correspondence is `crates/core/src/codec.rs`, `proof.rs`, `rpa.rs` and
`verify.rs`. Full mathematical arguments remain in the individual rule documents
linked below; consolidating wire notation does not replace those arguments.

## Primitive notation and framing

All integers are unsigned, little-endian, with the exact width in their name.
There is no padding, alignment, pointer, offset table, native Rust layout or
implicit terminator. `T[n]` means exactly n consecutive T records. Definitions
list fields in wire order. Array counts are u32, not byte lengths.

```
tag(k)      = u8 k; u8 0; u16 0
array<T>    = u32 n; T[n]
option<T>   = u8 0                 // absent
            | u8 1; T             // present
name        = u32 byte_count; byte[byte_count]

header      = byte[4] magic; u16 version; u16 0; u64 total_file_bytes
```

MCM magic is `4d 43 4d 00`; RPX magic is `52 50 58 00`. The header is 16 bytes;
its length includes itself and must equal the actual file length. MCM supports
only version 1. RPX supports versions 1–8 plus the explicitly unfrozen drafts 9 and 10
in the current working tree. Every reserved field must be zero. Unknown versions,
tags, option discriminants and trailing bytes reject. No unknown extension is
skipped. The entire proof, including both sides of every branch, is decoded before
execution; an unreachable branch cannot hide a malformed record.

Names are length-delimited UTF-8 at the codec layer. Model validation additionally
requires nonempty ASCII names without control bytes and at most 1,024 bytes.
Variable names are unique
within the variable vector; row names are unique within the row vector. Names
are metadata, never theorem authority.

### Exact rational and affine expression

```
Q    = tag(sign); u32 numerator_bytes; u32 denominator_bytes;
       byte[numerator_bytes] numerator_magnitude;
       byte[denominator_bytes] denominator_magnitude
Expr = Q constant; array<(u32 coordinate, Q coefficient)>
```

`sign=0` is nonnegative and `sign=1` is negative. Magnitudes are base-256
little-endian without high zero bytes. The denominator is nonzero and positive;
numerator and denominator are relatively prime. Zero has sign 0, zero numerator
bytes and denominator bytes `[1]`. Negative zero and unreduced fractions reject.
The smallest Q is therefore 13 bytes.

An Expr denotes `constant + sum(coefficient * coordinate)`. Its terms must have
strictly increasing coordinate IDs and nonzero coefficients. There is no implicit
sorting or merging of binary expressions. The applicable model/scope checks every
coordinate against its actual dimension. A continuous coordinate denotes a real
number even though all stored coefficients and bounds are rational.

## MCM 1: whole model

```
MCM  = header; name model_name; array<Var>; array<Row>; Expr objective
Var  = name; tag(domain); option<Q> lower; option<Q> upper
Row  = name; Expr expression; option<Q> lower; option<Q> upper
```

`domain=0` is continuous and `domain=1` is integer. A missing bound is infinite.
Rows mean `lower <= expression <= upper` for each present side; equal finite
sides mean equality. A contradictory model remains a well-formed possibly empty
domain and is not silently repaired. The objective is normalized to minimization,
including its constant. Import rules for default bounds, binary domains, ranges,
maximization and objective constants are in [MPS_V1](MPS_V1.md) and
[LP_V1](LP_V1.md). Those importers are trusted.

No source/target subset or model hash is embedded as an acceptance shortcut in
RPX. The verifier receives two complete MCMs and an independent requested contract.
All accepted relationships refer to those actual models.

## RPX outer layout and directional contracts

```
RPX = header;
      array<Claim>;
      array<Block>;                 // exactly one block per claim, same order
      [array<PointWitness>]         // present iff file version >= 3
      [array<BijectionWitness>]     // present iff file version >= 7

Claim = u8 flags; u8 objective_relation; u16 0;
        array<(u32 input_coordinate, u32 output_coordinate)> projection;
        option<u32> inverse_claim;
        [option<Q> input_objective_lower]           // version >= 3
        [array<(Expr input, Expr output)> affine_projection] // version >= 5
        [option<Q> input_objective_level]           // DRAFT version >= 9 only
```

Square-bracketed layout fields are physically absent in earlier versions, not
present with a zero marker. Arrays required by a version are present even when
empty. The certificate writer chooses the **lowest required version**, considering
all claims, point refutations, bijection proofs, nested Blocks and local Cases.
Encoding a legacy certificate without a draft level retains its earlier layout.

Claim flag bits through V9 are: bit 0 reverse; bit 1 input integer mode; bit 2 output integer
mode. All other bits are zero in these versions. The separate V10 draft assigns
bit 3 to an optional final halfspace Expr; see its exact wire delta.
Forward means source to target; reverse means
target to source. Integer mode enforces each model's declared integer coordinates;
LP mode removes integrality while retaining every finite bound and row.
Objective tags are 0=None, 1=Equal, 2=NonIncreasing. Equal requires equality of
normalized objective values; NonIncreasing requires output minus input <= 0.

A directional claim supplies a total output construction for every feasible input
in its declared domain. Its Block must prove every actual output obligation.
Coordinate/affine observations express caller-selected equalities, not permission
to omit unobserved output constraints. An `inverse` refers to an opposing affine
root Return with compatible domains/modes; both the current and opposing Blocks
must have a root Return (not a Split or lift endpoint). Its composition is checked
on every input coordinate. Full inverse identities and the separate V7 bijection mechanism
are distinct contracts. Unrestricted V1–V8 input lower bounds are global on the
actual declared input mode; the V9 section states the restricted-domain exception.

## Facts, references and sequential steps

Fact kinds are `tag(0)=Le`, `tag(1)=Eq`, `tag(2)=Int`, meaning respectively
`e<=0`, `e=0`, and integer-valued e. A reference has the following layout:

| tag | Ref | Payload | Meaning |
|---:|---|---|---|
| 0 | VarLower | u32 i | LE(lower_i − x_i), finite bound required |
| 1 | VarUpper | u32 i | LE(x_i − upper_i), finite bound required |
| 2 | VarInt | u32 i | INT(x_i), declared integer and integer input mode required |
| 3 | RowLower | u32 i | LE(lower_i − row_i), finite side required |
| 4 | RowUpper | u32 i | LE(row_i − upper_i), finite side required |
| 5 | RowEq | u32 i | EQ(row_i − bound_i), equal finite sides required |
| 6 | Local | u32 id | Live checked local definition |
| 7 | Assumption | u32 i | Current path assumption; 0 is the oldest |
| 8 | Exact | none | Narrow exact discharge rule, not an arbitrary trusted assertion |

Every table tag is the four-byte `tag` primitive. Exact has no u32 payload. It
discharges constant true LE/EQ or an affine integral combination of declared
integer input coordinates with integral constant in integer mode. A constant
integer needs no coordinate integrality and is also allowed in LP mode. Exact
cannot assert an arbitrary inequality or integrality of nonconstant LP expressions.
Exact is accepted only where the checker already supplies the desired proposition:
Return/injectivity checks, lift premises and a local Derivation Witness. It cannot
be read as a fact by Lin (even with multiplier zero), Round, EqPair, Plotkin, a
Split/Cases integer operand, or either Absurd endpoint. A checked EQ of the exact
requested expression can discharge LE or INT as well as EQ; raw instruction
premise kinds still follow each instruction's own rules.

```
Steps = array<Step>
```

| tag | Step | Payload after tag | Minimum version |
|---:|---|---|---:|
| 0 | Lin | u32 id; Kind; Q constant; array<(Ref, Q multiplier)> | 1 |
| 1 | Round | u32 id; Ref le; Ref integer | 1 |
| 2 | Drop | array<u32> ids | 1 |
| 3 | EqPair | u32 id; Ref positive; Ref negative | 2 |
| 4 | Cases | u32 id; Kind; Expr expression; Expr split; option<Ref> integer; Derivation left; Derivation right | 2 |
| 5 | Plotkin | u32 id; u32 bits; u32 distance; array<(u32 coordinate, u64 label)> variables; array<Ref> cliques | 3 |

Lin checks kind-specific multipliers and constants, including zero-weight
references, before accepting its exact sum. LE cannot use negative inequality
multipliers; EQ requires equalities; INT admits integral combinations of INT
facts and rational multiples of zero EQ facts. Round requires an LE expression
and INT expression with identical variable terms and rounds their constant
difference exactly. EqPair checks exact opposite inequalities. See
[core semantics](SEMANTICS_V1.md) and [V2 rules](FORMAT_V2.md).

Definitions cannot overwrite live IDs. Drop removes visibility in the current
scope; an ID may be reused only after removal. A child cannot publish arbitrary
facts into its parent or leak dropped/redefined facts to a sibling. References
are not raw offsets into the binary file.

Cases proves one fixed parent proposition using two isolated Derivations:

```
Derivation = Steps; DerivationEnd
DerivationEnd = tag(0); Ref witness
              | tag(1); Ref absurd
```

With no integer reference, its split assumptions are `split<=0` and `-split<=0`.
With a proved INT(split), they are `split<=0` and `1-split<=0`. Both cover the
parent domain. Each child proves the same requested expression/kind or a
variable-free positive LE/nonzero EQ contradiction. A Derivation has no output
map and cannot replace terminal model obligations. The Plotkin predicate, label
coverage, actual binary domains and clique-premise checks are fully specified in
[FORMAT_V3](FORMAT_V3.md); it is a static trusted theorem, not a callback.

## Blocks, complete returns and joint extensions

```
Block = Steps; End
```

| tag | End | Payload after tag | Minimum version |
|---:|---|---|---:|
| 0 | Return | array<Expr> map; array<Ref> checks | 1 |
| 1 | Split | Expr expression; option<Ref> integer; Block left; Block right | 1 |
| 2 | Absurd | Ref fact | 1 |
| 3 | FlowLift | FlowWitness witness; Block body | 4 |
| 4 | IntervalLift | array<IntervalWitness> intervals; Block body | 5 |
| 5 | MenuLift | array<MenuWitness> menus; Block body | 7 |
| 6 | SignedLift | array<SignedWitness> decompositions; Block body | 8 |

Step tags, End tags and DerivationEnd tags are separate namespaces. Split uses
the same exhaustive split assumptions as Cases, but each branch has its own
complete output construction or contradiction. There is no continuation after
Split that joins incomplete obligation sets. Absurd requires a checked constant
positive LE or nonzero EQ.

Return contains exactly one affine expression for **every output variable** in
output coordinate order. The checker constructs the following obligations in
order; `checks` must contain exactly one valid reference for each, without missing
or surplus entries:

1. For each output variable: finite lower, finite upper, then required integrality.
2. For each output row: one EQ for equal finite sides; otherwise finite lower then
   finite upper. A missing side creates no obligation.
3. Requested objective relation, if not None.
4. Coordinate observations, then affine observations, both in request order.
5. Every requested affine inverse coordinate identity.
6. Opposing inverse objective-level membership, **draft V9 only**, when applicable.
7. Requested input objective lower bound, when present.
8. Every V7 bijection forward-after-reverse composition whose `reverse_claim`
   selects this direction, in the Request's bijection-array order. Within a pair,
   use the forward map's complete output-coordinate order, which is this reverse
   direction's **original input** coordinate order, including through extensions.

All expressions use the same map tuple. A local proof cannot supply different
existential output values to different obligations.

### Witness layouts and trusted existence statements

```
FlowWitness = u32 nodes; array<(u32 tail, u32 head)> arcs; array<FlowGroup> groups
FlowGroup = u32 source; array<(u32 sink, Q demand)> commodities;
            array<Expr> flows; array<Ref> nonnegative; array<Ref> balances
IntervalWitness = array<Expr> lower; array<Expr> upper; array<Ref> checks
MenuWitness = u32 maximum_index; Expr activation; Expr index; array<Ref> checks
SignedWitness = Q capacity; Expr flow; Expr activation; array<Ref> checks
```

All expressions and premise references belong to the pre-extension scope. Every
premise for every item must pass there before the body can use generated rows.
The old model's complete variable/row prefixes and objective are preserved.

| Rule | Required premises | Joint generated tuple and specification |
|---|---|---|
| Flow | Every old arc flow nonnegative and every node's common-source demand balance, per group | Nonnegative real commodity flows preserving every arc total and each commodity balance, including loops/circulation; [FLOW_V4](FLOW_V4.md) fixes dimensions and row order |
| Interval | Every lower-minus-upper LE, in lower-major order | Independent continuous coordinates satisfying all their bounds together; [INTERVAL_V5](INTERVAL_V5.md) fixes free/one-sided cases and layout |
| Menu | LE(-A), LE(A-1), INT(A), LE(-I), LE(I-KA), INT(I), in that order | K+1 binary coordinates with sum A and indexed sum I; [MENU_V7](MENU_V7.md) |
| Signed | LE(-Z), LE(Z-1), INT(Z), LE(F-CZ), LE(-F-CZ), in that order; C>=0 | Real nonnegative p,n and binary u,v with p-n=F, u+v=Z, p<=Cu, n<=Cv; [FORMAT_V8](FORMAT_V8.md) |

Menu/Signed require integer input mode. Flow/Interval generate continuous
coordinates. Legacy affine `inverse` rejects these non-affine endpoints.
Extensions are forbidden in LP refutation Blocks. Old-scope checks, model
validation and complete child checks do **not** independently prove
`M(x) and P(x) => exists z. E(x,z)`. Each existence lemma and its implementation
remain trusted; [the trust review](../audit/LIFT_TRUST_REVIEW.md) states the exact
boundary. Shared construction mechanics introduce no additional theorem.

## Point and bijection records

```
PointWitness = PointClaim; array<Q> values;
               [option<Block> refutation]           // version >= 6
PointClaim = tag(0); u8 flags; u8 0; u16 0; option<Q> objective   // Feasible
           | tag(1); u32 inclusion_claim                        // Strictness
           | tag(2); u32 inclusion_claim                        // FiberStrictness, >=6

BijectionWitness = u32 forward_claim; u32 reverse_claim;
                   Steps injectivity_steps; array<Ref> injectivity_checks // >=7
```

Feasible point flag bit 0 selects target rather than source; bit 1 enables
integrality. All other bits are zero. Values cover every coordinate of the
selected actual model. Its optional objective must equal the actual full
objective, including the constant.

All requested directional proofs pass before their strictness witnesses are
used. Strictness requires a full coordinate permutation for the indexed LP
inclusion and an actual feasible output point whose inverse projection is not
input-feasible. FiberStrictness instead fixes every requested coordinate and
affine observation on the **whole actual input LP**, then requires an ordinary
fresh-scope LP contradiction proof. Coordinate equalities precede affine ones.
Its proof permits only Absurd/Split endpoints, with normal scalar/local Cases
steps and no borrowed integer domain. FiberStrictness requires a present refutation;
Feasible and Strictness require it to be absent and reject a surplus proof.
See [POINT_V3](POINT_V3.md) and [FIBER_POINT_V6](FIBER_POINT_V6.md).

A V7 bijection pair binds opposing compatible directions. The forward proof has
a root affine Return. Every reverse Return proves all forward-after-reverse
coordinate identities. A separate equality proof uses two complete actual input
domain copies and equality of every coordinate of the same forward map, proving
every original coordinate equal. Neither a menu-local uniqueness statement nor
an empty selected observation set replaces that full paired-domain proof. See
[MENU_V7](MENU_V7.md) and [FORMAT_V7](FORMAT_V7.md).

## RPA and independent requests

RPA starts with exact bytes `RPA N\n` for a supported N, followed by one strict
JSON Certificate. No comments, trailing commas, unknown fields/variants or extra
top-level values are accepted. Its header must permit all used features; the
assembler emits the lowest necessary RPX version, not necessarily N.

Every mathematical scalar is a string parsed exactly: integer, rational, decimal
or scientific notation. IDs, bit counts, maximum indices and graph endpoints are
unsigned JSON integers; booleans are JSON booleans. Canonical affine terms remain
strictly ordered and nonzero. There are no implicit symbolic variable names.

```
Certificate = { claims: Claim[], blocks: Block[], points?: PointWitness[],
                bijections?: BijectionWitness[] }
Request = { claims: Claim[], points?: PointClaim[], bijections?: BijectionClaim[] }
        | Claim[]
Expr = { constant: scalar_string, terms: [u32, scalar_string][] }
Block = { steps: Step[], end: End }
Derivation = { steps: Step[], end: DerivationEnd }
PointWitness = { claim: PointClaim, values: scalar_string[], refutation?: Block|null }
BijectionClaim = { forward_claim: u32, reverse_claim: u32 }
BijectionWitness = { claim: BijectionClaim,
                     injectivity: { steps: Step[], checks: Ref[] } }
```

This is schema notation; keys in actual JSON are quoted. Claim keys are
`reverse`, `input_integers`, `output_integers`, `objective`, `projection`,
`inverse`, `input_objective_lower`, `affine_projection` and the draft-only
`input_objective_level`. `inverse` defaults to null; optional scalar fields default
to null; optional arrays default to empty. Required mode/objective/projection
fields cannot be omitted. Objective and kind values use their case-sensitive
names: `None`, `Equal`, `NonIncreasing`; `Le`, `Eq`, `Int`.

Enum variants are externally tagged: `{"Lin":{...}}`, `{"Return":{...}}`,
`{"VarLower":0}`, `"Exact"`, `{"Witness":{"Local":1}}`,
`{"Absurd":{"Local":2}}` for a DerivationEnd. An End Absurd instead has the
record payload `{"Absurd":{"fact":{"Local":2}}}`. Step/End record payload keys
are the names in the tables above. Cases uses `expression`, `split`, `integer`,
`left`, `right`; FlowLift uses `witness`, `body`; other lifts use their named arrays
and `body`. Witness objects use exactly the fields in their layout definitions.
Point variants are `{"Feasible":{"target":bool,"integers":bool,"objective":scalar|null}}`,
`{"Strictness":{"inclusion_claim":u32}}` and
`{"FiberStrictness":{"inclusion_claim":u32}}`.

The separately supplied Request must exactly equal the certificate's claims,
point claims and bijection claims. It contains no proof witness and cannot be
silently weakened by the certificate. An empty request rejects. A plain Claim
array requests no points or V7 bijections. A complete small example and lexical
details remain in [RPA_V1](RPA_V1.md); the actual case directories contain complete
later-version programs.

## Capability history and resource policy

| Minimum version | Added capability |
|---:|---|
| 1 | Whole-model affine direction proofs; Lin/Round/Drop; Return/Split/Absurd |
| 2 | EqPair and local Cases |
| 3 | Plotkin, objective lower bounds, feasible/strictness points |
| 4 | Common-source joint FlowLift |
| 5 | Independent IntervalLift and affine observations |
| 6 | Complete-fiber strictness and point refutation payload |
| 7 | Optional MenuLift and explicit complete-domain bijection pairs |
| 8 | Activated signed real decomposition |
| 9, unfrozen | Caller-declared objective-level input domains |

There is one codec and one verifier with explicit feature gates, not a separate
engine per row of this table. Static theorem names do not authorize dynamic host
plugins. Shared affine-expression/mapping DAGs and dedicated batch records are
not implemented by this wire layout. Historical increment documents and frozen
replay receipts remain available; this consolidated reference does not reinterpret
old bytes or itself promise permanent support for every historical decoder.

Current implementation budgets are distinct from mathematical semantics:

| Layer | Current limit |
|---|---:|
| CLI owned file read | 512 MiB per file |
| RPA / Request text parser | 256 MiB; serde JSON nesting capacity 128 |
| Binary codec file | 1 GiB, subject to the stricter CLI read limit |
| One counted array / cumulative counted items | 10,000,000 / 20,000,000 |
| Numerator or denominator binary magnitude | 1,700 bytes each |
| Binary name length preflight / actual model name | 1 MiB / 1,024 bytes |
| Binary proof nesting | 64; root depth is 1 |
| Model variables / rows / terms | 2,000,000 / 2,000,000 / 20,000,000 |
| Exact arithmetic intermediate numerator/denominator | 65,536 bits |
| Default verification work / live facts / depth | 1,000,000,000 / 1,000,000 / 64 |

Counts also undergo checked arithmetic and minimum-remaining-payload preflight
before allocation. Model, theorem and proof limits may be stricter than a wire
count. Work is shared across directions, extensions, injectivity and point
refutations; nested scopes do not reset the request budget. Text parsing depth
and proof depth are different quantities. These limits may reject a mathematically
valid proof as RESOURCE_LIMIT; that is neither verification nor refutation.
The `verify` CLI accepts `--work <u64>` and `--live-facts <usize>` anywhere
after the subcommand. It reports the effective work, live-fact and depth budgets
in `limits`, including failures after valid argument parsing. The depth limit
is not configurable. The earlier 100,000,000 work default remains part of the
recorded historical benchmarks; raising the current default is a resource-policy
change and does not change existing RPX bytes or proof obligations.

Verification reports VERIFIED (exit 0), INVALID (2), RESOURCE_LIMIT (3), or
IO_ERROR (4). Successful auxiliary CLI commands instead report CANONICALIZED,
ASSEMBLED, DISASSEMBLED or INSPECTED, also with exit 0; their success does not
assert a model relation.
Build/test and vector evidence is indexed in [the trust report](../audit/TRUST_REPORT.md).

## Unfrozen objective-level draft

The working V9 layout adds only the final optional Claim field shown above.
`input_objective_level=L` intersects the actual complete input domain with its
full normalized objective equal to L. It asserts no feasibility, attainment,
bound or optimality. The trusted constructor preserves the whole model and appends
that one exact equality at its old row count. The restriction is caller-bound
and local to the direction.

If an opposing legacy affine inverse claim is restricted to L, the current
Return must also prove that its mapped output objective equals L, even when its
own objective relation is None. Composition alone cannot establish membership in
the opposing map's proved domain. `input_objective_lower` on a restricted claim
is conditional; a global bound needs a separate unrestricted claim. An actual
full-model feasible point can separately prove attainment.

Existing V7 paired-domain bijections and whole-model Strictness/FiberStrictness
reject restricted indexed claims; their older meanings are not silently changed.
Ordinary feasible points retain their actual-model meaning. The actual test80
certificate checks a global bound, attainment and both complete affine inverse
directions on the optimal face, but its successful receipt does not freeze V9.
See [the draft specification](FORMAT_V9_DRAFT.md),
[design argument](OBJECTIVE_LEVEL_DESIGN.md) and [actual test80](../cases/test80/README.md).
