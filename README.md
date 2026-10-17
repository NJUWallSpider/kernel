# RPX: exact MILP optimization equivalence

RPX checks one claim: two complete MILPs preserve feasibility, extended optimal value and constructive optimal-solution recovery. Its safe Rust kernel uses exact rational arithmetic and all actual bounds, rows, integer declarations and objective constants.

A certificate contains exactly two proof trees:

```text
Certificate { forward: Block, reverse: Block }
```

Each direction maps every feasible input to a feasible output with a nonincreasing objective. There is no Contract/Request, objective mode, LP mode, inverse declaration or property-selection interface. The same tuple must satisfy every output obligation. A reverse recovery map need not invert the forward map.

## Build and verify

```sh
cargo build -p kernel-core --release --locked
cargo test -p kernel-core --locked

target/release/rpx canonical source.mps source.mcm
target/release/rpx canonical target.lp target.mcm
target/release/rpx assemble proof.rpa proof.rpx
target/release/rpx verify source.mcm target.mcm proof.rpx
```

The current formats are **MCM 1, RPX 11, and RPA 12**. **RPA 12** is a line-oriented assembly that lowers directly to RPX; old `RPA 11` JSON and `RPA-S 1` text are rejected. `compile certificate.json proof.rpx` remains a separate structured JSON bridge used by the Python compiler, not an RPA text path.

`VERIFIED` certifies MI optimization equivalence. `INVALID`, `RESOURCE_LIMIT` and `IO_ERROR` establish no such result. Model import, compilation and proof planning are not certification.

## Authoring

The [Python API](docs/COMPILER_API.md) supplies exact models, scoped facts, explicit maps and mechanical obligation completion. Authors use `proof.forward` and `proof.reverse`. It does not discover a reformulation or search for a proof.

Scalar derivations, exhaustive branches and Interval, Menu, Signed, Flow and Subflow constructions remain available. Their role is to complete the fixed optimization-equivalence proof. A generic solver-facing recovery executor is not yet exposed.

## Validation and migration

All **81 complete cases across 11 families** have been migrated from 83 historical proof files into **81 two-block certificates**, each independently checked by the new kernel. Original models, proofs and historical receipts remain unchanged. Each case's `optimization.json` binds its current proof and models by SHA-256.

[Current validation evidence](audit/validation/mi-opt-simple-20261016/) includes test, example, migration and paired performance results. Historical [delivery](audit/FINAL_DELIVERY_REPORT.md) and [freeze](audit/PROTOCOL_V9_V10_FREEZE.md) reports retain their original property-based meanings and timings.

```sh
python3 tools/check_rpx_manual.py --kernel target/release/rpx
python3 tools/run_acceptance.py --label your-fresh-validation-label
PYTHONPATH=python KERNEL_RPX=target/release/rpx python3 -m unittest discover -s python/tests
```

[The explicit migration tool](tools/migrate_mi_opt.py) uses an external legacy binary to extract suitable whole-domain proofs, then recompiles and rechecks them. Legacy decoding never enters the current kernel.

## Documentation

- [Semantics](docs/SEMANTICS.md), [format](docs/FORMAT.md), [Rust/CLI API](docs/API.md), [Python API](docs/COMPILER_API.md).
- [RPA assembly](docs/RPA.md), [manual and examples](docs/README.md).
- Exact [MPS](docs/MPS_V1.md) and [LP](docs/LP_V1.md) import.
- [Current tools and historical drivers](tools/README.md).
