"""Explicit exact representation adaptation for standard decimal MPS.

This module chooses no reformulation or mathematical lemma. The caller selects
the adapter; its proof only scales the selected model's own rows/bounds and, when
needed, adds the uniquely defined value of its existing objective.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from fractions import Fraction
from math import gcd
from pathlib import Path
import tempfile

from .backend import Kernel, KernelError
from .expr import Expr, exact, _rational_text
from .model import Edit, Model, Row, Variable, _name
from .proof import BuildError


# Frozen codec.MAX_INTEGER_BYTES is 1700; derived intermediates have a separate,
# larger arithmetic bound. Every scalar actually encoded in a Lin must fit RPX.
_WIRE_SCALAR_BITS = 1700 * 8


def _nondecimal_part(denominator):
    # Remove 2 and 5 only: finite exact decimal coefficients need no scaling.
    denominator >>= (denominator & -denominator).bit_length() - 1
    while denominator % 5 == 0:
        denominator //= 5
    return denominator


def _proof_scalar(value, site):
    """Keep each generated Lin/map scalar within the existing wire/input limits."""
    try:
        value = exact(value)
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > _WIRE_SCALAR_BITS:
            raise ValueError(f"proof scalar exceeds the {_WIRE_SCALAR_BITS}-bit RPX component limit")
        exact(_rational_text(value))
    except (TypeError, ValueError) as error:
        raise BuildError(f"RESOURCE_LIMIT standard MPS adapter {site}: {error}") from error


def _scale(values, site, *, proof_values=None):
    values = tuple(values)
    scale = 1
    for value in values:
        if value is None:
            continue
        part = _nondecimal_part(value.denominator)
        ratio = part // gcd(scale, part)
        scale *= ratio
        if scale.bit_length() > 65536:
            raise BuildError(f"RESOURCE_LIMIT standard MPS adapter {site}: scale exceeds the 65536-bit rational limit")
    # Folding a row constant can create a denominator wider than either raw
    # bound or constant. Use the supplied original denominators to elaborate
    # the minimal normalized scale; gcd needs no factorization or proof search.
    remaining, chunk, chunks = scale, 1, []
    for value in values if proof_values is None else proof_values:
        if value is None:
            continue
        factor = gcd(remaining, _nondecimal_part(value.denominator))
        _proof_scalar(Fraction(factor), site + " scale factor")
        remaining //= factor
        if factor != 1:
            merged = chunk * factor
            if merged.bit_length() > _WIRE_SCALAR_BITS:
                chunks.append(Fraction(chunk))
                chunk = factor
            else:
                chunk = merged
    if remaining != 1:
        raise BuildError(f"Standard MPS adapter {site}: original denominators do not cover its normalized scale")
    if chunk != 1:
        chunks.append(Fraction(chunk))
    return Fraction(scale), tuple(chunks)


def _scaled_fact(builder, fact, chunks, *, reverse=False, negative=False):
    """Elaborate one supplied scaling using bounded ordinary Lin multipliers."""
    factors = tuple(reversed(chunks)) if reverse else chunks
    if not factors:
        return builder.eq([(fact, -1)]) if negative else fact
    for index, factor in enumerate(factors):
        multiplier = 1/factor if reverse else factor
        if negative and index == 0:
            multiplier = -multiplier
        fact = builder.lin(fact.kind, [(fact, multiplier)])
    return fact


def _fresh(base, occupied):
    base = _name(base)
    candidate, suffix = base, 1
    while candidate in occupied:
        ending = f"_{suffix}"
        candidate = base[:1024-len(ending)] + ending
        suffix += 1
    occupied.add(candidate)
    return candidate


@dataclass(frozen=True)
class _BoundMove:
    variable: int
    side: str
    row: int
    scale: Fraction
    chunks: tuple


@dataclass(frozen=True)
class _ObjectiveAuxiliary:
    variable: int
    row: int
    scale: Fraction
    chunks: tuple


class StandardMPSAdapter:
    """Inspectable, opt-in model representation with an ordinary RPX proof.

    ``source`` is the caller's unchanged model. ``target`` keeps every original
    variable in its original order. ``report`` is JSON-compatible inspection
    metadata; editing that returned dictionary never changes either model or
    the proof. The constructor checks actual standard MPS readback in Kernel.
    """
    __slots__ = ("_source", "_target", "_report", "_row_scales", "_bounds", "_objective", "_kernel")

    def __init__(self, source, *, objective_auxiliary=True, objective_name="__mps_objective"):
        if not isinstance(source, Model):
            raise TypeError("StandardMPSAdapter requires a Model")
        if type(objective_auxiliary) is not bool:
            raise TypeError("objective_auxiliary must be a boolean")
        _name(objective_name)
        kernel = source.kernel or Kernel()
        rows, scales, edits = [], [], []
        occupied_rows, occupied_vars = set(source.row_index), set(source.var_index)
        try:
            for index, row in enumerate(source.rows):
                lower = None if row.lower is None else exact(row.lower - row.expr.constant)
                upper = None if row.upper is None else exact(row.upper - row.expr.constant)
                scale, chunks = _scale((*row.expr.terms.values(), lower, upper), f"row {row.name!r}",
                                       proof_values=(*row.expr.terms.values(), row.expr.constant, row.lower, row.upper))
                normalized = Row(row.name, Expr(terms=((i, exact(scale*q)) for i, q in row.expr.terms.items())),
                                 None if lower is None else exact(scale*lower),
                                 None if upper is None else exact(scale*upper))
                rows.append(normalized)
                scales.append((scale, chunks))
                if normalized != row:
                    edits.append(Edit("StandardMPSRow", row.name, row, normalized,
                                      "Fold row constant and apply positive decimal representation scale"))
            variables, moves = [], []
            for index, variable in enumerate(source.vars):
                updated = variable
                for side in ("lower", "upper"):
                    bound = getattr(variable, side)
                    if bound is None or _nondecimal_part(bound.denominator) == 1:
                        continue
                    scale, chunks = _scale((bound,), f"{variable.name!r} {side} bound")
                    name = _fresh(f"__mps_bound_{index}_{side}", occupied_rows)
                    scaled_bound = exact(scale*bound)
                    row = Row(name, scale*Expr.var(index),
                              lower=scaled_bound if side == "lower" else None,
                              upper=scaled_bound if side == "upper" else None)
                    moves.append(_BoundMove(index, side, len(rows), scale, chunks))
                    rows.append(row)
                    updated = replace(updated, **{side: None})
                    edits.append(Edit("StandardMPSBoundRow", name, None, row,
                                      f"Move exact nonterminating {side} bound into a scaled row"))
                variables.append(updated)
                if updated != variable:
                    edits.append(Edit("SetBounds", variable.name, variable, updated,
                                      "Nonterminating sides remain enforced by explicit rows"))
            objective = source.objective
            auxiliary = None
            nonterminating_objective = any(_nondecimal_part(q.denominator) != 1
                                          for q in (objective.constant, *objective.terms.values()))
            if nonterminating_objective:
                if not objective_auxiliary:
                    raise BuildError("Standard MPS objective has a nonterminating exact decimal; enable objective_auxiliary")
                for q in (objective.constant, *objective.terms.values()):
                    _proof_scalar(q, "objective map")
                scale, chunks = _scale((objective.constant, *objective.terms.values()), "objective definition")
                name = _fresh(objective_name, occupied_vars)
                row_name = _fresh((name + "_definition")[:1024], occupied_rows)
                auxiliary = _ObjectiveAuxiliary(len(variables), len(rows), scale, chunks)
                cost = Variable(name, integer=False, lower=None, upper=None)
                variables.append(cost)
                definition = Row(row_name,
                                 Expr(terms=[(auxiliary.variable, scale),
                                             *((i, exact(-scale*q)) for i, q in objective.terms.items())]),
                                 exact(scale*objective.constant), exact(scale*objective.constant))
                rows.append(definition)
                objective = Expr.var(auxiliary.variable)
                edits.extend((Edit("AddVariable", name, None, cost, "Exact continuous objective value"),
                              Edit("AddRow", row_name, None, definition, "Define the original full objective exactly"),
                              Edit("SetObjective", source.name, source.objective, objective, "Minimize its exact value coordinate")))
            target = Model(source.name, variables, rows, objective, kernel=kernel,
                           ledger=(*source.ledger, *edits))
            # No rounding or fraction literals: acceptance uses the actual
            # standard-format reader and a complete exact named comparison.
            text = target.to_mps()
            byte_count = len(text.encode("utf-8"))
            if byte_count > 512*1024*1024:
                raise BuildError("RESOURCE_LIMIT standard MPS adapter: MPS exceeds the 512 MiB input limit")
            with tempfile.TemporaryDirectory(prefix="kernel-standard-mps-") as directory:
                mps = Path(directory) / "target.mps"
                mps.write_text(text)
                with Model.load(mps, kernel=kernel) as readback:
                    if not target.same_formulation(readback):
                        raise BuildError("Standard MPS adapter target differs from actual Kernel MPS readback")
            before, after = source.stats(), target.stats()
            report = {
                "before": before, "after": after,
                "added": {key: after[key]-before[key] for key in ("variables", "rows", "nonzeros")},
                "row_scales": [{"row": source.rows[i].name, "scale": _rational_text(scale),
                                **({"proof_chunks": [_rational_text(c) for c in chunks]} if len(chunks)>1 else {})}
                               for i, (scale, chunks) in enumerate(scales) if scale != 1],
                "bound_moves": [{"variable": source.vars[move.variable].name, "side": move.side,
                                 "bound": _rational_text(getattr(source.vars[move.variable], move.side)),
                                 "row": target.rows[move.row].name, "scale": _rational_text(move.scale)}
                                for move in moves],
                "objective_auxiliary": None if auxiliary is None else {
                    "variable": target.vars[auxiliary.variable].name,
                    "definition_row": target.rows[auxiliary.row].name,
                    "scale": _rational_text(auxiliary.scale),
                    "original_expression": source.objective.to_json()},
                "coefficient_stats": {"source": source.coefficient_stats(), "target": target.coefficient_stats()},
                "mps_readback": {"status": "MATCHED", "bytes": byte_count},
            }
        except BuildError:
            raise
        except (TypeError, ValueError, OSError, KernelError) as error:
            raise BuildError(f"Standard MPS adapter: {error}") from error
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_report", report)
        object.__setattr__(self, "_row_scales", tuple(scales))
        object.__setattr__(self, "_bounds", tuple(moves))
        object.__setattr__(self, "_objective", auxiliary)
        object.__setattr__(self, "_kernel", kernel)

    def __setattr__(self, name, value):
        raise AttributeError("StandardMPSAdapter is immutable; select a new adapter for another model")

    def __delattr__(self, name):
        raise AttributeError("StandardMPSAdapter is immutable")

    @property
    def source(self):
        return self._source

    @property
    def target(self):
        return self._target

    @property
    def report(self):
        return deepcopy(self._report)

    def proof(self):
        """Generate only mechanical MI and LP Equal affine inverse claims."""
        from .session import Proof
        proof = Proof(self.source, self.target, kernel=self._kernel)
        forward = {v.name: self.source.var(i) for i, v in enumerate(self.source.vars)}
        reverse = {v.name: self.target.var(i) for i, v in enumerate(self.source.vars)}
        if self._objective is not None:
            forward[self.target.vars[self._objective.variable].name] = self.source.objective
        try:
            for integers in (True, False):
                f, r = proof.bijection(forward, reverse, integers=integers, projection="retained")
                for index, (scale, chunks) in enumerate(self._row_scales):
                    if scale == 1:
                        continue
                    row = self.source.rows[index]
                    if row.equality:
                        _scaled_fact(f, f.row(index), chunks)
                        _scaled_fact(r, r.row(index), chunks, reverse=True)
                    else:
                        for side in ("Lower", "Upper"):
                            if getattr(row, side.lower()) is not None:
                                _scaled_fact(f, f.row(index, side=side), chunks)
                                _scaled_fact(r, r.row(index, side=side), chunks, reverse=True)
                for move in self._bounds:
                    side = move.side.capitalize()
                    bound = f.lower(move.variable) if move.side == "lower" else f.upper(move.variable)
                    _scaled_fact(f, bound, move.chunks)
                    _scaled_fact(r, r.row(move.row, side=side), move.chunks, reverse=True)
                if self._objective is not None:
                    _scaled_fact(r, r.row(self._objective.row), self._objective.chunks,
                                 reverse=True, negative=True)
                f.complete()
                r.complete()
            return proof
        except BaseException:
            proof.close()
            raise
