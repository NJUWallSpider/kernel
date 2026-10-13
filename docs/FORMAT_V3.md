# RPX / RPA 3: Plotkin bounds, objective bounds, and points

Version 3 adds one checked combinatorial inference, a directional objective-lower-bound contract, and exact supplementary point witnesses. MCM remains version 1. Existing RPX 1 and 2 bytes retain their original field layouts and meaning; their absent new fields decode to `None` and empty arrays. Version 1 rejects local Cases/EqPair, and both earlier versions reject Plotkin. The encoder emits the lowest required version after inspecting all nested blocks and local derivations. It emits version 3 if any Plotkin, non-null objective lower bound, or point witness occurs. A newer-version input may use only earlier features; re-encoding may then select an earlier version.

The actual motivation is `test71`: a Hamming-distance packing formulation adds a cardinality cut. Its requested relation combines equality of integer feasible sets, strict strengthening of the LP relaxation, and a certified optimum. A solver-reported objective cannot prove those statements. Generic local branching would have to reason over many binary coordinates. The new theorem checks explicit finite incidence data and arithmetic, while complete source/target obligations still bind the resulting fact to the actual models.

## Plotkin inference

```
Plotkin { id:u32, bits:u32, distance:u32,
          variables: [(u32 coordinate,u64 label)], cliques:[Ref] }
```

The instruction requires `1 <= bits <= 64`, `1 <= distance <= 64`, and `2*distance > bits`. Input integrality must be enabled. Selected coordinates must be distinct actual input variables, declared integer, with finite declared lower bounds at least zero and upper bounds at most one. Contradictory bounds are legal and simply make the underlying feasible set empty. Labels must fit in `bits` bits; duplicate labels are allowed only if their distance-zero pair passes the same coverage rule.

Every supplied clique reference must resolve in the current scope to a checked LE fact with exact expression `sum_{i in C} x_i - 1`. Every coefficient must equal one, including coefficients of coordinates outside the selected list. Every coordinate in such a clique must have a declared nonnegative lower bound. The latter requirement prevents an unselected negative coordinate from hiding two selected ones. Repeated clique references and empty cliques are allowed; they add no unjustified coverage. EQ or INT references are not implicitly treated as clique facts, though a prior checked Lin can explicitly convert EQ to LE.

For every distinct selected pair whose labels have Hamming distance less than `distance`, the checker requires at least one supplied checked clique containing both coordinates. It builds exact membership bitsets and checks their intersections; hashes, model names, row names, parity conventions, or expected instance sizes cannot establish coverage. Reordering the variables, rows or references and changing labels by a common XOR mask preserves the statement when all premises still hold.

The output is one fresh live LE fact:

```
sum(selected coordinates) - floor(2*distance / (2*distance-bits)) <= 0.
```

It follows the existing live-register, DROP, branch and local-Cases rules. It constructs no output mapping or auxiliary coordinate. It may use parent or branch-local checked clique facts and is therefore scoped to the current path. No incomplete subset of output-model obligations is discharged by the instruction itself.

### Proof

Fix any point satisfying the current model and path assumptions. Selected coordinates are binary. Let `k` be the number equal to one. A checked at-most-one clique prevents any selected close pair from both being one. Therefore the `k` corresponding labels have pairwise distance at least `d = distance`.

For bit position `h`, let `a_h` of these labels have bit one. Double-counting differences across unordered pairs gives

```
d*k*(k-1)/2 <= sum_h a_h*(k-a_h) <= bits*k*k/4.
```

The second inequality follows from `(a_h-k/2)^2 >= 0`. If `k > 0`, rearrangement gives `(2*d-bits)*k <= 2*d`; the denominator is positive by the checked premise. Since `k` is integral, `k <= floor(2*d/(2*d-bits))`. For `k=0` the conclusion also holds. Bounds on labels and all close-pair coverage, rather than any external code-family theorem, establish the premises. This argument applies to labels with repetition because simultaneous selected duplicate labels are excluded by the distance-zero coverage check.

### Cost and limits

For `n` selected variables, `r` clique references, and `s` total terms in their checked expressions, the algorithm performs `O(n + s + n^2*ceil(r/64))` operations in the worst case and uses `O(n*ceil(r/64) + n)` auxiliary words. Actual intersection scans stop at the first shared clique. A no-close-pair instance does not scan membership intersections. The exact pair count is charged before allocation or quadratic execution; every initialized membership word, variable scan, clique support scan, reference lookup and examined intersection word is charged against the request work budget. Pair-count and matrix-size arithmetic uses checked multiplication/addition. Membership allocation has an additional limit of 8,000,000 `u64` cells (64,000,000 payload bytes), checked before `try_reserve_exact`. Input/output vectors and other model, codec and fact limits also apply. Sorting the final canonical support and ordinary exact-arithmetic implementation overhead are not a hard real-time guarantee.

No unconstrained search, optimization, clique discovery or external solver runs in this checker. The certificate supplies candidate labels and clique references; all acceptance-relevant premises are checked against actual facts.

## Additional requested contracts

A Claim may contain `"input_objective_lower":"-12"` (an exact scalar string) or null/absent. After all ordinary output obligations, objective relation, projection obligations, and inverse-composition obligations, every Return must additionally prove

```
LE(input_objective_lower - actual input objective).
```

The input objective includes its constant and canonical minimization sign. The claim refers to this direction's input model and integrality mode, so reversing direction changes which model is bounded. A full contradiction endpoint remains vacuously valid for an empty input domain. The scalar is validated even before block execution. A claimed lower bound alone does not imply attainment; an exact feasible point with the corresponding objective supplies that separate evidence.

The V3 caller request is an object:

```
Request = { "claims": Claim[], "points": PointClaim[] }
PointClaim = { "Feasible": { "target": bool, "integers": bool,
                            "objective": null | exact-scalar-string } }
           | { "Strictness": { "inclusion_claim": u32 } }
PointWitness = { "claim": PointClaim, "values": exact-scalar-string[] }
Certificate = { "claims": Claim[], "blocks": Block[], "points": PointWitness[] }
```

The points arrays default to empty for legacy compatibility. The CLI also accepts the legacy plain array of Claim as a request with no points. The request is separately supplied by the caller. Every declared mapping claim and point claim must exactly match the request in order; a certificate cannot silently weaken an objective or omit a requested witness. `verify_request` allows a request containing only points, but rejects a completely empty request. The legacy `verify(..., &[Claim], ...)` entry point rejects certificates containing unrequested points.

All mapping claims are proved before point checking. `Feasible` checks the complete named model, all finite bounds, row sides and requested integrality, and optionally its exact objective value. `Strictness` refers to an already-proved LP-to-LP inclusion with a projection that bijectively covers every coordinate on both sides. Its point must satisfy the entire inclusion-output LP, while the corresponding input-coordinate tuple violates at least one actual input bound or row. Thus it proves strictness of that already-proved inclusion under the fixed coordinate permutation. It does not prove strictness for arbitrary partial projections or arbitrary affine inverse maps. Details, resource rules and independent point tests are specified in [POINT_V3.md](POINT_V3.md).

## Binary layout

All integers are little-endian. The common header is unchanged except the RPX version at offsets 4–5 is `03 00`. Existing tags 0–4 retain their documented payloads. All `tag(t)` records remain one byte `t` followed by three zero reserved bytes; every reserved bit/byte is checked. `array<T>` remains a `u32` count followed by elements, and `option<Q>` is one byte 0 or one byte 1 followed by canonical Q.

| Record | V3 encoding |
| --- | --- |
| Claim | Exact V1 Claim payload, then `option<Q> input_objective_lower` after `option<u32> inverse` |
| Step tag 5, Plotkin | `u32 id`, `u32 bits`, `u32 distance`, `array<(u32 coordinate,u64 label)> variables`, `array<Ref> cliques` |
| Certificate | `array<Claim>`, `array<Block>`, then `array<PointWitness> points` |
| PointClaim tag 0, Feasible | `u8 flags` (bit 0 target, bit 1 integers, other bits zero), three zero reserved bytes, `option<Q> objective` |
| PointClaim tag 1, Strictness | `u32 inclusion_claim` |
| PointWitness | `PointClaim`, then `array<Q> values` |

PointClaim begins with its own `tag(0)` or `tag(1)` before the listed payload. Point tags are a separate namespace from steps and block ends. Unknown point/step tags, invalid optional tags, reserved data, truncated payloads, surplus bytes and excessive counts reject even when earlier blocks end in contradictions. Claims/blocks must have equal counts. MCM headers continue to reject versions 2 and 3. The V1/V2 certificate layout contains neither the Claim's new option byte nor a points count at the end.

RPA 3 is the exact header `RPA 3\n` followed by strict JSON using the schemas above and the previous Expr/Ref/Step/Block definitions. Plotkin is the externally tagged variant `{"Plotkin":{...}}`. Every rational scalar is a string parsed exactly; JSON floats are not a rational encoding. RPA 1/2 reject every feature requiring V3, including a Plotkin nested in a local Cases child. The assembler discovers required versions across all branches without executing proof search.

## Implementation and executed evidence

`proof.rs` defines the data types, `rpa.rs` the exact scalar JSON/request parsing, `codec.rs` the independent field-by-field binary codec, `verify.rs::Context::plotkin` the theorem and final objective bound, and `point.rs` complete point evaluation. The point checker receives only the work budget remaining after all mapping claims; its consumed work and coefficient visits are added to the request statistics. `plotkin_pairs` counts all considered selected pairs, including those requiring no clique intersection.

The ten tests in `crates/core/tests/plotkin.rs` were executed. They include an independent exhaustive subset oracle for every binary assignment in five small distance models (up to 16 coordinates), valid label/reference permutations, all domain/parameter/pair/clique-premise attacks, nonnegative and negative padding coordinates, live/dead local references, exact requested objective bounds, Plotkin nested in Cases, full-width `u64` labels, empty selections, work exhaustion, request resource-error classification, every adjusted-header truncation, and four mutations at each payload byte of a small certificate. Existing V1/V2 file bytes round-trip unchanged.

`tests/vectors/generate_vectors.py` independently writes `identity-plotkin-v3.rpx` (279 bytes), including Plotkin, a global objective lower bound and exact feasible objective point, plus `invalid-v3-step-v2.rpx` and `invalid-v3-point-tag.rpx`. Rust independently decodes and verifies the positive file against a caller-constructed request, and rejects the two malformed vectors for their documented rules. The point suite adds independent Fraction oracle coverage described in POINT_V3.md. Actual test71 artifacts and receipts are maintained in `cases/test71/`; their successful replay, rather than this rule definition alone, establishes corpus coverage.

During V3 hardening, the generic accumulator gained a check on the temporary constant product before addition. A large product could previously cancel back into the supported bit range; all arithmetic was exact, so this was resource-policy consistency rather than a false mathematical acceptance. An explicit public-API regression now requires RESOURCE_LIMIT. Prior performance snapshots are retained unchanged.
