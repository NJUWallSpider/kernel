"""Expert inspection and assembly over the same frozen RPX formats."""

from ._native import (
    assemble,
    disassemble,
    verify,
    CertificateView,
    TraceView,
    StepView,
    CertificateBlockView,
    Assembler,
)


def affine(space, constant=0, terms=()):
    """Explicit positional authoring; the coordinate space is mandatory."""
    from . import Expr

    if hasattr(terms, "items"):
        return Expr.from_terms(space, terms.keys(), terms.values(), constant=constant)
    terms = tuple(terms)
    return Expr.from_terms(
        space, (i for i, _ in terms), (q for _, q in terms), constant=constant
    )
