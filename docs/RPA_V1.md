# RPA 1 text assembly

RPA 1 is UTF-8 text beginning with the exact bytes `RPA 1\n`, followed by a strict
JSON Certificate object. The explicit header separates it from the older D0 assembly
syntax. This deliberately small assembler performs parsing and binary encoding, not
proof search. Certificate preparation can use deterministic, untrusted Python scripts.

## Lexical rules

The body uses ordinary JSON objects, arrays, strings, booleans, and unsigned integer
IDs. JSON comments, trailing commas, multiple top-level values, unknown object fields,
and unknown enum variants reject. Significant spelling is case sensitive. Numeric
IDs are JSON integers in `0..4294967295`; they are not quoted. Mathematical scalars
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
Certificate = { "claims": Claim[], "blocks": Block[] }
Claim = {
  "reverse": boolean,
  "input_integers": boolean,
  "output_integers": boolean,
  "objective": "None" | "Equal" | "NonIncreasing",
  "projection": [u32, u32][],
  "inverse": null | u32
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

`inverse` may be omitted and defaults to null. All other listed structural fields
are required. Enum objects contain exactly one named variant. Affine terms must be
strictly increasing by variable ID, with nonzero coefficients, even when text literals
normalize to the same rational. There are no implicit symbolic names. Companion
`coordinate_index.json` files in real cases map actual model names to numeric IDs.

Expression variable IDs always refer to the current direction's input coordinates.
Static references resolve in that same model. Assumption 0 is the oldest enclosing
split, not a globally allocated reference. Local registers are visible only after a
checked definition and before DROP in the current branch. The complete rules, mapping
scope, and kernel-generated check order are in `SEMANTICS_V1.md`.

`request.json` is an independent plain JSON array of Claim values supplied by the
caller to the verifier. It must match the certificate claims exactly. A certificate
cannot request weaker claims than that independent input. Models are supplied as
separate MCM files and semantically bound through full checks, as documented there.

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
rounded to fit. The status correction postdates the frozen V7 checkpoint; the
original test47 recursion-limit receipt retains its historical INVALID outcome.
