from ._native import (
    Assembler as Assembler,
    CertificateView as CertificateView,
    TraceView as TraceView,
    StepView as StepView,
    CertificateBlockView as CertificateBlockView,
    assemble as assemble,
    disassemble as disassemble,
    verify as verify,
)
from ._native import Model, Scalar, Expr
from collections.abc import Mapping, Iterable

def affine(
    space: Model,
    constant: Scalar = 0,
    terms: Mapping[int, Scalar] | Iterable[tuple[int, Scalar]] = (),
) -> Expr: ...
