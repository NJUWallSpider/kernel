"""Exact, scoped proof authoring with explicit Kernel certification.

Start offline with ``python -m rpx help quickstart`` and run the self-contained
example with ``python -m rpx._help.examples.quickstart``. Use ``help(Model)``
or ``python -m rpx help Scope.map`` for contracts, and ``python -m rpx help agent``
for task navigation. JSON discovery: ``python -m rpx help --list --format json``.

ModelBuilder creates owned exact models. Proof owns forward/reverse scopes;
map, inspect goals, supply selected witnesses, and finish each leaf. compile
returns a portable Bundle; only a fresh VERIFIED Kernel result certifies it.
Fact arithmetic builds LinCombination, while variable arithmetic builds Expr.
Use Q or exact strings, never float. Expert codecs and assembly live in
rpx.lowlevel. Help queries read definitions/resources only, without proof work.
"""

from ._native import (
    Q,
    Expr,
    VarRef,
    Model,
    ModelBuilder,
    Fact,
    LinCombination,
    Scope,
    Goal,
    VariablesView,
    RowsView,
    RowRef,
    TermsView,
    MappingView,
    ObligationView,
    Derive,
    Cases,
    LiftResult,
    Generated,
    quicksum,
    CompilerError,
    CoordinateSpaceError,
    ScopeError,
    MappingError,
    InvalidDerivationError,
    UnprovedGoalError,
    ResourceLimitError,
    ArtifactMismatchError,
    KernelRejectedError,
)
from .proof import Proof, StandardMPSAdapter
from .artifacts import Bundle, Chain, VerificationReport
from .specs import (
    IntervalSpec,
    MenuSpec,
    SignedSpec,
    FlowSpec,
    FlowGroup,
    SubflowSpec,
    SubflowGroup,
)

__all__ = [
    "Q",
    "Expr",
    "VarRef",
    "Model",
    "ModelBuilder",
    "Fact",
    "LinCombination",
    "Scope",
    "Goal",
    "VariablesView",
    "RowsView",
    "RowRef",
    "TermsView",
    "MappingView",
    "ObligationView",
    "Derive",
    "Cases",
    "LiftResult",
    "Generated",
    "quicksum",
    "CompilerError",
    "CoordinateSpaceError",
    "ScopeError",
    "MappingError",
    "InvalidDerivationError",
    "UnprovedGoalError",
    "ResourceLimitError",
    "ArtifactMismatchError",
    "KernelRejectedError",
    "Proof",
    "StandardMPSAdapter",
    "Bundle",
    "Chain",
    "VerificationReport",
    "IntervalSpec",
    "MenuSpec",
    "SignedSpec",
    "FlowSpec",
    "FlowGroup",
    "SubflowSpec",
    "SubflowGroup",
]
