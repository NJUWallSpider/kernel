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
  [trusted MPS dialect](docs/MPS_V1.md), [trusted LP dialect](docs/LP_V1.md).
- [All corpus materials](audit/corpus_inventory.json), [audit narrative](audit/corpus_audit.md),
  [live acceptance ledger](audit/acceptance.json).
- [Initial performance evidence](bench/REPORT.md), [extended fixed measurements](bench/EXTENDED_REPORT.md), [shared scope measurements](bench/SHARED_SCOPE_REPORT.md), [raw runs](bench/results/).
- [Development record](audit/WORK_LOG.md).

Current acceptance is 12/81 real final targets; 69 proofs remain unfinished.
All 159 corpus MPS files and all three LP files have been imported. LP models
additionally match an independent exact parser field by field; import success is
separate from relation certification. The clean V6 build with shared scopes passes
154 tests and replays all twelve actual certificates successfully; see the
[checkpoint results](audit/validation/checkpoint-v6-shared-scopes/run.json).
The original test18 resource failure remains preserved, followed by a successful
replay of exactly the same model, RPX and requested-contract bytes.

V2 local fact branching and antisymmetry support the integer alias proof for test88
and parity fixation for test84. V3 Plotkin and exact point witnesses certify test71's
integer equivalence, strict LP strengthening, and exact source-integer and target-LP
optima. V4 jointly lifts all commodity flows for test28 while preserving integer decisions,
every attainable objective value and circulation. V5 interval lifting certifies test23 with explicit signed affine observations.
V6 proves partial-projection strictness through complete LP fiber refutations;
test18 and test19 now certify their full requested integer relationships and strict LP projection strengthening. Follow the
versioned specifications and live ledger for current status.

The existing Python FNV shim remains available; it does not implement verification.
