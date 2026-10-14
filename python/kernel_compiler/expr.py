"""Exact sparse affine expressions used by the proof authoring API.

Expressions use the kernel's coordinate indices. All coefficients are Fractions;
floating point input is rejected before it can enter a model or a certificate.
"""
from __future__ import annotations

from fractions import Fraction
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


class Expr:
    """Immutable affine expression: constant + sum(coefficient * coordinate).

    ``Expr(terms={0: '1/3', 2: -1})`` and ``Expr.var(0) / 3 - Expr.var(2)``
    denote the same expression. Multiplication is deliberately scalar-only.
    """
    __slots__ = ("_constant", "_terms", "_hash")

    def __init__(self, constant=0, terms=None):
        object.__setattr__(self, "_constant", rational(constant))
        accumulated = {}
        pairs = (terms or {}).items() if isinstance(terms, Mapping) else (terms or ())
        for index, coefficient in pairs:
            index, coefficient = coordinate(index), rational(coefficient)
            accumulated[index] = accumulated.get(index, Fraction(0)) + coefficient
        object.__setattr__(self, "_terms", MappingProxyType(dict(sorted((i, q) for i, q in accumulated.items() if q))))
        object.__setattr__(self, "_hash", hash((self._constant, tuple(self._terms.items()))))

    def __setattr__(self, name, value):
        raise AttributeError("Expressions are immutable")

    @property
    def constant(self):
        return self._constant

    @property
    def terms(self):
        return self._terms

    @classmethod
    def var(cls, index):
        return cls(0, {coordinate(index): 1})

    @staticmethod
    def coerce(value):
        return as_expr(value)

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, Mapping) or set(data) - {"constant", "terms"}:
            raise ValueError("An expression must contain only constant and terms")
        return cls(data.get("constant", 0), data.get("terms", ()))

    def to_json(self):
        return {"constant": str(self.constant), "terms": [[i, str(q)] for i, q in self.terms.items()]}

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, Expr):
            return self.constant == other.constant and self.terms == other.terms
        if isinstance(other, (int, str, Fraction)) and not isinstance(other, bool):
            return not self.terms and self.constant == rational(other)
        return False

    def __bool__(self):
        return bool(self.constant or self.terms)

    def __add__(self, other):
        other = as_expr(other)
        terms = dict(self.terms)
        for index, coefficient in other.terms.items():
            terms[index] = terms.get(index, Fraction(0)) + coefficient
        return Expr(self.constant + other.constant, terms)

    __radd__ = __add__

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + -as_expr(other)

    def __rsub__(self, other):
        return as_expr(other) + -self

    def __mul__(self, scalar):
        scalar = rational(scalar)
        return Expr(self.constant * scalar, ((i, q * scalar) for i, q in self.terms.items()))

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return self * (1 / rational(scalar))

    def coefficient(self, index):
        return self.terms.get(coordinate(index), Fraction(0))

    def substitute(self, replacements):
        """Simultaneously replace coordinates; unspecified coordinates stay unchanged.

        A sequence denotes a full coordinate map. A mapping permits partial maps.
        Replacements are not recursively substituted; this avoids order-dependent
        behavior and makes self-referential maps unambiguous.
        """
        mapping = isinstance(replacements, Mapping)
        constant, terms = self.constant, {}
        for index, coefficient in self.terms.items():
            replacement = as_expr(replacements[index]) if not mapping or index in replacements else Expr.var(index)
            constant += coefficient * replacement.constant
            for new_index, new_coefficient in replacement.terms.items():
                terms[new_index] = terms.get(new_index, Fraction(0)) + coefficient * new_coefficient
        return Expr(constant, terms)

    def evaluate(self, values):
        return self.constant + sum((q * rational(values[i]) for i, q in self.terms.items()), Fraction(0))

    def __repr__(self):
        return f"Expr(constant={str(self.constant)!r}, terms={{{', '.join(f'{i}: {str(q)!r}' for i, q in self.terms.items())}}})"


def as_expr(value) -> Expr:
    return value if isinstance(value, Expr) else Expr(value)


def linear_sum(items) -> Expr:
    """Accumulate expressions in one sparse pass, avoiding repeated map copies."""
    constant, terms = Fraction(0), {}
    for value in items:
        expression = as_expr(value)
        constant += expression.constant
        for index, coefficient in expression.terms.items():
            terms[index] = terms.get(index, Fraction(0)) + coefficient
    return Expr(constant, terms)
