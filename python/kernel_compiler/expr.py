"""Exact sparse affine expressions used by the proof authoring API.

Expressions use the kernel's coordinate indices. All coefficients are Fractions;
floating point input is rejected before it can enter a model or a certificate.
"""
from __future__ import annotations

from fractions import Fraction
from decimal import Decimal
from itertools import islice
from types import MappingProxyType
from collections.abc import Mapping
import re


def rational(value=0) -> Fraction:
    """Parse an exact integer, Fraction, decimal string, or rational string."""
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise TypeError("Use an integer, Fraction, or exact string (for example '0.1'); floats are forbidden")
    if isinstance(value, str):
        if not value or not value.isascii() or any(c.isspace() for c in value) or "_" in value:
            raise ValueError(f"Invalid exact rational {value!r}")
        if len(value) > 8224:
            raise ValueError("Rational text exceeds the kernel's number-text limit")
        value = value.replace("D", "E").replace("d", "e")
        # Fraction accepts negative denominators only via its two-argument form.
        if "/" in value:
            n, d = value.split("/")
            if not all(re.fullmatch(r"[+-]?[0-9]+", part) for part in (n, d)):
                raise ValueError(f"Invalid rational fraction {value!r}")
            if any(len(part.lstrip("+-")) > 4096 for part in (n, d)):
                raise ValueError("Integer literal exceeds the kernel's 4096-digit limit")
            value = Fraction(int(n), int(d))
        else:
            if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value):
                raise ValueError(f"Invalid exact rational {value!r}")
            parts = re.split("[eE]", value)
            if len(parts) == 2 and (len(parts[1].lstrip("+-")) > 6 or abs(int(parts[1])) > 4096):
                raise ValueError("Decimal exponent exceeds the kernel's limit")
            mantissa = parts[0].lstrip("+-")
            if sum(c.isdigit() for c in mantissa) > 4096:
                raise ValueError("Decimal literal exceeds the kernel's 4096-digit limit")
            fractional = len(mantissa.split(".")[1]) if "." in mantissa else 0
            if abs((int(parts[1]) if len(parts) == 2 else 0) - fractional) > 4096:
                raise ValueError("Effective decimal exponent exceeds the kernel's limit")
    result = Fraction(value)
    if abs(result.numerator).bit_length() > 65536 or result.denominator.bit_length() > 65536:
        raise ValueError("Rational exceeds the kernel's 65536-bit limit")
    return result


def coordinate(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**32:
        raise ValueError(f"Invalid coordinate index {value!r}")
    return value


exact = rational


def _rational_text(value):
    """Canonical Fraction text without changing Python's global digit policy."""
    try:
        return str(value)
    except ValueError:
        # Python 3.11+ limits int<->decimal text conversion. Decimal's exact
        # integer constructor/formatting does not depend on that global limit
        # or the caller's Decimal precision, and no floating arithmetic occurs.
        numerator = format(Decimal(value.numerator), "f")
        return numerator if value.denominator == 1 else numerator + "/" + format(Decimal(value.denominator), "f")


def _metadata_rational(value):
    """Decode bounded Kernel intermediate metadata, never proof scalar input."""
    if not isinstance(value, str):
        return rational(value)
    if len(value) > 2 * 19729 + 3:
        raise ValueError("Intermediate rational text exceeds the kernel's bit limit")
    if not re.fullmatch(r"[+-]?[0-9]+(?:/[+-]?[0-9]+)?", value):
        return rational(value)
    parts = value.split("/")
    numbers = []
    for part in parts:
        if len(part.lstrip("+-")) > 19729:
            raise ValueError("Intermediate integer exceeds the kernel's bit limit")
        try:
            number = int(part)
        except ValueError:
            number = int(Decimal(part))
        if abs(number).bit_length() > 65536:
            raise ValueError("Intermediate rational exceeds the kernel's 65536-bit limit")
        numbers.append(number)
    return rational(Fraction(*numbers))


from ._native import Expr as _NativeExpr


Expr = _NativeExpr


as_expr = lambda value: value if isinstance(value, Expr) else Expr(value)


def linear_sum(items):
    constant, terms = Fraction(0), {}
    for value in items:
        expression = as_expr(value)
        constant += expression.constant
        for index, coefficient in expression.terms.items():
            terms[index] = terms.get(index, Fraction(0)) + coefficient
    return Expr(constant, terms)
