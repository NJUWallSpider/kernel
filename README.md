# RPX: exact MILP optimization equivalence

RPX checks one claim: two complete MILPs preserve feasibility, extended optimal value and constructive optimal-solution recovery. Its safe Rust kernel uses exact rational arithmetic and all actual bounds, rows, integer declarations and objective constants.

The native compiler core produces a certificate with exactly two proof trees:

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

The current formats are **MCM 1, RPX 11, and RPA 12**. **RPA 12** is a line-oriented assembly that lowers directly to RPX; old `RPA 11` JSON and `RPA-S 1` text are rejected. The Python API compiles through the native Rust core to RPA 12 and then RPX 11; Certificate JSON is not a production proof path.

`VERIFIED` certifies MI optimization equivalence. `INVALID`, `RESOURCE_LIMIT` and `IO_ERROR` establish no such result. Model import, compilation and proof planning are not certification.

## Authoring

The [Python API](docs/COMPILER_API.md) supplies exact models, scoped facts, explicit maps and mechanical obligation completion. Authors use `proof.forward` and `proof.reverse`. It does not discover a reformulation or search for a proof.

Scalar derivations, exhaustive branches and Interval, Menu, Signed, Flow and Subflow constructions remain available. Their role is to complete the fixed optimization-equivalence proof. A generic solver-facing recovery executor is not yet exposed.

## Validation

All **81 complete cases across 11 families** are delivered as **MI_OPT-only**
two-block certificates. Each `cases/<case>/` directory contains the canonical
`source.mcm`, `target.mcm`, `proof.rpa` (RPA 12), `proof.rpx` (RPX 11),
`delivery.json`, and `preparation.json`. Historical receipts and old proof
versions have been removed; the current receipts bind the retained artifacts by
SHA-256.

```sh
python3 tools/cases.py check --jobs 4
python3 tools/check_rpx_manual.py --kernel target/release/rpx
PYTHONPATH=python python3 -m unittest discover -s python/tests
```

`tools/cases.py` verifies every MCM/RPX pair, audits `delivery.json`, and
requires byte-identical `RPA 12 -> RPX 11 -> RPA 12` conversion. Historical
migration and the LP-to-proof generators are not part of the current pipeline.

## Documentation

- [Semantics](docs/SEMANTICS.md), [format](docs/FORMAT.md), [Rust/CLI API](docs/API.md), [Python API](docs/COMPILER_API.md).
- [RPA assembly](docs/RPA.md), [manual and examples](docs/README.md).
- Exact [MPS](docs/MPS_V1.md) and [LP](docs/LP_V1.md) import.
- [Current tools and the native case pipeline](tools/README.md).
