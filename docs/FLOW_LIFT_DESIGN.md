# Proposed joint flow lift (not implemented or accepted yet)

This proposal is driven by actual test28. It is not a certificate, a V3 feature,
or a functional-coverage claim. A future RPX version must distinguish its bytes.

## Semantic operation

`End::FlowLift { witness, body }` proves a total constructive extension of the
current input point, then checks the complete requested output model with the
existing proof engine. It does not approve an output model by recognizing names
or a structural digest. Existing input coordinates and objective remain unchanged.
The current input may be restricted by already-checked branch assumptions.

Witness contains a finite directed multigraph (`nodes`, ordered `(tail,head)`
`arcs`) and one or more independent groups. Each group has one common source,
a nonempty list of `(sink, demand)` commodities with exact rational demand >=0,
one affine aggregate-flow expression per arc, one nonnegativity reference per
arc, and one conservation reference per node. All indices, dimensions, rational
sizes, expressions, and every reference are checked. Self loops and parallel arcs
are allowed and must be represented exactly. Empty arc sets are allowed only
when their explicitly checked conservation facts establish consistency.

Premises for each group, on the current input domain:

- `LE(-F_e)` for every arc e.
- `EQ(sum_out F_e - sum_in F_e - b_v)` for every node v, where
  `b_v = sum_k d_k * (1[v=source] - 1[v=sink_k])`.

Premises use the ordinary exact fact checker, allowing a tautological Exact
reference or an equal expression already proved by core rules. Every node is
checked, including a dropped/redundant balance row reconstructed by linear rules.
No external model scanner is trusted.

On success append simultaneously all continuous variables z[k,e]>=0 and laws:

- every commodity/node conservation `sum_out z[k,e] - sum_in z[k,e]
  = d_k*(1[v=source]-1[v=sink_k])`;
- every arc total `sum_k z[k,e] = F_e`.

New variables are ordered group, commodity, arc, after all current input variables.
New rows are ordered group, commodity-node balances, then arc totals, after all
current input rows. Appended row RHSs and expressions are constructed by the
kernel, never supplied as unchecked theorem conclusions. The witness schema
must document these indices so the untrusted RPA author can reference them.

The child body checks every actual target bound, row, requested integrality,
objective, and projection using the extended input. Old facts and branch
assumptions remain valid, and no extension fact can escape to a sibling.
An affine inverse claim is incompatible with this terminator and must reject.
The extension never implies integrality of new flows. It supports real flows
with rational model data, not only rational feasible points.

## Deterministic common construction and soundness

For each group start with residual flow F and zero commodity flows. Process
commodities in witness order. For a commodity with source != sink and positive
remaining demand, find a positive-residual simple path from source to that sink,
using graph traversal with arcs in witness order. Subtract the smaller of its
remaining demand and the minimum residual arc value along the path, adding this
amount to this commodity on every path arc. Every extraction either permanently
zeros an arc or finishes a commodity. Thus at most |E|+|K| extractions occur.
Source==sink or zero demand requires no path.

A needed path always exists. Let S be the vertices from which the selected sink
is reachable via positive residual arcs. If the source were outside S, no positive
arc could enter S, so the sum of residual divergences over S would be nonnegative.
But all non-source residual divergences are nonpositive and the unfinished sink
has a strict negative divergence, a contradiction. Residual balances are maintained
by each path subtraction. This argument works over real nonnegative flows.

After all nontrivial demands are met, residual flow has zero divergence at every
node. Add this entire residual circulation to the first commodity (which exists
by the nonempty requirement). This preserves its balances and makes all arc sums
exactly equal F. In particular cycles, self loops, and disconnected circulation
are retained. All groups use disjoint new coordinates; their extensions coexist
in one output point. Existing coupling constraints through shared arc totals and
retained variables remain separately checked by the complete child proof.

This is an explicit deterministic finite construction, not a call to a solver
or unbounded search. Production checks the structural premises and runs the
ordinary proof body; a test-only independent Fraction implementation must execute
this construction on generated cases and actual-model points.

## Resource and trust requirements

The trusted additions are graph/premise binding and generation of the jointly
satisfiable extension laws. Use checked products for group/commodity/arc/node
counts, resource budgets before allocation, fallible reservations, exact rational
intermediate checks, and a bounded nesting depth shared with other blocks. Charge
premise visits, graph scans, generated terms, and full copied model/fact work;
report physical bytes and generated-variable/row counts separately. This first
implementation may clone the input model; any later sharing optimization must
preserve the same checks and use an equal-task benchmark.

Required attacks include a missing middle arc or node, wrong source/sink/demand,
negative demand, absent nonnegativity, continuous flow falsely declared integral,
wrong arc sum, a per-commodity extra upper bound, unequal commodity objective
costs, omitted output constraints, branch-scope leakage, dimensions/counts and
version tags. Generic renaming/permutation and path/cycle/disconnected components
must be exercised. Actual test28 must pass its full two directions and preserve
all 150 integer decisions and every attainable objective value.
