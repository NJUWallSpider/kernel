# Post-delivery changes

The delivered tree is commit `49c9405` (tag `delivery-v10`). This note records
what changed afterwards in the working tree, why, and which recorded assertions
are intentionally invalidated. Every manifest, receipt, checkpoint and case
artifact imported by that commit is untouched.

## Unchanged

- **Delivered binary.** `target/validation-v10-complete/release/rpx`, SHA-256
  `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`, still byte
  identical, and still `target/release/rpx` for the unchanged sources.
- **Wire formats and verification rules.** MCM 1, RPX 1–10, RPA text, the
  resource policy defaults and every obligation, counter and rule in
  `docs/CURRENT_FORMAT.md` are unchanged.
- **Corpus artifacts.** All 81 case directories, their models, RPA/RPX and
  request files, and the audit ledgers.

## Changed

1. **Library façade** `crates/core/src/api.rs` (new, 319 lines). The report
   shape, status words and exit codes that the CLI already exposed as text now
   have names: `Status`, `Error::from_message` (the single place that classifies
   a failure), `limits_json`, `Timings`, `read_input`/`read_text`/`write_output`,
   `canonicalize_path`, `assemble_paths`, `disassemble_paths`,
   `inspect_model_path`, `verify_paths`, the filesystem-free `verify_bytes` and
   `verify_report`.
2. **`crates/core/src/main.rs` is a shell** over the façade (85 → 61 lines):
   argument parsing, dispatch, stdout, exit code.
3. **`crates/core/src/level.rs`**: removed the write-only
   `RestrictedDomain::halfspace_row` field (141 → 136 lines). No rule, row or
   counter changed; `verify.rs` never read the field.
4. **Python/FNV shim removed**: `crates/py/`, `python/`, `tests/test_api.py`,
   `pyproject.toml`, `uv.lock`, `.python-version`, the `pyo3` workspace
   dependency and the second workspace member. The extension exposed only
   `fnv1a64`, a hash utility that is not part of verification, and no caller
   used it. Reintroducing a Python surface means writing real bindings over
   `kernel_core::api`, not restoring this shim.
5. **`Cargo.lock`** loses the pyo3 family (10 packages); the dependency set is
   now `num-bigint`, `num-integer`, `num-rational`, `num-traits`, `serde`,
   `serde_json` plus their build/proc-macro transitive crates.
6. **README**: the FNV-shim sentence now points at the façade.
7. **Working-tree hygiene (untracked, no commit):** deleted nested Rust
   `target/` trees, four orphan prototype `docs/.build/` copies, the live
   `docs/.build/` and stale LaTeX intermediates, caches and `dist/`. Tree size
   went from 36 GiB to 34 GiB. The only manifest-pinned build outputs were kept:
   `audit/validation/builder-support-differential-v2/{baseline,extracted}/target/
   release/probe` (bound by `builder-support-differential-v2/result.json`) and
   `bench/builder-support-baseline/tests/__pycache__/test_api.cpython-313-*.pyc`
   (bound by `audit/builder_support_baseline.json:287`).

## Recorded assertions this invalidates

- `audit/finalize_delivery_manifest.py:37` asserts that every `crates/*` entry of
  `audit/checkpoints/v10-complete-source.json` equals the live file. After
  change 1–4 that assertion is intentionally false for the changed and removed
  paths. The finalizer refuses to re-run once its output exists, so this is a
  recorded invariant rather than an active test, and nothing else in that script
  or in any manifest is affected.
- The frozen checkpoint copies still carry the pre-change sources
  (`audit/checkpoints/v10-complete-source/…`,
  `audit/checkpoints/delivery-78-working-source/…`, `bench/*-prototype/…`), so
  reproductions performed inside those directories remain valid.
- `.gitignore` keeps rebuildable build output and the heavy generated artifacts
  (`*.rpa`, `*.rpx`, `*.mcm`, `audit/acceptance.json`) out of Git. Those files
  stay on disk and stay bound by the SHA-256 manifests, but a fresh clone cannot
  re-run the corpus replay without them, and manifests that hash files under
  `docs/.build/` or `__pycache__/` refer to on-disk files that Git does not
  version.

## Verification performed after the changes

- `cargo build -p kernel-core --release --locked`.
- `cargo test -p kernel-core --locked`: 262 passed, 0 failed across 33 test
  binaries — the delivered 262 minus the removed `fnv1a64` unit test, plus the
  new façade test `facade_matches_cli_and_classifies_status`.
- A/B against the delivered binary on 19 invocations (five verifying cases, two
  rejected proofs, work and live-fact limits, missing file, usage, bad flag,
  unknown command, `inspect-model`, canonical MPS and LP, assembly of a 0.4 MB
  and a 102 MB RPA, disassembly): identical reports and identical exit codes.
- All 83 recorded kernel calls in `audit/validation/v10-complete/run.json`
  replayed with the refactored binary: identical exit code and identical report
  fields except `read_us`, `model_decode_us`, `proof_decode_us`, `execute_us`
  and `total_us`.
- Assembler byte identity: `cases/test84/proof.rpa` → `ee8aaea4…` and
  `cases/test29/proof.rpa` → `65e2cfed…`, equal to the delivered `proof.rpx`.

## Returning to the delivered state

`git diff delivery-v10..HEAD` shows the delta; `git checkout delivery-v10`
restores the delivered sources. The delivered binary remains at
`target/validation-v10-complete/release/rpx`.

# Second change set: model export and structured diagnostics

Two capabilities the compiler/API layer needs, both additive; the wire formats,
verification rules and the delivered CLI reports are untouched.

1. **Canonical model export.** `model::to_json` emits the loaded MCM as JSON
   (scalars as strings in the `parse_q` vocabulary, `null` for unbounded sides),
   `api::export_model_paths` writes it, and the CLI gained
   `export-model model.mcm output.json` with status `EXPORTED` (exit 0). The
   round-trip property — export → read back through the documented grammar →
   re-encode equals the original MCM bytes — is asserted in
   `crates/core/tests/model_export.rs`. Note for callers: the existing
   `Serialize` derive on `Model` is *not* canonical for the four bound fields
   (it emits nested rational pair arrays); use `to_json`.
2. **Structured diagnostics.** `verify::{Location, Diagnostics}` plus
   `verify_request_with_diagnostics`, `verify_with_diagnostics`,
   `verify_points_with_diagnostics`, `verify_lp_refutation_with_diagnostics` and
   `verify_injectivity_with_diagnostics` report the failing `claim`, `point`,
   `block`, `step` and `obligation` indices through a caller-owned sink. All
   existing signatures are unchanged and delegate with a scratch sink. The
   façade attaches the location to `api::Error`, which now also carries a derived
   `snake_case` `code`; failure reports gained `code` and `location` keys.
   Diagnostics are written after every acceptance decision and are never read by
   the verifier, so they cannot change an error string, a counter or a decision.

Interface reference: [docs/API.md](../docs/API.md) (new). `docs/CURRENT_FORMAT.md`
is intentionally left byte-identical because
`audit/final_delivery_manifest.json` pins its hash; it documents the delivered
five-subcommand CLI, and the added subcommand and the failure schema are
documented in `docs/API.md` instead.

Evidence for this change set: `cargo test -p kernel-core --locked` passes 280
tests (the delivered 262 minus the removed `fnv1a64` unit test, plus 7 model
export tests, 10 diagnostics tests and 2 façade tests); all 83 recorded kernel
calls in `audit/validation/v10-complete/run.json` replay with identical exit
codes and identical reports apart from the five timing fields, so the success
path is unchanged; failure reports gained exactly the two documented keys.

# Third change set: bulk removal of duplicated snapshots

The working tree carried full copies of the crate and docs, plus dead scripts.
These were removed; every manifest and receipt was kept, so the records remain
complete even though the copies they hash are no longer on disk.

| Removed | What it was |
| --- | --- |
| `audit/checkpoints/*-source/` (11 trees, ~550 MB) | per-version full copies of the crate, docs, tests, tools and LaTeX output |
| `audit/checkpoints/*-source.tar.gz` (9 archives, 254 MB) | the same trees in archive form |
| crate/docs copies inside `bench/{builder-support-baseline,boxed-cases-prototype,flow-prune-prototype,shared-scope-prototype,shared-scope-prototype-initial,rational-shortcuts-prototype}/` | `crates/`, `docs/`, `tests/`, `tools/`, `Cargo.*`; the receipts, logs and diffs stay |
| `bench/baseline-source/{workspace,verify.rs}`, `bench/reconstructed-sparse-source/{crates,Cargo.*}` | sparse-reconstruction sources; `reconstruction.json` and the comparison stay |
| `tools/{checkpoint,exact_oracle,generalize_test38,replay_builder_support,audit_builder_support}.py` | zero invocations, zero imports and zero documentation mentions in the live tree |
| `.venv/` | dangling editable install of the removed Python shim |
| prototype build dirs under `target/` | `builder-support-baseline`, `builder-support-extracted`, `conditional-domain-production`, `subflow-next`, `subflow-production`, `test80-baseline`, `next-contracts-initial`, `maturin`, `wheels`, `tmp`, `flycheck0` |

Deliberately kept: every `audit/checkpoints/*.json` and receipt, the prototype
receipts/logs/diffs, `audit/subflow-next/` (read by `crates/core/tests/subflow.rs`),
`tools/prepare_test36.py` (bound by `cases/test36/attempts/preparation.json`),
the two manifest-pinned probe binaries, `docs/rpx-manual.pdf`, and all case
artifacts.

Consequences: manifests that hash removed paths (for example
`audit/builder_support_baseline.json`, `audit/validation/checkpoint-*/run.json`,
`audit/checkpoints/*.json`) no longer resolve against the working tree; they
remain complete hash records. The removed content is recoverable from Git with
`git checkout <commit> -- <path>`. Sizes: tree 34 GiB → 32 GiB, `audit/`
1.7 GiB → 0.99 GiB, `bench/` 289 → 149 MiB, `target/` 8.3 → 6.5 GiB.

Two recorded tools no longer run against the trimmed tree, and both say so
rather than silently skipping a check: `tools/report_v10_regression.py` stops
with `initial/old: source snapshot drift` because the old-source snapshots it
compares against were removed, and `tools/reproduce_sparse_ab.py` needs the
removed `bench/baseline-source/workspace`. The other report generators still
reproduce their checks from the kept receipts — `report_signed.py` (120
processes), `report_theorems.py` (312 observations) and
`report_rational_shortcuts.py` (1,176 processes) all pass. Restoring what the two
affected tools name is one command, for example
`git checkout delivery-v10 -- audit/checkpoints/delivery-78-working-source audit/checkpoints/v10-kernel-candidate bench/baseline-source`.

Caution: `report_v10_regression.py` writes its output file *before* its drift
guard fires, so a run against the trimmed tree leaves
`bench/results/v10-regression-comparison.json` holding a `VALIDATION_FAILED`
stub. That file is hash-pinned by `audit/final_delivery_manifest.json`
(`a246e6b4…`); after any such run restore it with
`git checkout delivery-v10 -- bench/results/v10-regression-comparison.json`.

# History trim: the checkpoint archives left `main`'s history

The nine `audit/checkpoints/*-source.tar.gz` archives (254 MB), already removed
from the working tree by the third change set, were also removed from every
commit of `main`. Nothing else changed: the tree of the new tip `8980a37` is
byte-identical to that of `23e57b2` (`git diff --stat 23e57b2 main` is empty),
and `delivery-v10` still points at `49c9405` with all nine archives in place.

Reason: those archives are the only incompressible weight in the repository. A
push of the full history is a 313.7 MiB pack, of which 312 MiB is the nine
archives plus the two tracked `audit/*.json.gz` snapshots; the hosting service
answers that POST with HTTP 500 once the upload completes, over HTTP/2 and over
HTTP/1.1 alike, while a 362-byte probe push to the same repository succeeds.
Without the archives the same push is a 60.3 MiB pack.

Consequence for the recovery command above: it still resolves, because
`delivery-v10` carries the archives, but `main`'s history no longer contains
them anywhere, so a clone that fetches only `main` cannot recover them.
