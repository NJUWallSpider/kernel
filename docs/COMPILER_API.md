# Python Compiler API

This is proof authoring over the current Kernel, not a new proof language.
The data path is **Python objects → typed Certificate → RPX → Kernel verification**.
There is no RPA intermediate, solver, proof search, or reformulation search.
Choose your strongest justified reformulation first. Supply its mathematical
maps and nontrivial derivations; the compiler handles exact arithmetic, scopes,
model edits, obligation ordering, serialization, and verification feedback.

For an affine elimination justified by your equality rows, the usual proof
authoring pattern is:

```python
source = Model.load("input/model.mps")
target = source.substitute(your_replacements, drop_rows=your_definition_rows)
proof = Proof(source, target)
f, r = proof.bijection(your_forward_map, your_reverse_map)
f.substitution({pivot: f.row(definition) for pivot, definition in your_pivot_rows.items()})
f.complete(); r.complete()
target.write_mps("output/reformulated.mps")
result = proof.verify("output", committed_model="output/reformulated.mps")
```

The names, maps, pivots, equations, and transformation are your proof input.
`substitution` mechanically rewrites the affected facts and derives equality
goals that reduce literally to zero under those supplied equations. It does
not find the substitutions or solve a linear combination search. Any remaining
bound, objective, integrality, or other obligation stays visible in `missing()`.

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
source.coefficient_stats()             # exact signed ranges and magnitude spans
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
`expr.summary(max_terms=8)` gives a bounded preview with the full term count;
very large scalar values appear as signed bit lengths. It is inspection
metadata, not a proof expression. Use `to_json()` for complete exact values.

## Target construction and audit

`Model.load` keeps the Kernel as the MPS/LP/MCM parsing and validation authority,
then reads its canonical MCM with bounded binary buffers directly into exact
Python objects; it does not export or materialize a complete intermediate JSON
model. Non-JSON inputs have an owned canonical snapshot at `model.path`, including
MCM inputs. `model.close()`, context-manager exit, or garbage collection releases
that snapshot; the original input is never modified or removed. Canonical `.json`
input retains its existing Python reader and `path=None` behavior.

Models are edited by returning a new model. These operations record an edit
ledger, which is authoring metadata; it never substitutes for a correctness proof.
Structural attributes (including both `vars` / `variables` aliases, indices,
rows, objective, name, and ledger) are read-only. Use the edit methods below;
direct reassignment would make coordinate maps and cached proof plans stale.

```python
target = source.substitute({"y": 2*source.var("x")}, drop_rows=["definition"])
target = target.delete_rows(["redundant"])
target = target.add_row("new_cut", target.var("x") + target.var("z"), upper=1)
target = target.add_variable("slack", integer=False, lower=0, upper=None,
                             reason="caller-selected auxiliary coordinate")
target = target.replace_row("gate", expr=target.var("x")-target.var("a"), upper=0)
target = target.with_bounds("x", lower=0, upper=1)
target = target.with_integrality(["x"], False)
target.ledger.to_json()
source.diff(target).to_json()
target.write_mps("output/reformulated.mps")
target.write_mcm("output/target.mcm")
```

Both `target.ledger` and `source.diff(target)` are `EditLedger` tuples,
iterable over `Edit` objects with `.kind`, `.subject`, `.before`, `.after`,
and `.reason`. Their `to_json()` returns a **list** of edit dictionaries,
not a mapping with `.keys()` / `.items()`. The ledger records the edit history;
`diff` compares the two complete named formulations.
`add_variable(name, *, integer=False, lower=0, upper=None, reason=None)` appends
one coordinate and returns a new Model. Use `target.var("slack")` to reference
the appended coordinate; supply its map and proof obligations explicitly.

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

When your chosen target contains nonterminating rational coefficients, explicitly
select a standard MPS representation adapter:

```python
adapter = authored_target.standard_mps_adapter(
    objective_auxiliary=True, objective_name="__mps_objective",
)
adapter.source                 # the unchanged authored target
adapter.target                 # a new immutable model, ready for standard MPS
adapter.report                 # JSON-compatible exact costs and changes
adapter.target.write_mps("output/reformulated.mps")
representation_proof = adapter.proof()
result = representation_proof.verify(
    "output/representation", committed_model="output/reformulated.mps",
)
```

The adapter folds row constants into RHS values and scales each row only by the
LCM of denominator parts remaining after removing factors 2 and 5. A row whose
coefficients and folded RHS values already have finite decimals keeps scale 1.
Nonterminating variable bounds become separate positively scaled lower/upper
rows, including equal fixed bounds. Original variables, names, order and integer
declarations remain; only the moved bound sides become absent declarations.
If the full objective has a nonterminating coefficient or constant, the adapter
adds a free continuous value coordinate `t`, a scaled equality `t=f(x)`, and
objective `t`. Setting `objective_auxiliary=False` rejects that objective rather
than rounding it. Generated names avoid collisions.

`adapter.proof()` produces four ordinary Equal affine inverse claims: MI forward,
MI reverse, LP forward, LP reverse, at indices 0 through 3. Its complete maps are
the identity on original variables, with `t=f(x)` forward when needed, and the
original-coordinate prefix reverse. Its only generated proof steps are `Lin`
scalings of the original row/bound facts and the defining equality. No proof
search, rounding, or solver runs occur. The constructor checks actual Kernel
standard MPS readback against the complete target. Add this representation proof
as a separate explicit stage with `write_chain` to preserve an already authored
proof without rewriting its leaves.
If a complete row scale exceeds one RPX scalar, the proof applies consecutive
positive scaling chunks derived by gcd from the given original denominators;
the reverse proof divides by those chunks in reverse order. Each encoded scalar
fits the frozen 13,600-bit component limit. Constant folding retains the minimal
row scale, and the generated model still has to satisfy actual Kernel readback.

The report contains `before`/`after` counts, `added` variable/row/nonzero counts,
`row_scales` for scales above 1, every `bound_moves` record, an optional
`objective_auxiliary` definition, source/target exact `coefficient_stats`, and
`mps_readback` status/size. It describes representation costs; it does not predict
solver performance. A multi-chunk row scale also records its `proof_chunks`.
Existing name, standard-format text, rational, model and
proof resource limits still apply; the adapter reports failure without changing
the authored model. Ordinary `write_mps` never selects this adapter automatically.

`coefficient_stats()` returns objective coefficients/constant, matrix
coefficients, and row-constant summaries. Each summary includes exact signed
minimum/maximum values, positive/negative counts and ranges, nonzero magnitude
minimum/maximum, and `magnitude_span = max(abs(q))/min(abs(nonzero q))`.
Rational outputs are canonical strings; empty ranges are `None`. This allows
inspection of the chosen representation's numeric scale without changing the
model or prescribing a transformation.

## Contracts, complete maps, and obligations

For supplied proofs, use these entry points before reading package internals:

| Authoring task | API |
| --- | --- |
| Declare paired full-domain contracts before supplying branch or lift maps | `proof.correspondence(projection=your_observations)` |
| Derive selected coordinate zeros from one supplied nonnegative zero-sum witness | `builder.zero_sum(fact, zeros=proved_zeros, scale=1, coordinates=None)` |
| Rewrite a batch of given facts using selected equality pivots | `builder.rewrite_many(facts, definitions)` |
| Elaborate literal-zero equality obligations from selected definitions | `claim.substitution(definitions)` |
| Reconstruct a given goal from its caller-proved residual | `builder.derive_substitution(goal, definitions, residual)` |
| Prove a given inequality using the actual input variable bounds | `builder.box_le(goal)` |
| Give piecewise maps or constructive reconstruction witnesses | `builder.split(...)`, `.intervals(...)`, `.menus(...)`, `.signed(...)`, `.flow(...)`, `.subflow(...)`; `claim.complete(scope=scope, mapping=...)` |
| Inspect unresolved obligations without printing full affine vectors | `[(g.label, g.kind, g.expression.summary()) for g in claim.missing()[:8]]` |
| Inspect contract scope and observation counts without dumping Request | `proof.contract_summary()` |

Choose the intended mathematical relation independently of its proof template.
An affine bijection is an optional stronger contract. Two unrestricted total
directions connecting the same two declared feasible domains, with non-increasing
canonicalization and equal-objective reconstruction, establish equal optimal
values; full pointwise inverse identities are a separate assertion. Use the
relation your argument intends and establishes. A reconstruction need not be
one affine formula in the original coordinates: splits allow branch maps,
and constructive scopes supply witnessed coordinates for a complete Return map.
The sections below explain their premises and exact certified scope.

Declare the directions first when their maps will use branches or constructive
witnesses:

```python
forward, reverse = proof.correspondence(projection=your_observations)
# In each supplied split callback, or after a constructive lift:
forward.complete(scope=your_forward_scope, mapping=your_complete_forward_map)
reverse.complete(scope=your_reverse_scope, mapping=your_complete_reverse_map)
```

`split(...)` calls your branch proofs with their own scopes; each branch must
complete its full map or close a contradiction. A constructive lift returns the
scope whose generated coordinates may occur in that terminal map. Omitting the
initial maps does not select a transformation, witness, or proof for you.

Definitions are caller-selected ordered pivot/equality pairs. Batch helpers
reuse the same sparse elimination plan; they do not discover pivots or missing
lemmas. When writing your own large model-construction loop, compute unchanged
membership sets and dependency metadata once outside the loop.

Each directional claim is a total map from every feasible input to a feasible
output. You supply an expression for **every output coordinate**. Projection
only states observations that are preserved; it does not replace the full map.
At each Return those expressions are affine in that proof scope's coordinates;
the whole proof may use different branch maps or generated witness coordinates.
Declare a claim without `mapping` when its complete map will be supplied later
to `claim.complete(scope=your_scope, mapping=your_complete_map)`.

`proof.contract_summary(max_items=8)` shows domains, directions, objective
relations, inverse indices, actual observation counts and a bounded sample of
named coordinate pairs. It also shows restrictions, point/improvement kinds,
and paired-domain bijection references. It does not complete a proof or request
Kernel obligations. The returned `request_summary` in `proof.verify(...)` and
the saved delivery/verification receipts contains the same bounded scope
metadata. The complete Request remains authoritative; a summary alone is not
a verification result. `input_objective_lower` is proved over the declared
input domain: it is global when unrestricted and conditional when an objective
level or halfspace restricts that domain. It does not add a restriction itself.
Use this summary plus the successful receipt when writing the
final report rather than reading a multi-megabyte Request to count observations.

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

For dominance/canonicalization with changed auxiliary fibers, use two total
maps rather than imposing inverse identities:

```python
f, r = proof.correspondence(forward_map, reverse_map,
                           projection=[("core_decision", "core_decision")])
```

Either map may be omitted and supplied later to `complete(scope=..., mapping=...)`.
Its explicit defaults are forward NonIncreasing and reverse Equal objective
relations; you can change either relation. This proves optimal-value and
feasibility correspondence when both maps are verified. Preserve observations
that your mathematical theorem actually requires. `projection="retained"`
requests equality for **every common name**, including auxiliary variables;
use it when that stronger condition is intended and true. Omitting an auxiliary
observation never omits its feasibility checks: both maps still cover every
output variable, bound, integrality requirement, and row.

`claim` also accepts independent `input_integers` / `output_integers`,
`objective="NonIncreasing"` or `"None"`, `inverse=claim_index`,
`input_objective_lower=q`, `input_objective_level=q`, and `input_halfspace=expr`.
An objective level/halfspace restricts the actual input domain; it does not
establish whole-model equivalence or attainment. The Kernel prepares that scope.
Its facts are available as `claim.domain.objective_level` and
`claim.domain.halfspace`; absent restrictions have `None` handles.

```python
goals = forward.obligations   # Kernel-owned ordered list, not Python's guess
[(g.label, g.kind, g.expression.summary()) for g in goals[:10]]
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
`objective.equal`, `objective.non_increasing`, `projection[i]`, and `inverse.coordinate[x]`.
Inspect actual labels from the plan when assigning witnesses. `complete` accepts
`witnesses={label_or_index: Fact}`, or use `.check(label, Fact)` in advance.

Automatic discharge only reuses an **identical** existing model/derived fact or
an exact tautology: zero equality, nonpositive constant inequality, or an affine
integer expression with integer coefficients over declared integer input vars.
It does not search for combinations, branches, witnesses, or transformations.
For a scaled/opposite fact, explicitly use `lin` with the required multiplier.

`missing()` and `complete()` use the Kernel's Return walker and exact fact
reuse through `resolve-return`. They do not materialize every already-discharged
goal expression in Python; detailed expressions are returned for missing goals.
Explicit `.obligations` / `.plan()` still expose the complete goal list when
you need it. Every completed Return retains its full map and ordered checks,
and the verifier independently checks every obligation.

The Proof stores an owned immutable MCM snapshot once per Model. Certificate
creation reuses completed checks while the map, contract, visible fact/drop
revisions, supplied witnesses, and opposing compositions remain unchanged.
Changes revalidate the terminal against the current complete contract. These
caches remove repeated bookkeeping; they do not search for a proof or replace
Kernel verification.

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
b.rewrite_many(your_facts, your_ordered_pivot_equalities)
b.derive_substitution(your_goal, your_ordered_pivot_equalities, proved_reduced_fact)
b.substitution(your_ordered_pivot_equalities, goals=your_equality_expressions)
b.combine_rows("Le", {"packing": 1, ("ranged", "Upper"): 2}, expect=desired_expr)
b.box_le(your_inequality_expression) # supplied goal, declared variable bounds only
b.eq_on_fixed(desired_expr, fixes={"x": proved_x_equals_constant})
b.zero_sum(your_zero_sided_fact, zeros=proved_zeros, scale=1)
b.batch(instances, lambda builder, item: your_template(builder, item))
b.drop(unneeded_local_fact)
```

`zero_sum(fact, *, zeros=None, scale=1, coordinates=None)` elaborates one
caller-selected zero-sum argument. Supply a visible Eq, or a Le with positive
scale. The fact must have constant zero. The helper cancels only the supplied
one-coordinate zero Eq facts at indices occurring in this fact; remaining
coefficients must be positive and their declared lower bounds nonnegative.
A single remaining coordinate in an Eq needs no bound or sign condition.
The result maps coordinate indices to exact Eq facts `x[i]=0`. `coordinates`
optionally selects a sequence of remaining names/indices; otherwise all remaining
coordinates are returned. The `zeros` mapping accepts indices and names (index
lookup first), including scaled zero equalities. It is never scanned in full.
Only ordinary Lin/EqPair steps are emitted. For m input terms and k selected
coordinates in an n-term residual, the generated proof contains O(m+k*n) premises.

You choose the witness rows, their order and orientation; this does not discover
a zero closure or choose a reformulation. For example:

```python
zeros = {}
for row_name, orientation in your_ordered_zero_witnesses:
    zeros.update(b.zero_sum(b.row(row_name), zeros=zeros, scale=orientation))
```

For your selected alias equations, cancel that same zero map in one batch,
then check the exact pair relation as part of the ordinary Eq construction:

```python
# your_aliases is a sequence of (removed_name, retained_name, equality_row_name).
reduced = b.rewrite_many([b.row(row) for _, _, row in your_aliases], zeros)
aliases = {}
for (removed, retained, _), fact in zip(your_aliases, reduced):
    coefficient = fact.expression.coefficient(b.model.var_index[removed])
    aliases[removed] = b.eq([(fact, 1/coefficient)],
                           expect=b.model.var(removed)-b.model.var(retained))
definitions = dict(zeros)
definitions.update(aliases)
```

This checks each supplied residual exactly without rebuilding a set of every
known zero for every alias. `rewrite_many` validates the shared pivot map once;
it does not find aliases or choose representatives.

`rewrite` performs only the explicitly supplied pivot eliminations. It combines
the old fact with your proved equalities using exact cancellation coefficients.
This is useful for substituted rows, eliminated bounds, and objective equations.
Pivots are applied once in the supplied dictionary order. A later equality
that reintroduces an earlier pivot leaves that coordinate in the residual.
`rewrite_many` validates one ordered plan for the supplied fact sequence;
`substitution` reuses one plan over affected model facts and supplied Eq goals.
These helpers update sparse coefficients without copying the whole expression
at each pivot. Use them for wide goals and batches rather than repeatedly
adding/scaling immutable Expr objects. They are available in generated and
case scopes as well as root claims. A ClaimBuilder's `substitution` also supplies
its currently missing Kernel Eq obligations through the compact resolver;
it does not materialize the full obligation list. Goals that do not reduce
exactly to zero stay unproved.
`rewrite` / `rewrite_many` retain separate ordered positions for name/index keys
that denote the same coordinate. The existing ClaimBuilder `substitution`
canonicalizes such aliases: the last equation wins at the first key's position.

`derive_substitution(goal, definitions, residual, kind=None)` works in the
opposite direction: reduce your selected goal using the selected ordered Eq
pivots, check that it is exactly the supplied proven residual, then reverse the
cancellation coefficients in one ordinary Lin step. For example, given a row
`x-2*y=0` and the declared upper bound `y<=1`:

```python
x, y = b.model.var("x"), b.model.var("y")
definitions = {"x": b.row("x_equals_twice_y")}
residual = b.le([(b.upper("y"), 2)], expect=2*y-2)
upper_x = b.derive_substitution(x-2, definitions, residual)
```

The default kind is the residual's kind. An explicit kind uses the complete Lin
premise restrictions below. The helper never guesses a residual or chooses an
equation, and a scope/drop/residual mismatch is rejected before emitting its
step. `derive_substitution_many([(goal, residual), ...], definitions, kind=None)`
reuses one plan; each item defaults to its own residual kind, while an explicit
kind applies to every item.
Linear rules check kinds and signs before emitting: Eq uses only Eq premises;
Le uses arbitrary Eq multiples and nonnegative Le multiples; Int uses Eq
premises and integer multiples of Int premises. Round requires identical terms
in its Le and Int premises. `expect=` detects a residual error at authoring time.

`box_le(expr)` elaborates the supplied inequality from declared variable bounds.
It selects the upper bound for a positive coefficient and the lower bound for
a negative coefficient, checks the exact box maximum is nonpositive, and emits
one ordinary Lin step. An unavailable bound or positive maximum raises
`BuildError` before any step is emitted. It does not use rows, discover a cut,
or search for stronger bounds.

A failed box check leaves the inequality unproved by this sufficient template;
it does not refute it on the model's full constrained feasible domain. Preserve
your intended map while checking your mathematical argument. Supply your chosen
row combination with `le`/`combine_rows`, equality substitutions with a proved
residual via `derive_substitution`, or an explicit `cases` argument when those
are the needed witnesses. The compiler does not discover those witnesses.

Integer-valued expressions need not be declared integer variables. Prove their
integerness from your equations and known Int facts, or export an Int conclusion
from exhaustive cases:

```python
# Input row 'definition' proves x-y=0; y is integer, x is continuous.
integer_x = b.int([(b.row("definition"), 1), (b.integer("y"), 1)],
                  expect=b.model.var("x"))
# A supplied inequality x <= 9/10 plus this Int fact rounds to x <= 0.
rounded = b.round(b.row("capacity"), integer_x)
# Cases also accept kind="Int" and require the SAME expression in both branches.
```

`b.integer(name)` means a model declaration; `b.int(...)` proves integerness of
an arbitrary affine expression on the feasible domain. These are different
sources of Int evidence. No bound rounding or derived integerness is automatic.
`b.parity_fix(variable, supplied_equality)` elaborates an explicit modular
certificate: the chosen binary has an odd coefficient, all other coefficients
are even over integer variables, and the equality constant is integral. It
uses ordinary Lin/Int/Round/EqPair steps, performs no modular search, and returns
the proved fixed-value equality.

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

For an explicitly chosen list of binary coordinates, `binary_cases` expands
the branch plumbing and gives your leaf proof a name-to-Eq fixing dictionary:

```python
fact = b.binary_cases(your_binary_variables, kind="Int", expect=your_common_goal,
                      prove=your_leaf_proof,
                      integers={"selected_continuous_var": your_proved_int_fact})
# your_leaf_proof(scope, fixes) must return the common Fact or a Contradiction.
# fixes[name] proves the exact expression x-bit = 0 in this leaf only.
```

Every selected coordinate needs finite declared bounds within `[0,1]` and an
actual Int Fact: active declared integrality or a supplied exact witness.
Duplicate coordinates and nonunit expressions are rejected. Narrower bounds
are weakened by explicit linear steps before deriving `x-bit=0`. All `2**n`
leaves call your callback, including branches you prove impossible; the helper
does not select variables, prune branches, or supply a mathematical lemma.
An empty list calls your proof once and returns its checked conclusion.

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
z = scope.interval(0).variable
reverse.complete(scope=scope, mapping={"x": scope.model.var("x"), "y": z})
```

For each interval with `p` lower and `q` upper expressions, supply exactly
`p*q` checks. Check `i*q+j` proves `Le(lower[i]-upper[j])`, in lower-major,
upper-minor order. For two of each, the order is `(lower[0],upper[0])`,
`(lower[0],upper[1])`, `(lower[1],upper[0])`, `(lower[1],upper[1])`.
Retain duplicates and zero propositions; an empty bound side needs no checks.
The generated variable is continuous, with its bounds expressed by the returned
rows. The lift does not grant integrality.

Other calls are `.menus(list_of_MenuWitness)`, `.signed(list_of_SignedWitness)`,
`.flow(FlowWitness)`, `.subflow(SubflowWitness)`. Witnesses use the frozen
fields documented in `compiler/FORMAT.md` (repository `docs/FORMAT.md`):
menu `{maximum_index,activation,index,checks}`, signed
`{capacity,flow,activation,checks}`, flow/subflow `{nodes,arcs,groups}`.
Expressions and checks may be Python Expr/Fact handles; lowering is automatic.
Menu and Signed lifts require enabled integer **input** mode. For a menu with
`K=maximum_index`, `A=activation`, and `I=index`, the six checks, in order, prove:

1. `Le(-A)`
2. `Le(A-1)`
3. `Int(A)`
4. `Le(-I)`
5. `Le(I-K*A)`
6. `Int(I)`

For a signed decomposition with nonnegative exact `C=capacity`, `F=flow`, and
`Z=activation`, the five checks, in order, prove:

1. `Le(-Z)`
2. `Le(Z-1)`
3. `Int(Z)`
4. `Le(F-C*Z)`
5. `Le(-F-C*Z)`

The Int checks may be explicitly derived facts; the expressions need not be
declared integer coordinates. Use `"Exact"` only when its narrow tautology or
declared-integrality rule proves the required expression.
Per-instance handles use the native preparation layout, so you do not calculate
coordinate or row offsets. Instance indices follow your supplied witness order:

| Accessor | Returned expressions and scoped Facts |
|---|---|
| `scope.interval(i)` | `.variable` Expr; `.lower_rows`, `.upper_rows` Le Fact tuples |
| `scope.menu(i)` | `.options` Expr tuple indexed by option value; `.sum`, `.moment` Eq Facts |
| `scope.signed_decomposition(i)` | `.positive`, `.negative`, `.positive_activation`, `.negative_activation` Exprs; `.flow`, `.activation` Eq Facts; `.positive_capacity`, `.negative_capacity` Le Facts |
| `scope.flow_group(i)` | `.source` node; `.commodities`; `.recovery` Eq Fact tuple indexed by supplied arc order |
| `scope.commodity(group, i)` | `.sink` node, exact `.demand`; `.flows` Expr tuple in arc order; `.balances` Eq Fact tuple in node order |
| `scope.subflow_group(i)` | `.source` node; `.flows` Expr tuple in arc order; `.balances` Eq Fact tuple in node order; `.remainder_nonnegative` Le Fact tuple in arc order |

For a menu, `item.sum` proves `sum(item.options) - activation == 0`, and
`item.moment` proves `sum(k*option[k]) - index == 0`. For a signed decomposition,
`item.flow` proves `positive - negative - original_flow == 0`; `item.activation`
proves `positive_activation + negative_activation - original_activation == 0`.
Flow recovery proves `sum(commodity.flows[arc]) - original_flow[arc] == 0`.
Subflow remainder facts prove `selected_flow[arc] - original_flow[arc] <= 0`.
All facts belong to the generated scope and remain visible in its descendants.
Using them in the old parent scope or an unrelated scope is rejected.
Variable reference helpers also accept a unit Expr directly, for example
`scope.lower(scope.menu(i).options[j])`, `scope.upper(z)`, and `scope.integer(z)`.
It must be exactly one current coordinate with coefficient 1 and constant 0;
the model must actually provide the requested bound or integer declaration.

`scope.layout`, `.generated_variables`, `.generated_rows`, and `.preparation`
also expose exact Kernel preparation metadata for inspection. Preparation alone
establishes no premise.
Affine `inverse` is for root Return maps; constructive bijections use the
existing separate injectivity witness and composition obligations.

```python
paired = proof.injectivity(forward)    # fresh Kernel-created paired domain
paired.goals                          # one input-coordinate equality each
# Supply derivations in paired.model using paired.row(...), paired.lin, cases, etc.
# your_coordinate_equalities contains one proved Eq Fact per paired goal.
paired.complete(witnesses={i: your_coordinate_equalities[i]
                          for i in range(len(paired.goals))})
proof.add_bijection(forward.index, reverse.index, paired)
```

The reverse Return automatically includes every Kernel composition obligation
for that declared bijection. Declare it before completing the reverse proof;
adding it later also refreshes terminal plans at compilation and exposes missing
checks. Paired variables and rows have their own generated names in paired.model.

Strict improvement witnesses have a high-level interface too:

```python
better = proof.improvement(positive_expr, target=False, integers=True,
                            margin={"Predicate": "1/2"}, mapping=your_improving_map)
# Author every output feasibility and objective-gap proof in better.
better.complete()
```

`{"Predicate":q}` demands an objective decrease of at least `q*positive_expr`;
`{"Constant":q}` demands a fixed positive margin. This is the existing V10
strict-domain contract, not a solver or an assertion that an optimum exists.

The actual domain is `positive_expr > 0`. Its weak consequence
`-positive_expr <= 0` is available as `better.domain.positive`, scoped
Assumption 0. Cases and terminal splits number their new assumptions after
that root fact. The weak fact does not assert strict positivity on its own and
cannot escape into an ordinary claim.

For a terminal branch that proves the exact root predicate is nonpositive,
use `scope.close_positive(fact)` with a Le or Eq Fact of `positive_expr`.
This emits the frozen `PositiveRefutation` terminal and excludes the branch
using the root's strict domain. For example:

```python
better.split(positive_expr, integer=None,
    left=lambda scope, nonpositive: scope.close_positive(nonpositive),
    right=lambda scope, nonnegative: better.complete(scope=scope, mapping=improving_map))
```

Both margin forms require `q > 0`. A predicate margin scales with the predicate;
it need not be a uniform positive constant near the domain boundary. A zero
predicate defines an empty strict domain and gives only a vacuous theorem,
without establishing nonemptiness, attainment, or a useful descent map.

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
Each generated file is written to an owned temporary file in the same directory
and then replaced; this is per-file replacement, not a whole-bundle transaction.
Existing symlinks/hardlinks do not redirect writes into
original artifacts. Failed encoding cleans its temporary output and preserves
the previous RPX file. After a failed attempt, use `verify_bundle` to check the
current artifacts against the manifest; an earlier verification receipt describes
its recorded hashes. A committed solver artifact must have a separate path
and inode from the reserved generated outputs.
When supplied, `committed_model` is read back and compared exactly with the proof
target (allowing coordinate/row order and folded row constants). MCM/MPS/LP use
the Kernel reader. Canonical model JSON uses the Python exact model reader;
the audit method names that reader instead of claiming Kernel format readback.
A different solver artifact is rejected, and its hash is recorded in delivery.
The returned and saved report includes `artifact_audit.status == "MATCHED"`
when that complete exact comparison succeeds, with the committed-artifact and
proof-target hashes. `artifacts` binds the actual MCM/RPX/Request files. This is
the standard-format serialization audit; inspect the native proof status
separately. It does not judge the usefulness of a reformulation or assertions
outside the submitted Request. Preserve the generated absolute paths in
`delivery.json`; add your relation without rewriting them. Portable custom
manifest paths passed to `verify_bundle` are relative to that manifest's directory.
`Proof.compile` emits the compiler artifacts without verifying. `Proof.preflight`
reports JSON size/depth and counts; actual Kernel work/live facts appear in
verification. `verify_bundle(manifest)` verifies every declared piece.
It also checks recorded artifact hashes and any declared committed model.

For successive reformulations, bind the already-written stage manifests explicitly:

```python
from kernel_compiler import write_chain, verify_bundle

# Compile each authored stage into its own directory, preserving its manifest.
for i, stage in enumerate(your_authored_stage_proofs):
    stage.compile(f"output/stage{i}")

manifest = write_chain(
    ["output/stage0/delivery.json", "output/stage1/delivery.json", "output/stage2/delivery.json"],
    "output/delivery.json",
    original_model="input/model.mps",    # optional first-source anchor
    committed_model="output/reformulated.mps",
    claim_paths={"mi_forward": [0, 0, 0], "mi_reverse": [1, 1, 1]},
)
result = verify_bundle(manifest)
```

Each stage manifest contains one piece. `write_chain` records absolute artifact
paths and every stage's source/target/RPX/Request SHA-256, including the stage
manifest itself; it does not copy the large files or verify their proofs.
Every stage's four proof-input hashes and the committed artifact hash are
mandatory for verification; an original anchor also requires its hash when
declared. Stage-manifest and other extra records are checked when present.
Keep the top-level destination distinct from every stage's manifest and artifacts;
the writer rejects aliases instead of overwriting a stage input.
Retain those records to preserve the writer's provenance: an unsigned hand-written
manifest with complete proof-input hashes establishes the submitted theorem,
without certifying that its metadata was inherited unchanged from an earlier author.
`verify_bundle` checks these hashes, verifies each stage with its own actual
coordinates, compares adjacent complete named formulations, and checks the last
target against the committed artifact. An optional original artifact is matched
only to the first source. Model NAME, coordinate/row order and folded row constants
may differ across exact joins; coefficients, names, domains and objectives must
match. Models are read and released one stage at a time.
Stage endpoints require Kernel-readable artifacts. The same-byte optimization
also requires the same reader family: `Model.load` dispatches `.json` first,
then MCM magic regardless of suffix, then case-insensitive `.lp`, then MPS.
Renaming MPS bytes to `.lp` or MCM bytes to `.json` cannot skip that reader.
JSON original/committed artifacts remain available for exact named comparison;
`composition.original_anchor_reader` and the final audit's reader fields identify
the actual readback, with a Python JSON audit method when appropriate.
The returned `artifacts` preserves all manifest records.
`artifact_audit.status == "MATCHED"` binds only the last complete proof target
to the committed artifact with their hashes. This serialization audit can match
even when a stage proof is invalid and the overall status is `INCOMPLETE`;
inspect `parts` and `composition` separately.

`claim_paths` labels are arbitrary. Each index array follows the original stage
order, including a reverse path; execution and observation composition reverse
that order for reverse claims. Every selected path must use one direction and
match its output/input integer modes exactly at each handoff. Invalid indices,
mixed directions or incompatible domains fail explicitly. Without paths, the
report verifies stages/joins and sets `composition.final_relation_derived=false`.
`composition.ordered_chain=true` is required; existing parallel bundles keep
their original semantics.

The report composes only the selected claims' coordinate observations, by name,
and never merges observations from different maps. It retains `Equal` only when
every objective is `Equal`, retains `NonIncreasing` when all objectives compare
and at least one is `NonIncreasing`, and retains `None` when any selected claim
has no objective comparison. Compatible forward/reverse paths can report
feasibility correspondence and equal optimal infima with conditional attainment
transfer when both objective comparisons exist. Common observations are the
intersection with the transposed completed reverse relation. Level/halfspace
restrictions stay verified locally with `composable=false`; a proved
`input_objective_lower` is recorded without restricting the domain. Affine
observations, inverse identities, full-model bijections, points and improvements
are not automatically inherited by the final model. A VERIFIED stage chain
therefore need not assert an unrestricted final relation.

`attack(proof, "output/attack", path_to_site, replacement=..., delete=False)`
mutates only the selected certificate containers while keeping the Request fixed;
it returns the native rejection and whether it matched the expected status.
This avoids copying an entire large proof for each negative check.

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
