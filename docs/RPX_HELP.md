# Offline RPX help

The wheel includes English task guides, API discovery, type declarations and
self-contained runnable examples. Nothing is fetched from the network.

```sh
python -m rpx
python -m rpx help quickstart
python -m rpx help Scope.map
python -m rpx help lifts.flow --format json
python -m rpx help --list
python -m rpx search "eliminate variable" --limit 5 --format json
```

Use `help(rpx)`, `help(Model)`, `help(Scope.map)` in Python. Native slot operators
use Python's standard slot descriptions; their full contracts are in each
class's Operators section and in individual CLI operator topics, such as
`python -m rpx help Fact.__mul__`. Generated lift fields and typed spec fields
are documented as separate discoverable topics even when reflection cannot
produce a runtime descriptor.

No arguments show a capability overview. Text is the default; markdown and JSON
are also supported, with no pager or ANSI formatting. Identifiers accept an
optional `rpx.` prefix or an unambiguous suffix. Unknown or ambiguous topics
exit 1 with suggestions. Invalid command syntax exits 2. Search requires every
case-insensitive keyword, ranks exact identifiers first, and orders ties by
identifier; default limit is 10, and total counts all matches. Limit zero is
useful for counting. JSON envelopes use `schema: "rpx.help/1"` and a `kind` of
overview, topic, index, search or error. Topic records have identifier, category,
title, summary, signature (null if inapplicable), named sections and related IDs.
Search/index results have structured identifier/category/title/summary/signature
records. Help queries only inspect symbols and package resources.

The existing Kernel executable `rpx` is unchanged. `python -m rpx` is a
documentation-only module entry point and never authors or verifies a proof.

## Start by task

- `quickstart`: installation and the first elimination proof.
- `workflow`: inspect, map, prove, finish both directions, compile and verify.
- `ownership`: exact arithmetic, model edits, scopes and stale goals.
- `derivations` and `branches`: selected witnesses, helpers, splits and Cases.
- `lifts.interval`, `lifts.menu`, `lifts.signed`, `lifts.flow`, `lifts.subflow`:
  typed premises and generated results.
- `delivery`: Bundle, Chain, artifacts and budgets.
- `large-models`: bounded views and batch arithmetic.
- `troubleshooting`: concrete corrections and next inspection commands.
- `agent`: task navigation and completion criteria.

## Run examples

```sh
python -m rpx._help.examples.quickstart
python -m rpx._help.examples.workflow
python -m rpx._help.examples.branches
python -m rpx._help.examples.lifts
python -m rpx._help.examples.errors
```

These are explicit execution commands, separate from help queries. Each builds
its inputs in memory, writes into a temporary directory and requires VERIFIED.
Read their installed source using `importlib.resources.files("rpx._help.examples")`.
Successful finish or compilation is never described as certification.

## Maintain the reference

Author native contracts beside definitions in `crates/python/src`, Python
contracts beside their definitions in `python/rpx`, and task guides in
`python/rpx/_help/guides`. The registry holds only navigation metadata. The
[generated reference](RPX_REFERENCE.md) reads actual docstrings and packaged
syntax-only type declarations; it has no separately maintained API catalog.

After rebuilding the native extension:

```sh
PYTHONPATH=python python3 tools/check_rpx_help.py --write
PYTHONPATH=python python3 tools/check_rpx_help.py --check
PYTHONPATH=python python3 -m unittest discover -s python/tests -p 'test_rpx_help.py'
```

The checker covers exports, members, properties, operator declarations, typed
and generated fields, parameter names/defaults and related links. Explicit
`None` defaults in native signatures are documented with their effective
numeric defaults; type stubs preserve the actual call signature.
