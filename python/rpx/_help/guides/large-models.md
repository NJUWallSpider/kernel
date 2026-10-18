Keep large model inspection native and bounded until materialization is intentional.

## Views
Use len(model.vars), indexed lookup and model.vars.iter(limit=20); rows have the same pattern. scope.missing(limit=20), goal expressions, sparse terms and indexed trace/certificate views avoid constructing a complete Python mirror. to_dict/to_list explicitly allocate full Python structures. Use scope.missing().count for the total; the count of a capped selection is capped too.

## Batch arithmetic and mapping
Use quicksum(model.vars), Expr.dot(integer_buffer, model.vars), or Expr.from_terms(model, indices, coefficients). Native views and integer buffers take the batch path. Python iterables are accepted but already-created Python objects still cost memory. `scope.map(default="same_name")` expands in Rust with sparse overrides and a version cache; do not build a Python identity dictionary for every variable.

## Repeated work
Reuse immutable preflight/compile snapshots. Verification always runs again with this call's limits. A view is a handle, not a second Python state store. Inspect `python -m rpx help MappingView` and `python -m rpx help Expr.dot` for contracts.
