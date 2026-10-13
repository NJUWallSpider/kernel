# RPX/RPA implementation version 1

This document describes the implemented safe Rust verifier's V1 baseline.
The [Chinese kernel manual](rpx-manual.pdf) now covers the current implementation.
Binary version 1 and textual `RPA 1` remain distinct from the historical,
unimplemented D0/v0.1 design; no D0 ABI compatibility is claimed.

## Mathematical objects and claims

A model has real coordinates, rational affine rows, effective rational finite
bounds or missing infinite bounds, and optional integer coordinate predicates.
Contradictory bounds are legal and denote an empty set. Objectives are normalized
to minimization including their constant. The MPS dialect is in `MPS_V1.md`.
All arithmetic is rational with arbitrary precision subject to explicit resource
budgets. No floating-point residuals, solver status, or hash equality grant facts.

The caller supplies the complete requested claim list independently of the RPX.
It must equal the certificate's list exactly. Each claim specifies:

- `reverse`: use target as input and source as output when true.
- `input_integers` and `output_integers`: include or relax each model's integer
  predicates independently. Bounds always apply in either mode.
- `objective`: `None`, `Equal`, or `NonIncreasing` for output minus input objective.
- `projection`: input/output coordinate pairs whose values are equal.
- `inverse`: optional index of an opposing claim; append equality of its affine
  map composed with this map to every input coordinate. Opposing model direction
  and domain modes must match. Both blocks must end with an affine Return.

Acceptance of one claim establishes a total (possibly piecewise affine) map
from every feasible input point to one jointly feasible output vector satisfying
all requested relations. Opposing Equal claims preserve every reachable objective
value and hence the extended infimum, even for empty or unbounded sets. Opposing
NonIncreasing claims establish equality of extended infima and equivalence of
nonemptiness. Projection equality must be requested explicitly. Mutual inverse
claims additionally establish bijection. None of these imply strict LP inclusion;
strictness requires separate exact witness verification, not currently implemented.

The verifier derives every output variable lower bound, upper bound, requested
integer predicate, every row side, objective relation, projection relation and
inverse composition obligation from the actual full models. There is no
certificate-selected subset. Equality rows generate one EQ obligation instead of
two inequalities. Return checks occur in precisely that order, with variables and
rows in model order, then projections in request order, then inverse coordinates.
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

The trusted implementation includes MPS parsing, MCM/RPX loading, rational library
operations, expression algebra and proof execution. RPA authors, preparation Python,
legacy trace verifiers, audit JSON and witnesses are untrusted. RPA assembly merely
encodes a program that the kernel must check. No theorem plugin or host callback is
supported in V1. Unknown instructions or extension tags reject.

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

`Drop(ids)` removes live facts, rejecting absent or repeated IDs. V1 intentionally
uses mutable register names: a dropped ID may later be assigned a new fact. Every
reference resolves immediately; there are no deferred references retaining an old
meaning. Dropping an inherited fact affects only the current branch's visible state.
This differs from D0 monotonically allocated logical IDs and avoids an unbounded
historical ID index. The implementation borrows immutable parent facts, stores local
definitions and deletion masks, and charges ancestor lookup probes. Logical live
counts exclude hidden ancestor facts; physical storage also includes those retained
ancestors and masks. See `audit/SHARED_SCOPE_REVIEW.md` for the representation invariant.

At Return, a witness must match the required expression exactly. An EQ fact can
also satisfy LE or INT of the identical expression because zero is nonpositive and
integral. `Exact` is only a terminal witness: EQ requires identically zero, LE a
constant <=0, INT an integral constant plus integral coefficients on input variables
whose integer predicates are enabled. It is not a general premise or solver.

## Control and joint mapping invariant

A block consists of linear/round/drop steps and one terminal. No fallthrough or
post-merge code exists in V1. A Return supplies a complete output vector at once;
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

These are mathematical rule arguments and implementation invariants, not a formal
verification of Rust, dependencies, compiler, allocator or operating system.

## Implemented limits and errors

See `FORMAT_V1.md` for decoder limits and `MPS_V1.md` for importer limits. Execution
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
