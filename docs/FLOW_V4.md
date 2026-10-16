# Joint common-source flow extension

`crates/core/src/flow.rs` prepares the graph premises and model extension used by
the `FlowLift` terminator. The proof engine must prove all of those premises
in the current input context before using the extension. The helper's result is
deliberately named `UncheckedFlowExtension`; calling it is not verification.
The binary/text version, terminal encoding and proof-engine integration are
specified in [FORMAT.md](FORMAT.md#constructive-witness-payloads). The constructive soundness argument
and current builder behavior are documented here.

## Data and exact premises

`FlowWitness { nodes, arcs, groups }` describes a directed multigraph with nodes
numbered from zero and ordered pairs `(tail,head)`. At least one node and group
are required. Every group has:

- a common `source` node;
- a nonempty ordered vector `commodities` of `(sink,demand)`, with rational demand
  greater than or equal to zero;
- one canonical affine `flows` expression F[e] over the current input variables
  for each arc;
- one `nonnegative` fact reference for each arc and one `balances` fact reference
  for each node.

All dimensions, endpoints, expressions and rational scalars are checked. Arcs
may be parallel or self-loops. Different groups may use overlapping affine
input expressions: each has its own disjoint new coordinates, so their
independent extensions coexist without changing any input value.

For each group the helper emits the following premises, in order:

1. Every arc: `LE(-F[e])` with its corresponding `nonnegative` reference.
2. Every node v: `EQ(sum_out F[e] - sum_in F[e] - b[v])` with its corresponding
   `balances` reference, where b[v] is total group demand originating at v minus
   total group demand terminating at v.

The checker must prove every premise, including a zero expression or a balance
that is redundant in the input model. The helper merely carries references
through; an invalid, absent or wrongly typed reference does not acquire any
authority from successful preparation. Each affine expression is formed by
appending sparse contributions and canonicalizing once, rather than repeatedly
merging a growing expression. Self-loop contributions cancel before insertion.

## Extension layout

Let N and R denote the number of input variables and rows on entry to this
terminator. The original variable/row vectors, model name and affine objective
are preserved exactly as prefixes. Generated names are fresh even if the input
already contains the internal naming prefix. Names do not determine proof IDs.

Append variables in group, commodity, arc order. All generated variables z[k,e]
are continuous with lower bound zero and no upper bound. If a group begins at
variable offset S and contains m arcs, the coordinate for commodity k and arc e
is `S + k*m + e`.

Append rows group by group. Within a group, first append one equality for every
commodity and node in that order:

`sum_out z[k,e] - sum_in z[k,e] = d[k]*(1[v=source]-1[v=sink[k]])`.

Then append one arc-total equality per arc:

`sum_k z[k,e] - F[e] = 0`.

The arc row contains the negated affine constant of F in its expression and
zero bounds. Commodity row expressions have zero constant and the displayed
right-hand side as both bounds. Thus a group with k commodities, m arcs and n
nodes adds k*m variables and k*n+m rows. Empty arc sets add no variables but
still add every commodity-node equality. Loops have no balance coefficient but
retain their own nonnegativity premise, generated coordinate and arc-total row.

## Why one joint extension exists

Fix any actual real-valued input point satisfying the checked premises. In a
group, start with residual arc values F and zero commodity flows. Process
commodities in order. A zero demand or a source equal to its sink requires no
path. Otherwise, find a simple positive-residual source-to-sink path by breadth
first traversal in witness arc order. Subtract the minimum of the remaining
commodity demand and residual values on that path, and add the same amount to
this commodity's path coordinates.

To see that a path exists, use divergence `out-in`. Let S be the vertices from
which the still-unsatisfied sink is reachable using positive residual arcs.
If the source were outside S, no positive arc could enter S. Its total
divergence would therefore be nonnegative. Yet every non-source residual
divergence is a nonpositive outstanding sink demand and the selected sink's is
strictly negative, a contradiction. Each subtraction changes divergence only
at its two endpoints, maintaining this invariant even when a path passes
through other sinks or several commodities have the same sink.

Every extraction either completes a commodity or permanently makes a residual
arc zero. There are at most m+k extractions; this finite argument does not
depend on rationality, a denominator bound or a numeric tolerance. At completion,
all residual divergences vanish. Add the entire remaining circulation to the
first commodity, which exists. This retains loops, disconnected cycles and all
arc totals. A first commodity with zero demand or source equal to sink can
receive this circulation because its required divergence is zero.

All generated coordinates are consequently nonnegative and satisfy every
generated row simultaneously. This is an existence-preserving extension of the
same input point. The child proof must then establish the complete actual output
model from the extension. It may not infer additional per-commodity capacities,
integrality or objectives from the theorem. Those remain ordinary obligations.
In particular, heterogeneous commodity costs are acceptable only if the actual
nonincreasing objective is independently proved by the child. The rule
does not claim an affine inverse or a bijection of original and grouped flow
vectors.

For integer-domain requests, only declared integer input coordinates carry
integer facts; generated flows remain continuous. No theorem-specific integer
mode bypasses that rule. The child cannot obtain `VarInt` for a new flow.

The production verifier checks premises and generates the extension laws; it
does not execute the path decomposition on input points. The construction proves
the trusted existence lemma and is executed independently by the test oracle.

## Resources and scope

Checked count arithmetic bounds the expanded model by the shared maximum
variables and rows, bounds premise count by `MAX_ROWS`, and conservatively bounds
the combined input, generated and uncanonicalized premise terms by `MAX_TERMS`.
Every demand sum, affine constant update and canonical coefficient sum is checked
against the shared rational bit limit. An excessive temporary value is a resource
error even if later terms could cancel it.

Controlled vectors, strings and name tables use fallible reservation. Preparation
charges input validation/copy work, graph and demand scans, generated dimensions,
coefficient storage/work and canonical sorting against the remaining request
budget before the corresponding large allocation or operation. The initial
storage charge is conservative: 32 units per generated variable or row, four
per generated/premise coefficient and four per premise, followed by sorting and
name-collision charges. Statistics distinguish work, generated variables,
generated rows and actual generated model coefficients. This work count is a
bounded deterministic metric, not a hardware-independent instruction count or
bit-complexity claim.

The proof engine transfers the current live facts into the child and retains
its current assumptions; it does not copy that fact set at this terminator.
Any branch copies remain subject to the ordinary branch work budget.
It checks all premises in the pre-extension scope; extension laws
are visible only to the child. Existing assumptions remain statements about
the unchanged input prefix. Siblings do not receive generated variables, rows
or local facts. A shared block-depth limit bounds nested extensions.

## Independent construction evidence

`audit/generate_flow_oracle.py` implements the finite construction independently
using Python `fractions.Fraction`, with no solver or Rust imports. Seed
1179406167 produces 97 cases containing 186 groups, including varied dimensions,
sources, demands, self-loops, parallel arcs, zero demands, source-equals-sink
commodities and circulation. An additional explicit case has zero arcs. The
generator checks every resulting commodity balance and every arc total and
records the full coordinate vectors in `tests/vectors/flow_oracle.json`.

`crates/core/tests/flow_builder.rs` evaluates every generated premise on those
independent aggregate points and checks every generated model bound and row on
the full common lifted vector. Additional attacks cover malformed endpoints,
missing/malformed premises, negative/noncanonical demands, scope-invalid affine
variables, work/dimension/large-intermediate limits and internal-name collisions.
These are supplementary to full proof-engine integration attacks.

Reproduce the fixture with `python3 audit/generate_flow_oracle.py` and run the
builder suite with `cargo test -p kernel-core --lib test_flow_builder`. As elsewhere,
executable tests and the mathematical rule argument do not constitute a machine
checked proof of the Rust implementation.

## Actual common-source aggregation

[test28](../cases/test28/README.md) applies this rule to 47 continuous commodities
on a 19-node, 50-arc graph, aggregated into 14 common-source groups. Its complete
historical two-direction contract preserves all 150 integer capacity coordinates and every
attainable objective value for each assignment. It does not claim a bijection of
the continuous flow vectors. The reverse extension adds 2,350 continuous flow
coordinates and 1,593 equalities; the ordinary child proof checks every actual
source bound, domain, row, objective and observation. The case record and
[delivery report](../audit/FINAL_DELIVERY_REPORT.md) locate the replay evidence.

The current migrated certificate checks only complete MI optimization equivalence; historical additional property checks are not part of RPX 11.
