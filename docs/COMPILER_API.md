# rpx Compiler API

`rpx` authors complete, two-direction MI_OPT certificates. Rust owns models,
coordinate identities, scopes, facts, sparse mappings, obligations and the
compiled snapshot. The frozen Kernel checks the resulting MCM 1, RPA 12 and
RPX 11 artifacts. The compiler expands only the mappings and derivations the
author selects; it does not run a solver or search for proofs.

## Installation and first proof

```sh
python3 -m pip install -e ./python
```

```python
from rpx import Model, Proof

source = Model.read("source.lp")
target = Model.read("target.lp")
proof = Proof(source, target)
f = proof.forward
f.map({"y": source.vars["x1"]}, default="same_name")
f.prove("objective.non_increasing", by=-f.row("balance"))
f.finish()
proof.reverse.map({
    "x0": 1-target.vars["y"],
    "x1": target.vars["y"],
}).finish()
bundle = proof.compile("build/elimination", target_artifact="target.lp")
report = bundle.verify()
report.raise_for_status()
print(report)
```

Executable versions of this example and four others are in
[the examples directory](rpx/examples/python-api/README.md). The
[notebook](rpx/examples/python-api/tutorial.ipynb) covers construction, views,
goals, split, lift, Cases and diagnostics.

## Exact numbers and expressions

`Q` accepts integers, exact strings (including rational and decimal notation),
`fractions.Fraction`, and finite `decimal.Decimal`. Float, bool, NaN and infinity
are rejected. Arithmetic is native and checked against the Kernel's exact
arithmetic budget; the frozen file encoders may impose a tighter scalar limit.

A `VarRef` is an expression tied to one coordinate space. Independent models
remain distinct even when names and contents match. Constants carry no space.
Model edits return a new model and space. Pass expressions from the model being
edited; obtain the result's variables from its own view afterward. There is no
implicit rebinding by name.

```python
from rpx import ModelBuilder, Q, Expr, quicksum
from array import array

b = ModelBuilder("capacity")
x = b.add_var("x", integer=True, lower=0, upper=1)
y = b.add_var("y", lower=0, upper=2)
b.add_row("cap", x+y, upper=2)
b.minimize(x/3+y/7)
model = b.build()
assert quicksum(model.vars) == x+y
assert Expr.dot(array("q", [2, 3]), model.vars) == 2*x+3*y
assert Expr.from_terms(model, array("I", [0, 1]), array("q", [2, 3])) == 2*x+3*y
```

`build()` closes the builder while preserving previously returned handles.
Variables default to free, continuous coordinates; bounds and integrality are
explicit. `quicksum`, `Expr.dot`, and `Expr.from_terms` accumulate in one native
call. Native variable views and integer buffers avoid per-element Python
wrappers. General Python iterables are consumed within that same call.
`Expr.from_terms` and expert `rpx.lowlevel.affine` require an explicit model.

## Models and views

`Model.read(path)` reads LP, MPS, or MCM. `vars` and `rows` support names,
nonnegative indices, lazy iteration, `iter(limit=...)`, and explicit `to_list()`.
Rows expose `name`, `index`, `expression`, `lower`, `upper`, and `equality`.
Expression `terms` is a native mapping from coordinates to exact coefficients;
use `items()`, `values()`, or explicit `to_dict()`.

Model edits include `renamed`, `with_objective`, `with_bounds`,
`with_integrality`, `add_variable`, `add_row`, `replace_row`, `delete_rows`, and
`substitute`. In `with_bounds` and `replace_row`, an omitted bound is preserved;
an explicit `None` removes it. Elimination rejects references to removed
coordinates. By default it preserves eliminated bounds as fresh named rows.
Use `drop_rows` for author-selected defining rows.

`stats`, `row_activity`, `support`, `check_point`, and `same_formulation` execute
model-scale work in Rust. `to_dict()` explicitly materializes the model.
`write_mcm`, `to_mps`, and `write_mps` preserve exact arithmetic. Ordinary MPS
export refuses nonterminating decimal coefficients; `rational_literals=True`
is an explicit exact extension. `StandardMPSAdapter(model)` constructs a
standard decimal MPS target by exact scaling, moved bounds and, when needed,
an objective auxiliary. Its `proof()` returns an ordinary closed `Proof`.

## Sparse mappings, goals and facts

`scope.map(overrides, default="same_name")` expands name matches in Rust, with
explicit overrides taking priority. Without a default, every output coordinate
must be supplied. Unknown output names, uncovered variables and foreign spaces
fail immediately. Each call replaces the whole specification and invalidates
old Goal and MappingView handles. `scope.mapping` is a native view;
`scope.pullback(output_expression)` applies it in one native operation.

`scope.plan()` and `scope.obligations` return an `ObligationView`; indexing by
label returns a `Goal`. `scope.missing(kind=..., limit=...)` exposes the total
`count` while bounding displayed results. The Kernel's `visit_return` defines
the obligation order and semantics. Explicit witnesses take precedence, then
Kernel literal Exact rules and visible exact-expression facts. Hash matches
are confirmed by complete expression comparison. Within the nearest visible
scope, local derivations take priority over assumptions and then base facts;
base ties use a fixed reference ordering. Inspecting goals does not change witness
selection or certificate bytes. No semantic matching/search is performed.

`scope.row(name, side="lower"|"upper"|"equal")`, `lower`, `upper`, and `integer`
return owned `Fact` handles. The side is optional for unambiguous rows.
Fact arithmetic creates a `LinCombination`, separate from affine `Expr`.
`scope.prove(label_or_goal, by=...)` checks expression and kind and binds the
witness. `scope.derive.eq/le/int(by, expect=...)` returns intermediate facts.
Inequalities require nonnegative multipliers; integer facts require integer
multipliers; Kernel rules restrict constant terms. Zero operands are removed
before lowering. Eq facts can discharge Eq, Le, or Int goals for the same
zero expression.

Other author-selected derivations are `round`, `eqpair`, `box_le`, `eq_on_fixed`,
`rewrite`, `rewrite_many`, `substitution`, `substitution_fact`, `zero_sum`,
`parity_fix`, `subset_bounds`, and `plotkin`, all under `scope.derive`.
Definitions map named variables or handles to explicit equality facts.
Ordered substitution respects caller order. Batch algorithms run in Rust and
roll back the entire attempted derivation on failure. `zero_sum` returns a
mapping from variable names to equality facts. `drop` respects ancestry and
only invalidates facts within the dropping scope and its descendants.

## Scope lifecycle, split and Cases

Editable scopes accept maps and steps. Installing a split or lift fixes the
parent; children must finish themselves. Cases suspends its parent until the
explicit derivation branches conclude. Successful `finish()` seals a leaf.
Further mutation is rejected. Rebuilding a proof is the way to change a
finished proof. A failed derivation, lift or finish leaves no partial proof
steps. Model base-fact caches are not proof steps.

```python
left, right = proof.forward.split(x, at=0, kind="continuous")
left.map({"y": -x}).finish()
right.map({"y": x}).finish()
```

Continuous assumptions are `expr <= at` and `expr >= at`, sharing the boundary.
Integer split uses `expr <= at` and `expr >= at+1`, requires an integer threshold,
and an exact Int witness via `because`. A declared integer variable can supply
its own exact witness. Split shares its parent's coordinate space. Fact and Goal
handles additionally validate Proof and scope identity.

```python
s = proof.forward
cases = s.derive.cases(x, kind="Le", expect=x-1, integer=s.integer("x"))
cases.left.conclude(cases.left.derive.le(cases.left.assumption-1))
cases.right.conclude(cases.right.upper("x"))
result = cases.finish()
```

Each branch submits the common expression through `conclude(fact)`, or a proved
contradiction through `close_absurd(fact)`. Cases may nest. Primitive callbacks
are not part of the API.

## Constructive extensions

`scope.lift_interval(lower=..., upper=..., because=fact)` returns a `LiftResult`
with `.scope`, `.variable` for a single interval, and indexed generated handles.
`lift_intervals` takes `IntervalSpec(lower, upper, because)` values. Each indexed
interval exposes `.variable`, `.lower_rows`, `.upper_rows`.

Other typed inputs are `MenuSpec`, `SignedSpec`, `FlowSpec`/`FlowGroup`, and
`SubflowSpec`/`SubflowGroup`, passed to `lift_menus`, `lift_signed`, `lift_flow`, and
`lift_subflow`. They preserve the frozen Kernel's premise order. `None` in a
premise position requests a literal Exact witness. Every supplied Fact must be
visible and prove that exact premise.

Generated Menu handles expose `.options`, `.sum`, `.moment`; Signed handles
expose `.positive`, `.negative`, `.positive_activation`, `.negative_activation`,
`.flow`, `.activation`, `.positive_capacity`, `.negative_capacity`. Flow groups
expose `.commodities` with `.flows`, `.balances`, and group `.recovery`; Subflow
groups expose `.flows`, `.balances`, `.remainder_nonnegative`.

Parent expressions embed in extensions. Newly generated coordinates cannot
escape to parents or sibling extensions. Users do not compute coordinate offsets
or construct generated-layout dictionaries.

## Certificates, delivery and reports

A closed proof lowers once to a native immutable Certificate. The frozen RPA
disassembler and RPX encoder consume that same Certificate independently;
production never reparses generated RPA. `preflight()` and `compile()` share the
snapshot, exact byte counts and encoded model/proof files. File writes do not
materialize Python certificate dictionaries or large byte strings. Indexing a trace or certificate block returns a native `StepView`; use `.kind` for the instruction name or explicit `.to_dict()` for its full payload.

`compile()` returns a `Bundle`. `Bundle.open(directory)` accepts the single
`rpx.bundle/1` manifest schema. All artifact paths are relative, with SHA-256
and exact byte counts. A supplied target artifact is copied byte-for-byte and
compared against the full named target formulation. Bundles can be moved.
Publication prepares a sibling temporary directory, audits it, then renames it.
Different existing deliveries and file/symlink destinations are rejected.
Identical deliveries are reused only after rechecking their digests.

`Chain([bundle1, bundle2, ...])` checks complete adjacent model formulations.
`chain.compile(directory, target_artifact=..., source_artifact=...)` copies all
stages and endpoints into a self-contained `rpx.chain/1` package. Omitted endpoint
artifacts default to the endpoint MCM files. `Chain.open` verifies complete
manifest coverage and connection order.

`Bundle.verify(work=..., live_facts=..., depth=...)` invokes the Kernel afresh.
`Proof.verify(directory, ...)` is compile followed by Bundle.verify. Historical
`verification.json` receipts are never trusted as verification evidence.
`VerificationReport` has `status`, `guarantee`, `statistics`, `kernel`,
`artifact_audit`, `to_dict()`, and `raise_for_status()`. Resource exhaustion or
Kernel rejection never claims overall delivery success. Artifact mismatch is a
typed error independent of the Kernel theorem result.

## Diagnostics and expert inspection

Public errors include `CoordinateSpaceError`, `ScopeError`, `MappingError`,
`InvalidDerivationError`, `UnprovedGoalError`, `ResourceLimitError`,
`ArtifactMismatchError`, and `KernelRejectedError`, deriving from `CompilerError`.
Default model, expression and obligation displays are bounded; unresolved-goal
diagnostics show at most 20 entries. No Rich dependency is required.

`rpx.lowlevel` provides `Assembler(scope).linear(...)` and explicit ordered
`assign(...)`, format `assemble`/`disassemble`/`verify`, and native trace and
certificate views. They use the same Core and ownership checks. Whole materialization
requires `to_dict()` or `to_list()`. Certificate dictionaries are inspection
outputs, not another compiler implementation or authoring input format.

## Verification and measurements

Run `cargo test --workspace --locked`, Python unittest discovery, the tool tests,
and `make -C docs/rpx check-compiler-api`. `tools/cases.py check` verifies the
81 frozen case payloads and their RPA/RPX byte roundtrips. Recipes build new
proofs; matching historical instruction bytes is not an acceptance condition.
`tools/benchmark_compiler_api.py` measures load, mapping, expression construction,
finish, encode and verify independently, with wall time, process RSS and Python
allocation peaks. See [the refactor evidence](COMPILER_REFACTOR.md) for measured
results and the Kernel freeze check.
