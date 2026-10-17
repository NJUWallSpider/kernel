# Python Compiler API

Python authors exact models and explicit proofs, compiles through RPA 12 to RPX 11, and calls the kernel. The certificate contains two required proof trees. There are no selectable correctness properties, LP mode, inverse declarations, or standalone improvement proofs.

## Complete maps and obligations

```python
from kernel_compiler import Expr, Model, Proof, Variable

source = Model("source", [Variable("x", True, 0, 1)], objective=Expr.var(0))
target = Model("target", [Variable("x", True, 0, 0)], objective=Expr.var(0))
proof = Proof(source, target)
f = proof.forward.map({"x": 0})
r = proof.reverse.map("identity")
f.complete()
r.le([(r.upper("x"), 1)], constant=-1)
r.complete()
result = proof.verify("output/proof")
assert result["status"] == "VERIFIED"
assert result["guarantee"] == "MI_OPT"
```

The forward map removes a dominated solution. No pointwise inverse or equality of suboptimal objectives is required. `proof.forward` and `proof.reverse` exist immediately, but both must be completed before serialization. Maps can be supplied later, including separately inside branches and constructive scopes.

`map` accepts a complete coordinate sequence, a dictionary naming every output variable, or `"identity"`. It checks dimensions and names. Each direction's input/output orientation is fixed by the containing Proof.

`direction.plan()` enumerates kernel-generated obligations; `missing()` lists those without reusable witnesses; `check(label, fact)` assigns a witness; `complete()` supplies exactly the ordered checks. Optional arguments include `mapping`, `scope`, `witnesses` and `auto`. The goal list is not configurable. Labels include `variable.lower[x]`, `variable.integer[x]`, `row.equal[r]`, and `objective.non_increasing`.

The author chooses the maps and mathematical derivations. Completion only reuses exact facts and literal tautologies; it does not solve for a proof. Changes to maps, steps or assigned witnesses invalidate completed-check caches.

## Exact expressions and models

`Expr` uses exact integers, fractions and rational strings. Primitive floats are not proof scalars. `Model.load` reads supported MPS/LP/MCM inputs; `Model`, `Variable` and `Row` also construct models directly. `write_mcm`, `write_mps`, model readback and `same_formulation` support exact artifact binding. Model transformations preserve immutable source objects.

Models expose bounds, rows, named variables and exact objective expressions. For selected affine elimination, use `source.substitute(replacements, drop_rows=definition_rows)` and explicitly provide both complete maps. Complete verification still uses the resulting actual models; a Python transformation does not establish correctness.

`Model.standard_mps_adapter()` performs explicit rational-to-standard-MPS normalization. Its `.proof()` constructs both fixed-goal maps, including any objective or bound auxiliaries. It no longer constructs extra LP or inverse claims.

## Facts, scopes and derivations

A `Builder` uses actual model integrality; there is no `integers` option. `lower`, `upper`, `integer` and `row` obtain model facts. `le`, `eq`, `int`, `round`, `eqpair` and `drop` emit ordinary checked steps. Integer-valued expressions involving continuous coordinates can still be proved from equalities to actual integer variables.

`cases` and `binary_cases` prove a supplied common fact in exhaustive branches. `split` supplies a complete directional construction in each branch; each leaf must return or close a checked contradiction. `close_absurd` needs a genuine contradiction. There is no strict-positive root assumption or `close_positive` method.

Facts carry their scope. Children may use parent facts; parent/sibling scopes cannot use private child facts. Dropped facts cannot be reused. Generated-model handles retain this same visibility discipline.

## Mechanical proof helpers

The following helpers elaborate author-selected arguments into existing rules:

- `substitution(definitions, goals=...)`: reuse a supplied ordered set of equality pivots; rewrite affected model facts and discharge kernel equality goals, including objective differences that reduce to zero. An Eq witness can prove a Le objective obligation.
- `rewrite`, `derive_substitution`, `derive_substitution_many`: explicit equality substitution with a supplied residual witness.
- `eq_on_fixed`: prove a supplied expression using selected fixed-coordinate equations.
- `zero_sum`: derive selected zeros from a supplied nonnegative sum constraint.
- `parity_fix`: derive a binary coordinate value from a supplied integer parity equality.
- `subset_bounds`: derive selected partial-sum bounds from supplied inequalities and bounds.
- `plotkin`: emit a checked code-distance bound from supplied labels and clique witnesses.

These helpers do not discover a reformulation, choose equations or run a solver. Existing arithmetic magnitude and resource limits apply to every intermediate expression.

## Constructive scopes

`intervals`, `menu`, `signed`, `flow`, and `subflow` obtain the kernel's generated model and premises. Supply explicit parent-scope witnesses, then use the returned child scope to prove the same complete target obligations. Typed layout handles name generated coordinates and rows without manual offsets.

For example, an interval extension can reconstruct a deleted continuous auxiliary between affine lower and upper bounds. A signed extension can reconstruct bounded directional flows and binary activations. See the [constructive semantics](SEMANTICS.md#joint-construction-rules) and executable examples in the current Python tests.

## Compilation, verification and artifacts

```python
proof.target.write_mps("output/reformulated.mps")
result = proof.verify("output/proof", committed_model="output/reformulated.mps")
```

Compilation saves `source.mcm`, `target.mcm`, `proof.rpa`, `proof.rpx`, and `delivery.json`. Verification additionally saves `verification.json`. It does not generate a Request, property-summary or Certificate JSON sidecar. `preflight()` reports steps, checks, maps, linear premises and exact RPA/RPX sizes; verification reports actual work.

`Proof.compile(directory, committed_model=None)` is the only compilation entry point; raw Certificate dictionaries are not accepted. The native core builds the certificate, renders canonical RPA 12, parses that text back into the certificate, and encodes RPX 11. Compilation alone is not certification.

`Kernel.verify(source, target, proof, work=None, live_facts=None)` accepts one proof. File publication is atomic in the Python authoring layer; failed writes retain existing artifacts. Output paths must not alias committed solver artifacts.

A successful artifact audit compares every named variable, bound, integrality declaration, row and objective against the committed model. The final verification status and artifact audit are separate checks; do not infer certification from file creation or a digest alone.

## Ordered stages

For successive reformulations, `write_chain(stage_manifests, destination, committed_model=..., original_model=...)` records the existing stage artifacts. `verify_bundle` checks their hashes, requires exact named joins, and calls the same fixed verifier for each complete stage. The only composition metadata is `ordered_chain: true`. There are no selected claim paths or weaker stage relations.

For a single model pair, `verify_bundle` requires one complete proof piece. It cannot combine incomplete directional files. A general solver-facing recovery executor remains future work; the proof currently establishes constructive existence.

## Migration

Removed methods include `claim`, `correspondence`, `bijection`, `injectivity`, `improvement`, `feasible_point`, `add_point` and property-summary methods. Replace their optimization-equivalence use with `proof.forward` and `proof.reverse`; remove additional declarations and their terminal checks, then reverify. Old APIs are not silently translated by the current package.
