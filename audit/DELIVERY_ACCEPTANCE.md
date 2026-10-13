# Delivery acceptance, 2026-10-11

The submitted **78 caller requests pass acceptance replay**. This is not yet
78 complete original-report contracts: test62 and test83 each omit a required
reported property. The corrected full-contract status is **76/81**, with existing
verified subcontracts retained. The five unfinished cases are 36,46,58,62,83.

## Executed verification

- Independent mechanical review: all78 inventory/model identities, receipt and
  artifact hashes, final verification exits/statuses, and request counts match.
  See `DELIVERY_LEDGER_REVIEW.json` and `DELIVERY_LEDGER_REVIEW.md`.
- Root independently regenerated both complete canonical models from each
  actual original MPS/LP file, assembled each full RPA, and verified each caller
  request with the submitted frozen executable. All78 regenerated MCM/RPX files
  are byte-identical; all non-timing JSON fields match the submitted cold replay.
  The 176.29-second run is an acceptance diagnostic, not a performance benchmark.
  Receipt: `validation/delivery-acceptance-2026-10-11/result.json`; reproducible
  driver: `accept_delivery_wave.py` (fixed submitted78 scope).
- The submitted cold-build receipt's Rust source and Cargo.lock hashes match
  the reviewed implementation. Its213 passing tests and78 successful executions
  are retained in `validation/wave-rpx-2026-10-11/run.json`. Root did not claim
  to rerun that build or those tests during the acceptance replay.
- Kernel identity is `694b1083e2f960aa6e9002c0ce20e796b3bcf091a3397810f30aa43f0ec9f655`.
  The641-file internal working-source snapshot is
  `checkpoints/delivery-78-working-source.json`. It is not a protocol release.

## Findings and disposition

1. **P2, test62 full-contract omission.** The actual report states that the
   complete fractional source point's retained image violates seven target
   unit clauses. Its request only checked source feasibility. No global LP
   containment is asserted by the original report, so existing Strictness must
   not be weakened to accommodate this task. Add an independently caller-bound
   point-image exclusion check and retain the original integer correspondence.
2. **P2, test83 full-contract omission.** The actual report states that no source
   optimizer can use any of61 strictly dominated columns. The submitted
   NonIncreasing/Equal maps prove minimum preservation and recovery but do not
   bind that universal optimizer exclusion. Add a strict-improvement contract
   for the positive sum of those original coordinates. The existing maps remain
   valid and retained.
3. **P3, current policy documentation.** `CURRENT_FORMAT.md` retained the old100M
   default after the approved1e9 policy change. Its table and CLI override/echo
   explanation are corrected. The previous document-review hashes describe the
   earlier document, not this amendment.
4. The earlier four P3 wave corrections are metadata reason/key amendments,
   not literally comment-only changes. Current artifacts and negative recipes
   are valid; the available records lack persisted before/after byte identities
   sufficient for an independent historical unchanged-bytes conclusion. This
   limitation does not invalidate the newly executed current-artifact replay.

No wrong kernel acceptance was found by this review. These conclusions are
evidence-based software/certificate audits, not unconditional formal correctness.
The100M→1e9 change is explicitly resource policy: `verify.rs` differs from its
pre-policy logic only in the default and explanatory comment; CLI flags forward
checked numeric budgets and echo effective limits. Accounting and obligations
were not relaxed. The larger budget is not a performance optimization.

## Continuation

Keep test46's complete existing-rule proof work separate. Combine the remaining
contract and joint-existence requirements in one next-version working draft:
strict improvement, point-image exclusion, and demand-bounded subflow. Retain
old bytes and their meanings; do not freeze one version per case. New tests and
actual complete certificates are required before any pending case is registered
as complete. Subflow construction remains explicitly trusted for its joint
existence lemma; a new builder or oracle does not remove that TCB responsibility.
