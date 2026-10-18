Publish portable bundles, audit artifacts, and verify with explicit resource budgets.

## Bundle
Proof.compile seals no unfinished scopes: finish both directions first. A single native Certificate snapshot feeds the existing RPA disassembler and RPX encoder independently. There is no production RPA-reparse pipeline. preflight and compile reuse the snapshot and exact byte counts. A Bundle contains source/target MCM, RPA, RPX, optional original target artifact and one new-schema manifest with package-relative paths and hashes.

## Publication and movement
Prepare and audit in a temporary directory before publication. Different existing contents and input aliases are rejected; identical cached contents require rechecking hashes. Move the whole bundle and reopen with Bundle.open. target_artifact bytes are copied and formulation-audited; changing or tampering with them must not pass as verified delivery.

## Chain
Chain takes ordered Bundles and checks adjacent formulations. Chain.compile copies stage packages and optional endpoint artifacts; the result is portable. Chain.verify rechecks contents and every stage. Run `python -m rpx._help.examples.workflow` for an executable moved-bundle and chain example.

## Budgets and reports
Bundle.verify and Chain.verify accept work, live_facts and depth. Each call uses its current limits and never reuses a successful report. Inspect report.status, report.kernel, report.statistics and report.artifact_audit. RESOURCE_LIMIT is not VERIFIED; increase a chosen budget and rerun only when appropriate. report.raise_for_status raises a typed error for non-success. `python -m rpx._help.examples.errors` demonstrates a failed work budget and a fresh successful verification.
