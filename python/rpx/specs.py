"""Explicit inputs for the Kernel's existing constructive rules.

None in a premise position requests a literal Exact witness, never proof search.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ._native import Affine, Scalar, Fact


@dataclass(frozen=True)
class IntervalSpec:
    """Ordered interval bounds and explicit pairwise feasibility witnesses.

    ## Fields
    lower: Sequence of lower affine bounds L[i] in the parent space.
    upper: Sequence of upper affine bounds U[j] in the parent space.
    because: Exactly len(lower)*len(upper) witnesses for L[i]-U[j] <= 0, lower-major then upper-minor. None means literal truth, never automatic fact lookup.

    ## Result
    One Generated item with variable, lower_rows (L[i]-variable <= 0) and upper_rows (variable-U[j] <= 0). See lifts.interval for a runnable example.
    """

    lower: Sequence[Affine]
    upper: Sequence[Affine]
    because: Sequence[Fact | None]


@dataclass(frozen=True)
class MenuSpec:
    """Construct a binary menu for an activated integer index.

    ## Fields
    maximum_index: Nonnegative integer K; generates K+1 binary options.
    activation: Parent-space affine value A, proved binary by the first three premises.
    index: Parent-space affine value I, proved integral and between 0 and K*A.
    because: Exactly six witnesses in order: Le(-A), Le(A-1), Int(A), Le(-I), Le(I-K*A), Int(I). None means literal truth only.

    ## Result
    options[0..K], sum (sum(options)-A = 0), moment (sum(j*options[j])-I = 0). See lifts.menu for executable usage.
    """

    maximum_index: int
    activation: Affine
    index: Affine
    because: Sequence[Fact | None]


@dataclass(frozen=True)
class SignedSpec:
    """Construct positive/negative flow parts with disjoint binary activations.

    ## Fields
    capacity: Exact nonnegative capacity C.
    flow: Parent-space affine flow F.
    activation: Parent-space affine activation Z.
    because: Exactly five witnesses: Le(-Z), Le(Z-1), Int(Z), Le(F-C*Z), Le(-F-C*Z). None means literal truth only.

    ## Result
    positive, negative, positive_activation, negative_activation variables; flow and activation equality facts; positive_capacity and negative_capacity inequality facts. See lifts.signed.
    """

    capacity: Scalar
    flow: Affine
    activation: Affine
    because: Sequence[Fact | None]


@dataclass(frozen=True)
class FlowGroup:
    """Explicit aggregate flow to decompose into selected commodities.

    ## Fields
    source: Zero-based source node within the enclosing FlowSpec.
    commodities: Ordered (sink node, nonnegative exact demand) pairs.
    flows: One parent-space affine aggregate flow per arc, in FlowSpec.arcs order.
    nonnegative: One Le(-flows[a]) witness per arc, in arc order.
    balances: One Eq witness per node in node-index order: outgoing minus incoming minus total demand at source, plus delivered demand at sinks, zero elsewhere. None requests literal truth only.

    ## Result
    A group Generated record with source, commodities and recovery. Each commodity has sink, demand, flows and balances. Recovery is sum of commodity flows minus input flow = 0 per arc. See lifts.flow.
    """

    source: int
    commodities: Sequence[tuple[int, Scalar]]
    flows: Sequence[Affine]
    nonnegative: Sequence[Fact | None]
    balances: Sequence[Fact | None]


@dataclass(frozen=True)
class FlowSpec:
    """A directed graph and explicit commodity decomposition groups.

    ## Fields
    nodes: Number of nodes; valid node indices are 0 through nodes-1.
    arcs: Ordered (tail, head) pairs. The order determines every flow and arc-witness position.
    groups: Ordered FlowGroup records; each requires len(arcs) nonnegative and nodes balance witnesses.

    ## Requirements
    Graph, demands and sizes must satisfy the frozen Kernel construction checks. Invalid inputs raise InvalidDerivationError or ResourceLimitError before parent mutation. See lifts.flow for a complete example.
    """

    nodes: int
    arcs: Sequence[tuple[int, int]]
    groups: Sequence[FlowGroup]


@dataclass(frozen=True)
class SubflowGroup:
    """Explicit aggregate flow from which a demand-serving subflow is selected.

    ## Fields
    source: Zero-based source node within the enclosing SubflowSpec.
    demands: Ordered (sink node, nonnegative exact demand) pairs.
    flows: One parent-space affine input flow per arc, in SubflowSpec.arcs order.
    nonnegative: One Le(-flows[a]) witness per arc, in arc order.
    balances: One Eq witness per node in node-index order: outgoing minus incoming minus total demand at source, plus delivered demand at sinks. None requests literal truth only.

    ## Result
    source, flows and balances for the generated subflow; remainder_nonnegative contains generated_flow-input_flow <= 0 per arc. No commodities field exists. See lifts.subflow.
    """

    source: int
    demands: Sequence[tuple[int, Scalar]]
    flows: Sequence[Affine]
    nonnegative: Sequence[Fact | None]
    balances: Sequence[Fact | None]


@dataclass(frozen=True)
class SubflowSpec:
    """A directed graph and explicit subflow construction groups.

    ## Fields
    nodes: Number of nodes; valid node indices are 0 through nodes-1.
    arcs: Ordered (tail, head) pairs controlling flow and witness order.
    groups: Ordered SubflowGroup records; each requires len(arcs) nonnegative and nodes balance witnesses.

    ## Requirements
    Invalid graph sizes, demands or premises fail before installing the child. See lifts.subflow for a complete executable example.
    """

    nodes: int
    arcs: Sequence[tuple[int, int]]
    groups: Sequence[SubflowGroup]
