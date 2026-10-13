# RPX/RPA 8: simultaneous activated signed decomposition

V8 adds the SignedLift existence endpoint. MCM remains V1. Earlier RPX/RPA versions
retain their mathematical meaning, bytes, request schema and Return-obligation
order. V8 has the complete V7 outer layout, including point refutation options and
the trailing bijection array. No new directional claim or scalar inference exists.

## Text schema and premises

RPA starts with `RPA 8\n`. Exact scalars remain strings; unknown fields reject.

```
SignedWitness { capacity: Q, flow: Expr, activation: Expr, checks: Ref[] }
End { "SignedLift": { decompositions: SignedWitness[], body: Block } }
```

Write C=capacity, F=flow, Z=activation. C must be a canonical nonnegative rational;
F and Z must be canonical affine expressions over the current parent model.
Exactly five references must prove, in this order:

1. LE(-Z)
2. LE(Z-1)
3. INT(Z)
4. LE(F-C*Z)
5. LE(-F-C*Z)

Every premise of every item is checked in the parent scope before any extension
row or variable becomes visible. No item may reference another item's new
coordinates. The current directional input mode must enable integers. Existing
`Exact` rules apply; generated facts cannot justify their own premises.

## Complete joint extension

For each item, append four coordinates in order p,n,u,v. Coordinates p,n are
continuous and lower bounded by zero with no finite upper bound. Coordinates u,v
are integer, each bounded [0,1]. Append four rows per item in order:

```
p - n - F = 0
u + v - Z = 0
p - C*u <= 0
n - C*v <= 0
```

Variables are ordered by item, then p,n,u,v; rows by item, then the four listed
rows. C=0 retains both capacity rows with zero coefficients omitted. The original
variables, rows and objective remain unchanged prefixes. Internal fresh names
avoid collisions and have no mathematical authority. An empty item list is an
identity extension subject to the same mode and nesting restrictions.

For any feasible parent point, the first three premises force Z in {0,1}. If Z=0,
the last two force F=0, and choose all four new values zero. If Z=1 and F>=0, choose
(p,n,u,v)=(F,0,1,0); otherwise choose (0,-F,0,1). The capacity premises give the
required upper bounds. In particular F=0,Z=1 still has u+v=1, preserving one
activation when required by the child objective. C=0 is valid. Each choice depends
only on its fixed parent point, so all items coexist in one common tuple.
Continuous coordinates keep real semantics; no integrality of F is assumed.

The child proves every actual output-model obligation under this jointly feasible
extension. The endpoint itself proves no output feasibility, projection, objective
relation, bijection or optimality claim. Original-coordinate observations retain
their original dimensions. Original affine `Claim.inverse` contracts reject this
endpoint. The V7 bijection mechanism may use SignedLift inside its reverse proof;
all compositions still execute at every Return and its separate complete paired
input-domain injectivity proof remains required. LP-fiber refutations reject this
endpoint, as they reject all existence extensions.

## Binary format

The RPX header uses u16 version 8 with existing magic, reserved fields and exact
file length. All primitives and previous tags are unchanged. SignedLift uses
endpoint tag 6, with the existing four-byte zero-reserved tag encoding:

```
SignedLift = tag(6) | array<SignedWitness> | Block(body)
SignedWitness = Q capacity | Expr flow | Expr activation | array<Ref> checks
```

The child increments combined proof depth by one. V1–V7 decoders reject endpoint
6. Version discovery traverses every branch, refutation and equality proof and
selects at least V8 if SignedLift occurs, including contradictory branches. A
later-visited V7 MenuLift cannot lower that requirement. Unknown tags, flags,
truncations, trailing bytes and excessive count/depth retain their old rejection
behavior. A witness needs at least 51 bytes before its premise entries; counts
are preflighted against remaining bytes and cumulative item budgets.

## Trusted implementation, cost and evidence

`crates/core/src/signed.rs` constructs an explicitly unchecked candidate model and
five propositions per item. `Context::run` in `verify.rs` checks each reference
against those exact propositions in the old scope, then executes the child. This
split leaves the premise formulas and joint-extension construction inside the
trusted inference implementation. There is no independent runtime proof of the
existence lemma or its implementation: old-scope premise checking, structural
model validation and the child proof do not provide that guarantee. No graph
labels, model identifiers, hashes, solver output or external code may justify
acceptance.

The builder bounds the old model, expanded variables and rows, premise counts and
combined term support before expansion. Every scalar is canonical and bounded;
intermediate C*Z products and both differences are checked before cancellation
can conceal a resource excess. It charges input copying, validation and generated
support to the shared remaining work budget and reserves controlled buffers
fallibly. The generated model is validated again. Mathematical work is linear in
copied input size and total witness support apart from exact rational arithmetic
and fresh-name collision handling. All lookups/name attempts are charged; no
unbounded search is performed. Owned model copying and standard library/internal
bigint allocation limitations remain as documented in the trust report.

Statistics add `signed_lifts`, `signed_generated_variables`, `signed_generated_rows`
and `signed_generated_terms`. `obligations` continues to count final mapped-output
obligations, not extension premises; premise checking is included in total work.
The counters are aggregated across all requested directions. Physical proof
size, mathematical generated size and executed sparse work are distinct measures.

The signed builder suite checks exact premises/rows, affine constants, zero and
large rational capacities, active zero flow, missing middle premises, coordinate
bounds, noncanonical arithmetic, intermediate overflow and budgets. The independent
Fraction generator supplies 72 signed-boundary cases and six joint batches up to
128 decompositions. Integration tests cover complete output checks, integer mode,
old scopes and dead facts, siblings, nested MenuLift, full V7 compositions,
refutation/inverse restrictions, all older-version downgrades, prefix truncation,
unknown fields, hostile counts and systematic payload mutations.

`tests/vectors/generate_vectors.py` separately writes a 673-byte `signed-v8.rpx`,
279-byte source MCM and 378-byte target MCM without invoking Rust encoding. It
includes a real signed flow, a binary gate, both capacity premises, affine
observations, nonzero objective constant, complete maps and all output checks.
The downgrade/count attack vectors are retained. Run receipts and actual-case
coverage are recorded separately; these tests are not a formal implementation
proof or evidence that the entire corpus task is complete.
