"""Exact model readback, explicit edits, and sparse model queries.

The immutable model value is native; this module keeps the Python dataclasses,
the edit ledger, and the standard-text exporters.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
import json
from pathlib import Path
import tempfile
from types import MappingProxyType

from . import _native
from .expr import Expr, as_expr, coordinate, rational


def _name(value):
    if not isinstance(value, str) or not value or not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"Invalid model name {value!r}")
    if len(value) > 1024:
        raise ValueError("Name exceeds the kernel's 1024-byte limit")
    return value


def _bound(value):
    return None if value is None else rational(value)


@dataclass(frozen=True)
class Variable:
    name: str
    integer: bool = False
    lower: Fraction | None = Fraction(0)
    upper: Fraction | None = None

    def __post_init__(self):
        _name(self.name)
        if not isinstance(self.integer, bool):
            raise TypeError("The integer declaration must be a boolean")
        object.__setattr__(self, "lower", _bound(self.lower))
        object.__setattr__(self, "upper", _bound(self.upper))

    def to_json(self):
        return {"name": self.name, "integer": self.integer,
                "lower": None if self.lower is None else str(self.lower),
                "upper": None if self.upper is None else str(self.upper)}


@dataclass(frozen=True)
class Row:
    name: str
    expr: Expr
    lower: Fraction | None = None
    upper: Fraction | None = None

    def __post_init__(self):
        _name(self.name)
        object.__setattr__(self, "expr", as_expr(self.expr))
        object.__setattr__(self, "lower", _bound(self.lower))
        object.__setattr__(self, "upper", _bound(self.upper))

    @property
    def equality(self):
        return self.lower is not None and self.lower == self.upper

    def to_json(self):
        return {"name": self.name, "expr": self.expr.to_json(),
                "lower": None if self.lower is None else str(self.lower),
                "upper": None if self.upper is None else str(self.upper)}


@dataclass(frozen=True)
class Edit:
    kind: str
    subject: str
    before: object = None
    after: object = None
    reason: str | None = None

    def to_json(self):
        def value(item):
            if hasattr(item, "to_json"):
                return item.to_json()
            if isinstance(item, Fraction):
                return str(item)
            if isinstance(item, Mapping):
                return {str(k): value(v) for k, v in item.items()}
            if isinstance(item, (tuple, list)):
                return [value(v) for v in item]
            return item
        return {"kind": self.kind, "subject": self.subject, "before": value(self.before),
                "after": value(self.after), "reason": self.reason}


class EditLedger(tuple):
    def to_json(self):
        return [edit.to_json() for edit in self]


def _variable(value):
    return value if isinstance(value, Variable) else Variable(**value)


def _row(value):
    if isinstance(value, Row):
        return value
    if "expr" in value and not isinstance(value["expr"], Expr):
        value = {**value, "expr": Expr.from_json(value["expr"]) if isinstance(value["expr"], Mapping) else value["expr"]}
    return Row(**value)


class Model:
    """An ordered, exact model with immutable variables, rows, and expressions."""
    _structural_fields = frozenset(("name", "vars", "variables", "rows", "objective", "var_index", "row_index", "ledger"))

    def __setattr__(self, name, value):
        if name in self._structural_fields and name in self.__dict__:
            raise AttributeError(f"Model.{name} is immutable; use a model edit method to construct a new model")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if name in self._structural_fields:
            raise AttributeError(f"Model.{name} is immutable")
        object.__delattr__(self, name)

    def __init__(self, name="MODEL", variables=(), rows=(), objective=0, *, vars=None,
                 kernel=None, path=None, ledger=()):
        if vars is not None:
            if variables:
                raise ValueError("Specify variables or vars, not both")
            variables = vars
        name = _name(name)
        variables = tuple(_variable(v) for v in variables)
        rows = tuple(_row(r) for r in rows)
        if isinstance(objective, Mapping):
            objective = Expr.from_json(objective)
        objective = as_expr(objective)
        try:
            native = _native.Model(name, variables, rows, objective)
        except (ValueError, TypeError) as error:
            raise type(error)(str(error)) from None
        self._bind(native, name, kernel, path, ledger, variables, rows, objective)

    def _bind(self, native, name, kernel, path, ledger, variables=None, rows=None, objective=None):
        if objective is None:
            objective = native.objective
        object.__setattr__(self, "_native", native)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_vars_cache", variables)
        object.__setattr__(self, "_rows_cache", rows)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "kernel", kernel)
        object.__setattr__(self, "path", None if path is None else Path(path).resolve())
        object.__setattr__(self, "ledger", EditLedger(ledger))
        object.__setattr__(self, "var_index", MappingProxyType(dict(native.var_index)))
        object.__setattr__(self, "row_index", MappingProxyType(dict(native.row_index)))
        object.__setattr__(self, "_temporary", None)

    @property
    def vars(self):
        value = self.__dict__.get("_vars_cache")
        if value is None:
            value = tuple(Variable(*item) for item in self._native.vars)
            object.__setattr__(self, "_vars_cache", value)
        return value

    @property
    def variables(self):
        return self.vars

    @property
    def rows(self):
        value = self.__dict__.get("_rows_cache")
        if value is None:
            value = tuple(Row(item[0], item[1], item[2], item[3]) for item in self._native.rows)
            object.__setattr__(self, "_rows_cache", value)
        return value

    @classmethod
    def _from_native(cls, native, *, kernel=None, path=None, ledger=(), variables=None, rows=None, objective=None):
        obj = object.__new__(cls)
        obj._bind(native, native.name, kernel, path, ledger, variables, rows, objective)
        return obj

    def _wrap(self, native, ledger, *, variables=None, rows=None, objective=None):
        return Model._from_native(native, kernel=self.kernel, path=self.path,
                                  ledger=ledger, variables=variables, rows=rows, objective=objective)

    def close(self):
        temporary, self._temporary = self._temporary, None
        if temporary is not None:
            temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        temporary = getattr(self, "_temporary", None)
        if temporary is not None:
            temporary.cleanup()

    @classmethod
    def from_json(cls, data, kernel=None):
        if not isinstance(data, Mapping) or set(data) - {"name", "variables", "vars", "rows", "objective"}:
            raise ValueError("Invalid canonical model JSON fields")
        if "variables" in data and "vars" in data:
            raise ValueError("Model JSON specifies both variables and vars")
        return cls(data["name"], data.get("variables", data.get("vars", ())),
                   data.get("rows", ()), data.get("objective", 0), kernel=kernel)

    @classmethod
    def load(cls, path, kernel=None):
        path = Path(path).resolve()
        if path.suffix.lower() == ".json":
            return cls.from_json(json.loads(path.read_text()), kernel=kernel)
        native = _native.Model.load(str(path))
        result = cls._from_native(native, kernel=kernel, path=path)
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic != b"MCM\0":
            temporary = tempfile.TemporaryDirectory(prefix="kernel-model-")
            canonical = Path(temporary.name) / "model.mcm"
            canonical.write_bytes(result.to_mcm())
            object.__setattr__(result, "path", canonical.resolve())
            object.__setattr__(result, "_temporary", temporary)
        return result

    def to_json(self):
        return {"name": self.name, "variables": [v.to_json() for v in self.vars],
                "rows": [r.to_json() for r in self.rows], "objective": self.objective.to_json()}

    def _index(self, identifier, *, row=False):
        if isinstance(identifier, Variable):
            identifier = identifier.name
        elif isinstance(identifier, Row):
            identifier = identifier.name
        return self._native.index_of(identifier, row)

    def var(self, identifier):
        return self._native.var(identifier)

    def row(self, identifier):
        item = self._native.row(identifier)
        return Row(item[0], item[1], item[2], item[3])

    def ref(self, kind, identifier):
        return self._native.ref_(kind, identifier)

    def fact(self, kind, identifier):
        return self._native.fact(kind, identifier)

    def _edited(self, edits=(), **changes):
        return Model(changes.get("name", self.name), changes.get("variables", self.vars),
                     changes.get("rows", self.rows), changes.get("objective", self.objective),
                     kernel=self.kernel, ledger=(*self.ledger, *edits))

    def renamed(self, name):
        return self._wrap(self._native.renamed(name), [*self.ledger, Edit("RenameModel", self.name, self.name, name)])

    def delete_rows(self, identifiers, *, reason=None):
        selected = {self._index(i, row=True) for i in _many(identifiers)}
        native = self._native.delete_rows(list(selected))
        edits = [Edit("DeleteRow", r.name, r, None, reason) for i, r in enumerate(self.rows) if i in selected]
        rows = tuple(r for i, r in enumerate(self.rows) if i not in selected)
        return self._wrap(native, (*self.ledger, *edits), rows=rows)

    def add_rows(self, rows, *, reason=None):
        rows = tuple(_row(r) for r in rows)
        native = self._native.add_rows(rows)
        edits = [Edit("AddRow", r.name, None, r, reason) for r in rows]
        return self._wrap(native, (*self.ledger, *edits), rows=(*self.rows, *rows))

    def add_row(self, name, expr, *, lower=None, upper=None, equal=None, reason=None):
        if equal is not None:
            if lower is not None or upper is not None:
                raise ValueError("Specify equal or lower/upper")
            lower = upper = equal
        return self.add_rows([Row(name, as_expr(expr), lower, upper)], reason=reason)

    def replace_row(self, identifier, *, expr=None, lower=..., upper=..., reason=None):
        index = self._index(identifier, row=True)
        before = self.rows[index]
        after = Row(before.name, before.expr if expr is None else expr,
                    before.lower if lower is ... else lower, before.upper if upper is ... else upper)
        native = self._native.replace_row(identifier, after)
        rows = list(self.rows)
        rows[index] = after
        return self._wrap(native, (*self.ledger, Edit("ReplaceRow", before.name, before, after, reason)), rows=tuple(rows))

    def add_variable(self, name, *, integer=False, lower=0, upper=None, reason=None):
        variable = Variable(name, integer, lower, upper)
        native = self._native.add_variable(variable)
        return self._wrap(native, (*self.ledger, Edit("AddVariable", name, None, variable, reason)),
                          variables=(*self.vars, variable))

    def with_objective(self, expr, *, reason=None):
        expr = as_expr(expr)
        native = self._native.with_objective(expr)
        return self._wrap(native, (*self.ledger, Edit("SetObjective", self.name, self.objective, expr, reason)), objective=expr)

    def with_bounds(self, identifier, *, lower=..., upper=..., reason=None):
        index = self._index(identifier)
        before = self.vars[index]
        after = replace(before, lower=before.lower if lower is ... else lower,
                        upper=before.upper if upper is ... else upper)
        native = self._native
        if lower is not ...:
            native = native.with_bound(index, "lower", lower)
        if upper is not ...:
            native = native.with_bound(index, "upper", upper)
        variables = list(self.vars)
        variables[index] = after
        return self._wrap(native, (*self.ledger, Edit("SetBounds", before.name, before, after, reason)), variables=tuple(variables))

    def with_integrality(self, identifiers, integer, *, reason=None):
        if not isinstance(integer, bool):
            raise TypeError("integer must be a boolean")
        indices = {self._index(i) for i in _many(identifiers)}
        native = self._native.with_integrality(sorted(indices), integer)
        variables = list(self.vars)
        edits = []
        for index in sorted(indices):
            before = variables[index]
            after = replace(before, integer=integer)
            variables[index] = after
            edits.append(Edit("SetIntegrality", before.name, before, after, reason))
        return self._wrap(native, (*self.ledger, *edits), variables=tuple(variables))

    def substitute(self, replacements, *, remove=True, drop_rows=(), preserve_bounds=True, reason=None):
        replacements = {self._index(i): as_expr(e) for i, e in replacements.items()}
        dropped = {self._index(i, row=True) for i in _many(drop_rows)}
        removed = set(replacements) if remove else set()
        if any(i in removed for e in replacements.values() for i in e.terms):
            raise ValueError("An elimination map must only reference retained variables; resolve dependent substitutions explicitly")
        if any(i >= len(self.vars) for e in replacements.values() for i in e.terms):
            raise ValueError("Substitution references a coordinate outside this model")
        keep = [i for i in range(len(self.vars)) if i not in removed]
        renumber = {old: Expr.var(new) for new, old in enumerate(keep)}
        mapping = {i: replacements[i].substitute(renumber) if i in replacements else renumber[i]
                   for i in range(len(self.vars))}
        rows = [replace(r, expr=r.expr.substitute(mapping)) for i, r in enumerate(self.rows) if i not in dropped]
        edits = [Edit("DeleteRow", r.name, r, None, reason) for i, r in enumerate(self.rows) if i in dropped]
        variables = [self.vars[i] for i in keep]
        names = {r.name for r in rows}
        for index in sorted(replacements):
            variable = self.vars[index]
            edits.append(Edit("EliminateVariable" if remove else "SubstituteVariable", variable.name,
                              variable, {"expression": replacements[index], "preserve_bounds": preserve_bounds}, reason))
            if remove and preserve_bounds and (variable.lower is not None or variable.upper is not None):
                base, suffix = f"__bound_{variable.name}"[:1000], 1
                name = base
                while name in names:
                    name = f"{base}_{suffix}"
                    suffix += 1
                row = Row(name, mapping[index], variable.lower, variable.upper)
                rows.append(row)
                names.add(name)
                edits.append(Edit("AddEliminatedBound", name, variable, row, reason))
        native = self._native.substitute(replacements, remove, list(dropped), preserve_bounds)
        return self._wrap(native, (*self.ledger, *edits), variables=tuple(variables),
                          objective=self.objective.substitute(mapping))

    def support(self, identifier, *, names=False):
        indices = tuple(self._native.support(identifier, names))
        return tuple(self.vars[i].name for i in indices) if names else indices

    def row_activity(self, identifier):
        lower, upper = self._native.row_activity(identifier)
        return (None if lower is None else rational(lower), None if upper is None else rational(upper))

    def is_binary(self, identifier):
        return self._native.is_binary(identifier)

    def column_incidence(self):
        return tuple(tuple((row, rational(value)) for row, value in column)
                     for column in self._native.column_incidence())

    def stats(self):
        return dict(self._native.stats())

    def coefficient_stats(self):
        def summarize(values):
            count = zeros = positive_count = negative_count = 0
            minimum = maximum = positive_min = positive_max = negative_min = negative_max = None
            magnitude_min = magnitude_max = None
            for value in values:
                count += 1
                minimum = value if minimum is None else min(minimum, value)
                maximum = value if maximum is None else max(maximum, value)
                if value > 0:
                    positive_count += 1
                    positive_min = value if positive_min is None else min(positive_min, value)
                    positive_max = value if positive_max is None else max(positive_max, value)
                elif value < 0:
                    negative_count += 1
                    negative_min = value if negative_min is None else min(negative_min, value)
                    negative_max = value if negative_max is None else max(negative_max, value)
                else:
                    zeros += 1
                if value:
                    magnitude = abs(value)
                    magnitude_min = magnitude if magnitude_min is None else min(magnitude_min, magnitude)
                    magnitude_max = magnitude if magnitude_max is None else max(magnitude_max, magnitude)
            def text(value):
                return None if value is None else str(value)
            return {"count": count, "zeros": zeros, "minimum": text(minimum), "maximum": text(maximum),
                    "positive": {"count": positive_count, "minimum": text(positive_min), "maximum": text(positive_max)},
                    "negative": {"count": negative_count, "minimum": text(negative_min), "maximum": text(negative_max)},
                    "magnitude_minimum_nonzero": text(magnitude_min), "magnitude_maximum": text(magnitude_max),
                    "magnitude_span": text(None if magnitude_min is None else magnitude_max / magnitude_min)}
        return {"objective": {"constant": str(self.objective.constant),
                              "coefficients": summarize(self.objective.terms.values())},
                "matrix": summarize(coefficient for row in self.rows for coefficient in row.expr.terms.values()),
                "row_constants": summarize(row.expr.constant for row in self.rows)}

    def check_point(self, values, *, integers=True):
        if isinstance(values, Mapping):
            values = [values[v.name] if v.name in values else values[i] for i, v in enumerate(self.vars)]
        if len(values) != len(self.vars):
            raise ValueError("A point must specify every coordinate")
        return self._native.check_point([rational(v) for v in values], integers)

    def diff(self, target):
        def named(expression, model):
            return {"constant": str(expression.constant), "terms": {model.vars[i].name: str(q) for i, q in expression.terms.items()}}
        edits = []
        for kind, before_items, after_items in (("Variable", self.vars, target.vars), ("Row", self.rows, target.rows)):
            before = {item.name: item.to_json() for item in before_items}
            after = {item.name: item.to_json() for item in after_items}
            if kind == "Row":
                for row in self.rows:
                    before[row.name]["expr"] = named(row.expr, self)
                for row in target.rows:
                    after[row.name]["expr"] = named(row.expr, target)
            for name in dict.fromkeys((*before, *after)):
                a, b = before.get(name), after.get(name)
                if a != b:
                    action = "Add" if a is None else "Delete" if b is None else "Change"
                    edits.append(Edit(action + kind, name, a, b))
        a, b = named(self.objective, self), named(target.objective, target)
        if a != b:
            edits.append(Edit("ChangeObjective", target.name, a, b))
        if self.name != target.name:
            edits.append(Edit("RenameModel", self.name, self.name, target.name))
        return EditLedger(edits)

    def same_formulation(self, other):
        return isinstance(other, Model) and self._native.same_formulation(other._native)

    def write_json(self, path):
        path = Path(path).resolve()
        path.write_text(json.dumps(self.to_json(), separators=(",", ":")) + "\n")
        return path

    def write_mcm(self, path):
        path = Path(path).resolve()
        path.write_bytes(self.to_mcm())
        return path

    def to_mcm(self):
        return bytes(self._native.to_mcm())

    def to_mps(self, *, rational_literals=False):
        if any(any(c.isspace() for c in item) or item.startswith("$") for item in [self.name, *(v.name for v in self.vars), *(r.name for r in self.rows)]):
            raise ValueError("MPS names must be whitespace-free and cannot start with '$'; use MCM for these names")
        def number(value):
            return str(value) if rational_literals else _decimal(value)
        occupied = set(self.row_index)
        objective_name = "__objective"
        while objective_name in occupied:
            objective_name += "_"
        lines = [f"NAME {self.name}", "ROWS", f" N {objective_name}"]
        rhs, ranges = [], []
        for row in self.rows:
            lo = None if row.lower is None else row.lower - row.expr.constant
            hi = None if row.upper is None else row.upper - row.expr.constant
            if lo is None and hi is None:
                raise ValueError(f"Unbounded row {row.name!r} has no MPS constraint-row encoding; use MCM")
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f"Contradictory row {row.name!r} has no range encoding; use MCM")
            if lo == hi:
                sense, bound = "E", lo
            elif hi is not None:
                sense, bound = "L", hi
                if lo is not None:
                    ranges.append(f" rng {row.name} {number(hi - lo)}")
            else:
                sense, bound = "G", lo
            lines.append(f" {sense} {row.name}")
            rhs.append(f" rhs {row.name} {number(bound)}")
        lines.append("COLUMNS")
        columns = self.column_incidence()
        in_integer, marker = False, 0
        for index, variable in enumerate(self.vars):
            if variable.integer != in_integer:
                lines.append(f" M{marker} 'MARKER' '{'INTORG' if variable.integer else 'INTEND'}'")
                marker += 1
                in_integer = variable.integer
            lines.append(f" {variable.name} {objective_name} {number(self.objective.coefficient(index))}")
            for row_index, coefficient in columns[index]:
                lines.append(f" {variable.name} {self.rows[row_index].name} {number(coefficient)}")
        if in_integer:
            lines.append(f" M{marker} 'MARKER' 'INTEND'")
        lines.append("RHS")
        lines.append(f" rhs {objective_name} {number(-self.objective.constant)}")
        lines.extend(rhs)
        if ranges:
            lines.append("RANGES")
            lines.extend(ranges)
        lines.append("BOUNDS")
        for variable in self.vars:
            lo, hi = variable.lower, variable.upper
            if lo is None and hi is None:
                lines.append(f" FR bnd {variable.name}")
            elif lo == hi:
                lines.append(f" FX bnd {variable.name} {number(lo)}")
            else:
                lines.append(f" MI bnd {variable.name}" if lo is None else f" LO bnd {variable.name} {number(lo)}")
                if hi is not None:
                    lines.append(f" UP bnd {variable.name} {number(hi)}")
        lines.append("ENDATA")
        return "\n".join(lines) + "\n"

    def write_mps(self, path, *, rational_literals=False):
        path = Path(path).resolve()
        path.write_text(self.to_mps(rational_literals=rational_literals))
        return path

    def standard_mps_adapter(self, *, objective_auxiliary=True, objective_name="__mps_objective"):
        from .mps_adapter import StandardMPSAdapter
        return StandardMPSAdapter(self, objective_auxiliary=objective_auxiliary,
                                  objective_name=objective_name)


def _many(values):
    return (values,) if isinstance(values, (str, int, Variable, Row)) else values


def _decimal(value):
    value = rational(value)
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError(f"{value} has no finite exact decimal; use MCM or rational_literals=True")
    places = max(twos, fives)
    scaled = abs(value.numerator) * 2**(places - twos) * 5**(places - fives)
    digits = str(scaled).rjust(places + 1, "0")
    text = digits if not places else (digits[:-places] + "." + digits[-places:]).rstrip("0").rstrip(".")
    return ("-" if value < 0 else "") + text
