Inspect, map, prove, finish, compile, then verify both directions.

## Authoring loop
1. Read or build source and target; inspect `model.stats()` and `model.vars.iter(limit=20)` / `model.rows.iter(limit=20)`.
2. Create `Proof(source, target)`. In forward, output coordinates are target variables and mapping expressions use source variables. Reverse swaps these roles.
3. Call `scope.map(overrides, default="same_name")` when same-name defaults are intended; otherwise supply a complete map. Each call replaces the previous specification.
4. Inspect `scope.plan()` and `scope.missing(limit=20)`. Use `scope.missing().count` for the full count; a limited view counts only its selection.
5. Select facts with row/lower/upper/integer. Use `scope.prove(goal, by=...)` or explicit `scope.derive` helpers. Inspect `fact.kind` and `fact.expression` if a match fails.
6. Finish every leaf in both directions. After split/lift, finish the children; the parent is a fixed container.
7. `bundle = proof.compile(directory)` writes a self-contained delivery. `report = bundle.verify()` performs fresh verification. Call `report.raise_for_status()` and inspect the artifact audit before claiming success.

## Complete example
Run `python -m rpx._help.examples.workflow` for an elimination proof, target artifact export/audit, moved bundle verification and a composed Chain. All files are created in a temporary directory.

## Completion boundary
The Compiler only expands author-selected mappings and derivations. It is not a solver. Certification requires a VERIFIED Kernel result, with any requested artifact audit successful. A historical receipt does not replace a fresh check.
