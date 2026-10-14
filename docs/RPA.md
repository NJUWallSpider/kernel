# RPA text assembly and caller requests (V1–V10)

RPA is UTF-8 text beginning with exact bytes `RPA N\n`, for N=1..10, followed by
one strict JSON Certificate object. All ten versions are implemented and frozen;
the authoritative schema is [FORMAT.md](FORMAT.md#rpa-text-and-independent-request-schema).
The assembler parses and encodes; it performs no proof search or verification.
Certificate preparation can use untrusted Python scripts or the public Rust
proof types and codec. Historical D0 assembly syntax is not accepted.

## Version selection

The header must be at least the minimum version required by every used feature.
V2 adds EqPair/Cases; V3 points, Plotkin and objective lower bounds; V4 FlowLift;
V5 IntervalLift and affine observations; V6 FiberStrictness and point refutations;
V7 MenuLift and bijection pairs; V8 SignedLift; V9 objective-level domains;
V10 halfspace domains, ImageExclusion, improvements and SubflowLift.

Assembly selects the lowest required RPX version. An `RPA 10` program using only
V1 features encodes as RPX 1. Disassembly also uses the lowest required version;
canonical reassembly preserves semantics but does not promise identical bytes
for arbitrary higher-version input encodings. Existing V1 examples remain valid.

## Lexical rules

The header permits no BOM, CRLF, extra spaces or comments; ordinary JSON
whitespace, including CRLF, is allowed in the body. The body uses ordinary JSON
objects, arrays, strings, booleans, and unsigned integer
IDs. JSON comments, trailing commas, multiple top-level values, unknown object fields,
duplicate record fields and unknown enum variants reject. Significant spelling is case sensitive. Numeric
IDs are JSON integers in `0..4294967295`; Plotkin labels are u64 integers.
They are not quoted. Mathematical scalars
are **strings**, never JSON floating-point numbers. A scalar is a signed integer,
integer fraction, or decimal/scientific literal accepted by `model::parse_q`:

```
"0"  "-7"  "3/11"  "-0.125"  "1e-6"  "2D+3"
```

Fractions are normalized exactly by the assembler. A zero denominator rejects.
Whitespace inside a scalar rejects. Decimal and exponent limits are implementation
resource bounds, not floating-point semantics. Disassembly emits canonical integer
or rational strings. The binary decoder still independently verifies canonical
fractions; it does not trust text assembly.

## Structural grammar

The notation below is schema notation, not literal omitted content allowed in a file.
`T[]` means an array of complete T values. `u32` is an unsigned JSON integer.

```
Certificate = {
  "claims": Claim[], "blocks": Block[],
  "points"?: PointWitness[], "bijections"?: BijectionWitness[],
  "improvements"?: ImprovementWitness[]
}
Request = {
  "claims": Claim[], "points"?: PointClaim[],
  "bijections"?: BijectionClaim[], "improvements"?: ImprovementClaim[]
} | Claim[]
Claim = {
  "reverse": boolean,
  "input_integers": boolean,
  "output_integers": boolean,
  "objective": "None" | "Equal" | "NonIncreasing",
  "projection": [u32, u32][],
  "inverse"?: null | u32,
  "input_objective_lower"?: null | scalar_string,
  "affine_projection"?: [Expr, Expr][],
  "input_objective_level"?: null | scalar_string,
  "input_halfspace"?: null | Expr
}
Expr = { "constant": scalar_string, "terms": [u32, scalar_string][] }
Block = { "steps": Step[], "end": End }
Ref = "Exact"
    | { "VarLower": u32 } | { "VarUpper": u32 } | { "VarInt": u32 }
    | { "RowLower": u32 } | { "RowUpper": u32 } | { "RowEq": u32 }
    | { "Local": u32 } | { "Assumption": u32 }
Step = { "Lin": { "id": u32, "kind": "Le" | "Eq" | "Int",
                    "constant": scalar_string, "terms": [Ref, scalar_string][] } }
     | { "Round": { "id": u32, "le": Ref, "integer": Ref } }
     | { "Drop": { "ids": u32[] } }
End = { "Return": { "map": Expr[], "checks": Ref[] } }
    | { "Split": { "expression": Expr, "integer": null | Ref,
                    "left": Block, "right": Block } }
    | { "Absurd": { "fact": Ref } }
```

The Step and End alternatives above show the V1 core. Current additional
variants and their exact payloads are defined in
[FORMAT.md](FORMAT.md#rpa-text-and-independent-request-schema):

| Record | Additional variants |
|---|---|
| Step | EqPair, Cases, Plotkin |
| End | FlowLift, IntervalLift, MenuLift, SignedLift, SubflowLift, ImproveReturn, PositiveRefutation |
| PointClaim | Feasible, Strictness, FiberStrictness, ImageExclusion |

Cases contains local Derivations, ending in `{"Witness": Ref}` or
`{"Absurd": Ref}`. Ordinary block Absurd instead uses
`{"Absurd": {"fact": Ref}}`. Bijection witnesses contain their pair contract
and a fresh injectivity proof; improvement witnesses contain their contract and
a complete improvement block. Point witnesses contain their contract, complete
value vector and, for FiberStrictness only, the required refutation block.

Optional arrays default to empty; optional scalars, inverse, halfspace,
refutation and Split/Cases integer operands default to null. Other structural
fields are required. Enum objects contain exactly one named variant. Affine terms must be
strictly increasing by variable ID, with nonzero coefficients, even when text literals
normalize to the same rational. There are no implicit symbolic names. Companion
`coordinate_index.json` files in real cases map actual model names to numeric IDs.

Directional map expressions use the current input scope, including valid earlier
extensions. Caller observations and restrictions instead use original model
dimensions; injectivity, point and improvement proofs have their specified
separate scopes. Static references resolve in the current proof model.
Assumption 0 is the oldest path assumption; improvements reserve it for the root
`LE(-P)`. Assumptions are not globally allocated references. Local registers are visible only after a
checked definition and before DROP in the current branch. The complete rules, mapping
scope, and kernel-generated check order are in [SEMANTICS.md](SEMANTICS.md) and
[FORMAT.md](FORMAT.md#return-obligation-order).

`request.json` is independent JSON supplied by the caller, without an RPA header
or proof witnesses. It may be a Request object or a legacy Claim array. Every
ordered contract array and field must match the certificate exactly, including
point maps, domain restrictions and improvement predicates. Matching uses parsed
values, not JSON byte spelling. An empty request rejects. A certificate cannot
request weaker claims than that independent input. Models are supplied as separate
MCM files and semantically bound through full checks.

## Complete small example

For identical source/target models with one integer coordinate in [0,1], no rows,
and zero objective, the following proves one requested identity direction:

```json
RPA 1
{
  "claims": [{
    "reverse": false,
    "input_integers": true,
    "output_integers": true,
    "objective": "Equal",
    "projection": [[0,0]],
    "inverse": null
  }],
  "blocks": [{
    "steps": [],
    "end": {"Return": {
      "map": [{"constant":"0","terms":[[0,"1"]]}],
      "checks": [{"VarLower":0},{"VarUpper":0},{"VarInt":0},"Exact","Exact"]
    }}
  }]
}
```

This is a complete program for the stated one-direction claim; it does not silently
claim bidirectional equivalence. Actual corpus certificates contain all requested
directions and every actual model obligation. For example, `cases/test40/proof.rpa`
is a fully expanded, executable four-claim proof, not a placeholder transcription.

```
rpx assemble proof.rpa proof.rpx
rpx disassemble proof.rpx recovered.rpa
rpx verify source.mcm target.mcm proof.rpx request.json
```

Assembler success only establishes an encodable certificate. Acceptance requires
independent model loading and complete kernel verification. Text parsing has a
256 MiB input limit and serde_json's default recursion limit of 128. Exhausting
that parser limit returns RESOURCE_LIMIT. JSON object/array wrappers and kernel
proof nesting are different counts: a proof below the kernel's depth budget may
still exceed the text parser's capacity. Neither limit is silently disabled.
Syntax, unknown fields and invalid variants remain INVALID. Binary proof limits
are documented separately. Normalization is exact; no source model or scalar is
rounded to fit. Historical checkpoint receipts retain their original outcomes;
current resource exhaustion is RESOURCE_LIMIT.
