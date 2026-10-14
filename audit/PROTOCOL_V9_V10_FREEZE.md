# V9/V10 protocol freeze — 2026-10-14

**Decision: V9 and V10 are frozen**, following the project owner's explicit
request on 2026-10-14. MCM remains version 1; all RPX/RPA versions 1–10 are now
frozen, with V10 the highest. The implemented bytes, feature gates and mathematical
acceptance conditions are retained. Incompatible changes require a new version.

[docs/FORMAT.md](../docs/FORMAT.md) replaces all ten FORMAT increment documents
and the duplicate CURRENT_FORMAT reference. Each primitive, contract, record,
rule, endpoint, JSON schema and resource table is defined once. The constructive
[Subflow lemma](../docs/SUBFLOW_V10.md) and other mathematical arguments remain
separate supporting explanations. The [Chinese manual](../docs/rpx-manual.pdf)
and current repository/case references have been synchronized.

The baseline starts from Git `1468f95` (manual refresh and repository cleanup).
Production Rust changes in this freeze are comments only; every non-comment
line in the three touched source files equals that baseline. No codec, proof
checker, builder or arithmetic behavior was changed to obtain the freeze.
The two preparer status descriptions now identify the frozen protocol.

## Fresh validation

The [machine-readable freeze manifest](validation/protocol-v9-v10-freeze-2026-10-14/freeze.json)
binds the source files, Cargo.lock, executable, unified specification, subflow
argument, PDF and validation reports by SHA-256. The independent build directory
is `target/validation-protocol-v9-v10-freeze-2026-10-14`.

- Fresh locked test/build: **280 tests passed, zero failed**, across 35 test-result
  suites including empty CLI/doc suites.
- [Complete actual-model replay](validation/protocol-v9-v10-freeze-2026-10-14/run.json):
  **81/81 cases, 83/83 successful verify calls**. Test46's three pieces remain
  independent complete requests. Replayed case IDs equal the current acceptance ledger.
- [Manual examples](validation/protocol-v9-v10-freeze-2026-10-14/manual-examples.json):
  three complete examples, **39 CLI checks**, including nine INVALID mutations,
  three RESOURCE_LIMIT checks and canonical byte round-trips.
- [Unified FORMAT example](validation/protocol-v9-v10-freeze-2026-10-14/format-example.json):
  the printed complete identity certificate was canonicalized, assembled and verified.
- Manual rebuilt with `make -B -C docs`: **65 pages**, no overfull or unresolved-reference
  warnings; title, status pages and revised appendix visually inspected.

Reproduce the tests/build/replay with `python3 tools/run_acceptance.py --label
<fresh-label>`, then run `tools/check_rpx_manual.py` with that label's release
executable. A fresh label preserves these receipts. The replay collector's
`functional_delivery_complete:false` records that replay alone is not a scope
review; the unchanged [acceptance ledger](acceptance.json) and
[final delivery report](FINAL_DELIVERY_REPORT.md) establish the complete 81-case
original-contract scope. The freeze does not reinterpret that collector field.

## Compatibility and historical evidence

The prior [78-request byte/non-timing compatibility review](validation/v10-complete-old-78-compatibility.json)
remains intact. The full current Rust suite includes independent byte vectors,
version downgrades, prefix truncations, strict request binding, scope/domain
restrictions, exact arithmetic and resource attacks. The fresh replay consumes
existing proof/model/request bytes, rather than replacing old artifacts with
newly weakened requests.

Three specifications pinned by the original delivery manifest were preserved
byte for byte in [specification-history](specification-history/README.md). Original
manifest paths, hashes, benchmark counts and receipts keep their snapshot meaning,
including the pre-freeze draft labels. Other removed increments are recoverable
at Git `1468f95`. The historical design proposals are not additional formats.

Frozen protocol status is a project decision, supported by this implementation
baseline and evidence. The trusted parsers, arithmetic and static joint-existence
builders retain their documented boundary; finite tests and corpus success are
not a formal verification of the Rust implementation.
