# Python Compiler API

This is proof authoring over the current Kernel, not a new proof language.
The data path is **Python objects → typed Certificate → RPX → Kernel verification**.
There is no RPA intermediate, solver, proof search, or reformulation search.
Choose your strongest justified reformulation first. Supply its mathematical
maps and nontrivial derivations; the compiler handles exact arithmetic, scopes,
model edits, obligation ordering, serialization, and verification feedback.

## Setup and model readback

From the Kernel checkout:

```sh
cargo build --release
PYTHONPATH=python python3 your_proof.py
```

In an evaluation workspace, the harness has already configured `PYTHONPATH`
and `KERNEL_RPX`; import the package directly in the persistent Python tool.
Do not call any assembly command.

```python
from kernel_compiler import Model, Expr, Proof, Builder, Variable, Row, exact

source = Model.load("input/model.mps")  # Kernel's own exact MPS/LP/MCM reader
source.stats()                         # variables, rows, nonzeros, integers
x = source.var("x")                    # affine coordinate expression
source.vars[source.var_index["x"]]     # name, integer, lower, upper
source.row("capacity")                 # Row(name, expr, lower, upper)
source.support("capacity", names=True)
source.row_activity("capacity")        # exact box lower/upper, None if unbounded
source.column_incidence()              # list of (row index, exact coefficient)
```

Scalars accept `int`, `Fraction`, or exact decimal/rational strings, including
scientific notation. Float input is rejected. Sparse affine expressions support
`+`, `-`, scalar `*`, `/`, `.constant`, `.terms`, `.coefficient(i)`,
`.substitute({index: Expr})`, `.to_json()`, and `Expr.from_json(data)`.
`Expr(3, {0: "1/2", 2: -1})` means `3 + x[0]/2 - x[2]`.
Expressions use the current model's coordinate order; use names when mapping
between different models.

## Target construction and audit

Models are edited by returning a new model. These operations record an edit
ledger, which is authoring metadata; it never substitutes for a correctness proof.

```python
target = source.substitute({"y": 2*source.var("x")}, drop_rows=["definition"])
target = target.delete_rows(["redundant"])
target = target.add_row("new_cut", target.var("x") + target.var("z"), upper=1)
target = target.replace_row("gate", expr=target.var("x")-target.var("a"), upper=0)
target = target.with_bounds("x", lower=0, upper=1)
target = target.with_integrality(["x"], False)
target.ledger.to_json()
source.diff(target)
target.write_mps("output/reformulated.mps")
target.write_mcm("output/target.mcm")
```

Substitutions are simultaneous in the original source coordinates. Elimination
renumbers all retained coordinates and rewrites rows and objective. Finite
bounds of eliminated variables are preserved as named rows by default; to
remove them explicitly use `preserve_bounds=False` and prove that removal.
No transformation is assumed to preserve integrality automatically. Explicitly
declare and prove the intended integer-domain relation.

You can also load an independently produced target MPS/LP, or construct a
`Model(name, [Variable(...)], [Row(...)], objective=Expr(...))` directly.
MCM supports all exact rationals. Standard MPS export uses exact terminating
decimals and raises on nonterminating rationals; do not round coefficients.
`rational_literals=True` is available for Kernel-only MPS readers, not standard
solver delivery. Row constants are folded into MPS right-hand sides.

## Contracts, complete maps, and obligations

Each directional claim is a total map from every feasible input to a feasible
output. You supply an expression for **every output coordinate**. Projection
only states observations that are preserved; it does not replace the full map.

```python
proof = Proof(source, target)
forward = proof.claim(mapping={v.name: source.var(v.name) for v in target.vars},
                      integers=True, objective="Equal", projection="retained")
reverse = proof.claim(reverse=True, mapping={...}, integers=True,
                      objective="Equal", projection="retained")
```

`mapping="identity"` matches all output variables by name. Mapping dictionaries
must cover exactly all output names; a list follows output coordinate order.
`projection="retained"` pairs shared variable names. You can supply explicit
`[(input_name, output_name)]` pairs and `affine_projection=[(input_expr, output_expr)]`.

For a genuine affine bijection, declare both complete maps up front:

```python
forward, reverse = proof.bijection(forward_map, reverse_map,
                                   integers=True, projection="retained")
```

This requests **both inverse compositions**, not just inclusion. To certify LP
equivalence too, add another pair with `integers=False`. Integer strengthening
often needs integer forward/reverse claims and only reverse LP inclusion; do
not claim full LP equality unless you actually prove it.

`claim` also accepts independent `input_integers` / `output_integers`,
`objective="NonIncreasing"` or `"None"`, `inverse=claim_index`,
`input_objective_lower=q`, `input_objective_level=q`, and `input_halfspace=expr`.
An objective level/halfspace restricts the actual input domain; it does not
establish whole-model equivalence or attainment. The Kernel prepares that scope.

```python
goals = forward.obligations   # Kernel-owned ordered list, not Python's guess
[(g.label, g.kind, g.expression) for g in goals[:10]]
forward.missing()             # only currently undischarged goals
forward.check("row.upper[new_cut]", supplied_fact)
forward.complete()           # complete Return or BuildError with named missing goals
reverse.complete()
result = proof.verify("output", committed_model="output/reformulated.mps")
assert result["status"] == "VERIFIED", result
```

Every goal has `.index`, `.kind` (`Le`, `Eq`, `Int`), `.expression`, `.origin`,
and `.label`. Labels include `variable.lower[x]`, `variable.upper[x]`,
`variable.integer[x]`, `row.equal[definition]`, `row.lower[r]`, `row.upper[r]`,
`objective.equal`, `objective.non_increasing`, `projection[i]`, and `inverse[i]`.
Inspect actual labels from the plan when assigning witnesses. `complete` accepts
`witnesses={label_or_index: Fact}`, or use `.check(label, Fact)` in advance.

Automatic discharge only reuses an **identical** existing model/derived fact or
an exact tautology: zero equality, nonpositive constant inequality, or an affine
integer expression with integer coefficients over declared integer input vars.
It does not search for combinations, branches, witnesses, or transformations.
For a scaled/opposite fact, explicitly use `lin` with the required multiplier.

## User-authored derivations

Proof builders return `Fact` handles containing the exact expression, kind,
wire reference, and scope. Use original names for model facts:

```python
b = forward
b.lower("x"); b.upper("x"); b.integer("x")
b.row("eq_row")                  # Eq for equality, otherwise the only finite side
b.row("ranged", side="Lower")   # ranged rows require explicit side
b.ref("RowUpper", "ranged")
f = b.lin("Le", [(b.row("r"), 1), (b.lower("z"), 3)], expect=desired_expr)
f = b.le([...], constant=-1)      # convenient Le / Eq / Int wrappers
e = b.eq([(b.row("eq_row"), -1)])
z = b.int([(b.integer("x"), 1)], constant=2)
rounded = b.round(le_fact, int_fact)
equality = b.eqpair(positive_le, negative_le)
b.rewrite(old_fact, {"pivot": proved_definition_eq}, expect=desired_expr)
b.batch(instances, lambda builder, item: your_template(builder, item))
b.drop(unneeded_local_fact)
```

`rewrite` performs only the explicitly supplied pivot eliminations. It combines
the old fact with your proved equalities using exact cancellation coefficients.
This is useful for substituted rows, eliminated bounds, and objective equations.
Linear rules check kinds and signs before emitting: Eq uses only Eq premises;
Le uses arbitrary Eq multiples and nonnegative Le multiples; Int uses Eq
premises and integer multiples of Int premises. Round requires identical terms
in its Le and Int premises. `expect=` detects a residual error at authoring time.

Local exhaustive cases export a single common proposition:

```python
fact = b.cases(b.model.var("a"), kind="Le", expect=goal,
    left=lambda branch, a_le_zero: branch.le([...], expect=goal),
    right=lambda branch, one_minus_a_le_zero: branch.le([...], expect=goal))
```

Default `integer=True` automatically references the input variable's declared
integrality. For a non-variable integer split supply the exact Int Fact.
For real splitting use `integer=None`; assumptions are `e<=0` and `-e<=0`.
Callbacks receive a scoped child builder and the new assumption. They return
the common Fact or `branch.absurd(contradiction_fact)`. Facts from sibling
branches cannot leak. Nest ordinary callbacks for arbitrary case trees.
`branch.binary_value(name, 0_or_1, assumption)` derives a fixed binary equality.

Whole-map splitting can use different maps in its branches:

```python
b.split(split_expr, integer=int_fact,
        left=lambda scope, assumption: forward.complete(scope=scope, mapping=left_map),
        right=lambda scope, assumption: forward.complete(scope=scope, mapping=right_map))
```

`scope.close_absurd(fact)` closes an infeasible domain. Existing Plotkin facts
are available with `b.plotkin(bits=...,distance=...,variables=[(index,code),...],cliques=[Fact,...])`.

## Constructive scopes and every frozen proof variant

Interval, menu, signed, flow, and subflow extensions use the **existing Kernel
builders** for exact generated coordinates, rows, and premise expressions.
Supply the old-scope proofs; use the returned model's generated names/indices:

```python
scope = reverse.intervals([{"lower": [Expr(0)], "upper": [reverse.model.var("x")],
                            "checks": [reverse.lower("x")]}])
z = scope.model.var(scope.generated_variables[0])
reverse.complete(scope=scope, mapping={"x": scope.model.var("x"), "y": z})
```

Other calls are `.menus(list_of_MenuWitness)`, `.signed(list_of_SignedWitness)`,
`.flow(FlowWitness)`, `.subflow(SubflowWitness)`. Witnesses use the frozen
fields documented in `compiler/FORMAT.md` (repository `docs/FORMAT.md`):
menu `{maximum_index,activation,index,checks}`, signed
`{capacity,flow,activation,checks}`, flow/subflow `{nodes,arcs,groups}`.
Expressions and checks may be Python Expr/Fact handles; lowering is automatic.
`scope.generated_variables`, `.generated_rows`, `.preparation` expose exact
Kernel preparation metadata. Preparation alone establishes no premise.
Affine `inverse` is for root Return maps; constructive bijections use the
existing separate injectivity witness and composition obligations.

Every frozen RPX feature is also accessible without a high-level convenience
wrapper via `compile_certificate(source, target, certificate, request, directory)`.
It accepts the existing Certificate data structure directly as a Python dict,
with Expr/Fact values automatically lowered; no source language is involved.
Use this for explicit injectivity, improvement, complex point refutations, or
other valid variants while higher-level conveniences evolve. There are **no
restrictions to an easy subset of reformulations**. An encoding success never
means a proof is accepted; call `Kernel.verify` on the actual artifacts.

`proof.feasible_point(values, target=False, integers=True, objective=None)`
adds a complete feasible point contract. `proof.add_point(claim,values,refutation=...)`
supports Strictness, FiberStrictness, and ImageExclusion;
`proof.add_improvement(claim,block)` and
`proof.add_bijection(forward_index,reverse_index,injectivity)` retain their
existing Kernel meanings. Use `Model.check_point` for exact authoring diagnostics.

## Delivery, failures, and reproducibility

`Proof.verify("output", committed_model="output/reformulated.mps")` writes
`source.mcm`, `target.mcm`, `certificate.json`, `proof.rpx`, `request.json`,
`delivery.json`, and `verification.json`. The request retains every explicit
claim, point, improvement, and bijection. Keep a runnable `output/proof.py`.
`Proof.compile` emits the same artifacts without verifying. `Proof.preflight`
reports JSON size/depth and counts; actual Kernel work/live facts appear in
verification. `verify_bundle(manifest)` verifies every declared piece.

Inspect `result["status"]`, `error`/`message`, `code`, and `location` on failure.
`BuildError` names an incomplete/mismatched proof site; `KernelError.report`
retains the native report when preparation or compilation fails. Verification
returns the native status so INVALID and RESOURCE_LIMIT remain distinct.
Change your derivation or report a concrete compiler gap; preserve the strongest
justified target if certification is incomplete. Never weaken the requested
mathematical claim merely to obtain VERIFIED.

Runnable end-to-end examples are in `python/tests/test_proof.py`, including
affine elimination, inverse identities, integer rounding, binary strengthening
with reverse LP inclusion and a strictness point, and non-injective interval
projection. These are general mathematical examples, not benchmark solutions.
