Discover contracts before authoring; report success only after fresh verification.

## Task navigation
- Start: `python -m rpx help quickstart`; run the packaged example.
- Eliminate variables: search "eliminate variable", then inspect Model.substitute, Scope.map and Derive.substitution.
- Choose witnesses: help derivations; inspect goal.kind/expression and normalized facts.
- Branch maps: help branches and Scope.split. Derive a common fact: Derive.cases.
- Extend coordinates: help lifts.interval, lifts.menu, lifts.signed, lifts.flow or lifts.subflow; read the typed spec and Generated fields before constructing witnesses.
- Ship evidence: help delivery, Bundle.verify and Chain.
- Diagnose errors: help troubleshooting and the specific exception name.

## Machine-readable discovery
Use `python -m rpx help --list --format json`, `python -m rpx help Scope.map --format json`, and `python -m rpx search "flow" --limit 5 --format json`. Responses use schema rpx.help/1. Topic identifiers resolve exactly or by unambiguous suffix; unknown/ambiguous topics fail with suggestions. Search requires all case-insensitive keywords, ranks exact identifiers first and breaks ties by identifier. Search is documentation lookup, never proof search.

## Completion criteria
Preserve coordinate and Proof ownership; use exact scalars; explicitly select maps and facts. Finish every leaf of forward and reverse; compile; verify with declared limits; require VERIFIED and successful requested artifact audit. Report paths and verification status. Never call a finished or compiled proof certified without the fresh Kernel result. Help queries only inspect definitions/resources and do not execute examples.
