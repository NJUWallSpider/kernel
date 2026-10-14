# Mathematical semantics of the current kernel

This document explains the invariants and rule arguments of the implemented
safe Rust verifier, covering frozen RPX/RPA V1–V10 and MCM 1. The complete
contract, instruction schemas, version gates and obligation ordering are in
[FORMAT.md](FORMAT.md); the [Chinese kernel manual](rpx/rpx-manual.pdf) covers the
same implementation. Feature versions identify minimum required encodings,
not separate verifiers. Historical D0/v0.1 syntax is not an accepted ABI.

## Mathematical objects and claims

A model has real coordinates, rational affine rows, effective rational finite
bounds or missing infinite bounds, and optional integer coordinate predicates.
Contradictory bounds are legal and denote an empty set. Objectives are normalized
to minimization including their constant. The MPS dialect is in `MPS_V1.md`.
All arithmetic is rational with arbitrary precision subject to explicit resource
budgets. No floating-point residuals, solver status, or hash equality grant facts.

The caller supplies an independent Request containing ordered directional,
point, bijection and improvement contracts. Every array must equal the
certificate's declarations exactly; an empty request rejects. The legacy plain
Claim array requests only directions. Each directional claim specifies:

- `reverse`: use target as input and source as output when true.
- `input_integers` and `output_integers`: include or relax each model's integer
  predicates independently. Bounds always apply in either mode.
- `objective`: `None`, `Equal`, or `NonIncreasing` for output minus input objective.
- `projection`: input/output coordinate pairs whose values are equal.
- `affine_projection`: ordered input/output affine expressions whose values
  are equal, validated against the original directional model dimensions.
- `inverse`: optional index of an opposing claim; append equality of its affine
  map composed with this map to every input coordinate. Opposing model direction
  and domain modes must match. Both roots must be affine Return endpoints.
- `input_objective_lower`: optional lower bound on the input objective over
  this direction's declared domain.
- `input_objective_level`: optional restriction to an exact input objective
  value, using the complete actual objective including its constant.
- `input_halfspace`: optional original-coordinate affine restriction `H<=0`.

Acceptance of one claim establishes a total (possibly piecewise affine) map
from every feasible input point in its declared domain to one jointly feasible
output vector satisfying all requested relations. Unrestricted opposing Equal
claims preserve every reachable objective value and hence the extended infimum,
even for empty or unbounded sets. Unrestricted opposing NonIncreasing claims
establish equality of extended infima and equivalence of nonemptiness.
Projection equality must be requested explicitly. Mutual inverse
claims additionally establish bijection when both compositions and domain
membership are checked. None of these alone imply strict LP inclusion;
that requires the separately requested Strictness or FiberStrictness witnesses.

The verifier derives every output variable lower bound, upper bound, requested
integer predicate, every row side, objective relation, projection relation and
inverse composition obligation from the actual full models. There is no
certificate-selected subset. Equality rows generate one EQ obligation instead of
two inequalities. Return checks occur in this order: variables, rows, objective,
coordinate and affine observations, legacy inverse coordinates, opposing inverse
objective-level membership, input objective lower bound, then V7 pair compositions.
Variables and rows use model order; observations and pairs use request order.
Surplus and missing witnesses reject. Bounds cannot be silently omitted for binary
variables; the canonical model explicitly stores their effective bounds.

## Binding and trust

The inputs passed to `verify` are the actual source and target models. Model
validation checks all coordinates, rows, bounds, rational encodings, objective and
names. Model loading is never skipped. Every premise resolves against the current
input model and every output obligation uses the current output model. RPX contains
no digest that authorizes bypassing these checks. It is intentionally legal for a
proof to verify other models if it proves all requested claims on those models too.
Artifact hashes in the corpus manifest identify provenance only. They are not the
proof of mathematical identity. This semantic binding avoids trusting collision
resistance as a mathematical equality oracle.

The trusted implementation includes MPS/LP parsing, MCM/RPX/RPA/Request loading,
rational library operations, expression algebra, proof execution, complete-domain
builders and the static Plotkin and joint-existence rules. RPA authors, preparation Python,
legacy trace verifiers, audit JSON and witnesses are untrusted. RPA assembly merely
encodes a program that the kernel must check. No dynamic theorem plugin or host
callback is supported. Unknown instructions or extension tags reject.

## Facts and scalar rules

Facts are LE(e): e<=0, EQ(e): e=0, INT(e): e is an integer. Static references expose
input variable bounds, integer predicates when enabled, row sides and equalities.
Every reference is checked even when its multiplier is zero.

`Lin(id, kind, c, [(reference, multiplier),...])` computes the exact affine sum.
For LE, c<=0 and LE multipliers must be nonnegative; EQ premises have arbitrary
rational multipliers. For EQ, c=0 and all premises are EQ. For INT, c is integral,
INT multipliers are integral, and EQ premises have arbitrary rational multipliers.
Each rule is sound by addition and closure of the corresponding mathematical set.
A live fact register cannot be overwritten.

`Round(id, le, integer)` requires LE(a) and INT(z) with identical nonconstant terms.
Write a=z+d for rational constant d. Since z<=-d and z is integral, z<=floor(-d).
The result is LE(z+ceil(d)). Negative values use mathematical floor/ceil, not
truncation. The output expression is checked for canonical form and bit budgets.

`Drop(ids)` removes live facts, rejecting absent or repeated IDs. The verifier
uses mutable register names: a dropped ID may later be assigned a new fact. Every
reference resolves immediately; there are no deferred references retaining an old
meaning. Dropping an inherited fact affects only the current branch's visible state.
This differs from D0 monotonically allocated logical IDs and avoids an unbounded
historical ID index. The implementation borrows immutable parent facts, stores local
definitions and deletion masks, and charges ancestor lookup probes. Logical live
counts exclude hidden ancestor facts; physical storage also includes those retained
ancestors and masks. See `audit/SHARED_SCOPE_REVIEW.md` for the representation invariant.

At a proposition check, a witness must match the required expression exactly. An EQ fact can
also satisfy LE or INT of the identical expression because zero is nonpositive and
integral. `Exact` discharges a checker-supplied proposition: EQ requires identically zero, LE a
constant <=0, INT an integral constant plus integral coefficients on input variables
whose integer predicates are enabled. It works for Return, lift premises,
derivation witnesses, injectivity and improvement checks, but cannot be read
as an ordinary fact by Lin, Round, EqPair, Split/Cases integer operands,
Plotkin or Absurd.

`EqPair` derives EQ(e) from exactly opposite LE(e) and LE(-e).
`Cases` checks one requested proposition in two isolated exhaustive local
derivations, each ending in its matching witness or a checked contradiction.
Only that common proposition is exported to the parent; no output map is merged.
`Plotkin` is a static trusted binary-code bound with checked integer domains,
labels and close-pair clique coverage; its formula and full premises are in
[FORMAT.md](FORMAT.md#plotkin).

## Control and joint mapping invariant

A block consists of sequential scalar steps and one endpoint. No fallthrough or
post-Split continuation exists. A Return supplies a complete output vector at once;
all output obligations refer to that same vector.

`Split(e,None,L,R)` checks both subtrees under e<=0 and -e<=0. These closed halfspaces
cover every real point; overlap at zero is harmless. `Split(e,Some(INT witness),L,R)`
first proves e integer, then checks e<=0 and 1-e<=0. The two integer cases are exhaustive.
Assumption references index the current root-to-leaf stack. Each child receives
an isolated view of the same parent live registers. A completed left branch never grants a
fact to the right. All branches must complete, with complete mappings and obligations
or an exact contradiction. There is no unsound union of branch obligations.

`Absurd(fact)` closes a domain only when a checked LE is a strictly positive constant,
or a checked EQ is a nonzero constant. All preceding instructions remain checked.
Both subtrees are decoded and executed even when the source model is infeasible;
there is no unreachable-byte escape from format or extension validation.

Induction on instructions establishes every live fact under the current assumptions.
The split cover property then lifts valid leaf maps to total piecewise maps. A chosen
branch's Return provides simultaneous outputs, so incompatible local existential
witnesses cannot be assembled. Mutual affine inverse obligations imply injectivity
and surjectivity on the two feasible sets once both directions' feasibility is proved.

### Joint extensions

FlowLift, IntervalLift, MenuLift, SignedLift and SubflowLift append jointly
satisfiable coordinates and laws after checking every premise in the old
input/fact/assumption scope. They retain the entire original model prefix and
objective. Their laws are child-local and cannot prove their own premises or
leak to siblings. The child must still prove every actual output obligation
using one complete tuple.

Each extension's existence lemma and its Rust builder are trusted inference
code. Checking premises and the complete output does not independently prove
that lemma. The constructive arguments are in [Flow](FLOW_V4.md),
[Interval](INTERVAL_V5.md), [Menu](MENU_V7.md),
[SignedLift](FORMAT.md#signedlift) and [Subflow](SUBFLOW_V10.md).
Flow/Interval/Subflow generate continuous variables in either input mode.
Menu/Signed require integer input mode, including empty families. No rule
grants extra output side constraints or objectives from a structural audit.

### Restricted domains and inverse closure

Objective-level and halfspace restrictions intersect the complete actual input
domain; they never replace its bounds or rows. The kernel appends the actual
objective equality first, then the halfspace inequality, when present. An empty
intersection makes a direction vacuous and proves neither attainment nor
optimality. A restricted input lower bound is conditional; a global bound
requires an unrestricted direction.

When a legacy opposing inverse has an objective level, the current map must
also prove that its image belongs to that level. Composition alone is
insufficient. Legacy inverse rejects a halfspace on either direction. V7 pairs
and indexed Strictness/FiberStrictness reject either restriction. Actual-model
point witnesses and improvements do not inherit directional restrictions.

### Complete bijections and points

A V7 pair binds a verified root-affine forward map F and an opposing verified
total reverse construction G. Every reverse Return proves F(G(t))=t on all
coordinates. A fresh paired domain copies the entire forward input twice and
imposes F(x)=F(x'). Ordinary scalar rules must prove x=x' on every coordinate,
including unobserved continuous ones. Injectivity plus the right inverse proves
a full bijection. Menu-local uniqueness or mutual feasible maps alone do not.
See [MENU_V7.md](MENU_V7.md#complete-bijection-contract).

Feasible points check every actual coordinate, bound, row and requested objective.
V3 Strictness requires a previously verified unrestricted LP inclusion with a
complete coordinate permutation and a feasible output separator.
V6 FiberStrictness instead fixes all requested coordinate/affine observations
of a feasible output point in the entire actual input LP and proves that fiber
empty in fresh state. It requires neither injective observations nor equal
dimensions. Its refutation ignores integer declarations and permits only
Split/Absurd endpoints with ordinary scalar/Cases steps.
V10 ImageExclusion checks a feasible actual LP point whose complete caller-bound
affine image violates the other actual LP; it does not prove global inclusion.
See [points](POINT_V3.md), [fibers](FIBER_POINT_V6.md) and
[the complete point contract](FORMAT.md#complete-point-witnesses).

### Strict improvements

A V10 improvement proves that every feasible point with caller-bound P(x)>0
has a complete feasible point y in the same actual model with f(y)<f(x).
The proof uses the weak root assumption P>=0, then either a checked positive
decrease margin at ImproveReturn or a PositiveRefutation proving P<=0.
Consequently every attained minimizer has P<=0. This asserts neither existence
nor value of a minimum. Full margin rules, scope and obligations are in
[FORMAT.md](FORMAT.md#strict-improvements).

These are mathematical rule arguments and implementation invariants, not a formal
verification of Rust, dependencies, compiler, allocator or operating system.

## Implemented limits and errors

See [FORMAT.md](FORMAT.md#resource-policies-reports-and-trust-boundary) for decoder limits and `MPS_V1.md` for importer limits. Execution
has a one billion work-unit default, one million live registers, and bounded branch
depth. The `verify` CLI accepts `--work <u64>` and `--live-facts <usize>` anywhere
after the subcommand to override these budgets; depth is not configurable.
Verification JSON echoes the effective budgets in `limits` (including failures
after valid argument parsing). Resource limits are implementation policy, not
changes to rational semantics.
A legal input beyond a resource budget is RESOURCE_LIMIT, never a successful result.
The CLI distinguishes VERIFIED (exit0), INVALID (exit2), RESOURCE_LIMIT (exit3), and
IO_ERROR (exit4). INVALID concerns an input or proof; it does not refute the claimed
model relation. Canonicalization and assembly have distinct non-verification statuses.

The operating system can kill the process; no structured reply is promised after
that. Some standard-library/dependency allocations are infallible; bounded input
and work limits reduce exposure but do not constitute complete recoverable-OOM
coverage. This remains an audit limitation.


## Physical fact storage and resource accounting

Each nested proof scope borrows its parent's immutable fact state. Lookup checks
local definitions first, then a local deletion mask, then ancestors. DROP hides an
inherited ID only in that child. Reusing a dropped ID creates a local definition;
dropping it again leaves the inherited value masked. The logical count tracks
currently visible IDs, including inherited facts, and governs the live-fact limit.
Sibling and parent scopes cannot observe child writes or deletion masks.

The verifier charges ancestor lookup probes, fact expression visits, duplicate-ID
checks and drops. Forking a child charges constant work because it does not copy
parent facts. This changes the implementation's resource consumption, not any
RPX version's mathematical interpretation. Logical `peak_live_facts` is not a
measurement of physical ancestor, hash-table, mask or decoded-proof storage. RSS
is measured independently. Scope depth remains bounded by the execution limit.
See `audit/SHARED_SCOPE_REVIEW.md` and `bench/SHARED_SCOPE_REPORT.md` for independent
state tests, implementation assumptions and controlled measurements.
