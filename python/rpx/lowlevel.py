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
    """Build an Expr from explicit coordinates in the supplied model space.

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
    """
    from . import Expr

    if hasattr(terms, "items"):
        return Expr.from_terms(space, terms.keys(), terms.values(), constant=constant)
    terms = tuple(terms)
    return Expr.from_terms(
        space, (i for i, _ in terms), (q for _, q in terms), constant=constant
    )


__all__ = [
    "affine",
    "assemble",
    "disassemble",
    "verify",
    "CertificateView",
    "TraceView",
    "StepView",
    "CertificateBlockView",
    "Assembler",
]
