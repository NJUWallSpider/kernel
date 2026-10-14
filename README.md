# RPX exact reformulation kernel

The supplied corpus is functionally accepted: **81/81 complete actual cases,
all 11 families**, with a fresh 262-test build and 83 successful final kernel
invocations. See the [complete delivery report](audit/FINAL_DELIVERY_REPORT.md)
for original-contract scope, reproducible evidence, performance and trust limits.
MCM 1 and RPX/RPA V1–V10 are frozen. V9/V10 were frozen on 2026-10-14;
see the [freeze baseline](audit/PROTOCOL_V9_V10_FREEZE.md).
The new [readable RPA-S source](docs/RPA_SOURCE.md) compiles explicit expressions,
aliases, comments, model-bound named checks and array expansions to the same Certificate/RPX. Its source
version is independent of the frozen protocol capability versions.

The [Python Compiler API](docs/COMPILER_API.md) authors exact models, explicit
maps and scoped user proofs, compiles directly to RPX, and calls the Kernel.
It uses no RPA intermediate and performs no proof search. Kernel-owned
obligation plans and constructive scopes replace manual check ordering and
offset bookkeeping. See [design coverage](docs/COMPILER_DESIGN.md) and
[real Agent acceptance](docs/COMPILER_AGENT_ACCEPTANCE.md); autonomous Agent
quality/time acceptance is separate from the historical corpus replay above.

Pure safe Rust validates exact rational MILP reformulation proofs
against complete source/target models and a caller-supplied requested contract.
The [Chinese kernel manual](docs/rpx/rpx-manual.pdf) and its
[LaTeX sources](docs/rpx/) describe the current implementation, including the
frozen V9/V10 extensions.

```sh
cargo build -p kernel-core --release --locked
cargo test -p kernel-core --locked
python3 tools/prepare_test40.py --kernel target/release/rpx
python3 tools/generalization.py --kernel target/release/rpx
```

Minimal toolchain:

```sh
target/release/rpx canonical input.mps input.mcm
target/release/rpx compile certificate.json proof.rpx
target/release/rpx assemble proof.rpa proof.rpx
target/release/rpx assemble proof.rpas proof.rpx
target/release/rpx disassemble-source proof.rpx recovered.rpas
target/release/rpx disassemble-source --models source.mcm target.mcm proof.rpx named.rpas
target/release/rpx verify source.mcm target.mcm proof.rpx request.json
target/release/rpx export-model source.mcm source.json
```

`VERIFIED` is successful proof verification. `INVALID`, `RESOURCE_LIMIT`, and
`IO_ERROR` are distinct failures; none establishes that a reformulation is wrong.
Assembly and canonicalization do not establish verification.

- [Unified frozen format specification](docs/FORMAT.md), [mathematical semantics](docs/SEMANTICS.md),
  [readable RPA-S tutorial](docs/RPA_SOURCE.md), [JSON RPA tutorial](docs/RPA.md),
  [rule arguments and manual index](docs/README.md),
  trusted [MPS](docs/MPS_V1.md) and [LP](docs/LP_V1.md) dialects.
- [All corpus materials](audit/corpus_inventory.json), [audit narrative](audit/corpus_audit.md),
  [live acceptance ledger](audit/acceptance.json).
- [Initial performance evidence](bench/REPORT.md), [extended fixed measurements](bench/EXTENDED_REPORT.md), [shared scope measurements](bench/SHARED_SCOPE_REPORT.md), [V7 theorem and actual-case baseline](bench/THEOREM_V7_REPORT.md), [exact arithmetic comparison](bench/RATIONAL_SHORTCUTS_REPORT.md), [V8 signed baseline](bench/SIGNED_V8_REPORT.md), [raw runs](bench/results/).
- [Development record](audit/WORK_LOG.md).
- [Current tooling and retired experiments](tools/README.md).

The frozen V8 rebuild passes 198 core tests and replays the 34 actual certificates
enumerated at its start in [V8 checkpoint results](audit/validation/checkpoint-v8/run.json).
The current [acceptance ledger](audit/acceptance.json) records all 81 cases as
verified; the new freeze baseline runs 280 tests and replays all 83 invocations.
V9 adds caller-declared objective-level domains; V10 adds strict improvement,
complete-image exclusion, affine input restrictions and joint demand-bounded subflows.
Their complete layouts and semantic boundaries are consolidated in [FORMAT](docs/FORMAT.md).
The [delivery acceptance review](audit/DELIVERY_ACCEPTANCE.md)
distinguishes successful submitted requests from complete original-report
contracts. Its 78 historical requests also reproduce byte-for-byte with the
V10 candidate in [compatibility evidence](audit/validation/v10-old-78-compatibility.json).
[Actual test80](cases/test80/README.md) preserves its recorded internal snapshot;
its historical receipt predates the explicit V9 freeze. [Shared builder mechanics](audit/BUILDER_SUPPORT_REVIEW.md)
subsequently pass both 210-test suites and 48 complete before/after case replays.
All 159 corpus MPS files and all three LP files have been imported. LP models
additionally match an independent exact parser field by field; import success is
separate from relation certification. The clean V7 arithmetic build passes 185 tests and replays all 26 actual certificates
present when its run began in [checkpoint results](audit/validation/checkpoint-v7-rational/run.json),
plus the late-prepared [test20 certificate](audit/validation/checkpoint-v7-rational/test20-late.json).
Later cases have separate full receipts in the live ledger. The [arithmetic merge review](audit/V7_ARITHMETIC_MERGE.md)
distinguishes the measured prototype from the final resource-policy repairs. Earlier
frozen checkpoints retain their original test and case counts.
The original test18 resource failure remains preserved, followed by a successful
replay of exactly the same model, RPX and requested-contract bytes.

V2 local fact branching and antisymmetry support the integer alias proof for test88
and parity fixation for test84. V3 Plotkin and exact point witnesses certify test71's
integer equivalence, strict LP strengthening, and exact source-integer and target-LP
optima. V4 jointly lifts all commodity flows for test28 while preserving integer decisions,
every attainable objective value and circulation. V5 interval lifting certifies test23 with explicit signed affine observations.
V6 proves partial-projection strictness through complete LP fiber refutations;
test18 and test19 now certify their full requested integer relationships and strict LP projection strengthening. Follow the
unified specification and live ledger for current status. V7 certifies the complete
integer menu bijections and LP observation images in test59/test60. Test38 verifies
shared switch-DAG aliases with existing scalar rules; test57 verifies its full
integer and LP affine bijections.

Programmatic callers use the `kernel_core::api` façade (`crates/core/src/api.rs`):
`canonicalize_path`, `assemble_paths`, `disassemble_paths`, `disassemble_source_paths`, `inspect_model_path`,
`export_model_paths`, `verify_paths` and the filesystem-free `verify_bytes`. The
CLI above is a thin shell over it, so both surfaces report the same statuses, the
same JSON fields and the same exit codes. Failures carry a `code` and, when the
verifier can attribute it, a `location` (`claim`/`point`/`block`/`step`/
`obligation`); successes are unchanged. [`docs/API.md`](docs/API.md) is the
interface reference, including the canonical model JSON that `export-model`
writes. The new Python package is in `python/kernel_compiler`; use
`PYTHONPATH=python python3 your_proof.py` after building the release binary.
`compile_certificate_paths`, `plan_return_paths`, and `prepare_injectivity_paths`
provide direct compiler bridges. The earlier Python FNV shim was removed: it
exposed only a hash helper and never implemented verification.

Some large cases use an explicit conjunction of independently complete requests
against the same source/target MCM pair. [Test46](cases/test46/README.md) supplies
three complete direction files because its combined RPA exceeds the unchanged
256 MiB assembler text limit. `bundle.json` is delivery metadata, not a new RPX
instruction or an acceptance authority: every listed request must verify, and
there are no cross-file fact, inverse or theorem references. The complete caller
request is retained in `combined-request.json`. `tools/check_delivery.py`
recanonicalizes actual models, reassembles each RPA and verifies every piece;
`tools/run_acceptance.py` includes all pieces in cold corpus replay. The ledger
labels aggregate results as multiple invocations and keeps original-contract
scope gates separate from successful kernel execution.
