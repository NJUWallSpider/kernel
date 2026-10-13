# Independent delivery/bundle review

Scope: `tools/case_delivery.py`, `prepare_affine.refresh_acceptance` and
`tools/run_acceptance.py`, plus the actual three-direction test46 delivery.
These are evidence bookkeeping tools, outside the mathematical kernel. The
review did not modify production code or the actual acceptance ledger.

The actual test46 delivery binds all three complete requests to the same full
source and target MCM files. Every RPA/RPX/request identity, verify operand,
successful exit, status and claim count matches its direction receipt. The
ordered concatenation matches the independently preserved complete request;
the middle MI reverse direction cannot be removed even if the remaining
directions are renumbered. Cross-file inverses and supplementary point,
bijection or improvement contracts are rejected rather than silently dropped.
The separate original raw-model/canonical correspondence and new actual kernel
replay are recorded in root's `completed-46-62-83-independent.json` validation.
This review's mechanical binding result is `audit/TEST46_BUNDLE_BINDING_REVIEW.json`.

The conjunction explicitly carries `not_a_single_kernel_invocation: true` and
retains all direction results. Current cumulative statistics are summed, while
`peak_live_facts` is the maximum across sequential pieces. No aggregate elapsed
time or new one-process kernel receipt is invented. Fresh acceptance replay
iterates all three pieces; a failed middle piece prevents a successful bundle.
The test46 aggregate of 551,077,751 work and 1,105,551 obligations is therefore
three completed requests, not one kernel invocation or one resource budget.

Three bookkeeping defects were found and repaired by root during this review:

1. The original scope predicate only checked that the listed review files still
   had matching hashes. An empty list, an intact unrelated old request, or an
   incomplete request list could incorrectly mark a gate complete. It now also
   requires the exact active piece-request path set, plus the combined request
   for bundles, and requires the scope file/schema. The actual configured
   test62/test83/test46 paths were already the correct fixed paths; this finding
   does not show that those actual cases had been miscounted.
2. The single-piece fresh replay summary originally tested the returned status
   string without also testing the process exit code. A controlled reply with
   `VERIFIED` and exit 1 was reported as successful. Root changed the final
   predicate to require exit 0 and `VERIFIED`. Bundle replay and historical
   receipt binding already checked both conditions. The actual old 78 receipts
   all had exit 0; the fixture exposed a reporting edge case, not an observed
   mathematical false acceptance.
3. `python -O` removed the helper's `assert` protections and allowed a changed
   request with a stale artifact hash to pass metadata binding. Root added an
   explicit module-entry guard that rejects optimized mode. Independent tests
   confirm rejection through direct helper loading, acceptance refresh and
   fresh replay, before any fixture ledger is written. The previous helper is
   preserved as `audit/checkpoints/case_delivery-before-optimized-mode-guard.py`.
   This is a bookkeeping-runtime safeguard; the Rust kernel was unaffected.

`audit/test_delivery_bundle_review.py` builds small isolated metadata fixtures
using copied versions of the real tools. It tests missing middle directions,
changed requests with and without updated hashes, changed paths with identical
bytes, wrong source operands, nonzero exits, wrong status/count, missing RPA,
incorrect peak aggregation, cross-file inverse, scope path sets, and fresh
three-piece execution. Its deliberately fake model/proof bytes and mock process
replies are labelled bookkeeping-only and are never placed in the real cases
directory or counted as mathematical certification. The before-fix failure,
old tool copies and raw result remain under
`audit/DELIVERY_BUNDLE_FIXTURES.before_exit_fix.json` and
`audit/fixtures/delivery_bundle_review_before_exit_fix/`.

After the repairs, all 24 fixtures pass: 21 normal-interpreter scenarios plus
three optimized-mode entry-point checks. The current machine result is
`audit/DELIVERY_BUNDLE_FIXTURES.json`. The original optimized helper's acceptance
of the changed request is reproduced against its preserved snapshot in those
tests. No normal-mode existing case was found to have been miscounted.

Boundary: matching a receipt is not an independent mathematical verification.
The helper does not authenticate receipt authors, prove that RPA assembles to
RPX, or prove that the MCM is the canonicalization of the original MPS. Fresh
canonicalization/assembly/kernel replay and a semantic original-contract review
are still required. Scope gates currently cover explicitly identified cases;
absence of a gate is not new evidence that an altered request covers an
original report. The immutable reviewed request identities and fresh validation
records must remain part of delivery evidence.
