# MCM 1 and RPX 11 format

The current kernel reads MCM 1 models and RPX 11 proofs. RPX 1–10 remain historical formats and are rejected by this decoder. RPX 11 has exactly two proof blocks and no property declarations. [Semantics](SEMANTICS.md) defines acceptance; this document defines data layout.

## Common encoding

Integers used for framing are unsigned little-endian. A 16-byte header contains four magic bytes, u16 version, u16 reserved zero, and u64 total file length. Magic is `MCM\0` or `RPX\0`. No trailing bytes are allowed. A tag is u8 followed by three zero bytes. A vector starts with u32 count. Names are u32 UTF-8 byte length followed by bytes.

Rationals contain a sign tag (0 nonnegative, 1 negative), u32 numerator byte length, u32 denominator byte length, then little-endian unsigned magnitudes. The denominator is positive, magnitudes have no redundant high zero bytes and numerator/denominator are coprime. Zero has no numerator bytes, positive sign and denominator one. Each wire magnitude is at most 1,700 bytes; exact intermediate arithmetic has its separate 65,536-bit bound.

An affine expression is a rational constant followed by a vector of `(u32 coordinate, rational coefficient)`. Coordinates strictly increase and coefficients are nonzero. An optional rational is u8 0, or u8 1 followed by a rational.

Resource limits: file at most 1 GiB; each counted vector at most 10,000,000 items; aggregate counted items at most 20,000,000; block/derivation depth at most 64; names at most 1 MiB. Path-based input reads have a separate 512 MiB per-file policy. Counts are checked against remaining bytes before allocation. Encoding applies the same structural limits.

## MCM model payload

The MCM 1 payload is unchanged:

- Model name.
- Variable vector: name, u8 integer flag (0 or 1), optional lower bound, optional upper bound.
- Row vector: name, affine expression, optional lower side, optional upper side.
- Complete affine minimization objective.

All expressions, names, variable indices and arithmetic representations are validated. See [MPS](MPS_V1.md), [LP](LP_V1.md), and the [model JSON API](API.md#model-json).

## Certificate payload

Immediately after the RPX 11 header comes the forward Block, followed by the reverse Block. There are no counts or optional flags around these two required trees. Their reference scopes are independent; the work budget is shared. The wire version is always 11 regardless of which constructive rules occur.

Corresponding JSON:

```json
{
  "forward": {"steps": [], "end": {"Return": {"map": [], "checks": ["Exact"]}}},
  "reverse": {"steps": [], "end": {"Return": {"map": [], "checks": ["Exact"]}}}
}
```

This example certifies two feasible zero-dimensional models with equal constant objectives. Unknown fields, absent directions and additional properties are errors, not ignored metadata.

## References

| Tag | Payload | Meaning |
| --- | --- | --- |
| 0 | u32 | Variable lower bound |
| 1 | u32 | Variable upper bound |
| 2 | u32 | Actual variable integrality |
| 3 | u32 | Row lower side |
| 4 | u32 | Row upper side |
| 5 | u32 | Row equality |
| 6 | u32 | Visible local fact |
| 7 | u32 | Active branch assumption |
| 8 | none | Exact terminal tautology |

Kinds use tags 0=Le, 1=Eq, 2=Int. JSON references use `{"VarLower":0}`, `{"Local":3}`, etc., or `"Exact"`.

## Steps

A Block begins with a vector of steps and ends with one terminal. Derivations use the same step sequence. Tags and payloads:

| Tag | Step | Payload |
| --- | --- | --- |
| 0 | Lin | u32 id, kind tag, rational constant, vector of (Ref, rational multiplier) |
| 1 | Round | u32 id, Le Ref, Int Ref |
| 2 | Drop | vector of u32 local ids |
| 3 | EqPair | u32 id, positive Ref, negative Ref |
| 4 | Cases | u32 id, kind tag, conclusion Expr, split Expr, optional Int Ref, left Derivation, right Derivation |
| 5 | Plotkin | u32 id, u32 bits, u32 distance, vector of (u32 coordinate,u64 label), vector of clique Refs |

An optional Ref is u8 0 or u8 1 followed by a Ref. DerivationEnd tag 0 is Witness(Ref), tag 1 is Absurd(Ref). Cases validates both derivations and exports only their common conclusion.

Plotkin requires 1<=bits,distance<=64 and 2 distance>bits, distinct actual binary coordinates and labels fitting the bit count. Every pair whose labels have Hamming distance below `distance` must occur together in at least one checked clique inequality. The resulting bound is sum of the selected binary variables <= floor(2 distance/(2 distance-bits)).

## Terminals

| Tag | Terminal | Payload |
| --- | --- | --- |
| 0 | Return | Expr vector for the complete output tuple, Ref vector for all obligations |
| 1 | Split | split Expr, optional Int Ref, left Block, right Block |
| 2 | Absurd | contradiction Ref |
| 3 | FlowLift | Flow witness, child Block |
| 4 | IntervalLift | Interval witness vector, child Block |
| 5 | MenuLift | Menu witness vector, child Block |
| 6 | SignedLift | Signed witness vector, child Block |
| 7 | SubflowLift | Subflow witness, child Block |

Tags 8 and 9, previously used for improvement endpoints, are invalid. Return always checks all finite output bounds, all actual output integrality, all row sides and the nonincreasing objective, in the [specified order](SEMANTICS.md#return-obligation-order).

## Constructive witness payloads

Flow: u32 node count, vector of `(u32 tail,u32 head)` arcs, vector of groups. Each group contains u32 source, vector of `(u32 sink,rational demand)`, Expr vector of aggregate arc flows, Ref vector of nonnegativity premises, Ref vector of node-balance premises. The child uses the jointly generated commodity variables and conservation rows.

Subflow has the same layout, with demanded sinks and one retained-flow vector per group instead of a commodity decomposition. Demand scalars are nonnegative; repeated sinks are accumulated exactly. Node/arc dimensions and premise counts must agree with the generated construction. Loop arcs, parallel arcs and empty demand lists are supported.

Interval: Expr vector of lower bounds, Expr vector of upper bounds, Ref vector for every lower/upper pair in lower-major order. Each witness appends one continuous variable.

Menu: u32 maximum index K, activation Expr, index Expr, Ref vector of six premises: lower/upper activation, integer activation, lower/upper index, integer index. It appends K+1 binary choices and two equalities.

Signed: rational capacity C, flow Expr, activation Expr, Ref vector of five premises: activation lower bound, activation upper bound, integer activation, positive capacity inequality, negative capacity inequality. It appends four coordinates and four equalities/inequalities.

All lift premises must be valid in the parent scope. Layout preparation is available to authors but does not certify premises. The precise generated expressions are defined by the checked instantiators in [flow.rs](../crates/core/src/flow.rs), [subflow.rs](../crates/core/src/subflow.rs), [interval.rs](../crates/core/src/interval.rs), [menu.rs](../crates/core/src/menu.rs), and [signed.rs](../crates/core/src/signed.rs).

## RPA text schema

Exact JSON assembly begins with `RPA 11` followed by LF and the Certificate object. Rational literals are strings. Enum payloads use the Rust serde external-tag representation, for example `{"Return":{"map":[],"checks":["Exact"]}}`. JSON objects reject unknown fields. Compilation of raw Certificate JSON omits only the RPA header.

Readable `RPA-S 1` is a separate source grammar that lowers to this same two-block schema. Its source-language version does not select older RPX semantics. See [the tutorial](RPA_SOURCE.md).

## Compatibility and migration

No legacy decoder, property selector or weaker verification API remains in the production kernel. MCM 1 remains byte-compatible. RPX proofs must be migrated and verified; changing only their version bytes is invalid. The [migration script](../tools/migrate_mi_opt.py) requires a separately supplied old binary and never overwrites historical proofs or receipts.
