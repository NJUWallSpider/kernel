# Capability proposal notes

**Proposal only: not implemented, not frozen, and no kernel or format change made.**
The version numbers below are tentative design allocations, not supported headers.

Baseline: [SEMANTICS_V1.md](../docs/SEMANTICS_V1.md) requires complete tuples and independent claims.
Both proposals follow the [TRUST_REPORT.md](TRUST_REPORT.md#corpus-completion-status-and-required-next-work) checklist.
[FORMAT_V9_DRAFT.md](../docs/FORMAT_V9_DRAFT.md) restricts to a supplied level; it does not identify an optimum.

## A. Caller-bound strict-improvement exclusion

Evidence: [test36 receipt](../cases/test36/preparation.json), including its 18-line
`schema_gap_sketch`, [strong request](../cases/test36/attempts/strong_request.json),
and the [positive-terminal witness](../cases/test36/attempts/positive_terminal.rpa).
The existing API rejects `all_source_optimizer_coordinates_zero`; a feasible
positive-terminal point at objective 6426 rules out an unconditional zero-fixing.
[test83 receipt](../cases/test83/preparation.json) certifies primary NonIncreasing/Equal maps,
not its ancillary all-optimizer exclusion. Test36's committed full contract requires
that exclusion and remains blocked; test83's completed contract does not certify it.

### 1. Exact universal statement
For the complete actual source integer-feasible set S and normalized minimized objective f,
independently request P. Acceptance means `forall x in S: P(x) => exists y in S: f(y)<f(x)`.
Every attained global source optimizer therefore avoids P, without assuming nonemptiness,
attainment, boundedness, or a known optimum. P may describe terminal positivity or a
noncanonical lift, but its meaning must be caller-encoded, not inferred from an audit label.
Minimum preservation between source and target remains a separate mapping claim.

### 2. Witness schema and counts
Propose separate `ExclusionClaim {input: Source, input_integers: true, condition: DNF}`
requests, matched exactly. DNF is ordered clauses of atoms `{relation: Le|Eq|Gt, expr}`;
Expr uses canonical rational constant/sparse original-coordinate terms. Gt(e) means e>0.
Empty DNF is false; an empty clause is true. Bound clauses, atoms, support and bit sizes.
Provide exactly one root per clause. Eq/Le atoms become ordinary facts; Gt atoms yield
weak `LE(-e)` facts plus separately tracked strictly-positive atom identifiers.
New `ImproveReturn` supplies a complete source-dimensional map and all domain checks,
`margin: Constant(Q>0)|PositiveAtom(atom_index, scale: Q>0)`, and an exact witness for
`LE(f(y)-f(x)+margin)`. Atom margins are scale*e(x); the atom must be this root's Gt atom.
`PositiveRefutation(atom_index, ref)` closes an impossible strict domain only by
proving LE(e) for that Gt atom; ordinary checked Absurd handles weak contradictions.
This sufficient interface does not promise certificates for every true strict-improvement
statement; it introduces no unchecked arbitrary positivity assertion.

### 3. Complete model-occurrence checks
Validate all predicate indices against original dimensions and match the entire caller
predicate, including every requested terminal coordinate. Copy the complete actual source
domain, never selected rows. Check every actual source bound, integer predicate and row
side for y. Derive f(x), f(y) and constants from the actual objective, not a surrogate.
These generated obligations cover every occurrence of changed coordinates; terminal/chain
interpretations grant no exemption. The target receives complete checks in separate maps.
Unknown fields, missing checks and surplus witnesses reject.

### 4. One coherent reconstructed tuple
Every ImproveReturn defines all coordinates of one y simultaneously, possibly
using jointly existing coordinates from already justified lifts. Separate improving
witnesses for separate rows cannot be combined. Every output Split leaf provides a
complete tuple or a checked refutation; Cases still exports only ordinary facts.
Strict atom identifiers belong to their exclusion root and cannot leak to siblings,
other claims or ordinary Returns. Existing affine-inverse restrictions remain.

### 5. Soundness and builder/kernel division
Every x satisfying P satisfies a clause. Prove one complete feasible y there and
`f(y)-f(x)<=-h(x)` with checked h(x)>0; x cannot minimize f. Proving on a strict clause's
weak closure is sufficient but stronger than required. Refutation combines e>0 and e<=0.
For test36, the untrusted builder supplies normalization branches and affine savings for
noncanonical lifts. A canonical active-terminal branch must prove the 7283 lower bound
and fully check the 6425 source witness before using constant margin 858.
Those numbers are proposed proof obligations, not accepted bounds in this note.
For test83, a checked replacement tuple and positive savings on deleted integer columns
supply the atom margin. The kernel checks condition binding, generated obligations,
strict-margin semantics and existing inference. No new trusted chain-AND theorem,
normalization algorithm or Python-audit authority is proposed.

### 6. Resources and charging
For C clauses, A atoms, predicate support T and complete model size M, domain preparation
is O(C*M+A+T) if copying each root; proof work is additional. Charge all inspected/copied
model entries, predicate terms, generated facts, strict-atom lookups, substitutions and
existing fact/ancestor probes. Roots share the request-wide 100M budget, not per-clause
budgets. Preflight checked counts/support and fallible reservations; retain rational,
live-fact, depth and byte limits. RESOURCE_LIMIT is not acceptance or a wall-clock bound.

### 7. Versioned encoding
Tentative RPX/RPA 10: append a counted ExclusionClaim array and corresponding roots;
allocate distinct new endpoint tags for ImproveReturn and PositiveRefutation.
Use existing u32 counts/indices, canonical Q/Expr/Ref encodings and strict JSON.
Any such record requires the new header, including vacuous or refuted conditions.
Older headers reject new fields/tags. Ordinary Claim/Return/PointClaim and V9 levels
retain their exact meanings; MCM remains 1 and old canonical bytes remain unchanged.
Final tag numbers and the relationship to unfrozen V9 require independent review.

### 8. Positive, negative and generalization tests
Positive: integer strict dominance; continuous savings arbitrarily close to zero;
constant-margin replacement; overlapping clauses; empty source/condition; complete
test36 normalization plus terminal exclusion and separately checked target maps.
Negative/regression: strong_request.json remains INVALID under old versions;
positive_terminal.rpa remains feasible, so unconditional zero-fixing must reject.
Reject a weak-only margin, zero/negative scale, wrong predicate/atom/source mode,
missing clause, changed objective constant, missing output row/integrality, mixed
tuples, sibling atom leakage, and strict equality-boundary false acceptance.
Generalize by coordinate/row permutation, nonzero objective offsets, rational
rescaling, tied optimizers, nonattained infima and unbounded models. Independently
enumerate small integer domains and exact rational boundary examples. Test all
truncations, unknown tags, downgrades, count overflow and shared work/depth limits.

### 9. Explicit non-claims
No optimum value, attainment, LP exclusion, all-point equality/bijection, unrestricted
source zero-fixing, automatic predicate discovery, or general strict theorem solver.
Exclusion alone does not certify the test36 target transformation or update acceptance.

## B. Joint demand-bounded subflow lift

Evidence: canonical [test58 BLOCKED receipt](../cases/test58/preparation.json),
[blocker](../cases/test58/attempts/blocker.json), [local merge attempt](../cases/test58/attempts/local_merge_attempt.rpa),
and [circulation fixture](../cases/test58/attempts/circulation_counterexample.json).
[FORMAT_V4.md](../docs/FORMAT_V4.md) preserves arc totals by retaining residual circulation.
It cannot be reinterpreted as cycle removal; the blocker does not claim fundamental ISA impossibility.

### 1. Exact universal statement
For any finite directed multigraph (loops allowed), source s, demands d_v>=0 at
nodes v!=s and B=sum d_v, every real nonnegative arc flow f with divergence B at s
and -d_v elsewhere admits one real tuple g with the identical node divergences and
`0<=g_e<=f_e` and `g_e<=B` for every arc. Zero B and disconnected circulations are
included. This is existence of a subflow, not a bound on the original f.

### 2. Witness schema and counts
Propose `DemandSubflowLift {witness, body}` with witness `{nodes: u32, arcs:
[(tail,head)], groups: [{source: u32, demands: [(sink,Q)], flows: Expr[],
nonnegative: Ref[], balances: Ref[]}]}`. Sinks differ from their group's source;
repeated sinks aggregate exactly, zero demands are legal, and an empty demand list
means B=0. There is at least one group and node; empty arc lists are legal.
For each group require exactly m flows/nonnegative refs and n balance refs.
Compute B and all node demands in the kernel; do not accept a supplied total.
Generate exactly m continuous g coordinates, n balance equalities and m coupling
inequalities `g_e-f_e<=0`, with variable bounds [0,B]; preflight all expanded counts.

### 3. Complete model-occurrence checks
Validate endpoints, scalars, coordinates and counts. Construct LE(-f_e) for every arc and
EQ(div_v(f)-b_v) for every node, including isolated vertices and loop cancellation;
prove all in the old scope first. The graph is a proposal, not authority to select rows.
Copy every actual old domain, row and objective unchanged. Complete child-map obligations
cover every actual output occurrence, including activation costs and non-network coupling;
no selected network-row whitelist may bypass any of them.

### 4. One coherent reconstructed tuple
All g coordinates jointly satisfy their complete balance/coupling system. Groups have
disjoint new coordinates and coexist. Old coordinates/objective prefixes are unchanged;
new objective coefficients are zero and names/indices are kernel-generated. Every Return
uses the same tuple for all output obligations; separate per-arc interval choices are forbidden.

### 5. Soundness and builder/kernel division
Append a supersink and arcs v->supersink of flow d_v. Extract positive simple
source-to-supersink paths, transferring the minimum residual arc flow along each;
a reachable-set divergence argument guarantees a path while demand remains.
Each extraction zeros an arc, so at most m+number_of_demand_arcs transfers suffice.
Retain only extracted path flow on original arcs and discard residual circulation.
Balances are unchanged; subtraction ensures g<=f; each simple path uses each arc
at most once, and all extracted path weights sum B, hence g_e<=B simultaneously.
When B=0 choose g=0. Loops and disconnected cycles are harmless and can disappear.
The untrusted generator discovers representations and supplies ordinary premises
and the child proof. The trusted extension builder constructs the laws, and the
kernel checks all premises and complete output obligations. No runtime path search
or cycle cancellation is required for verification; an independent exact oracle
executes the construction for tests. Do not reuse V4's residual-preserving conclusion.

### 6. Resources and charging
For G groups and incidence/flow support T, generated size is O(G*(n+m)+T). Preflight
checked counts and fallible reservations; charge prefix copying/validation, all node/arc/
demand/term visits, accumulation/sorts, bounds/rows, name probes, premises and child work.
All share request-wide work/depth limits. An oracle may cost O((m+k)*(n+m+k)); it is not
uncharged verifier work. Rational/decoder bounds remain, not a hard memory/time guarantee.

### 7. Versioned encoding
Tentative RPX/RPA 11 adds a distinct DemandSubflowLift End tag, with counted arrays
and the existing exact Q/Expr/Ref/Block encodings. Gate it on the new version even
if its body uses only older rules. Keep MCM 1, all old End tags and V4 FlowLift laws
unchanged; unknown tags, older-header payloads and unsupported fields must reject.
Depth increases by one child level. Numerical tag allocation remains review work.

### 8. Positive, negative and generalization tests
The two-node/three-arc fixture has f=(82,82,82), balances (82,-82), and valid
subflow g=(82,0,0). Its naive merged tuple (164,82) must still fail the 82 cap;
(82,0) is the positive bounded reconstruction seed. Independent clipping to
(82,82) violates the merged balance and must reject. Preserve the old local-merge
obligation-1372 failure as a negative regression, not a refutation of existence.
Add loops, disconnected cycles, source-entering circulation, parallel arcs, multiple
sinks, zero demands/B/arcs, fractional real flows and independently checked batches.
Reject missing middle node/arc premises, wrong incidence/demand/total, negative f,
unequal balances, output g>f, incompatible per-row witnesses, hidden output coupling,
false integer output, objective increases, stale/sibling refs and unchecked premises.
Use exact path-decomposition oracles on permuted/scaled graphs plus independently
encoded vectors, systematic mutations/truncations and work/depth/count boundaries.

### 9. Explicit non-claims
No f_e<=B assertion, equality g=f, preservation of circulation, independent clipping,
integer-flow output, multi-source generalization, optimizer computation, arbitrary
flow-side-constraint preservation, LP equality or all-point bijection. The theorem
alone does not certify test58: the complete forward map and objective relation still
need proofs, together with its separately requested reverse direction.
