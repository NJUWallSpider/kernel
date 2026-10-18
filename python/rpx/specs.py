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
    lower: Sequence[Affine]
    upper: Sequence[Affine]
    because: Sequence[Fact | None]


@dataclass(frozen=True)
class MenuSpec:
    maximum_index: int
    activation: Affine
    index: Affine
    because: Sequence[Fact | None]


@dataclass(frozen=True)
class SignedSpec:
    capacity: Scalar
    flow: Affine
    activation: Affine
    because: Sequence[Fact | None]


@dataclass(frozen=True)
class FlowGroup:
    source: int
    commodities: Sequence[tuple[int, Scalar]]
    flows: Sequence[Affine]
    nonnegative: Sequence[Fact | None]
    balances: Sequence[Fact | None]


@dataclass(frozen=True)
class FlowSpec:
    nodes: int
    arcs: Sequence[tuple[int, int]]
    groups: Sequence[FlowGroup]


@dataclass(frozen=True)
class SubflowGroup:
    source: int
    demands: Sequence[tuple[int, Scalar]]
    flows: Sequence[Affine]
    nonnegative: Sequence[Fact | None]
    balances: Sequence[Fact | None]


@dataclass(frozen=True)
class SubflowSpec:
    nodes: int
    arcs: Sequence[tuple[int, int]]
    groups: Sequence[SubflowGroup]
