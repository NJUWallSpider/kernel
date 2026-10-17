"""Checked authoring helpers backed by the native compiler core."""
from __future__ import annotations

from collections import ChainMap
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from . import _native
from .expr import Expr, exact, _rational_text
from .model import Model, Row, Variable


def _key(kind, expression):
    return kind, expression


def wire(value):
    if isinstance(value, _native.Fact):
        return value.reference
    if isinstance(value, Expr):
        return value.to_json()
    if isinstance(value, Fraction):
        return _rational_text(value)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


class BuildError(ValueError):
    """A user proof is incomplete or disagrees with the supplied rule."""


Fact = _native.Fact


@dataclass(frozen=True)
class Contradiction:
    fact: Fact


def _raise(error):
    if isinstance(error, BuildError):
        raise error
    raise BuildError(str(error)) from None


def _mapping(input_model, output_model, mapping):
    if mapping is None or mapping == "identity":
        return [input_model.var(v.name) for v in output_model.vars]
    if isinstance(mapping, dict):
        expected = {v.name for v in output_model.vars}
        if set(mapping) != expected:
            raise BuildError(f"A map must cover every output coordinate: missing={sorted(expected-set(mapping))[:10]}, extra={sorted(set(mapping)-expected)[:10]}")
        return [Expr.coerce(mapping[v.name]) for v in output_model.vars]
    values = [Expr.coerce(v) for v in mapping]
    if len(values) != len(output_model.vars):
        raise BuildError("A map must cover every output coordinate")
    return values


def _wrap_model(native, source):
    return Model._from_native(native, kernel=source.kernel, path=source.path)


class Builder:
    """One proof scope. Child facts cannot escape except through Cases conclusions."""

    def __init__(self, model, *, parent=None, assumptions=(), counter=None):
        if parent is not None:
            raise BuildError("Child and branch builders are created by their parent scope")
        self._native = _native.Builder(model._native)
        self._children = None
        self._indexed = False
        self._facts = ChainMap({})
        self._base = {}
        self._assigned = {}
        self._completion = None
        self._fact_cache = {}
        self._layout_handles = {}

    @classmethod
    def _from_native(cls, native):
        obj = object.__new__(cls)
        obj._native = native
        obj._model_cache = None
        obj._children = None
        obj._indexed = False
        obj._facts = ChainMap({})
        obj._base = {}
        obj._assigned = {}
        obj._completion = None
        obj._fact_cache = {}
        obj._layout_handles = {}
        return obj

    @property
    def model(self):
        cached = getattr(self, "_model_cache", None)
        if cached is None:
            cached = (_wrap_model(self._native.model, self.model_source)
                      if hasattr(self, "model_source") else Model._from_native(self._native.model))
            self._model_cache = cached
        return cached

    @property
    def _native_model(self):
        return self._native.model

    @property
    def parent(self):
        value = self._native.parent
        return None if value is None else Builder._from_native(value)

    @property
    def assumptions(self):
        return tuple(self._native.assumptions)

    @property
    def steps(self):
        return self._native.steps

    @property
    def end(self):
        return self._native.end

    @property
    def layout(self):
        return self._native.layout

    @layout.setter
    def layout(self, value):
        # Native owns the layout; this setter exists only for old metadata users.
        pass

    @property
    def generated_variables(self):
        return tuple(self._native.generated_variables)

    @property
    def generated_rows(self):
        return tuple(self._native.generated_rows)

    def _visible(self, fact):
        if not isinstance(fact, Fact):
            raise BuildError("Expected a Fact handle returned by this builder")
        if fact.reference == "Exact":
            raise BuildError("Exact is a terminal witness and cannot be a rule premise")
        try:
            self._native.visible_fact(fact)
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None
        return fact

    def _expression(self, expression):
        expression = Expr.coerce(expression)
        if any(i >= len(self.model.vars) for i in expression.terms):
            raise BuildError("Expression coordinate is outside this scope")
        return expression

    def _cache(self, fact):
        return self._fact_cache.setdefault(fact.id, fact)

    def ref(self, kind, site):
        parent = self.__dict__.get("_parent_wrapper")
        if parent is not None and self._native.same_model(parent._native):
            return parent._ref_cached(kind, site)
        try:
            fact = self._native.ref_(kind, site)
        except ValueError as error:
            if kind.startswith("Var") and "outside model" in str(error):
                raise IndexError(str(error)) from None
            _raise(error)
        except TypeError as error:
            _raise(error)
        self._indexed = True
        return self._cache(fact)

    def _ref_cached(self, kind, site):
        fact = self._native.ref_(kind, site)
        return self._cache(fact)

    def lower(self, variable):
        return self.ref("VarLower", variable)

    def upper(self, variable):
        return self.ref("VarUpper", variable)

    def integer(self, variable):
        return self.ref("VarInt", variable)

    def row(self, row, side=None):
        try:
            return self._cache(self._native.row(row, side))
        except (ValueError, TypeError) as error:
            _raise(error)

    def lin(self, kind, terms=(), *, constant=0, expect=None):
        try:
            fact = self._native.lin(kind, list(terms), constant, expect)
        except (ValueError, TypeError) as error:
            _raise(error)
        if isinstance(fact.reference, dict) and "Local" in fact.reference:
            self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def eq(self, terms=(), **kwargs):
        return self.lin("Eq", terms, **kwargs)

    def le(self, terms=(), **kwargs):
        return self.lin("Le", terms, **kwargs)

    def int(self, terms=(), **kwargs):
        return self.lin("Int", terms, **kwargs)

    def combine_rows(self, kind, coefficients, *, constant=0, expect=None):
        pairs = coefficients.items() if hasattr(coefficients, "items") else coefficients
        terms = []
        for row, coefficient in pairs:
            if isinstance(row, tuple):
                row, side = row
            else:
                side = None
            terms.append((self.row(row, side=side), coefficient))
        return self.lin(kind, terms, constant=constant, expect=expect)

    def box_le(self, expression):
        try:
            fact = self._native.box_le(expression)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def subset_bounds(self, fact, subsets):
        from ._subsets import subset_bounds
        return subset_bounds(self, fact, subsets)

    def eq_on_fixed(self, expression, fixes=None):
        try:
            fact = self._native.eq_on_fixed(expression, fixes or {})
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def zero_sum(self, fact, *, zeros=None, scale=1, coordinates=None):
        zeros = {} if zeros is None else zeros
        needed = set(fact.expression.terms)
        for index in list(needed):
            if 0 <= index < len(self.model.vars):
                needed.add(self.model.vars[index].name)
        selected_zeros = {}
        missing = object()
        for key in needed:
            value = zeros.get(key, missing)
            if value is not missing:
                index = key if isinstance(key, int) and not isinstance(key, bool) else self.model._index(key)
                selected_zeros[index] = value
        coordinates = None if coordinates is None else [self.model._index(item) for item in coordinates]
        try:
            result = self._native.zero_sum(fact, selected_zeros, scale, coordinates)
        except (ValueError, TypeError) as error:
            _raise(error)
        for item in result.values():
            self._facts.maps[0][item.reference["Local"]] = item
        return result

    def round(self, le, integer):
        try:
            fact = self._native.round(le, integer)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def parity_fix(self, variable, equality):
        try:
            fact = self._native.parity_fix(variable, equality)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def eqpair(self, positive, negative):
        try:
            fact = self._native.eqpair(positive, negative)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def _definitions(self, definitions):
        return list(definitions.items())

    def rewrite(self, fact, definitions, *, expect=None):
        try:
            result = self._native.rewrite(fact, self._definitions(definitions), expect)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][result.reference["Local"]] = result
        return result

    def rewrite_many(self, facts, definitions):
        try:
            result = self._native.rewrite_many(list(facts), self._definitions(definitions))
        except (ValueError, TypeError) as error:
            _raise(error)
        for fact in result:
            self._facts.maps[0][fact.reference["Local"]] = fact
        return result

    def derive_substitution(self, goal, definitions, residual, *, kind=None):
        try:
            result = self._native.derive_substitution(goal, self._definitions(definitions), residual, kind)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][result.reference["Local"]] = result
        return result

    def derive_substitution_many(self, items, definitions, *, kind=None):
        try:
            result = self._native.derive_substitution_many(list(items), self._definitions(definitions), kind)
        except (ValueError, TypeError) as error:
            _raise(error)
        for fact in result:
            self._facts.maps[0][fact.reference["Local"]] = fact
        return result

    def substitution(self, definitions, *, goals=()):
        try:
            result = self._native.substitution(self._definitions(definitions), list(goals))
        except (ValueError, TypeError) as error:
            _raise(error)
        for fact in result:
            self._facts.maps[0][fact.reference["Local"]] = fact
        return result

    def drop(self, *facts):
        try:
            self._native.drop(list(facts))
        except (ValueError, TypeError) as error:
            _raise(error)
        for fact in facts:
            ident = fact.reference.get("Local") if isinstance(fact.reference, dict) else None
            if ident is not None:
                self._facts.maps[0].pop(ident, None)

    def absurd(self, fact):
        try:
            value = self._native.absurd(fact)
        except (ValueError, TypeError) as error:
            _raise(error)
        return value if isinstance(value, Contradiction) else Contradiction(value.fact)

    def _branch(self, expression):
        try:
            child, assumption = self._native.branch(expression)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._indexed = True
        wrapped = Builder._from_native(child)
        wrapped._parent_wrapper = self
        wrapped._fact_cache = self._fact_cache
        wrapped._layout_handles = self._layout_handles
        wrapped._fact_cache[assumption.id] = assumption
        return wrapped, assumption

    def _split(self, expression, integer):
        if integer is False:
            integer = None
        if integer is True:
            expression = self._expression(expression)
            if expression.constant == 0 and len(expression.terms) == 1 and next(iter(expression.terms.values())) == 1:
                integer = self.integer(next(iter(expression.terms)))
            else:
                raise BuildError("Supply an explicit INT fact for a non-variable integer split")
        try:
            expression, fact = self._native.split_options(expression, integer)
        except (ValueError, TypeError) as error:
            _raise(error)
        return Expr.coerce(expression), fact

    def cases(self, expression, *, kind, expect, left, right, integer=True):
        expression, integer = self._split(expression, integer)
        try:
            fact = self._native.cases(expression, kind, expect, left, right, integer)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def binary_value(self, variable, value, assumption):
        if value == 0:
            return self.eqpair(assumption, self.lower(variable))
        if value == 1:
            return self.eqpair(self.upper(variable), assumption)
        raise BuildError("binary_value supports 0 or 1")

    def binary_cases(self, variables, *, kind, expect, prove, integers=None):
        if kind not in ("Le", "Eq", "Int"):
            raise BuildError(f"Unknown fact kind {kind}")
        expect = self._expression(expect)
        if not callable(prove):
            raise BuildError("binary_cases needs a caller-provided leaf proof callback")
        indices = tuple(self.model._index(variable) for variable in variables)
        if len(set(indices)) != len(indices):
            raise BuildError("binary_cases coordinates must be distinct")
        if integers is not None and not hasattr(integers, "items"):
            raise BuildError("binary_cases integers must be a coordinate-to-INT-fact mapping")
        supplied = {}
        for variable, fact in (integers or {}).items():
            index = self.model._index(variable)
            if index in supplied or index not in indices:
                raise BuildError("Integer witnesses must uniquely name selected binary_cases coordinates")
            if not self._native.owns(fact):
                raise BuildError("Integer witnesses must belong to this proof scope")
            self._visible(fact)
            if fact.kind != "Int" or fact.expression != self.model.var(index):
                raise BuildError("binary_cases needs INT of each exact selected coordinate")
            supplied[index] = fact
        witnesses = []
        for index in indices:
            variable = self.model.vars[index]
            if variable.lower is None or variable.upper is None or not 0 <= variable.lower <= variable.upper <= 1:
                raise BuildError("binary_cases needs declared bounds within [0,1]")
            if index not in supplied and not variable.integer:
                raise BuildError("binary_cases needs an explicit INT witness for a coordinate without active declared integrality")
            witnesses.append(supplied[index] if index in supplied else self.integer(index))

        def visit(scope, position, fixes):
            if position == len(indices):
                conclusion = prove(scope, dict(fixes))
                if hasattr(conclusion, "fact") and not isinstance(conclusion, Fact):
                    scope.absurd(conclusion.fact)
                else:
                    if conclusion.expression != expect or (conclusion.kind != kind and conclusion.kind != "Eq"):
                        raise BuildError("Binary case leaf must prove the common requested expression or a contradiction")
                return conclusion
            index = indices[position]
            variable = scope.model.vars[index]
            if not isinstance(variable, Variable):
                variable = Variable(*variable)
            expression = Expr.var(index)
            def left(child, assumption):
                lower = child.lower(index)
                if variable.lower:
                    lower = child.le([(lower, 1)], constant=-variable.lower, expect=-expression)
                fixing = child.eqpair(assumption, lower)
                return visit(child, position + 1, {**fixes, variable.name: fixing})
            def right(child, assumption):
                upper = child.upper(index)
                if variable.upper != 1:
                    upper = child.le([(upper, 1)], constant=variable.upper - 1, expect=expression - 1)
                fixing = child.eqpair(upper, assumption)
                return visit(child, position + 1, {**fixes, variable.name: fixing})
            return scope.cases(expression, kind=kind, expect=expect, integer=witnesses[position],
                               left=left, right=right)
        return visit(self, 0, {})

    def split(self, expression, *, left, right, integer=True):
        expression, integer = self._split(expression, integer)
        try:
            children = self._native.split(expression, left, right, integer)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._children = [Builder._from_native(child) for child in children]
        for child in self._children:
            child._fact_cache = self._fact_cache
        self._completion = None
        return self._children

    def close_absurd(self, fact):
        try:
            self._native.close_absurd(fact)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._completion = None

    def batch(self, instances, template):
        return [template(self, instance) for instance in instances]

    def plotkin(self, *, bits, distance, variables, cliques):
        try:
            fact = self._native.plotkin(bits, distance, list(variables), list(cliques))
        except (ValueError, TypeError) as error:
            _raise(error)
        self._facts.maps[0][fact.reference["Local"]] = fact
        return self._cache(fact)

    def find(self, kind, expression):
        expression = self._expression(expression)
        try:
            value = self._native.find(kind, expression)
        except (ValueError, TypeError) as error:
            _raise(error)
        self._indexed = True
        return self._cache(value) if isinstance(value, Fact) else value

    def _generated_instance(self, kind, index):
        if self._native.layout_kind != kind or not isinstance(self.layout, list):
            raise BuildError(f"This scope has no {kind} layout; use the scope returned by its constructive lift")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.layout):
            raise BuildError(f"{kind} instance index {index!r} is outside the generated layout")
        return self.layout[index]

    def interval(self, index):
        entry = self._generated_instance("Interval", index)
        key = ("Interval", index)
        if key in self._layout_handles:
            return self._layout_handles[key]
        value = SimpleNamespace(
            variable=self.model.var(entry["variable"]),
            lower_rows=tuple(self.ref("RowLower", i) for i in entry["lower_rows"]),
            upper_rows=tuple(self.ref("RowUpper", i) for i in entry["upper_rows"]))
        self._layout_handles[key] = value
        return value

    def menu(self, index):
        entry = self._generated_instance("Menu", index)
        key = ("Menu", index)
        if key in self._layout_handles:
            return self._layout_handles[key]
        value = SimpleNamespace(
            options=tuple(self.model.var(i) for i in entry["options"]),
            sum=self.ref("RowEq", entry["sum_row"]),
            moment=self.ref("RowEq", entry["moment_row"]))
        self._layout_handles[key] = value
        return value

    def signed_decomposition(self, index):
        entry = self._generated_instance("Signed", index)
        key = ("Signed", index)
        if key in self._layout_handles:
            return self._layout_handles[key]
        value = SimpleNamespace(
            positive=self.model.var(entry["positive"]), negative=self.model.var(entry["negative"]),
            positive_activation=self.model.var(entry["positive_activation"]),
            negative_activation=self.model.var(entry["negative_activation"]),
            flow=self.ref("RowEq", entry["flow_row"]),
            activation=self.ref("RowEq", entry["activation_row"]),
            positive_capacity=self.ref("RowUpper", entry["positive_capacity_row"]),
            negative_capacity=self.ref("RowUpper", entry["negative_capacity_row"]))
        self._layout_handles[key] = value
        return value

    def flow_group(self, index):
        entry = self._generated_instance("Flow", index)
        key = ("Flow", index)
        if key in self._layout_handles:
            return self._layout_handles[key]
        commodities = tuple(SimpleNamespace(
            sink=item["sink"], demand=exact(item["demand"]),
            flows=tuple(self.model.var(i) for i in item["flows"]),
            balances=tuple(self.ref("RowEq", i) for i in item["balance_rows"]))
            for item in entry["commodities"])
        value = SimpleNamespace(source=entry["source"], commodities=commodities,
                                recovery=tuple(self.ref("RowEq", i) for i in entry["recovery_rows"]))
        self._layout_handles[key] = value
        return value

    def commodity(self, group, index):
        commodities = self.flow_group(group).commodities
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(commodities):
            raise BuildError(f"Flow commodity index {index!r} is outside group {group}")
        return commodities[index]

    def subflow_group(self, index):
        entry = self._generated_instance("Subflow", index)
        key = ("Subflow", index)
        if key in self._layout_handles:
            return self._layout_handles[key]
        value = SimpleNamespace(
            source=entry["source"], flows=tuple(self.model.var(i) for i in entry["flows"]),
            balances=tuple(self.ref("RowEq", i) for i in entry["balance_rows"]),
            remainder_nonnegative=tuple(self.ref("RowUpper", i) for i in entry["remainder_nonnegative_rows"]))
        self._layout_handles[key] = value
        return value

    def lift(self, kind, witness):
        tags = {"interval": ("Interval", "intervals"), "menu": ("Menu", "menus"),
                "signed": ("Signed", "decompositions"), "flow": ("Flow", "witness"),
                "subflow": ("Subflow", "witness")}
        spec_tag, end_field = tags[kind.lower()]
        handles = {}
        def collect(value):
            if isinstance(value, Fact):
                if value.reference == "Exact":
                    raise BuildError("Exact is not a valid lift premise")
                handles[json.dumps(value.reference, sort_keys=True)] = value
            elif isinstance(value, dict):
                for child in value.values():
                    collect(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    collect(child)
        collect(witness)
        lowered = wire(witness)
        if spec_tag == "Interval":
            for item, original in zip(lowered, witness):
                for field in ("lower", "upper"):
                    item[field] = [self._expression(e).to_json() for e in original[field]]
        elif spec_tag in ("Menu", "Signed"):
            for item, original in zip(lowered, witness):
                for field in (("activation", "index") if spec_tag == "Menu" else ("activation", "flow")):
                    item[field] = self._expression(original[field]).to_json()
                if spec_tag == "Signed":
                    item["capacity"] = str(exact(original["capacity"]))
        elif spec_tag in ("Flow", "Subflow"):
            for item, original in zip(lowered["groups"], witness["groups"]):
                item["flows"] = [self._expression(e).to_json() for e in original["flows"]]
                field = "commodities" if spec_tag == "Flow" else "demands"
                item[field] = [[i, str(exact(q))] for i, q in original[field]]
        try:
            prepared = _native.prepare_extension(self._native.model, {spec_tag: lowered})
            for premise in prepared["premises"]:
                fact = handles.get(json.dumps(premise["reference"], sort_keys=True))
                expression = premise["expression"] if isinstance(premise["expression"], Expr) else Expr.from_json(premise["expression"], intermediate=True)
                if premise["reference"] == "Exact" and self.find(premise["kind"], expression) == "Exact":
                    continue
                if fact is None or fact.expression != expression or (fact.kind != premise["kind"] and fact.kind != "Eq"):
                    raise BuildError(f"{kind} premise mismatch: {premise}")
            model = Model.from_json(prepared["model"], kernel=self.model.kernel)
            child = self._native.install_lift(model._native, {spec_tag: lowered}, json.dumps(prepared["layout"]))
        except BuildError:
            raise
        except (ValueError, TypeError) as error:
            _raise(error)
        wrapped = Builder._from_native(child)
        wrapped.model_source = model
        wrapped._fact_cache = self._fact_cache
        wrapped._children = []
        self._children = [wrapped]
        self._native_end_field = end_field
        self._completion = None
        return wrapped

    def intervals(self, intervals):
        return self.lift("interval", intervals)

    def menus(self, menus):
        return self.lift("menu", menus)

    def signed(self, decompositions):
        return self.lift("signed", decompositions)

    def flow(self, witness):
        return self.lift("flow", witness)

    def subflow(self, witness):
        return self.lift("subflow", witness)

    def to_json(self):
        try:
            return self._native.to_json()
        except (ValueError, TypeError) as error:
            _raise(error)

    to_certificate = to_json
