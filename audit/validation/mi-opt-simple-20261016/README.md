# RPX 11: fixed MILP optimization equivalence

The certificate is now exactly `Certificate { forward: Block, reverse: Block }`. Each direction uses the entire actual MI input domain, proves a complete output tuple feasible, and proves objective nonincrease. The two independent scopes share a work budget. The kernel exposes no weaker certification target.

Removed production machinery: Claim/Contract property selection, LP modes, projection equalities, inverse and bijection checks, point/fiber/image separation, objective-level and halfspace root restrictions, standalone improvements, and their compiler planning paths. Scalar derivation, exhaustive branching, contradictions, Plotkin, and the five joint construction rules remain. Python authors the two directions directly. Verification accepts exactly two complete models and one proof file.

RPX/RPA 11 deliberately rejects versions 1–10. MCM 1 remains unchanged. Migration uses an external legacy decoder, extracts unrestricted MI objective-nonincreasing/equal directions, removes only the trailing auxiliary Return obligations, and requires complete re-verification. It does not rename weaker claims as optimization equivalence. All 81 cases migrated from 83 historical proof files to 81 new certificates; original proofs and receipts are unchanged. Each `cases/test*/optimization.json` binds the new proof and complete models. Generated binary certificates and intermediate migration JSON follow existing artifact/target ignore rules.

## Verification evidence

- [validation.json](validation.json): 81 bound case receipts, artifact hashes, current source hashes, kernel identities and test totals. All new proofs pass; the paired comparison also re-executed all 81 under both implementations.
- [rust-tests.log](rust-tests.log): 148 tests pass, including independent exact construction/arithmetic oracles, scope-state audits, adversarial semantic checks, Plotkin enumeration, resource/codec tests and mandatory two-direction checks.
- [python-tests.log](python-tests.log): 141 tests pass. [tools-tests.log](tools-tests.log): 13 pass.
- [manual-final.json](manual-final.json): three examples, 42 CLI operations, 12 negative checks, RPA/RPA-S byte roundtrips.
- [delivery.json](delivery.json): test36, test46 and test58 re-imported from their original files, proof bytes regenerated through text, complete MI_OPT checks passed.
- [docs-check.log](docs-check.log): current Markdown local links pass.
- [retired-tests.json](retired-tests.json): SHA-256 and disposition of removed legacy harnesses. Retained mathematical tests were ported; old optional-property and V1–V10 wire fixtures no longer exercise the current interface. Test counts do not establish equivalent coverage or formal correctness.

The first delivery replay hit the 512 MiB text-path limit when pretty RPA for test36 expanded beyond it; [the original failure](delivery-initial-resource-limit.json) is retained. The review tool now strips the RPA header and insignificant pretty-print indentation and uses the existing bounded Certificate JSON compiler for oversized text. The kernel's verification limits and mathematical conditions were not relaxed. The subsequent complete replay passes and reproduces identical proof bytes.

## Paired descriptive measurement

[comparison.json](comparison.json) records one fresh process per implementation per case, with alternating before/after order. Both versions certify MI_OPT on the same complete model pairs. MCM import and proof generation are excluded; the host was not exclusive. These are single-pass observations, not statistical runtime claims.

| Aggregate metric | Previous implementation | Two-tree RPX 11 | Change |
| --- | ---: | ---: | ---: |
| Proof bytes | 2,906,200,909 | 2,057,328,689 | -29.2% |
| Charged work | 2,281,011,027 | 1,644,377,506 | -27.9% |
| Kernel execution seconds | 119.020 | 83.056 | -30.2% |
| Process wall seconds | 141.098 | 101.270 | -28.2% |
| Maximum per-process RSS bytes | 2,189,295,616 | 2,212,184,064 | +1.0% |

The changes remove proof content and its verification, rather than isolating interpreter dispatch overhead. They do not establish a memory improvement or a universal speedup. The measured two-tree binary precedes the final removal of a dead version helper and fixed-size CLI argument storage; both binary identities are retained. No mathematical rule changes followed measurement.

The paper and Chinese manual were rewritten for this scope, compiled, checked for unresolved references/overflow, and selected rendered pages visually inspected. Historical experiments remain explicitly labeled as historical and were not rerun as fresh-authoring studies. `paper/` remains ignored by the user's existing Git rules; local sources/PDFs were updated without changing those rules.

The guarantee includes constructive mathematical optimal-solution recovery. A generic solver-facing numerical recovery executor is not implemented. The Rust implementation and its trusted lift lemmas are not mechanically verified.
