# RPX exact reformulation kernel

Work in progress. Pure safe Rust validates exact rational MILP reformulation proofs
against complete source/target models and a caller-supplied requested contract.
The old `docs/rpx/` D0 manual is a design draft, not the implemented ABI.

```sh
cargo build -p kernel-core --release --locked
cargo test -p kernel-core --locked
python3 tools/prepare_test40.py --kernel target/release/rpx
python3 tools/generalization.py --kernel target/release/rpx
```

Minimal toolchain:

```sh
target/release/rpx canonical input.mps input.mcm
target/release/rpx assemble proof.rpa proof.rpx
target/release/rpx verify source.mcm target.mcm proof.rpx request.json
```

`VERIFIED` is successful proof verification. `INVALID`, `RESOURCE_LIMIT`, and
`IO_ERROR` are distinct failures; none establishes that a reformulation is wrong.
Assembly and canonicalization do not establish verification.

- [Implemented semantics](docs/SEMANTICS_V1.md), [binary format](docs/FORMAT_V1.md),
  [RPA text syntax](docs/RPA_V1.md), [V2 extensions](docs/FORMAT_V2.md),
  [V3 theorem and witnesses](docs/FORMAT_V3.md), [V4 joint flow lift](docs/FORMAT_V4.md), [exact point contracts](docs/POINT_V3.md),
  [V7 menus and full bijections](docs/FORMAT_V7.md), [V8 activated signed decomposition](docs/FORMAT_V8.md), [trusted MPS dialect](docs/MPS_V1.md), [trusted LP dialect](docs/LP_V1.md).
- [All corpus materials](audit/corpus_inventory.json), [audit narrative](audit/corpus_audit.md),
  [live acceptance ledger](audit/acceptance.json).
- [Initial performance evidence](bench/REPORT.md), [extended fixed measurements](bench/EXTENDED_REPORT.md), [shared scope measurements](bench/SHARED_SCOPE_REPORT.md), [V7 theorem and actual-case baseline](bench/THEOREM_V7_REPORT.md), [exact arithmetic comparison](bench/RATIONAL_SHORTCUTS_REPORT.md), [V8 signed baseline](bench/SIGNED_V8_REPORT.md), [raw runs](bench/results/).
- [Development record](audit/WORK_LOG.md).

The frozen V8 rebuild passes 198 core tests and replays the 34 actual certificates
enumerated at its start in [V8 checkpoint results](audit/validation/checkpoint-v8/run.json).
Subsequent successful cases and all unfinished cases remain in the
[live acceptance ledger](audit/acceptance.json), with all 81 supplied runs retained.
The working V9 objective-domain change is an [unfrozen draft](docs/FORMAT_V9_DRAFT.md),
not a completed release or certification of test80.
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
versioned specifications and live ledger for current status. V7 certifies the complete
integer menu bijections and LP observation images in test59/test60. Test38 verifies
shared switch-DAG aliases with existing scalar rules; test57 verifies its full
integer and LP affine bijections.

The existing Python FNV shim remains available; it does not implement verification.
