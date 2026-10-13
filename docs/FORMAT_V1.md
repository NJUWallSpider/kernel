# MCM / RPX implementation format, version 1

This document specifies the V1 binary format implemented by `crates/core/src/codec.rs`. Version 1 is distinct from the historical unimplemented D0 / RPX 0.1 proposal. The rewritten [Chinese kernel manual](rpx-manual.pdf) describes the current implementation. V1 does not implement D0's section directory, expression pool, implicit fact IDs, merge/yield operations, batch operations, or theorem calls. Unknown tags and versions are rejected. RPA assembly must produce exactly the data described here; assembly is not proof verification.

The decoder also supports the separately specified [version 2 local-derivation extension](FORMAT_V2.md). That extension does not change v1 bytes or enable its new step tags under a v1 header. MCM remains version 1.

## Common conventions and file header

All integers are unsigned, little endian, with explicitly stated widths. Records have no alignment padding and no native-language layout. Arrays preserve encoded order. There are no floating-point fields, executable host-code fields, pointers, optional unknown sections, or trailing bytes.

| Byte offset | Width | Meaning |
| --- | --- | --- |
| 0 | 4 | `4d 43 4d 00` for MCM or `52 50 58 00` for RPX |
| 4 | 2 | Version, exactly `01 00` |
| 6 | 2 | Reserved flags, exactly zero |
| 8 | 8 | Total file length, including this 16-byte header |
| 16 | remaining | One complete model or certificate payload |

The declared file length must equal the provided byte slice length. The decoder must consume the payload exactly. Header length mismatch, truncation, extra data, nonzero reserved flags, invalid tags, and noncanonical scalars/expressions are INVALID. The result is never a partial accepted object.

Primitive types used below:

- `u8`, `u16`, `u32`, `u64`: the named unsigned widths.
- `tag(t)`: `u8=t`, then one zero `u8`, then one zero `u16` (four bytes total). All reserved bytes are checked.
- `array<T>`: a `u32` item count followed by exactly that many records of type T.
- `name`: a `u32` UTF-8 byte length followed by exactly that many bytes. Model validation additionally requires the implementation's ASCII, nonempty, no-control-character naming rules and unique variable/row names; bytes must round-trip without normalization.
- `option<T>`: a `u8` discriminator, 0 for absent or 1 followed by T. Other values are invalid.

## Exact rational and affine expression

A rational Q is encoded as:

```
tag(sign)                       // 0 positive/nonnegative, 1 negative
u32 numerator_magnitude_bytes
u32 denominator_magnitude_bytes
u8 numerator_magnitude[numerator_magnitude_bytes]
u8 denominator_magnitude[denominator_magnitude_bytes]
```

Magnitudes are unsigned little-endian integer bytes. A nonempty magnitude has a nonzero last byte. Denominator length is positive and its magnitude is nonzero. The numerator/denominator gcd must be exactly one. The only zero encoding has sign 0, numerator length 0, denominator length 1 and denominator byte `01`. Negative zero, leading zero magnitude bytes, and unreduced fractions are invalid. There are no inline special integers.

An affine expression is `Q constant`, then `array<(u32 variable_id, Q coefficient)>`. IDs must be strictly increasing and coefficients nonzero. Every model expression ID is checked against that model's variable count. Every proof expression ID is checked against its claim's actual input model during semantic validation, including expressions in branches that later prove unreachable. An expression is `constant + sum(coefficient * x[variable_id])`.

Scalar vectors (entire Q records):

```
zero: 00 00 00 00 00 00 00 00 01 00 00 00 01
one:  00 00 00 00 01 00 00 00 01 00 00 00 01 01
-1/2: 01 00 00 00 01 00 00 00 01 00 00 00 01 02
```

Replacing the final numerator/denominator of the last record with `02 04` is INVALID (unreduced). Replacing the denominator with `00` is INVALID (nonminimal/zero denominator). Setting sign 1 in the zero vector is INVALID.

## MCM payload

```
name model_name
array<Variable> variables
array<Row> rows
Expr objective
```

A Variable record is `name`, `tag(domain)`, `option<Q> lower`, `option<Q> upper`. Domain 0 means continuous, 1 means integer. There is no separate binary tag: the trusted MPS importer converts binary to integer plus the exact intersection with `[0,1]`. Omitting either effective binary bound during import would change the mathematical model and is forbidden.

A Row record is `name`, `Expr expression`, `option<Q> lower`, `option<Q> upper`. It means `lower <= expression(x) <= upper`, omitting absent sides. MPS rows are imported with zero expression constant, but the MCM schema permits affine row constants and preserves them. Equal finite bounds give an equality row. Inverted finite bounds are valid empty-domain conditions in this implementation, unlike the D0 draft's structural rejection. Rows and variables without bounds are allowed.

The objective is minimized and includes its exact constant. A maximization input is converted by negating both its coefficients and constant. Names are retained for auditing; mathematical checking uses stable IDs in encoded order. MCM decoding checks all scalars, all expressions, all names, every bound, and all model structure before returning.

## RPX payload and claims

```
array<Claim> claims
array<Block> blocks
```

There must be exactly one Block per Claim, in the same order. Each block proves only its associated directional claim. The empty arrays are decodable syntax but do not by themselves constitute a verification request or proof of a model relation.

A Claim record is:

```
u8 flags
u8 objective_relation
u16 reserved = 0
array<(u32 input_coordinate, u32 output_coordinate)> projection
option<u32> inverse_claim_index
```

Claim flags: bit 0 is reverse, bit 1 enables input integrality, bit 2 requires output integrality; all other bits must be zero. Forward uses source as input and target as output; reverse swaps them. Disabling integrality relaxes all integer coordinates while retaining their finite bounds. Objective relation is 0 NONE, 1 EQ, or 2 LE (`f_output(map(x)) <= f_input(x)`). Other relation bytes are invalid.

Each projection pair adds equality `map[output_coordinate](x) = x[input_coordinate]`. An inverse-claim reference requests composition equalities for every input coordinate. The verifier checks its index and the paired direction/domain modes and restricts inverse claims to complete affine root Return maps. One composition gives only a one-sided inverse; a bijection request needs both checked directions and both compositions.

The caller separately supplies the requested Claim array. It must exactly match the certificate claims. This prevents the certificate from weakening the request. Full model constraints and bounds are always obligations; objective NONE only removes objective obligations.

Version 1 contains no digest-only model identity shortcut. Every proof is verified against the actual complete external MCM models, whose facts supply premises and whose complete output obligations are regenerated. A reusable proof may pass on other supplied models only when those same checks establish its requested relation on the other models. Provenance hashes in inventory files are not mathematical proof authorities.

## Fact references, steps, and blocks

A fact reference is `tag(reference_kind)` plus one `u32` index, except Exact (tag 8), which has no index:

| Tag | Meaning of index |
| --- | --- |
| 0 | Input variable lower-bound LE fact |
| 1 | Input variable upper-bound LE fact |
| 2 | Input variable INT fact, available only when input integrality is enabled |
| 3 | Input row lower-side LE fact |
| 4 | Input row upper-side LE fact |
| 5 | Input equality-row EQ fact |
| 6 | Explicit local derived fact ID |
| 7 | Zero-based branch assumption index, ordered from the oldest ancestor to the current branch |
| 8 | Exact check sentinel; no index |

References are checked semantically for actual model IDs, existing sides, enabled integrality, live local definitions, and valid scope. The Exact sentinel is not an arbitrary axiom; it is available only where the semantic checker implements an exact sufficient condition.

A Block is `array<Step>` followed by exactly one End record. Step tags are independent of End and reference tags.

| Step tag | Payload after its four-byte tag |
| --- | --- |
| 0 Lin | `u32 id`, `tag(kind)`, `Q constant`, `array<(Ref premise,Q multiplier)>` |
| 1 Round | `u32 id`, `Ref le`, `Ref integer` |
| 2 Drop | `array<u32> ids` |

Lin kind tags are 0 LE, 1 EQ, 2 INT. The declared fact ID is explicit. The verifier constructs its expression from the constant and referenced facts and checks the kind's sign/integer premises. Round proves an integer-valued expression's rounded upper bound when it differs from the LE bound only by a constant. These fields carry exact operations; no certificate-supplied success bit exists.

Version 1 deliberately uses reusable local registers, unlike D0's permanent SSA IDs. A live ID cannot be overwritten. DROP must name currently live IDs; duplicate IDs in one DROP fail when the duplicate is encountered. A dropped ID may be redefined by a later checked derivation, and references after that definition denote the new fact. A reference between DROP and redefinition fails. Branches own copied local register state, so a child may drop an inherited fact only in its private copy; the sibling begins with the unchanged parent snapshot. No historical fact can become valid merely through storage reuse: redefinition always checks a fresh sound derivation. There is no continuation after a split requiring a merged register file.

| End tag | Payload after its four-byte tag |
| --- | --- |
| 0 Return | `array<Expr> map`, `array<Ref> checks` |
| 1 Split | `Expr expression`, `option<Ref> integer`, `Block left`, `Block right` |
| 2 Absurd | `Ref fact` |

Return supplies one simultaneous affine mapping for every output variable and one check for every kernel-generated obligation, in the verifier's documented deterministic order. No output variable or generated obligation may be omitted. Split with absent integer reference creates branches `e <= 0` and `-e <= 0`; with a valid INT(e) reference it creates `e <= 0` and `1-e <= 0`. Both branches are present, recursively decoded in full, and semantically checked from the same parent state. Return maps in separate leaves may differ. No branch merge or yield occurs: each leaf proves its complete directional result or closes by contradiction. Absurd requires a checked constant-positive LE or constant-nonzero EQ.

Unknown Step, End, kind, reference, option, or domain tags are invalid even if execution would not reach the record. The decoder cannot skip an unsupported extension. All recursive children are structurally decoded before any mathematical execution begins.

## Resource policy and allocation

These are implementation limits, not statements that valid larger mathematical proofs are false:

| Resource | Codec limit |
| --- | --- |
| File bytes | 1,073,741,824 (1 GiB); CLI input limit is stricter, currently 512 MiB |
| Items in one array | 10,000,000 |
| Sum of counts of all arrays | 20,000,000 |
| Name bytes during decoding | 1,048,576; model validation further limits names to 1,024 bytes |
| Numerator or denominator magnitude | 1,700 bytes (13,600 bits, fewer than 4,096 decimal digits) |
| Nested block depth | 64, counting a root block as depth 1 |

Model and execution limits may further restrict a decodable object. Every count is checked against its minimum possible remaining byte size before allocation; all vector allocations use `try_reserve`. Offsets use checked addition before slicing. Counts, scalar magnitudes and nesting are checked before the associated allocation/recursion. Big-integer arithmetic and the host runtime still make bounded internal allocations; this does not promise recovery after an operating-system forced termination.

Codec errors start with `INVALID:` or `RESOURCE_LIMIT:`. File I/O is handled by the caller, which reports IO_ERROR. Decoding successfully is not VERIFIED; only the complete semantic checker can return that status.

## Reproducible vectors and decoder tests

The empty certificate is exactly 24 bytes:

```
52 50 58 00 01 00 00 00 18 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00
```

The `codec::tests::certificate` fixture supplies all ordinary step variants, exact/fact references, a noninteger negative rational, an integer split, a nested Return, an Absurd, projection and inverse metadata. Its deterministic full binary comes from the public encoder and is round-tripped by the decoder; the scalar and empty-file vectors above also have independent byte assertions. Batch and theorem vectors are not provided as successes because version 1 implements neither; their unknown tags must fail.

Independent file vectors live in `tests/vectors/`, generated by the standard-library-only `generate_vectors.py` without calling the Rust encoder. `identity.mcm` is 117 bytes; `identity-ordinary.rpx` is a 496-byte bidirectional affine-bijection proof; `identity-nested.rpx` is an 864-byte proof containing a sign split, an integer split, and a local contradiction. `empty.mcm` and `empty-syntax.rpx` are complete decoding examples. `invalid-*` records deliberately violate the named rule; `resource-count.rpx` exceeds a count budget. `crates/core/tests/binary_vectors.rs` checks the exact files and independently requested claims.

Run the codec evidence with:

```
cargo test -p kernel-core codec:: --lib
```

Tests cover every byte truncation of model and nested proof fixtures, both with original and adjusted file-length headers, trailing data, unknown tags, reserved fields, noncanonical zero/fractions, duplicate expression terms, malicious maximum counts, depth limits, and deterministic malformed byte input. Every fixture byte is mutated to each of `00 01 7f 80 fe ff`; legal mutations may decode and must have the same canonical encoding. A further 2,048 deterministic pseudo-random payloads retain valid file headers to exercise payload decoding (seed `0x726f757465`). These bounded tests are actual executions, not a claim of exhaustive fuzzing or a formal implementation proof.
