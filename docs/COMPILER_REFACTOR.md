# Compiler refactor acceptance record

2026-10-18 · API and native implementation: [Compiler API](COMPILER_API.md).

## Contract and frozen boundary

The public package is `rpx`. It has one Rust state owner and no old-package
entry point, compatibility aliases, Python fact mirror, recursive completion
refresh, or RPA-to-certificate production pipeline. `rpx.lowlevel` shares the
same native proof, coordinate identities and validation.

Independent model spaces cannot mix even when names and formulations match.
Builder handles survive build; edits create a new space. Splits share coordinates;
lifts create descendant spaces. Facts and goals also belong to their Proof.
Mappings invalidate previous goals. Closed scopes cannot be edited, and failed
derivations, lifts and completion do not leave certificate steps behind.

The compiler uses the frozen Kernel's obligation visitor, extension preparation,
RPA disassembler and RPX encoder. Compilation caches one immutable Certificate
and its two encodings. Verification always runs again with the requested limits.
The wire contracts remain MCM 1, RPA 12, RPX 11 and full MI_OPT in both directions.
No solver or proof search was introduced.

[Boundary hashes](../tests/vectors/compiler_boundary.json) record all 39 files in
`crates/core` and the 324 source/target/RPA/RPX payloads of the 81 historical cases.
`python3 tools/check_compiler_boundary.py` checks contents and Kernel inventory.
All remain byte-for-byte unchanged. The pre-existing continuous split right
branch fix is retained: continuous `e >= 0` uses `-e <= 0`, while integer splitting
uses `1-e <= 0` on the right.

The frozen Kernel tests referenced an absent Subflow oracle fixture. The exact
original `audit/subflow-next/fixtures/oracle.json` was restored from commit
`bbeb994` (3,301,851 bytes); no Kernel source or expected result was changed.
The PyO3 cdylib is tested inside Python, not as an executable without a Python
interpreter.

## Acceptance coverage

[Machine-readable receipt](measurements/compiler-acceptance-2026-10-18.json)
records the individual historical cases, migrated recipes, build hashes and checks.

The starting workspace passed 131 Python tests and 4 Compiler Core Rust tests.
The old interface tests were replaced by semantic tests for the new interface;
test counts are not a claim that the interfaces remain compatible. The final
suite passes 93 Python API tests, 4 tool tests and 136 Rust tests (including the
4 Compiler Core tests). The installed abi3 wheel also passes all 93 Python tests;
Python 3.9 type checking passes. The manual passes 39 CLI commands and 12 negative
checks, and its PDF rebuild succeeds.

The new tests cover exact numbers, independent spaces and Proof ownership,
parent/child and sibling visibility, variable escape, drop, stale goals, rollback,
sealed scopes, every existing derivation helper and all five lift families.
Artifact tests cover relocation, Chain joins, full named-formulation auditing,
digest tampering, file/hardlink/symlink protection, publication failures and a
concurrent destination creation, deterministic output and changing verification
budgets. Reentrant Python iterable inputs are consumed before acquiring the
native proof lock.

The historical 81 cases pass Kernel verification, delivery audit, and both
RPA/RPX roundtrips. The eight migrated recipes (test8–test15) compile new proofs,
verify them, compare full endpoint formulations with historical cases, and check
both new codec roundtrips. They do not require the historical instruction bytes.
Their manifest requires the corresponding external `reform_test/runs` inputs.
The five Python examples and all executable notebook cells use the new API.

Bundle and Chain manifests use only `rpx.bundle/1` and `rpx.chain/1`, relative
paths and content digests. Files are prepared in a sibling temporary directory.
Publication uses an atomic exclusive rename on macOS/Linux (Windows rename is
already exclusive); an existing destination is only reused after digest and
manifest equality checks. Target artifacts are copied byte-for-byte and audited.
Historical verification receipts never authorize subsequent verification.

## Measured performance

[Raw phase records](measurements/compiler-2026-10-18.json) include wall time,
RSS high-water, Python allocation deltas, source/native binary hashes, encoded
sizes and verification results. Both versions were built with Cargo `release
--locked` against the same frozen Kernel. Each case ran in a fresh process.
These are single observations on macOS arm64, not repeated controlled estimates.
Background development work and macOS memory pressure were not controlled.
The originally installed baseline extension was excluded because its build
profile differed from the release build.

Synthetic inputs have N binary variables, N rows, two row terms per variable,
and objective coefficient 0.125. The real case is the 2,298-variable test9 input.
Both directions use identity-by-name mappings. The old expression benchmark uses
its whole-expression constructor; the new one uses `Expr.dot(array('q'), vars)`.
The new map validates and expands immediately; the old identity declaration
defers work until completion, so their mapping phases have different boundaries.

Times are seconds, shown as **baseline → new**.

| Coordinates | Load | Mapping | Expression | Finish | Encode | Verify |
|---|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.003900 → 0.001407 | 0.000065 → 0.000082 | 0.012356 → 0.000359 | 0.006090 → 0.005640 | 0.001999 → 0.001664 | 0.004692 → 0.005864 |
| 10,000 | 0.029340 → 0.013017 | 0.000434 → 0.000635 | 0.127113 → 0.003369 | 0.064364 → 0.061325 | 0.020719 → 0.016237 | 0.051513 → 0.045496 |
| 100,000 | 0.314439 → 0.143073 | 0.004696 → 0.009968 | 1.475346 → 0.033685 | 0.736976 → 0.704973 | 0.224267 → 0.249028 | 0.589421 → 0.805147 |
| 1,000,000 | 4.207134 → 2.369118 | 0.047469 → 0.214971 | 16.769493 → 0.346979 | 9.919075 → 9.254537 | 2.413561 → 2.108061 | 6.733538 → 6.409990 |
| Real 2,298 | 0.007046 → 0.003435 | 0.000086 → 0.000158 | 0.018848 → 0.000811 | 0.016705 → 0.014831 | 0.003325 → 0.003854 | 0.015238 → 0.015847 |

| Coordinates | Process RSS high-water MiB, old → new | Expression Python peak bytes, old → new |
|---|---:|---:|
| 1,000 | 26.5 → 35.2 | 486,590 → 8,705 |
| 10,000 | 106.7 → 149.3 | 4,884,661 → 80,705 |
| 100,000 | 923.8 → 1,362.0 | 48,819,013 → 800,705 |
| 1,000,000 | 3,225.1 → 5,622.7 | 488,989,161 → 8,000,709 |
| Real 2,298 | 33.4 → 41.5 | 918,185 → 19,089 |

The native obligation store and exact fact index increase process memory; this
is a measured regression, not a memory optimization claim. Mapping also does
more eager work, and some smaller encoding/verification measurements are slower.
The caches deliberately
retain immutable native data for subsequent queries. No claim is made that all
phases or all models become faster.

Default mapping peaks at 1,034–1,038 bytes of Python allocation across all four
synthetic sizes. Model loading and unfiltered view construction do not allocate
one Python object per coordinate. Integer buffer expression construction uses
one FFI call and one contiguous byte-buffer copy (8N bytes here), not N Python
scalar wrappers or N FFI calls. Ordinary Python iterables still incur their own
iteration costs. Non-contiguous integer buffers follow the same native path;
floating-point and bool buffers are rejected.

Two cached preflight calls plus two unfiltered goal views take 16–40 microseconds
across the synthetic sizes, with 1,890–1,898 bytes of peak Python allocation.
Every measured proof has `lowering_count == 1`, including after publication,
verification and repeated queries. The raw records distinguish encoding,
publication and verification instead of attributing all work to compile.

## Reproduction

```sh
cargo test --workspace --locked
cargo build -p kernel-compiler-python --release --locked
cargo build -p kernel-core --release --locked --bin rpx
cp target/release/lib_native.dylib python/rpx/_native.abi3.so  # macOS development build
PYTHONPATH=python python3 -m unittest discover -s python/tests
PYTHONPATH=python:tools python3 -m unittest discover -s tools/tests
python3 tools/check_compiler_boundary.py
python3 tools/cases.py check --jobs 2
python3 tools/cases.py build --out-root build/recipes
python3 tools/benchmark_compiler_api.py --output build/performance \
  --source ../reform_test/runs/test9-nomf-20261004-004349/input/model.mps
python3 tools/check_docs.py
make -C docs/rpx check check-compiler-api
(cd python && maturin build --release)
```

The wheel is built from `python/` so maturin reads the `rpx` package metadata and
includes its type declarations. The raw benchmark JSON is checked in; generated
million-coordinate models and bundles are intentionally not source artifacts.
