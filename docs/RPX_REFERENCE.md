# RPX generated API reference

Generated from installed definitions and packaged type declarations. Do not edit.

Regenerate: `PYTHONPATH=python python3 tools/check_rpx_help.py --write`.
Check: `PYTHONPATH=python python3 tools/check_rpx_help.py --check`.

Start with `python -m rpx help quickstart`; use `python -m rpx help agent` for task navigation.

# ArtifactMismatchError

Artifact bytes, manifest hashes, model formulation or publication destination disagree. Restore the intended inputs or publish to a fresh directory, then audit again.

# Bundle

A self-contained published proof directory. Use Proof.compile or Bundle.open(directory). Source, target, RPA, RPX and optional original target artifact are addressed by relative paths and hashes. open audits contents; verify runs the Kernel afresh.

## Fields

directory: Path to the published bundle directory; moving the whole directory preserves internal references.

# Bundle.directory

directory: Path

Path to the published bundle directory; moving the whole directory preserves internal references.

Related: Bundle

# Bundle.manifest

manifest: Path

The package-local Path to the manifest.

## Example

bundle.manifest

Related: Bundle

# Bundle.open

open(directory: FilePath) -> Bundle

Read a new-schema bundle at directory and audit relative paths and content hashes; return Bundle. Mismatches raise ArtifactMismatchError. Does not substitute for fresh Kernel verification.

## Parameters

directory: FilePath

## Returns

Bundle

## Example

Bundle.open("build/bundle")

Related: Bundle

# Bundle.proof

proof: Path

The package-local Path to the RPX certificate.

## Example

bundle.proof

Related: Bundle

# Bundle.rpa

rpa: Path

The package-local Path to the RPA certificate.

## Example

bundle.rpa

Related: Bundle

# Bundle.source

source: Path

The package-local Path to the source MCM model.

## Example

bundle.source

Related: Bundle

# Bundle.target

target: Path

The package-local Path to the target MCM model.

## Example

bundle.target

Related: Bundle

# Bundle.verify

verify(*, target_artifact: FilePath | None=None, work: int | None=None, live_facts: int | None=None, depth: int | None=None) -> VerificationReport

Audit bundle bytes and optional target_artifact, then run the frozen Kernel with this call's work/live_facts/depth limits. Return VerificationReport; successful reports are never reused. Artifact mismatches raise ArtifactMismatchError.

## Parameters

target_artifact: FilePath | None
work: int | None
live_facts: int | None
depth: int | None

## Returns

VerificationReport

## Example

bundle.verify(work=1000000).raise_for_status()

Related: Bundle

# Cases

Two explicit derivation scopes producing one common conclusion. Obtain with scope.derive.cases(...), use left/right.assumption, then conclude a matching fact or close_absurd in each branch. finish returns one Fact in the parent. This is distinct from Scope.split, whose leaves complete mappings.

# Cases.finish

finish() -> Fact

Combine completed left/right derivations into one Fact in the parent. Both must conclude the declared fact or a valid contradiction; incomplete branches raise UnprovedGoalError.

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

cases.finish()

Related: Cases

# Cases.left

left: Scope

The left derivation Scope, with its own assumption.

## Example

cases.left

Related: Cases

# Cases.right

right: Scope

The right derivation Scope, with its own assumption.

## Example

cases.right

Related: Cases

# Chain

Chain(stages: Iterable[Bundle])

An ordered sequence of Bundle stages with matching endpoint formulations. Construction checks joins; compile copies stages and optional endpoint artifacts into a portable directory. Verify every stage with current limits before claiming success. Example: Chain([first, second]).

## Fields

stages: Ordered tuple of Bundle objects; adjacent models must match.
directory: Published directory, available after compile/open; an unpublished chain has no directory.

# Chain.compile

compile(directory: FilePath, *, target_artifact: FilePath | None=None, source_artifact: FilePath | None=None) -> Chain

Publish stage copies and optional source_artifact/target_artifact as a portable Chain at directory. Check joins and artifact formulations; refuse different existing contents. Return the published Chain.

## Parameters

directory: FilePath
target_artifact: FilePath | None
source_artifact: FilePath | None

## Returns

Chain

## Example

chain.compile("build/chain")

Related: Chain

# Chain.directory

directory: Path

Published directory, available after compile/open; an unpublished chain has no directory.

Related: Chain

# Chain.open

open(directory: FilePath) -> Chain

Read a published new-schema chain directory and validate stage hashes, artifacts and joins; return Chain. Audit errors raise ArtifactMismatchError.

## Parameters

directory: FilePath

## Returns

Chain

## Example

Chain.open("build/chain")

Related: Chain

# Chain.stages

stages: tuple[Bundle, ...]

Ordered tuple of Bundle objects; adjacent models must match.

Related: Chain

# Chain.verify

verify(*, work: int | None=None, live_facts: int | None=None, depth: int | None=None) -> VerificationReport

Recheck chain contents and verify every stage with this call's work/live_facts/depth budgets. Return a combined VerificationReport; no cached success is trusted.

## Parameters

work: int | None
live_facts: int | None
depth: int | None

## Returns

VerificationReport

## Example

chain.verify().raise_for_status()

Related: Chain

# CompilerError

Base class for invalid compiler input. Inspect the specific subclass and the troubleshooting topic.

# CoordinateSpaceError

Expressions belong to incompatible coordinate spaces. Reacquire handles from the intended model; never rebind by name implicitly.

# Derive

Explicit derivation operations for one scope. Obtain via scope.derive; each operation checks selected premises and returns facts. No solver or proof search is run. The scope must be editable, premises visible and proof-owned, and expressions in its coordinate space. Invalid operations raise InvalidDerivationError without appending partial steps.

# Derive.box_le

box_le(expression: Affine) -> Fact

Return a Le Fact for expression by explicit model-bound expansion. Fail if a required bound is absent or the resulting bound does not prove expression <= 0.

## Parameters

expression: Affine

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.box_le(x-1)

Related: Derive

# Derive.cases

cases(split: Affine, *, kind: Kind, expect: Affine, integer: Fact | None=None) -> Cases

Create explicit left/right derivation scopes splitting at zero, for the common kind and expect expression. integer selects integer branching with an exact Int witness; otherwise branching is continuous. Return Cases; conclude or close_absurd in each child, then call Cases.finish.

## Parameters

split: Affine
kind: Kind
expect: Affine
integer: Fact | None

## Returns

Cases

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.cases(x, kind="Le", expect=x-1)

Related: Derive

# Derive.eq

eq(by: Combination, *, expect: Affine | None=None) -> Fact

Return an Eq Fact from by; only equality contributions and zero constant are allowed. expect, when supplied, must equal the resulting affine expression.

## Parameters

by: Combination
expect: Affine | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.eq(-scope.row("balance"))

Related: Derive

# Derive.eq_on_fixed

eq_on_fixed(expression: Affine, fixes: dict[Variable, Fact] | None=None) -> Fact

Return an Eq Fact for expression using fixed model bounds and optional explicit variable-to-equality fixes. Fail if the residual is not identically zero.

## Parameters

expression: Affine
fixes: dict[Variable, Fact] | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.eq_on_fixed(x-1)

Related: Derive

# Derive.eqpair

eqpair(positive: Fact, negative: Fact) -> Fact

Return an Eq Fact from opposite Le facts positive and negative with exactly negated expressions.

## Parameters

positive: Fact
negative: Fact

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.eqpair(upper_zero, lower_zero)

Related: Derive

# Derive.int

int(by: Combination, *, expect: Affine | None=None) -> Fact

Return an Int Fact from by: Int premises require integral coefficients and the constant must be integral; Eq premises allow arbitrary exact coefficients. expect checks the exact result.

## Parameters

by: Combination
expect: Affine | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.int(scope.integer("x")+1)

Related: Derive

# Derive.le

le(by: Combination, *, expect: Affine | None=None) -> Fact

Return a Le Fact from by. Inequality multipliers must be nonnegative; equality multipliers can have either sign; the added constant must be nonpositive. expect checks the exact result.

## Parameters

by: Combination
expect: Affine | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.le(2*scope.upper("x")-1)

Related: Derive

# Derive.parity_fix

parity_fix(variable: Variable, equality: Fact) -> Fact

Return a binary variable fixing from a selected equality with an odd coefficient for variable and even coefficients for other integral variables.

## Parameters

variable: Variable
equality: Fact

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.parity_fix("x", scope.row("parity"))

Related: Derive

# Derive.plotkin

plotkin(*, bits: builtins.int, distance: builtins.int, variables: Iterable[tuple[Variable, builtins.int]], cliques: Iterable[Fact]) -> Fact

Expand the explicit Plotkin construction for bits, distance, (variable, codeword) pairs and selected clique facts. Return a Le Fact; this does not discover codes or cliques.

## Parameters

bits: builtins.int
distance: builtins.int
variables: Iterable[tuple[Variable, builtins.int]]
cliques: Iterable[Fact]

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.plotkin(bits=2, distance=2, variables=[("x", 0), ("y", 3)], cliques=[clique])

Related: Derive

# Derive.rewrite

rewrite(fact: Fact, definitions: dict[Variable, Fact], *, expect: Affine | None=None) -> Fact

Return fact rewritten with ordered variable-to-equality definitions. Dictionary order is semantic; expect optionally checks the exact result.

## Parameters

fact: Fact
definitions: dict[Variable, Fact]
expect: Affine | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.rewrite(fact, {"x": definition})

Related: Derive

# Derive.rewrite_many

rewrite_many(facts: Iterable[Fact], definitions: dict[Variable, Fact]) -> list[Fact]

Rewrite each selected fact using ordered definitions in one native batch; return a list of Facts. Failure rolls back the batch.

## Parameters

facts: Iterable[Fact]
definitions: dict[Variable, Fact]

## Returns

list[Fact]

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.rewrite_many([fact], {"x": definition})

Related: Derive

# Derive.round

round(le: Fact, integer: Fact) -> Fact

Round the bound in le using integer as an exact matching integrality witness; return a Le Fact.

## Parameters

le: Fact
integer: Fact

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.round(scope.upper("x"), scope.integer("x"))

Related: Derive

# Derive.subset_bounds

subset_bounds(fact: Fact, subsets: Iterable[Iterable[Variable]]) -> list[Fact]

Derive one Le Fact per selected coordinate subset by bounding omitted terms using model bounds. Return a list; missing required bounds rolls back the batch.

## Parameters

fact: Fact
subsets: Iterable[Iterable[Variable]]

## Returns

list[Fact]

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.subset_bounds(fact, [["x"], ["y"]])

Related: Derive

# Derive.substitution

substitution(definitions: dict[Variable, Fact], *, goals: Iterable[Affine] | None=None) -> list[Fact]

Expand ordered equality definitions to prove selected goals, or current obligations when goals is None. Return a list of Facts; no automatic definition discovery occurs.

## Parameters

definitions: dict[Variable, Fact]
goals: Iterable[Affine] | None

## Returns

list[Fact]

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.substitution({"x": definition})

Related: Derive

# Derive.substitution_fact

substitution_fact(goal: Affine, definitions: dict[Variable, Fact], residual: Fact, *, kind: Kind | None=None) -> Fact

Prove goal using explicit ordered definitions and the supplied residual Fact. kind defaults to the residual kind; return a Fact.

## Parameters

goal: Affine
definitions: dict[Variable, Fact]
residual: Fact
kind: Kind | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.substitution_fact(x-1, {"x": definition}, residual)

Related: Derive

# Derive.zero_sum

zero_sum(fact: Fact, *, zeros: dict[Variable, Fact] | None=None, scale: Scalar | None=None, coordinates: Iterable[Variable] | None=None) -> dict[str, Fact]

Extract selected zero coordinates from a nonpositive weighted sum of nonnegative variables. zeros supplies known equalities; scale normalizes the fact; coordinates optionally limits extraction. Return name-to-Fact dictionary.

## Parameters

fact: Fact
zeros: dict[Variable, Fact] | None
scale: Scalar | None; None uses one.
coordinates: Iterable[Variable] | None

## Returns

dict[str, Fact]

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.derive.zero_sum(scope.row("sum"), coordinates=["x"])

Related: Derive

# Expr

Expr(constant: Scalar | None=None)

An immutable affine expression with coordinate ownership. Scalars are space-free; variables from independent models cannot be mixed. Parent expressions embed in lift children, never the reverse or across siblings. Arithmetic returns Expr, not a proof. Example: 2 * model.vars["x"] - 1. Use Expr(0) for a constant; use from_terms for indexed construction.

## Operators

__add__: Add an exact scalar or compatible affine expression; return Expr.
__radd__: Reversed addition; return Expr.
__sub__: Subtract a compatible operand; return Expr.
__rsub__: Subtract self from the left operand; return Expr.
__mul__: Scale by an exact scalar; return Expr. Nonlinear products are not accepted.
__rmul__: Reversed exact scalar multiplication; return Expr.
__truediv__: Divide by a nonzero exact scalar; return Expr. ZeroDivisionError on zero.
__neg__: Negate without deriving a fact; return Expr.
__eq__: Compare exact coefficients and identical space identity; return bool, not a constraint.
__ne__: Negate exact expression equality; return bool, not a constraint.
__hash__: Return a hash consistent with equality.

# Expr.__add__

__add__(other: Affine) -> Expr

Add an exact scalar or compatible affine expression; return Expr.

Related: Expr

# Expr.__eq__

__eq__(other: object) -> bool

Compare exact coefficients and identical space identity; return bool, not a constraint.

Related: Expr

# Expr.__hash__

__hash__() -> int

Return a hash consistent with equality.

Related: Expr

# Expr.__mul__

__mul__(other: Scalar) -> Expr

Scale by an exact scalar; return Expr. Nonlinear products are not accepted.

Related: Expr

# Expr.__ne__

__ne__(other: object) -> bool

Negate exact expression equality; return bool, not a constraint.

Related: Expr

# Expr.__neg__

__neg__() -> Expr

Negate without deriving a fact; return Expr.

Related: Expr

# Expr.__radd__

__radd__(other: Affine) -> Expr

Reversed addition; return Expr.

Related: Expr

# Expr.__rmul__

__rmul__(other: Scalar) -> Expr

Reversed exact scalar multiplication; return Expr.

Related: Expr

# Expr.__rsub__

__rsub__(other: Affine) -> Expr

Subtract self from the left operand; return Expr.

Related: Expr

# Expr.__sub__

__sub__(other: Affine) -> Expr

Subtract a compatible operand; return Expr.

Related: Expr

# Expr.__truediv__

__truediv__(other: Scalar) -> Expr

Divide by a nonzero exact scalar; return Expr. ZeroDivisionError on zero.

Related: Expr

# Expr.constant

constant: Q

The exact constant term as Q.

## Example

expr.constant

Related: Expr

# Expr.dot

dot(coefficients: Iterable[Scalar], variables: Iterable[Affine]) -> Expr

Return the exact affine dot product of equally sized coefficients and variables. Native variable views and integer buffers use batch paths. Cross-space variables raise CoordinateSpaceError.

## Parameters

coefficients: Iterable[Scalar]
variables: Iterable[Affine]

## Returns

Expr

## Example

Expr.dot([2, 3], model.vars)

Related: Expr

# Expr.evaluate

evaluate(values: Mapping[str, Scalar] | Sequence[Scalar]) -> Q

Return Q at an exact coordinate sequence or variable-name mapping; missing coordinates fail.

## Parameters

values: Mapping[str, Scalar] | Sequence[Scalar]

## Returns

Q

## Example

expr.evaluate({"x": 1})

Related: Expr

# Expr.from_terms

from_terms(space: Model, indices: Iterable[int], coefficients: Iterable[Scalar], constant: Scalar | None=None) -> Expr

Accumulate sparse indices and coefficients once in native code, with explicit model space and optional constant. Lengths must match; invalid coordinates fail. Integer buffers use a batch path.

## Parameters

space: Model
indices: Iterable[int]
coefficients: Iterable[Scalar]
constant: Scalar | None; None uses zero.

## Returns

Expr

## Example

Expr.from_terms(model, [0], [2], constant=1)

Related: Expr

# Expr.substitute

substitute(replacements: Mapping[int, Affine] | Sequence[Affine] | MappingView) -> Expr

Return an expression after explicit coordinate replacement. Use a MappingView or complete sequence for mapping; a mapping of indices selects replacements. Replacement expressions must have compatible spaces.

## Parameters

replacements: Mapping[int, Affine] | Sequence[Affine] | MappingView

## Returns

Expr

## Example

expr.substitute(scope.mapping)

Related: Expr

# Expr.terms

terms: TermsView

The native-backed sparse coefficient view.

## Example

expr.terms

Related: Expr

# Expr.to_dict

to_dict() -> dict[str, Any]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[str, Any]

## Example

expr.to_dict()

Related: Expr

# Fact

A proof-owned assertion: Eq means expression = 0, Le means expression <= 0, Int means expression is integral. Obtain facts from a scope or its derive methods. Arithmetic such as 2*a-b-1 returns LinCombination, never Expr and never a new fact. Use fact.expression for affine algebra. Cross-Proof combinations raise ScopeError.

## Operators

__add__: Add an exact scalar or compatible proof combination; return LinCombination.
__radd__: Reversed addition; return LinCombination.
__sub__: Subtract a compatible operand; return LinCombination.
__rsub__: Subtract self from the left operand; return LinCombination.
__mul__: Scale by an exact scalar; return LinCombination. Nonlinear products are not accepted.
__rmul__: Reversed exact scalar multiplication; return LinCombination.
__truediv__: Divide by a nonzero exact scalar; return LinCombination. ZeroDivisionError on zero.
__neg__: Negate without deriving a fact; return LinCombination.
__eq__: Compare fact identity including owning Proof; return bool.
__hash__: Return a hash consistent with equality.

# Fact.__add__

__add__(other: Combination) -> LinCombination

Add an exact scalar or compatible proof combination; return LinCombination.

Related: Fact

# Fact.__eq__

__eq__(other: object) -> bool

Compare fact identity including owning Proof; return bool.

Related: Fact

# Fact.__hash__

__hash__() -> int

Return a hash consistent with equality.

Related: Fact

# Fact.__mul__

__mul__(other: Scalar) -> LinCombination

Scale by an exact scalar; return LinCombination. Nonlinear products are not accepted.

Related: Fact

# Fact.__neg__

__neg__() -> LinCombination

Negate without deriving a fact; return LinCombination.

Related: Fact

# Fact.__radd__

__radd__(other: Combination) -> LinCombination

Reversed addition; return LinCombination.

Related: Fact

# Fact.__rmul__

__rmul__(other: Scalar) -> LinCombination

Reversed exact scalar multiplication; return LinCombination.

Related: Fact

# Fact.__rsub__

__rsub__(other: Combination) -> LinCombination

Subtract self from the left operand; return LinCombination.

Related: Fact

# Fact.__sub__

__sub__(other: Combination) -> LinCombination

Subtract a compatible operand; return LinCombination.

Related: Fact

# Fact.__truediv__

__truediv__(other: Scalar) -> LinCombination

Divide by a nonzero exact scalar; return LinCombination. ZeroDivisionError on zero.

Related: Fact

# Fact.expression

expression: Expr

The exact owned affine expression.

## Example

fact.expression

Related: Fact

# Fact.kind

kind: Kind

The assertion or instruction kind.

## Example

fact.kind

Related: Fact

# FlowGroup

FlowGroup(source: int, commodities: Sequence[tuple[int, Scalar]], flows: Sequence[Affine], nonnegative: Sequence[Fact | None], balances: Sequence[Fact | None])

Explicit aggregate flow to decompose into selected commodities.

## Fields

source: Zero-based source node within the enclosing FlowSpec.
commodities: Ordered (sink node, nonnegative exact demand) pairs.
flows: One parent-space affine aggregate flow per arc, in FlowSpec.arcs order.
nonnegative: One Le(-flows[a]) witness per arc, in arc order.
balances: One Eq witness per node in node-index order: outgoing minus incoming minus total demand at source, plus delivered demand at sinks, zero elsewhere. None requests literal truth only.

## Result

A group Generated record with source, commodities and recovery. Each commodity has sink, demand, flows and balances. Recovery is sum of commodity flows minus input flow = 0 per arc. See lifts.flow.

# FlowGroup.balances

balances: Sequence[Fact | None]

One Eq witness per node in node-index order: outgoing minus incoming minus total demand at source, plus delivered demand at sinks, zero elsewhere. None requests literal truth only.

Related: FlowGroup

# FlowGroup.commodities

commodities: Sequence[tuple[int, Scalar]]

Ordered (sink node, nonnegative exact demand) pairs.

Related: FlowGroup

# FlowGroup.flows

flows: Sequence[Affine]

One parent-space affine aggregate flow per arc, in FlowSpec.arcs order.

Related: FlowGroup

# FlowGroup.nonnegative

nonnegative: Sequence[Fact | None]

One Le(-flows[a]) witness per arc, in arc order.

Related: FlowGroup

# FlowGroup.source

source: int

Zero-based source node within the enclosing FlowSpec.

Related: FlowGroup

# FlowSpec

FlowSpec(nodes: int, arcs: Sequence[tuple[int, int]], groups: Sequence[FlowGroup])

A directed graph and explicit commodity decomposition groups.

## Fields

nodes: Number of nodes; valid node indices are 0 through nodes-1.
arcs: Ordered (tail, head) pairs. The order determines every flow and arc-witness position.
groups: Ordered FlowGroup records; each requires len(arcs) nonnegative and nodes balance witnesses.

## Requirements

Graph, demands and sizes must satisfy the frozen Kernel construction checks. Invalid inputs raise InvalidDerivationError or ResourceLimitError before parent mutation. See lifts.flow for a complete example.

# FlowSpec.arcs

arcs: Sequence[tuple[int, int]]

Ordered (tail, head) pairs. The order determines every flow and arc-witness position.

Related: FlowSpec

# FlowSpec.groups

groups: Sequence[FlowGroup]

Ordered FlowGroup records; each requires len(arcs) nonnegative and nodes balance witnesses.

Related: FlowSpec

# FlowSpec.nodes

nodes: int

Number of nodes; valid node indices are 0 through nodes-1.

Related: FlowSpec

# Generated

A native layout record returned by lift[index]. Available fields depend on the construction; unavailable fields raise AttributeError. Variables belong to the child coordinate space and cannot escape to parents or sibling extensions. Fact fields belong to the same Proof. See Fields for the exact per-family layout.

## Fields

variable: Interval only: generated VarRef.
lower_rows: Interval only: Le facts L[i]-variable in lower input order.
upper_rows: Interval only: Le facts variable-U[j] in upper input order.
options: Menu only: K+1 binary VarRef values in option-index order.
sum: Menu only: Eq(sum(options)-activation).
moment: Menu only: Eq(sum(j*options[j])-index).
positive: Signed only: nonnegative positive-flow VarRef.
negative: Signed only: nonnegative negative-flow VarRef.
positive_activation: Signed only: binary positive activation VarRef.
negative_activation: Signed only: binary negative activation VarRef.
flow: Signed only: Eq(positive-negative-input_flow).
activation: Signed only: Eq(positive_activation+negative_activation-input_activation).
positive_capacity: Signed only: Le(positive-capacity*positive_activation).
negative_capacity: Signed only: Le(negative-capacity*negative_activation).
source: Flow/Subflow group only: source node index.
sink: Flow commodity only: sink node index.
demand: Flow commodity only: exact demand Q.
flows: Flow commodity or Subflow group: generated VarRef sequence in arc order.
commodities: Flow group only: Generated records in input commodity order.
balances: Flow commodity or Subflow group: Eq conservation facts in node order.
recovery: Flow group only: Eq(sum(commodity flows)-input flow) per arc.
remainder_nonnegative: Subflow group only: Le(generated flow-input flow) per arc.

# Generated.activation

activation: Fact

Signed only: Eq(positive_activation+negative_activation-input_activation).

Related: Generated

# Generated.balances

balances: Sequence[Fact]

Flow commodity or Subflow group: Eq conservation facts in node order.

Related: Generated

# Generated.commodities

commodities: Sequence[Generated]

Flow group only: Generated records in input commodity order.

Related: Generated

# Generated.demand

demand: Q

Flow commodity only: exact demand Q.

Related: Generated

# Generated.flow

flow: Fact

Signed only: Eq(positive-negative-input_flow).

Related: Generated

# Generated.flows

flows: Sequence[VarRef]

Flow commodity or Subflow group: generated VarRef sequence in arc order.

Related: Generated

# Generated.lower_rows

lower_rows: Sequence[Fact]

Interval only: Le facts L[i]-variable in lower input order.

Related: Generated

# Generated.moment

moment: Fact

Menu only: Eq(sum(j*options[j])-index).

Related: Generated

# Generated.negative

negative: VarRef

Signed only: nonnegative negative-flow VarRef.

Related: Generated

# Generated.negative_activation

negative_activation: VarRef

Signed only: binary negative activation VarRef.

Related: Generated

# Generated.negative_capacity

negative_capacity: Fact

Signed only: Le(negative-capacity*negative_activation).

Related: Generated

# Generated.options

options: Sequence[VarRef]

Menu only: K+1 binary VarRef values in option-index order.

Related: Generated

# Generated.positive

positive: VarRef

Signed only: nonnegative positive-flow VarRef.

Related: Generated

# Generated.positive_activation

positive_activation: VarRef

Signed only: binary positive activation VarRef.

Related: Generated

# Generated.positive_capacity

positive_capacity: Fact

Signed only: Le(positive-capacity*positive_activation).

Related: Generated

# Generated.recovery

recovery: Sequence[Fact]

Flow group only: Eq(sum(commodity flows)-input flow) per arc.

Related: Generated

# Generated.remainder_nonnegative

remainder_nonnegative: Sequence[Fact]

Subflow group only: Le(generated flow-input flow) per arc.

Related: Generated

# Generated.sink

sink: int

Flow commodity only: sink node index.

Related: Generated

# Generated.source

source: int

Flow/Subflow group only: source node index.

Related: Generated

# Generated.sum

sum: Fact

Menu only: Eq(sum(options)-activation).

Related: Generated

# Generated.upper_rows

upper_rows: Sequence[Fact]

Interval only: Le facts variable-U[j] in upper input order.

Related: Generated

# Generated.variable

variable: VarRef

Interval only: generated VarRef.

Related: Generated

# Goal

A mapping-version-bound obligation. Obtain it from scope.plan() or scope.obligations and pass to scope.prove(goal, by=...). Replacing the mapping invalidates old handles; reacquire them. Cross-Proof, wrong-scope and stale handles raise ScopeError.

# Goal.discharged

discharged: bool

Whether this goal currently has an exact witness; stale handles raise ScopeError.

## Example

goal.discharged

Related: Goal

# Goal.expression

expression: Expr

The exact owned affine expression.

## Example

goal.expression

Related: Goal

# Goal.kind

kind: Kind

The assertion or instruction kind.

## Example

goal.kind

Related: Goal

# Goal.label

label: str

The stable label within this mapping version.

## Example

goal.label

Related: Goal

# IntervalSpec

IntervalSpec(lower: Sequence[Affine], upper: Sequence[Affine], because: Sequence[Fact | None])

Ordered interval bounds and explicit pairwise feasibility witnesses.

## Fields

lower: Sequence of lower affine bounds L[i] in the parent space.
upper: Sequence of upper affine bounds U[j] in the parent space.
because: Exactly len(lower)*len(upper) witnesses for L[i]-U[j] <= 0, lower-major then upper-minor. None means literal truth, never automatic fact lookup.

## Result

One Generated item with variable, lower_rows (L[i]-variable <= 0) and upper_rows (variable-U[j] <= 0). See lifts.interval for a runnable example.

# IntervalSpec.because

because: Sequence[Fact | None]

Exactly len(lower)*len(upper) witnesses for L[i]-U[j] <= 0, lower-major then upper-minor. None means literal truth, never automatic fact lookup.

Related: IntervalSpec

# IntervalSpec.lower

lower: Sequence[Affine]

Sequence of lower affine bounds L[i] in the parent space.

Related: IntervalSpec

# IntervalSpec.upper

upper: Sequence[Affine]

Sequence of upper affine bounds U[j] in the parent space.

Related: IntervalSpec

# InvalidDerivationError

Selected premises do not prove the requested assertion. Inspect fact.kind, fact.expression and the exact goal; correct multipliers or select matching witnesses.

# KernelRejectedError

Verification did not report VERIFIED. Inspect report.kernel and report.artifact_audit; never claim certification from compilation alone.

# LiftResult

A successful constructive extension. scope is the editable extended child; parent is fixed. Indexing yields family-specific Generated records. variable is a convenience only for a single Interval item; otherwise it raises TypeError. Example: lift = scope.lift_interval(lower=0, upper=1); lift.scope.map(default="same_name").finish().

## Operators

__getitem__: Return family-specific Generated record at a nonnegative index; out-of-range raises IndexError.
__len__: Return generated item/group count.

# LiftResult.__getitem__

__getitem__(index: int) -> Generated

Return family-specific Generated record at a nonnegative index; out-of-range raises IndexError.

Related: LiftResult

# LiftResult.__len__

__len__() -> int

Return generated item/group count.

Related: LiftResult

# LiftResult.scope

scope: Scope

The editable child Scope created by this lift.

## Example

lift.scope

Related: LiftResult

# LiftResult.variable

variable: VarRef

The generated VarRef for a single Interval lift; other layouts raise TypeError.

## Example

lift.variable

Related: LiftResult

# LinCombination

An explicit linear combination of proof facts and an exact constant. Fact arithmetic builds this immutable value; it does not derive or certify anything. Pass it to scope.prove or scope.derive.eq/le/int. Zero coefficients disappear before lowering. Le requires nonnegative multipliers on inequality premises and a nonpositive added constant; Eq uses equalities and zero constant; Int uses integral multipliers on Int premises and an integral constant; Eq premises allow any exact multiplier. Example: scope.derive.le(2 * scope.upper("x") - 1).

## Operators

__add__: Add an exact scalar or compatible proof combination; return LinCombination.
__radd__: Reversed addition; return LinCombination.
__sub__: Subtract a compatible operand; return LinCombination.
__rsub__: Subtract self from the left operand; return LinCombination.
__mul__: Scale by an exact scalar; return LinCombination. Nonlinear products are not accepted.
__rmul__: Reversed exact scalar multiplication; return LinCombination.
__truediv__: Divide by a nonzero exact scalar; return LinCombination. ZeroDivisionError on zero.
__neg__: Negate without deriving a fact; return LinCombination.

# LinCombination.__add__

__add__(other: Combination) -> LinCombination

Add an exact scalar or compatible proof combination; return LinCombination.

Related: LinCombination

# LinCombination.__mul__

__mul__(other: Scalar) -> LinCombination

Scale by an exact scalar; return LinCombination. Nonlinear products are not accepted.

Related: LinCombination

# LinCombination.__neg__

__neg__() -> LinCombination

Negate without deriving a fact; return LinCombination.

Related: LinCombination

# LinCombination.__radd__

__radd__(other: Combination) -> LinCombination

Reversed addition; return LinCombination.

Related: LinCombination

# LinCombination.__rmul__

__rmul__(other: Scalar) -> LinCombination

Reversed exact scalar multiplication; return LinCombination.

Related: LinCombination

# LinCombination.__rsub__

__rsub__(other: Combination) -> LinCombination

Subtract self from the left operand; return LinCombination.

Related: LinCombination

# LinCombination.__sub__

__sub__(other: Combination) -> LinCombination

Subtract a compatible operand; return LinCombination.

Related: LinCombination

# LinCombination.__truediv__

__truediv__(other: Scalar) -> LinCombination

Divide by a nonzero exact scalar; return LinCombination. ZeroDivisionError on zero.

Related: LinCombination

# MappingError

Unknown output name or incomplete mapping. Supply every output coordinate or use default="same_name" with explicit overrides.

# MappingView

A native view of the current expanded output-to-input mapping. Index by output coordinate to get an Expr in the input space. Mapping replacement is visible through this view; Goal handles instead become stale. Example: scope.mapping[0].

## Operators

__getitem__: Return the input-space Expr for an output coordinate index.
__len__: Return output coordinate count.

# MappingView.__getitem__

__getitem__(index: int) -> Expr

Return the input-space Expr for an output coordinate index.

Related: MappingView

# MappingView.__len__

__len__() -> int

Return output coordinate count.

Related: MappingView

# MenuSpec

MenuSpec(maximum_index: int, activation: Affine, index: Affine, because: Sequence[Fact | None])

Construct a binary menu for an activated integer index.

## Fields

maximum_index: Nonnegative integer K; generates K+1 binary options.
activation: Parent-space affine value A, proved binary by the first three premises.
index: Parent-space affine value I, proved integral and between 0 and K*A.
because: Exactly six witnesses in order: Le(-A), Le(A-1), Int(A), Le(-I), Le(I-K*A), Int(I). None means literal truth only.

## Result

options[0..K], sum (sum(options)-A = 0), moment (sum(j*options[j])-I = 0). See lifts.menu for executable usage.

# MenuSpec.activation

activation: Affine

Parent-space affine value A, proved binary by the first three premises.

Related: MenuSpec

# MenuSpec.because

because: Sequence[Fact | None]

Exactly six witnesses in order: Le(-A), Le(A-1), Int(A), Le(-I), Le(I-K*A), Int(I). None means literal truth only.

Related: MenuSpec

# MenuSpec.index

index: Affine

Parent-space affine value I, proved integral and between 0 and K*A.

Related: MenuSpec

# MenuSpec.maximum_index

maximum_index: int

Nonnegative integer K; generates K+1 binary options.

Related: MenuSpec

# Model

An immutable exact model. Use Model.read(path) for LP, MPS or MCM, or ModelBuilder for construction. Edits return a new model with a new coordinate identity, even if names match. Example: model.vars["x"]. Inspect native views before materializing data.

# Model.add_row

add_row(name: str, expression: Affine, *, lower: Scalar | None=None, upper: Scalar | None=None, equal: Scalar | None=None) -> Model

Return a new model with the named bounded expression row. equal cannot be combined with lower/upper.

## Parameters

name: str
expression: Affine
lower: Scalar | None
upper: Scalar | None
equal: Scalar | None

## Returns

Model

## Example

model.add_row("cap", model.vars["x"], upper=1)

Related: Model

# Model.add_variable

add_variable(name: str, *, integer: bool=False, lower: Scalar | None=None, upper: Scalar | None=None) -> Model

Return a new model with one named variable; obtain its handle from the returned vars view.

## Parameters

name: str
integer: bool
lower: Scalar | None
upper: Scalar | None

## Returns

Model

## Example

model.add_variable("slack", lower=0)

Related: Model

# Model.check_point

check_point(values: Mapping[str, Scalar] | Sequence[Scalar], *, integers: bool=True) -> list[dict[str, Any]]

Return violations for supplied name-to-value mapping or coordinate sequence. integers controls integrality checking. An empty list means the point meets the checked model conditions, not proof certification.

## Parameters

values: Mapping[str, Scalar] | Sequence[Scalar]
integers: bool

## Returns

list[dict[str, Any]]

## Example

model.check_point({"x": 0})

Related: Model

# Model.delete_rows

delete_rows(rows: str | int | Iterable[str | int]) -> Model

Return a new model without the named/indexed rows.

## Parameters

rows: str | int | Iterable[str | int]

## Returns

Model

## Example

model.delete_rows(["cap"])

Related: Model

# Model.is_binary

is_binary(variable: Variable) -> bool

Test whether the selected variable is integral with bounds contained in [0, 1].

## Parameters

variable: Variable

## Returns

bool

## Example

model.is_binary("x")

Related: Model

# Model.name

name: str

The declared name.

## Example

model.name

Related: Model

# Model.objective

objective: Expr

The exact affine minimization objective.

## Example

model.objective

Related: Model

# Model.read

read(path: Path) -> Model

Read exact MCM, LP or MPS from path; return a new Model. Unknown formats raise TypeError and I/O failures raise OSError.

## Parameters

path: Path

## Returns

Model

## Example

Model.read("model.mps")

Related: Model

# Model.renamed

renamed(name: str) -> Model

Return a new model named name, with a fresh coordinate space.

## Parameters

name: str

## Returns

Model

## Example

model.renamed("revised")

Related: Model

# Model.replace_row

replace_row(row: str | int, *, expression: Affine=..., lower: Scalar | None=..., upper: Scalar | None=...) -> Model

Return a new model replacing only supplied row fields. Omitted fields stay unchanged; explicit None removes a bound.

## Parameters

row: str | int
expression: Affine
lower: Scalar | None
upper: Scalar | None

## Returns

Model

## Example

model.replace_row("cap", upper=2)

Related: Model

# Model.row_activity

row_activity(row: str | int) -> tuple[Q | None, Q | None]

Return exact lower/upper box activity for the selected row, using None for an unbounded side.

## Parameters

row: str | int

## Returns

tuple[Q | None, Q | None]

## Example

model.row_activity("cap")

Related: Model

# Model.rows

rows: RowsView

The native-backed row view.

## Example

model.rows

Related: Model

# Model.same_formulation

same_formulation(other: Model) -> bool

Compare exact model formulation data, independent of coordinate identity.

## Parameters

other: Model

## Returns

bool

## Example

model.same_formulation(other_model)

Related: Model

# Model.stats

stats() -> dict[str, Any]

Return model size and sparsity statistics without materializing all rows.

## Returns

dict[str, Any]

## Example

model.stats()

Related: Model

# Model.substitute

substitute(replacements: dict[Variable, Affine], *, remove: bool=True, drop_rows: Iterable[str | int] | None=None, preserve_bounds: bool=True) -> Model

Return an edited model after explicit affine replacement. remove deletes substituted variables; drop_rows selects rows to remove; preserve_bounds retains replaced-variable bounds as constraints. Reacquire variable handles from the result.

## Parameters

replacements: dict[Variable, Affine]
remove: bool
drop_rows: Iterable[str | int] | None
preserve_bounds: bool

## Returns

Model

## Example

model.substitute({"x": 1-model.vars["y"]}, drop_rows=["balance"])

Related: Model

# Model.support

support(row: str | int) -> list[int]

Return the coordinate indices with nonzero coefficients in the selected row.

## Parameters

row: str | int

## Returns

list[int]

## Example

model.support("cap")

Related: Model

# Model.to_dict

to_dict() -> dict[str, Any]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[str, Any]

## Example

model.to_dict()

Related: Model

# Model.to_mps

to_mps(*, rational_literals: bool=False) -> str

Return an exact MPS string. rational_literals opts into rational literals; standard output requires representable coefficients or an explicit StandardMPSAdapter.

## Parameters

rational_literals: bool

## Returns

str

## Example

model.to_mps()

Related: Model

# Model.vars

vars: VariablesView

The native-backed input variable view.

## Example

model.vars

Related: Model

# Model.with_bounds

with_bounds(variable: Variable, *, lower: Scalar | None=..., upper: Scalar | None=...) -> Model

Return a new model with the selected variable bounds replaced. Omitted bounds stay unchanged; explicit None removes a bound.

## Parameters

variable: Variable
lower: Scalar | None
upper: Scalar | None

## Returns

Model

## Example

model.with_bounds("x", upper=1)

Related: Model

# Model.with_integrality

with_integrality(variables: Variable | Iterable[Variable], integer: bool) -> Model

Return a new model with integer flags set for the selected variables.

## Parameters

variables: Variable | Iterable[Variable]
integer: bool

## Returns

Model

## Example

model.with_integrality(["x"], True)

Related: Model

# Model.with_objective

with_objective(expression: Affine) -> Model

Return a new model minimizing expression from this model space.

## Parameters

expression: Affine

## Returns

Model

## Example

model.with_objective(model.vars["x"])

Related: Model

# Model.write_mcm

write_mcm(path: Path) -> PathLike[str]

Write canonical MCM to path and return that path.

## Parameters

path: Path

## Returns

PathLike[str]

## Example

model.write_mcm("model.mcm")

Related: Model

# Model.write_mps

write_mps(path: Path, *, rational_literals: bool=False) -> PathLike[str]

Write the exact MPS representation to path and return that path. See to_mps for rational_literals.

## Parameters

path: Path
rational_literals: bool

## Returns

PathLike[str]

## Example

model.write_mps("model.mps")

Related: Model

# ModelBuilder

ModelBuilder(name: str='MODEL')

Construct a model in one owned coordinate space. add_var returns usable VarRef handles immediately. build seals the builder and preserves these handles in the resulting model; later mutation raises ScopeError. Example: b = ModelBuilder("demo"); x = b.add_var("x", lower=0); b.minimize(x); model = b.build().

# ModelBuilder.add_row

add_row(name: str, expression: Affine, *, lower: Scalar | None=None, upper: Scalar | None=None, equal: Scalar | None=None) -> None

Add a named affine row to this builder. equal specifies equality; do not combine it with lower/upper. Return None.

## Parameters

name: str
expression: Affine
lower: Scalar | None
upper: Scalar | None
equal: Scalar | None

## Returns

None

## Example

builder.add_row("balance", x+y, equal=1)

Related: ModelBuilder

# ModelBuilder.add_var

add_var(name: str, *, integer: bool=False, lower: Scalar | None=None, upper: Scalar | None=None) -> VarRef

Add a named variable and return its owned VarRef. integer sets integrality; lower/upper are exact optional bounds.

## Parameters

name: str
integer: bool
lower: Scalar | None
upper: Scalar | None

## Returns

VarRef

## Example

builder.add_var("x", lower=0, upper=1)

Related: ModelBuilder

# ModelBuilder.build

build() -> Model

Seal this builder and return an immutable Model. Previously returned variable handles remain valid.

## Returns

Model

## Example

builder.build()

Related: ModelBuilder

# ModelBuilder.minimize

minimize(expression: Affine) -> None

Set the exact affine minimization objective in this builder; return None.

## Parameters

expression: Affine

## Returns

None

## Example

builder.minimize(x)

Related: ModelBuilder

# ObligationView

A native-backed selection of goals. Index by position or label; count and len refer to this selection (including any applied limit). summary counts kinds and discharge state; to_list materializes the selection. Example: scope.missing(limit=20).

## Operators

__getitem__: Return Goal by selection index or label; stale handles raise ScopeError when inspected.
__len__: Return goal count for this selection, including its filter and limit.

# ObligationView.__getitem__

__getitem__(key: int | str) -> Goal

Return Goal by selection index or label; stale handles raise ScopeError when inspected.

Related: ObligationView

# ObligationView.__len__

__len__() -> int

Return goal count for this selection, including its filter and limit.

Related: ObligationView

# ObligationView.count

count: int

The number of goals in this view selection.

## Example

scope.obligations.count

Related: ObligationView

# ObligationView.summary

summary() -> dict[str, int]

Return counts by assertion kind and discharge state for this view.

## Returns

dict[str, int]

## Example

scope.obligations.summary()

Related: ObligationView

# ObligationView.to_list

to_list() -> list[Goal]

Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.

## Returns

list[Goal]

## Example

scope.obligations.to_list()

Related: ObligationView

# Proof

Proof(source: Model | Path, target: Model | Path)

Own the forward and reverse scopes for an explicit MI_OPT proof. source and target accept Model objects or model paths. Complete every leaf in both directions before compiling. Compilation writes one native certificate as RPA and RPX; only a successful fresh Kernel verification certifies the result. Example: Proof(source, target).

# Proof.certificate

certificate() -> CertificateView

Return a native CertificateView for inspection of the proof; completed proofs are required when materializing certificate data.

## Returns

CertificateView

## Example

proof.certificate()

Related: Proof

# Proof.compile

compile(directory: Path, *, target_artifact: Path | None=None) -> Bundle

Publish a self-contained Bundle to directory from a single native certificate snapshot. Both directions must be complete. target_artifact, if supplied, is copied byte-for-byte and audited. Different existing contents or aliases are rejected with ArtifactMismatchError. No Kernel certification is implied.

## Parameters

directory: Path
target_artifact: Path | None

## Returns

Bundle

## Example

proof.compile("build/bundle")

Related: Proof

# Proof.forward

forward: Scope

The source-to-target root Scope.

## Example

proof.forward

Related: Proof

# Proof.preflight

preflight() -> dict[str, int]

Return exact compiled sizes from the immutable native snapshot after both directions finish. Reuses lowering with compile; not certification.

## Returns

dict[str, int]

## Example

proof.preflight()

Related: Proof

# Proof.reverse

reverse: Scope

The target-to-source root Scope.

## Example

proof.reverse

Related: Proof

# Proof.source

source: Model

The source Model.

## Example

proof.source

Related: Proof

# Proof.target

target: Model

The target Model.

## Example

proof.target

Related: Proof

# Proof.verify

verify(directory: Path, *, target_artifact: Path | None=None, work: int | None=None, live_facts: int | None=None, depth: int | None=None) -> VerificationReport

Compile to directory then run Bundle.verify with the supplied work/live_facts/depth budgets. Return VerificationReport; call raise_for_status to require VERIFIED. target_artifact is copied and audited.

## Parameters

directory: Path
target_artifact: Path | None
work: int | None
live_facts: int | None
depth: int | None

## Returns

VerificationReport

## Example

proof.verify("build/bundle").raise_for_status()

Related: Proof

# Q

Q(numerator: Scalar | None=None, denominator: Scalar | None=None)

An immutable exact rational number. Accept int, exact str, Fraction, finite Decimal, or Q; reject bool, float, NaN and infinity. A zero denominator raises ZeroDivisionError. Arithmetic returns Q; int(q) truncates toward zero; bool(q) tests nonzero. Example: Q("1/3") + Q(1, 6).

## Operators

Comparison accepts exact numeric operands, but not strings.
__add__: Add an exact scalar or compatible rational; return Q.
__radd__: Reversed addition; return Q.
__sub__: Subtract a compatible operand; return Q.
__rsub__: Subtract self from the left operand; return Q.
__mul__: Scale by an exact scalar; return Q. Nonlinear products are not accepted.
__rmul__: Reversed exact scalar multiplication; return Q.
__truediv__: Divide by a nonzero exact scalar; return Q. ZeroDivisionError on zero.
__neg__: Negate without deriving a fact; return Q.
__rtruediv__: Divide an exact scalar by this nonzero Q; return Q.
__abs__: Return the nonnegative exact magnitude as Q.
__int__: Truncate toward zero and return int.
__bool__: Return False exactly when zero.
__lt__: Compare exact numeric values: less than; return bool.
__le__: Compare exact numeric values: less than or equal to; return bool.
__gt__: Compare exact numeric values: greater than; return bool.
__ge__: Compare exact numeric values: greater than or equal to; return bool.
__eq__: Compare exact numeric values: equal to; return bool.
__ne__: Compare exact numeric values: unequal to; return bool.
__hash__: Return a hash consistent with equality.

# Q.__abs__

__abs__() -> Q

Return the nonnegative exact magnitude as Q.

Related: Q

# Q.__add__

__add__(other: Scalar) -> Q

Add an exact scalar or compatible rational; return Q.

Related: Q

# Q.__bool__

__bool__() -> bool

Return False exactly when zero.

Related: Q

# Q.__eq__

__eq__(other: object) -> bool

Compare exact numeric values: equal to; return bool.

Related: Q

# Q.__ge__

__ge__(other: Scalar) -> bool

Compare exact numeric values: greater than or equal to; return bool.

Related: Q

# Q.__gt__

__gt__(other: Scalar) -> bool

Compare exact numeric values: greater than; return bool.

Related: Q

# Q.__hash__

__hash__() -> int

Return a hash consistent with equality.

Related: Q

# Q.__int__

__int__() -> int

Truncate toward zero and return int.

Related: Q

# Q.__le__

__le__(other: Scalar) -> bool

Compare exact numeric values: less than or equal to; return bool.

Related: Q

# Q.__lt__

__lt__(other: Scalar) -> bool

Compare exact numeric values: less than; return bool.

Related: Q

# Q.__mul__

__mul__(other: Scalar) -> Q

Scale by an exact scalar; return Q. Nonlinear products are not accepted.

Related: Q

# Q.__ne__

__ne__(other: object) -> bool

Compare exact numeric values: unequal to; return bool.

Related: Q

# Q.__neg__

__neg__() -> Q

Negate without deriving a fact; return Q.

Related: Q

# Q.__radd__

__radd__(other: Scalar) -> Q

Reversed addition; return Q.

Related: Q

# Q.__rmul__

__rmul__(other: Scalar) -> Q

Reversed exact scalar multiplication; return Q.

Related: Q

# Q.__rsub__

__rsub__(other: Scalar) -> Q

Subtract self from the left operand; return Q.

Related: Q

# Q.__rtruediv__

__rtruediv__(other: Scalar) -> Q

Divide an exact scalar by this nonzero Q; return Q.

Related: Q

# Q.__sub__

__sub__(other: Scalar) -> Q

Subtract a compatible operand; return Q.

Related: Q

# Q.__truediv__

__truediv__(other: Scalar) -> Q

Divide by a nonzero exact scalar; return Q. ZeroDivisionError on zero.

Related: Q

# Q.denominator

denominator: int

The reduced positive integer denominator.

## Example

q.denominator

Related: Q

# Q.numerator

numerator: int

The reduced signed integer numerator.

## Example

q.numerator

Related: Q

# ResourceLimitError

A configured resource budget was exhausted. Inspect report.statistics and retry verification with an explicit sufficient budget; this is not a proof rejection or certification.

# RowRef

A read-only named model row, with affine expression and optional lower/upper bounds. This is model data, not a proof Fact: use scope.row(row.name) for a witness. Example: model.rows[0].expression.

# RowRef.equality

equality: bool

Whether both row bounds coincide.

## Example

row.equality

Related: RowRef

# RowRef.expression

expression: Expr

The exact owned affine expression.

## Example

row.expression

Related: RowRef

# RowRef.index

index: int

The zero-based coordinate position; this alone does not carry ownership.

## Example

row.index

Related: RowRef

# RowRef.lower

lower: Q | None

The exact lower bound, or None if unbounded.

## Example

row.lower

Related: RowRef

# RowRef.name

name: str

The declared name.

## Example

row.name

Related: RowRef

# RowRef.upper

upper: Q | None

The exact upper bound, or None if unbounded.

## Example

row.upper

Related: RowRef

# RowsView

A native-backed row view indexed by name or position. Use iter(limit=20) for bounded inspection; to_list materializes every RowRef. Unknown names raise KeyError and invalid positions raise IndexError. Example: model.rows["balance"].

## Operators

__getitem__: Return RowRef by name or index; unknown names/indices fail.
__len__: Return row count without materialization.
__contains__: Test a row name.
__iter__: Iterate RowRef values lazily.

# RowsView.__contains__

__contains__(name: str) -> bool

Test a row name.

Related: RowsView

# RowsView.__getitem__

__getitem__(key: str | int) -> RowRef

Return RowRef by name or index; unknown names/indices fail.

Related: RowsView

# RowsView.__iter__

__iter__() -> Iterator[RowRef]

Iterate RowRef values lazily.

Related: RowsView

# RowsView.__len__

__len__() -> int

Return row count without materialization.

Related: RowsView

# RowsView.iter

iter(limit: int | None=None) -> Iterator[RowRef]

Return an iterator over at most limit entries; None means all. Only visited entries get Python wrappers.

## Parameters

limit: int | None

## Returns

Iterator[RowRef]

## Example

model.rows.iter(limit=20)

Related: RowsView

# RowsView.to_list

to_list() -> list[RowRef]

Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.

## Returns

list[RowRef]

## Example

model.rows.to_list()

Related: RowsView

# Scope

A proof-owned authoring scope. Declare an output-to-input map, inspect obligations, supply selected witnesses, then finish. Successful finish seals the leaf. split/lift turns the parent into a fixed container; work continues in children. Facts must be visible in this scope and belong to this Proof. Example: proof.forward.map(default="same_name").finish(). This is authoring completion, not certification.

# Scope.assumption

assumption: Fact

The branch assumption Fact; unavailable outside a branch.

## Example

scope.assumption

Related: Scope

# Scope.close_absurd

close_absurd(fact: Fact) -> None

Close a branch using a visible contradictory Fact; return None. The Kernel contradiction rule must hold.

## Parameters

fact: Fact

## Returns

None

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

branch.close_absurd(contradiction)

Related: Scope

# Scope.conclude

conclude(fact: Fact) -> None

Submit a visible Fact as the common conclusion of a Cases branch; return None. Its kind and expression must match the declared Cases conclusion.

## Parameters

fact: Fact

## Returns

None

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

cases.left.conclude(conclusion)

Related: Scope

# Scope.derive

derive: Derive

The explicit derivation interface bound to this scope.

## Example

scope.derive

Related: Scope

# Scope.drop

drop(facts: Fact | Iterable[Fact]) -> None

Drop selected visible local facts from subsequent availability; return None. Future derivations or goal discharge cannot reuse dropped facts.

## Parameters

facts: Fact | Iterable[Fact]

## Returns

None

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.drop(fact)

Related: Scope

# Scope.finish

finish() -> Scope

Check every obligation, seal this leaf, and return this Scope. Missing goals raise UnprovedGoalError and leave it editable. Success prevents further mutation but is not Kernel certification.

## Returns

Scope

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.finish()

Related: Scope

# Scope.integer

integer(variable: Variable) -> Fact

Return the Int Fact for an integral variable; a continuous variable is invalid.

## Parameters

variable: Variable

## Returns

Fact

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.integer("x")

Related: Scope

# Scope.lift_flow

lift_flow(spec: Any) -> LiftResult

Apply FlowSpec with explicit graph and group witnesses; return LiftResult. See FlowGroup for arc/node ordering and Generated for commodity fields.

## Parameters

spec: Any

## Returns

LiftResult

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

Related: Scope

# Scope.lift_interval

lift_interval(*, lower: Affine, upper: Affine, because: Fact | None=None) -> LiftResult

Create one variable between lower and upper in an extended child. because proves lower-upper <= 0; None requests literal truth only. Return LiftResult; success fixes the parent, failure leaves it editable.

## Parameters

lower: Affine
upper: Affine
because: Fact | None

## Returns

LiftResult

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

Related: Scope

# Scope.lift_intervals

lift_intervals(specs: Iterable[Any]) -> LiftResult

Apply ordered IntervalSpec inputs atomically and return LiftResult. See IntervalSpec for lower-major premise ordering and Generated for fields.

## Parameters

specs: Iterable[Any]

## Returns

LiftResult

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

Related: Scope

# Scope.lift_menus

lift_menus(specs: Iterable[Any]) -> LiftResult

Apply ordered MenuSpec inputs atomically and return LiftResult. Six ordered premises are required per item; see MenuSpec.

## Parameters

specs: Iterable[Any]

## Returns

LiftResult

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

Related: Scope

# Scope.lift_signed

lift_signed(specs: Iterable[Any]) -> LiftResult

Apply ordered SignedSpec inputs atomically and return LiftResult. Five ordered premises are required per item; see SignedSpec.

## Parameters

specs: Iterable[Any]

## Returns

LiftResult

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

Related: Scope

# Scope.lift_subflow

lift_subflow(spec: Any) -> LiftResult

Apply SubflowSpec with explicit graph and group witnesses; return LiftResult. See SubflowGroup for arc/node ordering and Generated for remainder fields.

## Parameters

spec: Any

## Returns

LiftResult

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

Related: Scope

# Scope.lower

lower(variable: Variable) -> Fact

Return the lower-bound Fact, normalized as lower - variable <= 0. The bound must exist.

## Parameters

variable: Variable

## Returns

Fact

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.lower("x")

Related: Scope

# Scope.map

map(overrides: dict[str, Affine] | None=None, *, default: Literal['same_name'] | None=None) -> Scope

Replace the entire mapping specification and return this Scope. overrides maps output variable names to input-space affine expressions. default="same_name" fills remaining output variables by name; without it coverage must be complete. Unknown names or uncovered coordinates raise MappingError; wrong spaces raise CoordinateSpaceError. Old Goal handles become stale, even if the new map is equivalent.

## Parameters

overrides: dict[str, Affine] | None
default: Literal['same_name'] | None

## Returns

Scope

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.map({"y": scope.vars["x"]}, default="same_name")

Related: Scope

# Scope.mapping

mapping: MappingView

The current native output-to-input mapping view.

## Example

scope.mapping

Related: Scope

# Scope.missing

missing(*, limit: int | None=None, kind: str | None=None) -> ObligationView

Return unresolved obligations filtered by kind and capped by limit. Omit limit to count all missing goals. Explicit witnesses, exact visible facts and literal truths are the only discharge routes.

## Parameters

limit: int | None
kind: str | None

## Returns

ObligationView

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.missing(limit=20, kind="Le")

Related: Scope

# Scope.model

model: Model

The input Model of this scope, including any extension coordinates.

## Example

scope.model

Related: Scope

# Scope.obligations

obligations: ObligationView

The native obligation view for the current mapping.

## Example

scope.obligations

Related: Scope

# Scope.output

output: Model

The output Model whose coordinates this scope maps.

## Example

scope.output

Related: Scope

# Scope.plan

plan() -> ObligationView

Return the same obligation view as obligations, based on the current mapping; no proof search occurs.

## Returns

ObligationView

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.plan()

Related: Scope

# Scope.prove

prove(goal: str | Goal, *, by: Combination) -> Fact

Derive and bind an exact witness to the selected goal label or Goal. by is a Fact, LinCombination or exact constant; both kind and full expression must match. Returns Fact. Stale/wrong-proof goals raise ScopeError; invalid combinations raise InvalidDerivationError.

## Parameters

goal: str | Goal
by: Combination

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.prove("objective.non_increasing", by=-scope.row("balance"))

Related: Scope

# Scope.pullback

pullback(expression: Affine) -> Expr

Substitute the current output-to-input map into an output-space expression and return an input-space Expr.

## Parameters

expression: Affine

## Returns

Expr

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.pullback(scope.output.objective)

Related: Scope

# Scope.row

row(row: str | int, *, side: Literal['lower', 'upper', 'equal'] | None=None) -> Fact

Return a proof Fact for a model row. Select lower, upper or equal with side when required; inequalities are normalized to expression <= 0.

## Parameters

row: str | int
side: Literal['lower', 'upper', 'equal'] | None

## Returns

Fact

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.row("balance")

Related: Scope

# Scope.split

split(expr: Affine, *, at: Scalar | None=None, kind: Literal['continuous', 'integer']='continuous', because: Fact | None=None) -> tuple[Scope, Scope]

Fix this parent and return left/right mapping scopes. Continuous branches assume expr <= at and expr >= at (including equality on both). Integer branches assume expr <= at and expr >= at+1; require integer at and an exact Int witness because for expr. For a single declared integral variable, omitting because uses its base integrality fact. Each child exposes assumption and must finish or close absurd.

## Parameters

expr: Affine
at: Scalar | None; None uses zero.
kind: Literal['continuous', 'integer']
because: Fact | None

## Returns

tuple[Scope, Scope]

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

scope.split(scope.vars["x"], at=0)

Related: Scope

# Scope.trace

trace: TraceView

The native instruction trace view.

## Example

scope.trace

Related: Scope

# Scope.upper

upper(variable: Variable) -> Fact

Return the upper-bound Fact, normalized as variable - upper <= 0. The bound must exist.

## Parameters

variable: Variable

## Returns

Fact

## Requirements and errors

Inspection does not require an editable scope. Coordinates must belong to this scope model; unknown names/indices or absent bounds fail. Goal handles remain subject to mapping-version and Proof ownership checks.

## Example

scope.upper("x")

Related: Scope

# Scope.vars

vars: VariablesView

The native-backed input variable view.

## Example

scope.vars

Related: Scope

# ScopeError

Wrong Proof/scope ownership, stale Goal, sealed scope or invisible Fact. Inspect the current scope and reacquire goals after mapping replacement; rebuild sealed proofs.

# SignedSpec

SignedSpec(capacity: Scalar, flow: Affine, activation: Affine, because: Sequence[Fact | None])

Construct positive/negative flow parts with disjoint binary activations.

## Fields

capacity: Exact nonnegative capacity C.
flow: Parent-space affine flow F.
activation: Parent-space affine activation Z.
because: Exactly five witnesses: Le(-Z), Le(Z-1), Int(Z), Le(F-C*Z), Le(-F-C*Z). None means literal truth only.

## Result

positive, negative, positive_activation, negative_activation variables; flow and activation equality facts; positive_capacity and negative_capacity inequality facts. See lifts.signed.

# SignedSpec.activation

activation: Affine

Parent-space affine activation Z.

Related: SignedSpec

# SignedSpec.because

because: Sequence[Fact | None]

Exactly five witnesses: Le(-Z), Le(Z-1), Int(Z), Le(F-C*Z), Le(-F-C*Z). None means literal truth only.

Related: SignedSpec

# SignedSpec.capacity

capacity: Scalar

Exact nonnegative capacity C.

Related: SignedSpec

# SignedSpec.flow

flow: Affine

Parent-space affine flow F.

Related: SignedSpec

# StandardMPSAdapter

StandardMPSAdapter(source: Model, *, objective_auxiliary: bool=True, objective_name: str='__mps_objective')

Prepare a standard-MPS-compatible model and explicit equivalence proof from source. objective_auxiliary controls an auxiliary objective variable; objective_name names it. Inspect report for transformations, then verify proof(). Example: adapter = StandardMPSAdapter(model).

# StandardMPSAdapter.proof

proof() -> Proof

Return the explicit bidirectional adapter Proof. Compile and verify it before claiming equivalence.

## Returns

Proof

## Example

adapter.proof()

Related: StandardMPSAdapter

# StandardMPSAdapter.report

report: dict[str, Any]

A dictionary describing the adapter transformations.

## Example

adapter.report

Related: StandardMPSAdapter

# StandardMPSAdapter.source

source: Model

The source Model.

## Example

adapter.source

Related: StandardMPSAdapter

# StandardMPSAdapter.target

target: Model

The target Model.

## Example

adapter.target

Related: StandardMPSAdapter

# SubflowGroup

SubflowGroup(source: int, demands: Sequence[tuple[int, Scalar]], flows: Sequence[Affine], nonnegative: Sequence[Fact | None], balances: Sequence[Fact | None])

Explicit aggregate flow from which a demand-serving subflow is selected.

## Fields

source: Zero-based source node within the enclosing SubflowSpec.
demands: Ordered (sink node, nonnegative exact demand) pairs.
flows: One parent-space affine input flow per arc, in SubflowSpec.arcs order.
nonnegative: One Le(-flows[a]) witness per arc, in arc order.
balances: One Eq witness per node in node-index order: outgoing minus incoming minus total demand at source, plus delivered demand at sinks. None requests literal truth only.

## Result

source, flows and balances for the generated subflow; remainder_nonnegative contains generated_flow-input_flow <= 0 per arc. No commodities field exists. See lifts.subflow.

# SubflowGroup.balances

balances: Sequence[Fact | None]

One Eq witness per node in node-index order: outgoing minus incoming minus total demand at source, plus delivered demand at sinks. None requests literal truth only.

Related: SubflowGroup

# SubflowGroup.demands

demands: Sequence[tuple[int, Scalar]]

Ordered (sink node, nonnegative exact demand) pairs.

Related: SubflowGroup

# SubflowGroup.flows

flows: Sequence[Affine]

One parent-space affine input flow per arc, in SubflowSpec.arcs order.

Related: SubflowGroup

# SubflowGroup.nonnegative

nonnegative: Sequence[Fact | None]

One Le(-flows[a]) witness per arc, in arc order.

Related: SubflowGroup

# SubflowGroup.source

source: int

Zero-based source node within the enclosing SubflowSpec.

Related: SubflowGroup

# SubflowSpec

SubflowSpec(nodes: int, arcs: Sequence[tuple[int, int]], groups: Sequence[SubflowGroup])

A directed graph and explicit subflow construction groups.

## Fields

nodes: Number of nodes; valid node indices are 0 through nodes-1.
arcs: Ordered (tail, head) pairs controlling flow and witness order.
groups: Ordered SubflowGroup records; each requires len(arcs) nonnegative and nodes balance witnesses.

## Requirements

Invalid graph sizes, demands or premises fail before installing the child. See lifts.subflow for a complete executable example.

# SubflowSpec.arcs

arcs: Sequence[tuple[int, int]]

Ordered (tail, head) pairs controlling flow and witness order.

Related: SubflowSpec

# SubflowSpec.groups

groups: Sequence[SubflowGroup]

Ordered SubflowGroup records; each requires len(arcs) nonnegative and nodes balance witnesses.

Related: SubflowSpec

# SubflowSpec.nodes

nodes: int

Number of nodes; valid node indices are 0 through nodes-1.

Related: SubflowSpec

# TermsView

A sparse native coefficient view keyed by coordinate index. Missing coefficients raise KeyError on indexing; get accepts a default. Iteration yields indices; items and values are lazy. Example: expr.terms.get(0, 0).

## Operators

__getitem__: Return Q coefficient at a stored coordinate; absent indices raise KeyError.
__len__: Return stored nonzero term count.
__iter__: Iterate coordinate indices lazily.

# TermsView.__getitem__

__getitem__(index: int) -> Q

Return Q coefficient at a stored coordinate; absent indices raise KeyError.

Related: TermsView

# TermsView.__iter__

__iter__() -> Iterator[int]

Iterate coordinate indices lazily.

Related: TermsView

# TermsView.__len__

__len__() -> int

Return stored nonzero term count.

Related: TermsView

# TermsView.get

get(index: int, default: Any=None) -> Any

Return the coefficient at index, or default when absent.

## Parameters

index: int
default: Any

## Returns

Any

## Example

expr.terms.get(0, 0)

Related: TermsView

# TermsView.items

items() -> Iterator[tuple[int, Q]]

Iterate stored (coordinate index, Q coefficient) pairs lazily.

## Returns

Iterator[tuple[int, Q]]

## Example

expr.terms.items()

Related: TermsView

# TermsView.keys

keys() -> Iterator[int]

Iterate stored coordinate indices lazily.

## Returns

Iterator[int]

## Example

expr.terms.keys()

Related: TermsView

# TermsView.to_dict

to_dict() -> dict[int, Q]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[int, Q]

## Example

expr.terms.to_dict()

Related: TermsView

# TermsView.values

values() -> Iterator[Q]

Iterate stored Q coefficients lazily.

## Returns

Iterator[Q]

## Example

expr.terms.values()

Related: TermsView

# UnprovedGoalError

finish found unresolved obligations. Inspect scope.missing(limit=20), supply selected witnesses and retry.

# VarRef

A variable expression bound to its builder or model coordinate space. Obtain it with model.vars["x"] or builder.add_var("x"); do not construct by index alone. Model edits produce a new space: obtain fresh handles from the edited model. Inherits affine arithmetic from Expr.

# VarRef.index

index: int

The zero-based coordinate position; this alone does not carry ownership.

## Example

variable.index

Related: VarRef

# VarRef.integer

integer: bool

Whether the variable is declared integral.

## Example

variable.integer

Related: VarRef

# VarRef.lower

lower: Q | None

The exact lower bound, or None if unbounded.

## Example

variable.lower

Related: VarRef

# VarRef.name

name: str

The declared name.

## Example

variable.name

Related: VarRef

# VarRef.upper

upper: Q | None

The exact upper bound, or None if unbounded.

## Example

variable.upper

Related: VarRef

# VariablesView

A native-backed variable view. Lookup by name, index or an owned VarRef; iteration wraps only visited items. Use iter(limit=20) for bounded inspection and to_list only for explicit full materialization. Example: model.vars["x"].

## Operators

__getitem__: Return VarRef by variable name, index or owned VarRef. Invalid names/indices fail.
__len__: Return variable count without materialization.
__contains__: Test a variable name.
__iter__: Iterate VarRef values lazily.

# VariablesView.__contains__

__contains__(name: str) -> bool

Test a variable name.

Related: VariablesView

# VariablesView.__getitem__

__getitem__(key: Variable) -> VarRef

Return VarRef by variable name, index or owned VarRef. Invalid names/indices fail.

Related: VariablesView

# VariablesView.__iter__

__iter__() -> Iterator[VarRef]

Iterate VarRef values lazily.

Related: VariablesView

# VariablesView.__len__

__len__() -> int

Return variable count without materialization.

Related: VariablesView

# VariablesView.iter

iter(limit: int | None=None) -> Iterator[VarRef]

Return an iterator over at most limit entries; None means all. Only visited entries get Python wrappers.

## Parameters

limit: int | None

## Returns

Iterator[VarRef]

## Example

model.vars.iter(limit=20)

Related: VariablesView

# VariablesView.to_list

to_list() -> list[VarRef]

Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.

## Returns

list[VarRef]

## Example

model.vars.to_list()

Related: VariablesView

# VerificationReport

Typed result of a fresh Kernel verification plus artifact audit. status must be VERIFIED for overall success; finish or compile alone is not certification. Read kernel and artifact_audit separately. Example: bundle.verify().raise_for_status().

# VerificationReport.artifact_audit

artifact_audit: dict[str, Any]

A copy of artifact audit details; inspect status independently.

## Example

report.artifact_audit

Related: VerificationReport

# VerificationReport.guarantee

guarantee: str | None

The Kernel guarantee on success, otherwise None.

## Example

report.guarantee

Related: VerificationReport

# VerificationReport.kernel

kernel: dict[str, Any]

A copy of the Kernel result, separate from artifact auditing.

## Example

report.kernel

Related: VerificationReport

# VerificationReport.raise_for_status

raise_for_status() -> VerificationReport

Return this report if status is VERIFIED. Raise ResourceLimitError for RESOURCE_LIMIT and KernelRejectedError for other non-success statuses.

## Returns

VerificationReport

## Example

report.raise_for_status()

Related: VerificationReport

# VerificationReport.statistics

statistics: dict[str, Any]

A copy of Kernel resource and proof statistics.

## Example

report.statistics

Related: VerificationReport

# VerificationReport.status

status: str

Overall verification status; only VERIFIED is success.

## Example

report.status

Related: VerificationReport

# VerificationReport.to_dict

to_dict() -> dict[str, Any]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[str, Any]

## Example

report.to_dict()

Related: VerificationReport

# lowlevel.Assembler

Assembler(scope: Scope)

Expert operand lists; uses exactly the same ownership checks and state machine.
Expert assembly in an existing editable Scope, using the same Compiler Core. Prefer scope.prove and scope.derive for ordinary authoring. Example: Assembler(scope).linear("Le", [(scope.upper("x"), 1)]).

# lowlevel.Assembler.assign

assign(checks: Iterable[Fact | None]) -> None

Finish a scope using checks in obligation order; None means a literal Exact witness. Requires exact coverage, valid witnesses and an editable scope.

## Parameters

checks: Iterable[Fact | None]

## Returns

None

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

assembler.assign([None])

Related: lowlevel.Assembler

# lowlevel.Assembler.linear

linear(kind: Kind, terms: Iterable[tuple[Fact, Scalar]], *, constant: Scalar | None=None, expect: Affine | None=None) -> Fact

Derive a Fact from explicit (Fact, coefficient) terms and constant with requested kind. expect checks the exact resulting expression. Same ownership and Kernel linear rules as Derive apply.

## Parameters

kind: Kind
terms: Iterable[tuple[Fact, Scalar]]
constant: Scalar | None; None uses zero.
expect: Affine | None

## Returns

Fact

## Requirements and errors

The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.

## Example

assembler.linear("Le", [(scope.upper("x"), 1)])

Related: lowlevel.Assembler

# lowlevel.CertificateBlockView

A native certificate block view. Index instructions to obtain StepView; to_dict includes instructions and the block end. Example: proof.certificate()["forward"].to_dict().

## Operators

__getitem__: Return StepView at a nonnegative index; out-of-range raises IndexError.
__len__: Return instruction count in this block.

# lowlevel.CertificateBlockView.__getitem__

__getitem__(index: int) -> StepView

Return StepView at a nonnegative index; out-of-range raises IndexError.

Related: lowlevel.CertificateBlockView

# lowlevel.CertificateBlockView.__len__

__len__() -> int

Return instruction count in this block.

Related: lowlevel.CertificateBlockView

# lowlevel.CertificateBlockView.to_dict

to_dict() -> dict[str, Any]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[str, Any]

## Example

block.to_dict()

Related: lowlevel.CertificateBlockView

# lowlevel.CertificateView

A native certificate view of a completed proof. Access forward/reverse blocks by key; to_dict explicitly materializes debug data. This is not a verification report. Example: proof.certificate()["forward"].

## Operators

__getitem__: Return CertificateBlockView for key forward or reverse; other keys raise KeyError.
__len__: Return 2, the forward/reverse block count.

# lowlevel.CertificateView.__getitem__

__getitem__(key: Literal['forward', 'reverse']) -> CertificateBlockView

Return CertificateBlockView for key forward or reverse; other keys raise KeyError.

Related: lowlevel.CertificateView

# lowlevel.CertificateView.__len__

__len__() -> int

Return 2, the forward/reverse block count.

Related: lowlevel.CertificateView

# lowlevel.CertificateView.to_dict

to_dict() -> dict[str, Any]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[str, Any]

## Example

certificate.to_dict()

Related: lowlevel.CertificateView

# lowlevel.StepView

A native view of one instruction. kind identifies the instruction; to_dict explicitly materializes its certificate-debug fields. Example: scope.trace[0].to_dict().

# lowlevel.StepView.kind

kind: str

The assertion or instruction kind.

## Example

step.kind

Related: lowlevel.StepView

# lowlevel.StepView.to_dict

to_dict() -> dict[str, Any]

Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.

## Returns

dict[str, Any]

## Example

step.to_dict()

Related: lowlevel.StepView

# lowlevel.TraceView

A native-backed proof trace. Indexing yields StepView; to_list explicitly materializes all instructions. Reading the trace does not certify the proof. Example: scope.trace[0].kind.

## Operators

__getitem__: Return StepView at a nonnegative index; out-of-range raises IndexError.
__len__: Return current instruction count.

# lowlevel.TraceView.__getitem__

__getitem__(index: int) -> StepView

Return StepView at a nonnegative index; out-of-range raises IndexError.

Related: lowlevel.TraceView

# lowlevel.TraceView.__len__

__len__() -> int

Return current instruction count.

Related: lowlevel.TraceView

# lowlevel.TraceView.to_list

to_list() -> list[dict[str, Any]]

Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.

## Returns

list[dict[str, Any]]

## Example

scope.trace.to_list()

Related: lowlevel.TraceView

# lowlevel.affine

affine(space: Model, constant: Scalar=0, terms: Mapping[int, Scalar] | Iterable[tuple[int, Scalar]]=()) -> Expr

Build an Expr from explicit coordinates in the supplied model space.

## Parameters

space: Model whose coordinates the indices refer to.
constant: Exact scalar constant, default zero.
terms: Index-to-coefficient mapping or iterable of (index, coefficient).

## Returns

Expr, accumulated by the native from_terms implementation.

## Errors

Invalid coordinate indices or inexact scalars fail; no name rebinding occurs.

## Example

affine(model, constant=1, terms=[(0, 2)])

# lowlevel.assemble

assemble(source: str, target: str) -> None

Assemble RPA source file into RPX target file using the frozen codec. Returns None; malformed input raises CompilerError. This does not verify a certificate.

# lowlevel.disassemble

disassemble(source: str, target: str) -> None

Disassemble RPX source file into RPA target file using the frozen codec. Returns None; malformed input raises CompilerError. This does not verify a certificate.

# lowlevel.verify

verify(source: str, target: str, proof: str, *, work: int | None=None, live_facts: int | None=None, depth: int | None=None) -> dict[str, Any]

Verify source/target model files and proof certificate with the frozen Kernel and optional work/live_facts/depth budgets. Return a result dictionary. Inspect status before claiming certification; this low-level function does not perform Bundle artifact audits.

# quicksum

quicksum(items: Iterable[Affine]) -> Expr

Return the affine sum of items with one native accumulator. The empty sum is Expr(0). Inputs must have compatible coordinate spaces; native views avoid per-coordinate Python construction. Example: quicksum(model.vars).
