# Independent review of the shared fact-scope candidate

Reviewed candidate:
`bench/shared-scope-prototype/crates/core/src/verify.rs`, SHA-256
`c21e14f1f4176eecddf98466fc7fc6b522d8f57495852ca8b163c892e72ad4a2`.
The generating script is `tools/prepare_scope_experiment.py`. This is the second
prototype, which charges ancestor lookup probes. The candidate is based on the
frozen V5 verifier; this review does not claim that an unreviewed later port or
V6 refutation integration has automatically been checked.

No mathematical acceptance or state-isolation defect was found in this review.
This is an implementation audit with independent executable evidence, not a
formal proof of the full verifier.

## Representation invariant

Let P be the immutable parent's visible map, L the local map and D the local
deleted-ID set. A scope's visible map is L union (P with D removed), with L taking
precedence. On every reachable state:

- D is a subset of the parent's visible IDs.
- A local ID that also exists in P is in D. This is a reused, previously dropped
  inherited register, not an illegal overwrite.
- `count` is exactly the visible-map size: `|L| + |P without D|`.

`Facts::insert` is a private low-level operation that relies on its caller.
`Context::steps` first checks absence through the full scope lookup and then checks
the configured logical live-fact limit. A future caller must retain both checks;
calling `insert` directly on an existing visible ID would violate the invariant.

Forking borrows the parent immutably, creates empty L and D, and copies only the
logical count. Inserting an absent ID adds exactly one visible binding. Removing
an inherited binding adds its ID to D; removing a local binding deletes it from L
and retains or creates D if the parent also has that ID. Therefore a drop after
reuse cannot resurrect the parent's older value. A lookup first sees a current
local value, then a deletion mask, then its parent. A mask in any ancestor remains
effective unless a descendant explicitly defines a new local value.

A failed drop leaves the state unchanged. A repeated ID in one DROP list is thus
rejected on its second occurrence. Child-local changes cannot alter the borrowed
parent. Cases checks both children in separate forks and inserts only the common
conclusion afterward. A child's use or drop of the future conclusion ID does not
change whether that ID is already live in the parent. Whole Split can safely
check its left child in a fork and then move the unchanged parent state into its
right child; no state is needed after the terminal split. Model extensions move
the same fact state into their sole child and preserve all input coordinate
prefixes, so they do not invalidate inherited fact expressions.

## Counts, depth and allocation

Logical live-fact counts matched the copied-map reference at every tested state,
including full-capacity scopes, inherited deletion and register reuse. The
unchecked arithmetic in private `insert` and `remove` is justified by those
invariants plus the caller's pre-insertion limit check: insert cannot increment
past the configured `usize` limit, and a successful lookup before remove implies
a positive count. These are caller-dependent invariants, not guarantees of those
private methods when invoked arbitrarily.

Lookup reports one probe for a local hit, two for a local miss plus deletion test,
and adds the parent's returned probes when recursing. The candidate charges those
probes at local-reference reads, overwrite checks and drops, including the extra
parent lookup needed during removal. Deterministic tests cover successful and
unsuccessful ancestor lookup, masked lookup, reused local lookup and removal.
The returned probe count is a lookup metric; it is not a count of every hash-table
operation, allocation or destructor instruction.

Scope ancestry is bounded by the existing proof nesting limit. A scope lookup
may do its bounded ancestor walk before returning the cost; DROP may reserve one
new deletion-mask entry before the caller charges that returned lookup cost.
This is bounded residual work on a failing budget check, not an unbounded search.
Both local insertion and deletion-mask growth use fallible reservation. No forced
allocation-failure experiment was performed.

`peak_live_facts` continues to mean the peak logical number of visible facts.
It is not physical allocation: immutable ancestors retain facts hidden in children,
and deletion masks occupy memory. Physical storage is bounded by actual writes,
ancestor depth, the live-fact bound and the work budget, and should be measured
separately in performance reports. The representation eliminates whole-map copying
but does not promise constant physical memory per logically live fact across all
active ancestors.

## Independent state oracle

The private candidate-only module
`bench/shared-scope-prototype/crates/core/src/scope_state_audit.rs` uses a complete
`BTreeMap` clone for each reference child. It does not reproduce parent links or
tombstone logic. Every operation compares all visible IDs, payload values, fact
kinds and logical counts. Random operations include accepted/rejected definitions,
drops, lookups, nested sibling forks, the configured live limit and extreme u32
IDs. Separate regressions cover repeated inherited drop/reuse/drop, masked-parent
reuse in a grandchild, whole-Split right ownership and 64 ancestor scopes.

Run `python3 audit/run_scope_state_audit.py`. The runner copies the candidate into
a temporary workspace, adds a test-only module hook there and runs the seven unit
tests. It verifies the candidate verifier's hash is unchanged afterward. It does
not edit production, frozen checkpoints, measured candidate `verify.rs` or its
performance metadata.

Executed result: PASS, seven tests, 128 deterministic state trees from seed base
`0x52505853434f5045`, 127,072 operations, 47,528 definition attempts, 39,541 drop
attempts, 7,486 child forks and 60,004 expected operation rejections. Total runner
time including the independent temporary build was 15.442 seconds. The exact
result, source hashes and raw test output are retained in
`audit/scope_state_audit.json` and `audit/scope_state_audit.log`.

These state tests complement the existing complete proof tests. Before adopting
the candidate, retain the existing scope/type/branch attacks and rerun real RPX
certificates unchanged, especially the previously resource-limited test18. A
different work result from eliminating real copies is expected; it does not
change the mathematical rules or make a previously failed proof a model refutation.
