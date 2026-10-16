# Current repository tools

Run these from the repository root. The Rust `rpx` CLI performs verification;
Python tools prepare certificates, orchestrate checks, and summarize evidence.

| Task | Entry point |
| --- | --- |
| Complete case delivery, one two-block RPX certificate per model pair | `check_delivery.py` |
| Corpus acceptance replay | `run_acceptance.py` |
| Manual examples and rejection checks | `check_rpx_manual.py` |
| Historical-proof migration | `migrate_mi_opt.py` |
| Paired simplification comparison | `benchmark_mi_opt_migration.py` |
| Saved benchmark analysis | `report*.py` |
| Compiler API demand tables | `aggregate_api_demand.py` |
| Fresh matched compiler/nomf Agents | `run_compiler_agents.py` |
| Independent post-commit reformulation quality | `evaluate_compiler_quality.py` |

Historical `cold_checkpoint.py`, `generalization.py`, `prepare_test*.py` and
older `benchmark*.py` drivers (excluding the current migration comparison) retain the earlier Request interface and require their
recorded kernel versions. Use `run_acceptance.py` for current builds and replay.

Some case preparers import helpers from earlier, partial preparers. Those modules
remain necessary even when their original command-line attempt is superseded.
For example, `prepare_test58_full.py` imports the reverse-map builder from
`prepare_test58.py`. Follow the case README for its current complete preparation.

## Retired experiment generators

These one-time scripts depended on removed source snapshots or prototype builds.
Their changes are already in production; they are not current reproduction
entry points and have been removed:

- `prepare_boxed_cases_experiment.py`
- `prepare_scope_experiment.py`
- `prepare_rational_shortcuts_experiment.py`
- `diagnose_rational_shortcuts.py`
- `reproduce_sparse_ab.py`

The original files remain in Git commit `bbeb994`. Historical reports, hashes,
and logs retain their original paths and meanings. To inspect a retired script
without modifying the checkout, use, for example:

```sh
git show bbeb994:tools/prepare_scope_experiment.py
```

Reproducing an old experiment also requires its exact old source, dependencies
and binary; running its retired generator against today's kernel is insufficient.
Current report generators that read retained evidence remain available. Some
historical comparison drivers still require removed snapshots, as documented in
`audit/POST_DELIVERY_CHANGES.md`.

Current verification takes source MCM, target MCM and one RPX 11 file; no Request argument. `run_acceptance.py`, `check_delivery.py`, `check_rpx_manual.py` and the compiler-agent review harness use fixed MI_OPT. Historical preparation/benchmark scripts and their hash-pinned receipts describe the earlier request-based interface and require their recorded binaries.
