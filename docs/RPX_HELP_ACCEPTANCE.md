# Offline help acceptance — 2026-10-18

Implemented the English offline help system on the native RPX API baseline.
No Kernel/proof semantics, certificate formats or executable entry points changed.
No Git commit or publication was performed.

## Delivered

- 338 discoverable topics generated from public definitions, packaged types and
  14 task guides; text/Markdown/`rpx.help/1` JSON output, deterministic search,
  ambiguity diagnostics and nonzero error exits.
- Native/Python docstrings, typed spec premise ordering and per-family generated
  fields, operator contracts, Agent navigation and exception-driven corrections.
- Packaged examples for elimination, delivery/Chain, continuous/integer branching,
  Cases, all five lift families and six representative error corrections.
- Definition-backed reference generation/check command and `make -C docs/rpx check-help`.
  README, Compiler guide, documentation navigation and notebook now lead to help.

## Validation

| Check | Result |
| --- | --- |
| Python suite, including 8 help tests | 101 passed |
| Tool suite (`PYTHONPATH=tools:python`) | 4 passed |
| `cargo test --workspace --locked` | 136 passed |
| Help exports, fields, operators, signatures, defaults and links | 338 topics passed |
| Generated reference | Reproduced from both checkout and installed wheel |
| Packaged complete examples | All require fresh VERIFIED results |
| Historical cases, artifact audits, RPA/RPX round trips | 81 passed |
| Migrated recipes, endpoint comparisons, new round trips | 8 VERIFIED |
| Python types | mypy passed, Python 3.9 target |
| Documentation and manual | Local links passed; 39 CLI commands and 12 negative checks passed |
| Existing examples and notebook | Five scripts and all notebook code cells passed |
| Frozen boundary | 39 Kernel files and 324 historical payload hashes unchanged |
| `git diff --check` | Passed |

Built the abi3 macOS arm64 wheel with `maturin build --release` from `python/`.
Installed it with `--no-index --no-deps` into a separate venv. From `/tmp`, with
Python isolated mode (`-I`), all 101 tests passed against the installed package;
help/search/JSON, packaged examples and ordinary Python introspection worked
without repository imports or external model files. The installed definitions
also reproduced the checked-in generated reference.

Help tests render every topic while compile/verify execution boundaries are
patched to fail, and confirm an existing proof's trace is unchanged. Resource
examples are executed only by explicit example commands, never by help queries.

## Native introspection detail

CPython supplies generic text for extension slot descriptors such as
`Q.__add__`. Their full contracts are in native class docstrings under Operators
(visible in `help(Q)`) and in individual CLI topics (`help Q.__add__`). No wrapper
classes or operator behavior changes were introduced to replace these slots.
Runtime signatures retain existing `None` sentinels where applicable; docs state
the effective numeric default and packaged declarations now match those calls.
