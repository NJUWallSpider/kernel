# Current repository tools

Run these from the repository root. The Rust `rpx` CLI performs verification;
Python tools prepare certificates, orchestrate checks, and summarize evidence.

| Task | Entry point |
| --- | --- |
| Complete case delivery, including multi-file requests | `check_delivery.py` |
| Corpus acceptance replay | `run_acceptance.py` |
| Manual examples and rejection checks | `check_rpx_manual.py` |
| Fresh source/build/test checkpoint | `cold_checkpoint.py` |
| Synthetic semantic generalization | `generalization.py` |
| Per-case certificate preparation | `prepare_test*.py` and shared builders |
| Current performance matrices | `benchmark*.py` |
| Saved benchmark analysis | `report*.py` |
| Compiler API demand tables | `aggregate_api_demand.py` |

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
