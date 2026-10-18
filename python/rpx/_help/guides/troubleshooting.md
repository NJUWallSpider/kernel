Correct the concrete contract violation, then inspect and retry explicitly.

## MappingError
Cause: missing output coordinates or an unknown override name. Correction: map all output names or use default="same_name" with valid overrides. Inspect `scope.output.vars.iter(limit=20)`; next command: `python -m rpx help Scope.map`.

## CoordinateSpaceError
Cause: expressions from separate models or an escaped lift variable. Correction: rebuild expressions using handles from the intended scope.model; use generated variables only in the lift child. Next: `python -m rpx help ownership`.

## InvalidDerivationError
Cause: incorrect sign, assertion kind, exact expression or premise order. Correction: compare goal.expression with fact.expression and select a valid combination; do not negate an inequality to prove its opposite. Next: `python -m rpx help Derive.le`.

## ScopeError: stale Goal
Cause: map was called after obtaining a Goal. Correction: reacquire scope.obligations[label] and prove against the new mapping. Next: `python -m rpx help Goal`.

## ScopeError: sealed or foreign scope
Cause: modifying after finish, using a fixed split/lift parent, or mixing facts from different Proof objects. Correction: continue in the child, or build a fresh Proof and use its facts. Next: `python -m rpx help Scope`.

## UnprovedGoalError
Cause: finish still has missing witnesses. Correction: inspect scope.missing(limit=20), derive the selected exact witnesses, then retry finish. Next: `python -m rpx help Scope.prove`.

## ResourceLimitError
Cause: verification exhausted the current work/live_facts/depth budget. Correction: inspect report.statistics, select an adequate budget and verify again. A resource-limited result cannot certify anything. Next: `python -m rpx help Bundle.verify`.

## ArtifactMismatchError and KernelRejectedError
Restore the intended artifact bytes or choose a fresh publication directory; do not edit hashes to hide a mismatch. Inspect report.kernel and artifact_audit for a Kernel rejection. Next: `python -m rpx help delivery`.

## Executable corrections
Run `python -m rpx._help.examples.errors` for mapping, ownership, invalid derivation, stale-goal, sealed-scope and budget corrections, followed by VERIFIED results.
