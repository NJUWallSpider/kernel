"""Exact model readback, explicit edits, and sparse model queries.

This module is an untrusted authoring helper. Its MCM outputs are decoded and
validated by the kernel at verification time. An edit ledger describes edits;
it never serves as evidence that those edits preserve a feasible set.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
import json
from pathlib import Path
import struct
import tempfile
from types import MappingProxyType

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


class Model:
    """An ordered, exact model with immutable variables, rows, and expressions.

    All editing methods return a new model. ``target = source.delete_rows([...])``
    retains the source and records the deletion in ``target.ledger``. Models always
    minimize their objective, matching the canonical kernel representation.
    """
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
        self.name = _name(name)
        self.vars = tuple(v if isinstance(v, Variable) else Variable(**v) for v in variables)
        self.variables = self.vars
        self.rows = tuple(r if isinstance(r, Row) else Row(**{**r, "expr": Expr.from_json(r["expr"]) if isinstance(r["expr"], Mapping) else r["expr"]}) for r in rows)
        self.objective = Expr.from_json(objective) if isinstance(objective, Mapping) else as_expr(objective)
        self.kernel = kernel
        self.path = None if path is None else Path(path).resolve()
        self.ledger = EditLedger(ledger)
        self.var_index = MappingProxyType({v.name: i for i, v in enumerate(self.vars)})
        self.row_index = MappingProxyType({r.name: i for i, r in enumerate(self.rows)})
        if len(self.var_index) != len(self.vars) or len(self.row_index) != len(self.rows):
            raise ValueError("Variable names and row names must each be unique")
        if len(self.vars) > 2_000_000 or len(self.rows) > 2_000_000:
            raise ValueError("Model exceeds the kernel's dimension limit")
        expressions = [self.objective, *(r.expr for r in self.rows)]
        if sum(len(e.terms) for e in expressions) > 20_000_000:
            raise ValueError("Model exceeds the kernel's term limit")
        if any(i >= len(self.vars) for e in expressions for i in e.terms):
            raise ValueError("Expression references a coordinate outside this model")
        self._temporary = None

    def close(self):
        """Release a temporary canonical input after it is no longer needed."""
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
        """Use the kernel's own MPS/LP reader and MCM export; never reparse MPS."""
        from .backend import Kernel
        kernel, path = kernel or Kernel(), Path(path).resolve()
        if path.suffix.lower() == ".json":
            return cls.from_json(json.loads(path.read_text()), kernel=kernel)
        temporary = tempfile.TemporaryDirectory(prefix="kernel-model-")
        directory = Path(temporary.name)
        try:
            canonical = path
            with path.open("rb") as input_file:
                magic = input_file.read(4)
            if magic != b"MCM\0":
                canonical = directory / "model.mcm"
                kernel.call("canonical", path, canonical)
            exported = directory / "model.json"
            kernel.call("export-model", canonical, exported)
            result = cls.from_json(json.loads(exported.read_text()), kernel=kernel)
            result.path = canonical
            result._temporary = temporary
            return result
        except BaseException:
            temporary.cleanup()
            raise

    def to_json(self):
        return {"name": self.name, "variables": [v.to_json() for v in self.vars],
                "rows": [r.to_json() for r in self.rows], "objective": self.objective.to_json()}

    def _index(self, identifier, *, row=False):
        table, length = (self.row_index, len(self.rows)) if row else (self.var_index, len(self.vars))
        if isinstance(identifier, Expr):
            if row or identifier.constant or len(identifier.terms) != 1 or next(iter(identifier.terms.values())) != 1:
                raise ValueError("A variable reference expression must be exactly one unit coordinate")
            identifier = next(iter(identifier.terms))
        if isinstance(identifier, str):
            if identifier not in table:
                raise KeyError(f"Unknown {'row' if row else 'variable'} {identifier!r}")
            return table[identifier]
        if isinstance(identifier, Variable):
            return self._index(identifier.name)
        if isinstance(identifier, Row):
            return self._index(identifier.name, row=True)
        index = coordinate(identifier)
        if index >= length:
            raise IndexError(f"{'Row' if row else 'Variable'} index {index} outside model")
        return index

    def var(self, identifier):
        return Expr.var(self._index(identifier))

    def row(self, identifier):
        return self.rows[self._index(identifier, row=True)]

    def ref(self, kind, identifier):
        if kind not in ("VarLower", "VarUpper", "VarInt", "RowLower", "RowUpper", "RowEq"):
            raise ValueError(f"Unknown model fact {kind!r}")
        self.fact(kind, identifier)  # Refuse unbounded sides and absent integer facts.
        return {kind: self._index(identifier, row=kind.startswith("Row"))}

    def fact(self, kind, identifier):
        if kind.startswith("Var"):
            index = self._index(identifier)
            variable, expression = self.vars[index], Expr.var(index)
            if kind == "VarInt":
                if not variable.integer:
                    raise ValueError(f"Variable {variable.name!r} has no integer declaration")
                return "Int", expression
            if kind == "VarLower" and variable.lower is not None:
                return "Le", variable.lower - expression
            if kind == "VarUpper" and variable.upper is not None:
                return "Le", expression - variable.upper
        elif kind.startswith("Row"):
            row = self.row(identifier)
            if kind == "RowEq" and row.equality:
                return "Eq", row.expr - row.lower
            if kind == "RowLower" and row.lower is not None:
                return "Le", row.lower - row.expr
            if kind == "RowUpper" and row.upper is not None:
                return "Le", row.expr - row.upper
        raise ValueError(f"Unavailable fact {kind}({identifier!r})")

    def _edited(self, edits=(), **changes):
        return Model(changes.get("name", self.name), changes.get("variables", self.vars),
                     changes.get("rows", self.rows), changes.get("objective", self.objective),
                     kernel=self.kernel, ledger=(*self.ledger, *edits))

    def renamed(self, name):
        return self._edited([Edit("RenameModel", self.name, self.name, name)], name=name)

    def delete_rows(self, identifiers, *, reason=None):
        selected = {self._index(i, row=True) for i in _many(identifiers)}
        edits = [Edit("DeleteRow", r.name, r, None, reason) for i, r in enumerate(self.rows) if i in selected]
        return self._edited(edits, rows=[r for i, r in enumerate(self.rows) if i not in selected])

    def add_rows(self, rows, *, reason=None):
        rows = tuple(rows)
        rows = tuple(r if isinstance(r, Row) else Row(**{**r, "expr": Expr.from_json(r["expr"]) if isinstance(r["expr"], Mapping) else r["expr"]}) for r in rows)
        return self._edited([Edit("AddRow", r.name, None, r, reason) for r in rows], rows=(*self.rows, *rows))

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
        rows = list(self.rows)
        rows[index] = after
        return self._edited([Edit("ReplaceRow", before.name, before, after, reason)], rows=rows)

    def add_variable(self, name, *, integer=False, lower=0, upper=None, reason=None):
        variable = Variable(name, integer, lower, upper)
        return self._edited([Edit("AddVariable", name, None, variable, reason)], variables=(*self.vars, variable))

    def with_objective(self, expr, *, reason=None):
        expr = as_expr(expr)
        return self._edited([Edit("SetObjective", self.name, self.objective, expr, reason)], objective=expr)

    def with_bounds(self, identifier, *, lower=..., upper=..., reason=None):
        index = self._index(identifier)
        before = self.vars[index]
        after = replace(before, lower=before.lower if lower is ... else lower,
                        upper=before.upper if upper is ... else upper)
        variables = list(self.vars)
        variables[index] = after
        return self._edited([Edit("SetBounds", before.name, before, after, reason)], variables=variables)

    def with_integrality(self, identifiers, integer, *, reason=None):
        if not isinstance(integer, bool):
            raise TypeError("integer must be a boolean")
        indices = {self._index(i) for i in _many(identifiers)}
        variables = list(self.vars)
        edits = []
        for index in sorted(indices):
            before = variables[index]
            after = replace(before, integer=integer)
            variables[index] = after
            edits.append(Edit("SetIntegrality", before.name, before, after, reason))
        return self._edited(edits, variables=variables)

    def substitute(self, replacements, *, remove=True, drop_rows=(), preserve_bounds=True, reason=None):
        """Apply caller-provided simultaneous affine substitutions, optionally eliminate.

        Replacement expressions use this model's coordinates and must only refer
        to retained coordinates when ``remove=True``. Bounds on eliminated
        variables become explicit rows by default. Their integrality is recorded
        as a deletion: the caller's proof must justify the affine recovery.
        """
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
        return self._edited(edits, variables=[self.vars[i] for i in keep], rows=rows,
                            objective=self.objective.substitute(mapping))

    def support(self, identifier, *, names=False):
        indices = tuple(self.row(identifier).expr.terms)
        return tuple(self.vars[i].name for i in indices) if names else indices

    def row_activity(self, identifier):
        """Exact box lower/upper activity; None denotes an unbounded side."""
        row = self.row(identifier)
        lower = upper = row.expr.constant
        for i, coefficient in row.expr.terms.items():
            variable = self.vars[i]
            lo, hi = (variable.lower, variable.upper) if coefficient > 0 else (variable.upper, variable.lower)
            lower = None if lower is None or lo is None else lower + coefficient * lo
            upper = None if upper is None or hi is None else upper + coefficient * hi
        return lower, upper

    def is_binary(self, identifier):
        v = self.vars[self._index(identifier)]
        return v.integer and v.lower is not None and v.upper is not None and v.lower >= 0 and v.upper <= 1

    def column_incidence(self):
        columns = [[] for _ in self.vars]
        for ri, row in enumerate(self.rows):
            for vi, coefficient in row.expr.terms.items():
                columns[vi].append((ri, coefficient))
        return tuple(tuple(column) for column in columns)

    def stats(self):
        return {"variables": len(self.vars), "rows": len(self.rows),
                "integers": sum(v.integer for v in self.vars),
                "nonzeros": sum(len(r.expr.terms) for r in self.rows),
                "objective_nonzeros": len(self.objective.terms),
                "equalities": sum(r.equality for r in self.rows),
                "ranged_rows": sum(r.lower is not None and r.upper is not None and not r.equality for r in self.rows)}

    def coefficient_stats(self):
        """Exact objective/matrix coefficient and row-constant ranges for inspection.

        Counts are integers; rational values are canonical strings or None for
        an empty category. Magnitude span is max(abs(nonzero))/min(abs(nonzero)).
        The result describes the current representation, without solver advice
        or normalization that changes the caller's formulation.
        """
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
        """Return exact feasibility violations for a supplied point, without a solver."""
        if isinstance(values, Mapping):
            values = [values[v.name] if v.name in values else values[i] for i, v in enumerate(self.vars)]
        if len(values) != len(self.vars):
            raise ValueError("A point must specify every coordinate")
        values = [rational(v) for v in values]
        violations = []
        for index, (variable, value) in enumerate(zip(self.vars, values)):
            for kind, bound, fails in (("VarLower", variable.lower, lambda b: value < b),
                                       ("VarUpper", variable.upper, lambda b: value > b)):
                if bound is not None and fails(bound):
                    violations.append({"kind": kind, "index": index, "name": variable.name, "value": str(value), "bound": str(bound)})
            if integers and variable.integer and value.denominator != 1:
                violations.append({"kind": "VarInt", "index": index, "name": variable.name, "value": str(value)})
        for index, row in enumerate(self.rows):
            value = row.expr.evaluate(values)
            for kind, bound, fails in (("RowLower", row.lower, lambda b: value < b),
                                       ("RowUpper", row.upper, lambda b: value > b)):
                if bound is not None and fails(bound):
                    violations.append({"kind": kind, "index": index, "name": row.name, "value": str(value), "bound": str(bound)})
        return violations

    def diff(self, target):
        """Compare all semantic fields by names, independent of coordinate renumbering."""
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
        """Compare the complete exact named formulation, allowing MPS normalization.

        Variable/row order and the model NAME are immaterial. Variable and row
        names, domains, objective, and every named coefficient must agree.
        Row constants are folded into finite bounds exactly, as MPS export does.
        This is a representation comparison, not an equivalence proof or a
        tolerance-based numerical comparison.
        """
        if not isinstance(other, Model):
            return False
        if {v.name: v for v in self.vars} != {v.name: v for v in other.vars}:
            return False
        if set(self.row_index) != set(other.row_index):
            return False
        def terms(expression, model):
            return {model.vars[i].name: coefficient for i, coefficient in expression.terms.items()}
        if self.objective.constant != other.objective.constant or terms(self.objective, self) != terms(other.objective, other):
            return False
        for row in self.rows:
            target = other.row(row.name)
            if terms(row.expr, self) != terms(target.expr, other):
                return False
            for side in ("lower", "upper"):
                a, b = getattr(row, side), getattr(target, side)
                a = None if a is None else a - row.expr.constant
                b = None if b is None else b - target.expr.constant
                if a != b:
                    return False
        return True

    def write_json(self, path):
        path = Path(path).resolve()
        path.write_text(json.dumps(self.to_json(), separators=(",", ":")) + "\n")
        return path

    def write_mcm(self, path):
        """Write exact MCM v1 directly. No decimal rounding or RPA intermediary."""
        path = Path(path).resolve()
        path.write_bytes(self.to_mcm())
        return path

    def to_mcm(self):
        def array(items):
            return struct.pack("<I", len(items)) + b"".join(items)
        def name(value):
            raw = value.encode("ascii")
            return struct.pack("<I", len(raw)) + raw
        def scalar(value):
            value = rational(value)
            n, d = abs(value.numerator), value.denominator
            n = n.to_bytes((n.bit_length() + 7) // 8, "little")
            d = d.to_bytes((d.bit_length() + 7) // 8, "little")
            return struct.pack("<BBHII", int(value < 0), 0, 0, len(n), len(d)) + n + d
        def optional(value):
            return b"\0" if value is None else b"\1" + scalar(value)
        def expression(value):
            return scalar(value.constant) + array([struct.pack("<I", i) + scalar(q) for i, q in value.terms.items()])
        variables = [name(v.name) + struct.pack("<BBH", v.integer, 0, 0) + optional(v.lower) + optional(v.upper) for v in self.vars]
        rows = [name(r.name) + expression(r.expr) + optional(r.lower) + optional(r.upper) for r in self.rows]
        payload = name(self.name) + array(variables) + array(rows) + expression(self.objective)
        return b"MCM\0" + struct.pack("<HHQ", 1, 0, len(payload) + 16) + payload

    def write_mps(self, path, *, rational_literals=False):
        """Write an exact free MPS. Nonterminating decimals require explicit opt-in.

        ``rational_literals=True`` emits fractions accepted by the kernel; some
        external MPS consumers require decimal literals. Row constants are folded
        into RHS bounds, preserving the model's mathematical meaning.
        """
        path = Path(path).resolve()
        path.write_text(self.to_mps(rational_literals=rational_literals))
        return path

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
