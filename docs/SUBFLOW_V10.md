# Trusted demand-bounded real subflow lemma

Introduced in historical V10; the same construction is retained in RPX 11. This document corresponds to `crates/core/src/subflow.rs` and
the SubflowLift endpoint in [FORMAT.md](FORMAT.md#constructive-witness-payloads).

Let a finite directed multigraph have n>=1 nodes and m>=0 arcs, with loops and
parallel arcs allowed. Fix source s and a finite demand list (t_i,d_i), where
t_i!=s and rational d_i>=0. Repeated sinks aggregate; an empty list is valid.
Let B=sum d_i, b_s=B and b_v=-sum_{t_i=v} d_i otherwise. Divergence means outgoing
minus incoming, so loops cancel. For every REAL f>=0 satisfying div(f)=b there
exists ONE REAL tuple g with

`div(g)=b; 0<=g_e<=f_e; g_e<=B for every arc e`.

## Constructive argument

When B=0 choose g=0. Otherwise add a new supersink t* and a demand arc t_i->t*
carrying d_i for each positive entry. The augmented flow has divergence B at s,
-B at t*, and zero elsewhere. Initialize residual R to this flow and g to zero.

While s has positive residual divergence, t* is reachable from s along positive
residual arcs. Otherwise the positive-arc reachable set U contains s, excludes t*,
and has no positive outgoing arc, so its total divergence is nonpositive. Its
specified total divergence is positive, a contradiction. Choose a simple such
path and subtract its minimum positive residual weight h. Add h to g on the
original arcs of that path.

This preserves internal divergences and decreases source/supersink residuals
equally. At least one positive arc becomes zero each time, and no residual ever
increases, so at most m+k+ paths are extracted, with k+ the positive demand-list
length. This finite termination holds for arbitrary real f, including irrational
coordinates, without an integrality or minimum-step assumption.

At termination all supersink arcs have zero residual, since the supersink has
no outgoing arcs and zero residual divergence. Consequently g has the specified
original-node divergence b. Only residual subtraction was used, so 0<=g<=f.
The extracted path weights sum to B, and a simple path uses an original arc at
most once, so every g_e<=B simultaneously. Remaining circulation is discarded.
Loops, disconnected cycles and cycles entering s need no separate assumptions.

Independent groups share the same old point and have disjoint fresh coordinates;
their constructions therefore coexist. This gives no theorem about additional
side constraints or objectives. Every actual output obligation must still be
proved for one common tuple in the child.

## Builder correspondence and scopes

Require n>=1 and at least one group. Every source/endpoint is in range. Every
demand is nonnegative and its sink differs from source, including zero demands.
The empty demand list and m=0 are supported. For each group exactly m affine
flow expressions, m nonnegative references and n balance references are required.
All flow expressions use only the pre-extension coordinates and are canonical.

The builder returns premises in group order, with m `LE(-flow[e])` in arc order,
then n `EQ(div(flow)_v-b_v)` in node order. The verifier discharges EVERY premise
in the old model and old fact/assumption scope. References to any new group
variable, any appended row, missing/surplus premises, or inaccessible facts reject.
No group can use another simultaneously added group's coordinates in its premise.

For each group append m continuous variables in arc order, bounded [0,B], and
then n equalities div(g)_v=b_v in node order followed by m inequalities
g_e-flow[e]<=0 in arc order. Each group's variable block starts at old_vars+group*m;
its row block starts at old_rows+group*(n+m). The full original variable/row
prefixes and objective are copied unchanged. New coordinates have zero objective
coefficient. Fresh names avoid collisions and confer no proof authority.

The child can use all groups' appended bounds/rows simultaneously. Its complete
actual output tuple must satisfy every actual domain, row and nonincreasing objective.
The logical inference is old model AND checked premises implies EXISTS one
extension; arbitrary new coordinates are not assumed feasible. An incorrect
builder could still break soundness. Model validation and old-scope premise checks
do not independently verify this existential theorem.

## Bounds and evidence

With G groups, output growth is G*m variables and G*(n+m) rows. For group g,
let T_g count affine flow support and m0 nonloop arcs. Its generated row support
is 2*m0+m+T_g; pre-canonical premise support is at most 3*T_g. Each divergence is
assembled sparsely then sorted/merged. Prefix validation/copying, sparse work,
demand sums, generated fields, allocations and name probes are bounded/charged
before use via shared `build_support`. Combined old/generated/premise support,
dimensions, all intermediate rational scalars and remaining shared work are
checked. Controlled vector reservations are fallible; the existing standard
library/bigint allocation limitation remains.

The production verifier does not run the path search. An independent adjacency
list construction takes at most m+k+ searches, each O(n+m+k+) graph operations;
exact rational bit cost is additional. This describes the oracle, not a runtime
claim for production construction or the complete proof.

The current builder tests are in `crates/core/tests/subflow_builder.rs`;
run `cargo test -p kernel-core --lib test_subflow_builder --locked`. They retain
983 independent exact Fraction construction fixtures and arithmetic/resource
checks. Current proof-engine and Python tests check premises and complete
output obligations; the migrated 81-case replay also exercises this rule.
Historical [test36](../cases/test36/README.md) and
[delivery](../audit/FINAL_DELIVERY_REPORT.md) records describe the earlier format
and its additional properties, not the current proof interface.

The earlier isolated candidate's identity and nine builder tests are preserved
in `audit/subflow-next/receipt.json` as historical development evidence.
The vectors include shared
arcs, loops, parallel arcs, empty/zero/repeated demands, multi-group affine
expressions, scope/name collisions, arithmetic/resource boundaries and complete
path-trace reconstruction.
The concrete regression f=(82,82,82) on arcs s->t,s->t,t->s has demand82;
merging gives (164,82), and independent clipping to (82,82) breaks divergence.
A joint subflow (82,0) satisfies every bound and balance. The lemma justifies
that joint choice; it does not authorize clipping unrelated output rows.
