# RPX / RPA 4: joint common-source flow lifting

Version 4 adds `End::FlowLift`, a terminal operation that proves a simultaneous extension of the current input point by nonnegative commodity flows, then checks a child proof against the entire actual output model. Existing V1–V3 records and contracts keep their meanings; MCM stays version 1. The new operation needs a V4 header even when its child uses only earlier instructions. It is not a structural whitelist for a particular model, and no output constraint is accepted merely because it resembles a network.

The motivating actual case is `test28`. Its target groups commodities having the same source. Reverse lifting must reconstruct all commodity flows jointly and retain all aggregate circulation, including disconnected cycles. Independent existential values for each output row would not establish a feasible output tuple. `FlowLift` provides one common extension domain with checked coupling equations; the ordinary Return checker still verifies every actual output variable bound, row, required integrality, objective and projection.

## Witness schema and premises

```
FlowWitness = { "nodes": u32, "arcs": [[u32 tail,u32 head]],
                "groups": FlowGroup[] }
FlowGroup = { "source": u32, "commodities": [[u32 sink,exact-scalar-string demand]],
              "flows": Expr[], "nonnegative": Ref[], "balances": Ref[] }
End = prior variants
    | { "FlowLift": { "witness": FlowWitness, "body": Block } }
```

The graph has at least one node; its arc list is ordered and may contain self-loops and parallel arcs. Every endpoint, group source and commodity sink must be a valid node. There is at least one group, and each group has at least one commodity. All demands are exact, canonical, nonnegative rationals. Zero demand and source equal to sink are allowed. Groups may use the same nodes and old expressions, but their appended coordinates are disjoint.

For a group with common source `s`, ordered commodities `(t_k,d_k)`, and one canonical current-input expression `F_e` for every arc, the checker constructs the following obligations. The witness must supply one nonnegative reference per arc and one balance reference per node, with no missing or extra entries:

- Every arc: `LE(-F_e)`.
- Every node `v`: `EQ(sum_{e:tail=v} F_e - sum_{e:head=v} F_e - b_v)`, where `b_v = sum_k d_k*(1[v=s]-1[v=t_k])`.

Self-loops cancel exactly from divergence, but remain in nonnegativity and total-flow premises and conclusions. The source and sink contribution of a source-equals-sink commodity cancels. All scalar intermediates and canonical expression dimensions are checked. Ref/Exact use ordinary exact fact matching in the current proof scope, so equality facts may justify matching LE facts as usual. A reference to a row or variable that this lift would create is invalid at this stage. Every premise must pass before the child can use any extension law.

## Simultaneous extension and ordering

For each group and each commodity/arc pair, append a fresh continuous variable `z[k,e]` with lower bound zero and no upper bound. Old variables, rows, domain flags and objective remain unchanged at their existing indices. New variables are ordered by group, then commodity, then arc. If the old variable count is `V`, the first group starts at `V`; following groups start after all prior groups' `commodity_count * arc_count` variables.

For each group, append rows in this order:

1. Commodity-major, node-minor conservation: `sum_out z[k,e] - sum_in z[k,e] = d_k*(1[v=s]-1[v=t_k])`. Every node appears, including redundant zero balances.
2. Arc-major totals: `sum_k z[k,e] - F_e = 0`.

Then continue with the next group's rows. All rows are equality rows with equal finite lower and upper values. Conservation rows store zero expression constant and the signed demand on both bounds. Arc-total rows store `-F_e.constant` in the expression, old terms negated, appended `+1` commodity coefficients, and zero bounds. New names are deterministic collision-free internal names and confer no mathematical authority.

The child executes against this extended input model using the same requested claim, actual output model, live facts and path assumptions. Prior facts remain valid because their coordinates and rows are unchanged. The child has no continuation back in the pre-extension scope. A sibling of an enclosing Split gets its own original state and cannot see these rows/variables. A nested FlowLift may build on earlier jointly introduced coordinates after proving its own current-scope premises.

Each Return still supplies one affine tuple covering every actual output variable. The output tuple may now depend on the jointly existing flow coordinates. The accepted direction therefore proves a total existence relation with the stated objective/projection properties; it is not necessarily an affine map of the original input alone. Requested projections are validated against the original input dimensions before execution, preventing appended witness coordinates from enlarging the requested observation. The preserved input objective is used for objective equality, nonincrease and V3 lower bounds. New flow variables are continuous even when original input integrality is enabled. Any integrality required by an actual output variable still needs an ordinary exact proof.

V1 affine inverse claims require both root endpoints to be Return and consequently reject FlowLift or a Split containing it. The extension does not silently reinterpret an affine inverse claim as an existential relation.

## Mathematical construction

Fix any real input point satisfying the current model and branch assumptions. All checked `F_e` are nonnegative and have the checked aggregate divergences. For each group, initialize residual flow to `F` and all commodity flows to zero. Process commodities in witness order. Skip zero demand and source-equals-sink commodities. Otherwise repeatedly choose a simple positive-residual path from the common source to this sink, with deterministic arc-order graph traversal, and transfer the minimum of the remaining commodity demand and the residual values on its path.

A required path always exists. Let `S` contain all vertices from which the unfinished sink is reachable along positive residual arcs. If the source were outside `S`, no positive arc could enter `S` (such a predecessor could also reach the sink). Thus the sum of residual divergences in `S` is nonnegative. But all non-source residual divergences are nonpositive, and the unfinished sink has strictly negative divergence, a contradiction. This cut argument applies to real flow values and maintained residual demands, including several commodities sharing a sink.

Each transfer either finishes the current commodity or permanently zeros at least one positive residual arc. With `m` arcs and `k` commodities, at most `m+k` transfers are needed. After all nontrivial demands are met, the residual has zero divergence at every node. Add the entire residual circulation to the group's first commodity, which exists by the checked nonempty premise. This preserves its balances and makes every arc total exactly equal to `F_e`. It retains self-loops, disconnected cycles, and circulation through source or sink, including the all-zero-demand case.

The resulting commodity tuple is nonnegative and satisfies all appended laws simultaneously. Different groups use disjoint new coordinates, so their extensions coexist. Therefore every old feasible input point has at least one extended point, and every extended point retains the old input constraints. A child proof valid for all such extended points supplies a valid actual output for each old input. Contradiction in a child is sound only if the original current domain was empty, because the extension premises guarantee joint existence.

The production checker validates this finite theorem's premises and constructs its algebraic extension laws; it does not execute the point-dependent path algorithm, invoke a solver, discover a graph, or run arbitrary code from the certificate. The deterministic construction defines the actual mathematical mapping and is executed independently by the test oracle. There is no claim that LP flow coordinates become integer or that this theorem covers groups with different sources inside one group.

## Binary encoding and versioning

The RPX header version is `04 00`. Earlier End tags 0 Return, 1 Split and 2 Absurd are unchanged. The new End record is:

```
tag(3)
u32 nodes
array<(u32 tail,u32 head)> arcs
array<FlowGroup> groups
Block body
```

Each FlowGroup encodes, in order:

```
u32 source
array<(u32 sink,Q demand)> commodities
array<Expr> flows
array<Ref> nonnegative
array<Ref> balances
```

The shared `tag`, Q, Expr, Ref and array encodings remain unchanged. V4 includes the V3 Claim optional objective-lower field and trailing point array, even when absent/empty. All V1–V3 decoders reject End tag 3; unknown tags reject in every version. A FlowLift child increments the same root-at-one depth counter as a Split or Cases child. The maximum codec depth remains 64. Decoder counts, field lengths, reserved bytes, canonical rationals and expression ordering are checked across the complete body before execution.

RPA 4 uses exact header `RPA 4\n`, strict JSON and the schema above. Source/sink/arc indices are JSON unsigned integers, while demands are exact scalar strings. Existing proof syntax and lexical scope rules remain unchanged. The assembler cannot accept a V4 endpoint under an older header.

## Trusted code, resources and evidence

`proof.rs` defines the witness; `codec.rs` and `rpa.rs` implement the independent wire/text schema. `flow::prepare_unchecked_extension` checks structural dimensions/scalars and returns an explicitly **unchecked** candidate extended model, required premises and resource statistics. This helper is not an acceptance entry point. `verify.rs` checks every returned premise against the original current scope before entering `body` with the extended input. All actual model obligations remain in the existing Return checker.

The helper preflights graph counts, expanded variable/row counts, total existing/generated/premise support and work using checked sums/products before controlled allocations. It validates and copies the complete old model. Sparse incidence lists and one canonicalization per node avoid repeated whole-expression merges. All new equality-row indices and coefficients are kernel-generated. Fallible reservations are used for explicitly controlled vectors, maps and strings; dependency BigInt allocations and ordinary cloned facts retain the documented allocator limitations. Generation work, final sparse sorts and name-collision probes are charged; ordinary premise checking and child execution consume the same request-wide remaining budget. `flow_generated_variables`, `flow_generated_rows` and `flow_generated_terms` report generated structure separately from file size and `work`.

The integration suite `crates/core/tests/flow_lift.rs` covers a complete simultaneous extension with a demanded path, a sink self-loop and disconnected circulation, complete target constraints/objective, attempts to use new facts before proving premises, missing middle arc/node premises, changed source/demand, negative or absent commodity demand, wrong target objective, extra target upper bound, false integer output, omitted constraints, original-coordinate projection bounds, sibling isolation, inverse rejection, version downgrade, truncation, mutation and shared work/depth limits. The six integration tests were executed successfully, including a nested-lift test that preserves earlier extension coordinates. The six builder tests independently evaluate 97 exact construction cases with 186 groups, as documented in [FLOW_V4.md](FLOW_V4.md); actual corpus acceptance is defined by full-model replay receipts, not merely these synthetic tests.

`tests/vectors/generate_vectors.py` supplies a separate Python byte writer for a source-binary-variable/self-loop extension with one new continuous output variable and exact total-flow row. The 226-byte target MCM and 292-byte RPX were generated and the Rust tests decode them, verify the full requested map, and reject the V3-header downgrade. As with earlier versions, bounded testing and this rule proof are evidence, not a formal verification of the Rust implementation or arithmetic dependencies.

The full actual test28 replay passed on V4: two claims, 5,666 terminal obligations,
2,350 generated variables, 1,593 generated rows, 459,185 physical RPX bytes and
399,856 charged work units. All four targeted corruptions (missing node premise,
wrong demand, missing nonnegativity, and lost output-flow mapping) were rejected.
`cases/test28/preparation.json` records the reproduction and measured timing;
these counts do not imply coverage of all other flow-family instances.
