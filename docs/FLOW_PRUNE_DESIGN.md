# Common-source circulation pruning: proposed V10

Status: design and isolated prototype. V9 is being integrated separately; this document does not assert a released opcode or certified test58. No existing version changes meaning.

## Actual need and chosen scope

The committed test58 reduces an undirected fixed-charge network by cancelling opposite directions, fixing bridge net flows, contracting degree-two zero-balance paths, and deleting two expensive parallel paths. Its forward contract is objective nonincrease; its reverse contract is objective equality. Every original bound, row and objective must remain bound to the actual source and target.

Merging parallel flows can exceed the common capacity of 82. A local cost comparison does not justify accepting that map. The report's valid argument uses the single source and nonnegative demands to discard circulation and route all demand within the activated support. Existing V4 FlowLift retains aggregate arc totals, including circulation, so it supplies no universal total-demand bound. V8 SignedLift handles direction selection but does not perform this pruning.

The proposed extension asserts only existence of a bounded nonnegative subflow of a supplied feasible common-source flow. It performs no connectivity search, path selection, optimization or objective inference in the verifier. All input premises and subsequent actual output obligations are checked explicitly.

## Schema and premises

Proposed endpoint: `FlowPrune { witness: FlowWitness, body: Block }`. Reuse the V4 graph schema unchanged:

- `nodes > 0`, directed `arcs[(tail,head)]`, and at least one group;
- each group has `source`, a nonempty list of `(sink, nonnegative rational demand)` commodities, one old-scope affine `flows[e]` per arc, and matching `nonnegative[e]` and `balances[v]` references;
- arbitrary loops, parallel arcs, repeated sinks, zero demands and source-equal-to-sink commodities are permitted.

For a group let `B = sum_k demand[k]` and `b[v] = sum_k demand[k]*(1[v=source] - 1[v=sink[k]])`. The premises, in this exact order, are:

1. `LE(-flows[e])` for every arc in graph order.
2. `EQ(sum_out flows[e] - sum_in flows[e] - b[v])` for every node in node order.

The original scope must prove every reference with the ordinary rules. Successful helper preparation is not evidence that these premises hold. Loops cancel from node divergence but retain their nonnegativity premise. Expressions reference only existing coordinates, including coordinates introduced by earlier proved extensions.

`B` includes demand at the source itself. This yields a harmless possibly loose bound and keeps its definition simple. Such a commodity contributes zero to every node balance and requires no path. Every addition and all intermediate affine arithmetic must pass the shared exact rational bit budget.

## Joint extension and order

Retain every original input variable, row, name and objective as exact prefixes. For each group in order append one continuous variable `g[e]` per arc, with bounds `0 <= g[e] <= B`.

Rows are appended group by group. Within each group append:

1. One equality `sum_out g[e] - sum_in g[e] = b[v]` for every node.
2. One inequality `g[e] - flows[e] <= 0` for every arc.

Groups have disjoint generated coordinates, even if old flow expressions overlap. With n nodes, m arcs and q groups the extension adds q*m variables and q*(n+m) rows. Zero arcs are allowed: balances still have to be proved and all node rows are generated. Row/variable names are fresh and carry no semantic authority. Self-loop coordinates can be zero; disconnected circulations can all be discarded.

Only after all parent premises pass may the child execute using this extended model. The input objective is preserved. Complete actual output bounds, rows, integrality, objectives, projections and V7 composition checks remain mandatory. The rule grants no integer fact for a generated flow. It is valid with continuous or integer input modes. As with every existential lift, the legacy affine `inverse` field and refutation-only endpoints reject it.

## Soundness over real input points

Fix any input point satisfying all group premises. Write F for its nonnegative arc values. Start a residual vector R=F and a kept vector g=0. Process each commodity with sink different from the source and positive demand. While it has unsatisfied amount d, select a simple positive-residual source-to-sink path and subtract the minimum of d and the path's residual arc values; add that amount to g on the path.

A path always exists. Let S be all vertices from which the unsatisfied sink is reachable through positive residual arcs. If the source were not in S, no positive residual arc could enter S. Thus its total residual divergence (out-in) would be nonnegative. But every non-source divergence is minus its outstanding demand, and the selected sink has strictly positive outstanding demand. Summing the balances over S would give a strictly negative divergence, a contradiction.

Each extraction finishes a commodity or permanently zeros at least one residual arc. There are at most m+k extractions; neither real-valued inputs nor tiny residuals cause an infinite process. The simple paths use each arc at most once. Their total extracted amount is the sum of non-source demands, at most B. Consequently every arc satisfies `0 <= g[e] <= F[e]` and `g[e] <= B`. At the end g has precisely the demanded node divergence; the remaining R has zero divergence and is discarded. Loops are never needed in a simple source-to-distinct-sink path. If every demand is zero or at the source, take g=0 immediately.

This argument gives a single jointly feasible vector for every group without changing any input coordinate. Independent groups therefore coexist. The verifier need not execute the path construction: it checks the exact old-scope hypotheses, creates only the explicitly listed consequences, and checks the entire child proof for all extended feasible points.

## Test58 construction using the extension

Derive bridge net-flow equalities by summing their actual cut balance rows. Integer rounding of actual directed capacity inequalities gives the required activation cost of each nonzero bridge; their checked sum is 205. Derive all signed flow equalities along each actual series path from internal balance rows.

Use existing interval/Cases templates to form each edge's OR activation and each series path's AND activation, proving capacity and the path cost bound against every constituent original edge. SignedLift supplies nonnegative directions for each path. Merge each dominated parallel pair's matching directions and use the OR of its activations. Check every residual node balance from the actual original balances and the proved bridge/series identities; no capacity claim is made about the merged amounts.

Apply FlowPrune to this merged nonnegative directed graph with the actual residual source and all actual nonnegative demands. Each pruned direction is at most 82. If a target activation is zero, ordinary binary Cases and the supplied subflow inequalities force the corresponding pruned direction to zero. If it is one, the new bound supplies capacity. Thus the difference of the two pruned directions satisfies both actual target signed capacity rows. The complete target balance equations and objective nonincrease are checked by the final Return.

The reverse direction uses V8 SignedLift on every retained target path, restores fixed bridges and zeroes deleted paths. Actual original capacities and all 500 original balance rows are checked; the complete objective equality includes the target's fixed OBJFIX coordinate and coefficient 205. No global pruning theorem is required for this reverse map.

## Format, budgets and validation

Reserve RPA/RPX version 10 and endpoint tag 8 only after the V9 checkpoint is frozen. The endpoint encodes the existing FlowWitness fields followed by its child block, with ordinary bounded graph/count/rational/reference decoding. Version discovery visits every block including point refutations; version <10 rejects the tag even when the implementation knows it. Unknown fields, tags and trailing bytes remain errors. Old artifacts retain identical bytes and interpretation.

The helper uses fallible reserved buffers and checked integer count arithmetic. Charge input validation/copy work, graph scanning, every scalar demand update, expanded variables/rows/terms, sparse collection/sorting and name collision attempts against the shared remaining budget. Validate the old model and every old-scope expression before generating an extension. Bound aggregate old/generated/premise terms, all graph endpoints, group/demand counts and total dimensions. Prefix copying does not imply permission to reset work, fact scope or proof depth.

Required evidence: an independent Python Fraction path-extraction oracle on directed multigraphs with loops, parallel arcs, repeated sinks, source=sink, zero demand, disconnected circulation and rational flows; full generated-model point checks and all premises; deliberate negative-flow, wrong-balance, bad-endpoint, missing-middle-ref, new-scope-ref, continuous-as-integer, malformed scalar and budget failures; sibling isolation/Drop/extension nesting and full actual-output attacks; RPA/RPX v1–9 byte compatibility; and a fixed multi-scale benchmark reporting proof/preparation size, execution and complete verification separately. An isolated prototype or successful oracle is not a substitute for the actual full test58 replay.
