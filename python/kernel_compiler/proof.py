"""Checked authoring helpers for the frozen Kernel proof objects.

All arithmetic here is untrusted convenience. The Rust Kernel is the acceptance
authority. Helpers only elaborate caller-supplied derivations and trivial facts.
"""
from __future__ import annotations

from collections import ChainMap
from collections.abc import Mapping
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from heapq import heapify, heappop, heappush
from itertools import count
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from .expr import Expr, exact, _rational_text
from .model import Model


def _key(kind, expression):
    # Expr already caches its canonical sparse hash. Do not allocate another
    # term tuple for every obligation lookup in a large model.
    return kind, expression


def wire(value):
    """Lower Python objects directly to existing Certificate JSON data types."""
    if isinstance(value, Fact):
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


@dataclass(frozen=True)
class Fact:
    kind: str
    expression: Expr
    reference: object
    scope: object

    @property
    def expr(self):
        return self.expression


@dataclass(frozen=True)
class Contradiction:
    fact: Fact


class _PivotPlan:
    """One caller-selected, ordered list of equality pivots.

    Only nonzero pivots in the current residual are visited. A pivot introduced
    after its position has passed stays in the residual, exactly as in one
    sequential pass through the supplied definitions.
    """
    def __init__(self, builder, definitions):
        entries = []
        positions = {}
        for pivot, equality in definitions.items():
            pivot = builder.model._index(pivot)
            builder._visible(equality)
            if equality.kind != "Eq" or not equality.expression.terms.get(pivot):
                raise BuildError("Each rewrite definition must be an EQ with a nonzero selected pivot")
            positions.setdefault(pivot, []).append(len(entries))
            entries.append((pivot, equality, equality.expression.terms[pivot]))
        self.entries = tuple(entries)
        # Distinct keys may name the same coordinate (for example 'x' and 0).
        # rewrite historically visits both positions, so retain their order.
        self.positions = {pivot: tuple(order) for pivot, order in positions.items()}

    @staticmethod
    def _bounded(value):
        # Match Expr arithmetic's intermediate magnitude bound without making
        # an immutable sparse expression for every coefficient update.
        if abs(value.numerator).bit_length() > 65536 or value.denominator.bit_length() > 65536:
            raise ValueError("Rational exceeds the kernel's 65536-bit limit")
        return value

    def reduce(self, expression):
        constant, coefficients = expression.constant, dict(expression.terms)
        active = [position for index in coefficients for position in self.positions.get(index, ())]
        heapify(active)
        queued = set(active)
        cancellation = []
        while active:
            position = heappop(active)
            queued.remove(position)
            pivot, equality, divisor = self.entries[position]
            coefficient = coefficients.get(pivot, 0)
            if not coefficient:
                continue
            multiplier = exact(-coefficient / divisor)
            equation = equality.expression
            constant = self._bounded(constant + self._bounded(multiplier * equation.constant))
            for index, value in equation.terms.items():
                updated = self._bounded(coefficients.get(index, 0) + self._bounded(multiplier * value))
                if updated:
                    coefficients[index] = updated
                    order = self.positions.get(index, ())
                    for later in order[bisect_right(order, position):]:
                        if later not in queued:
                            heappush(active, later)
                            queued.add(later)
                else:
                    coefficients.pop(index, None)
            cancellation.append((equality, multiplier))
        return constant, coefficients, cancellation


class Builder:
    """One proof scope. Child facts cannot escape except through Cases conclusions."""
    def __init__(self, model, *, integers=True, parent=None, assumptions=(), counter=None):
        self.model = model
        self.integers = integers
        self.parent = parent
        self.assumptions = tuple(assumptions)
        self._counter = counter if counter is not None else count()
        self.steps = []
        self._facts = ChainMap({}, *parent._facts.maps) if parent else ChainMap({})
        self._lookup = ChainMap({}, *parent._lookup.maps) if parent else ChainMap({})
        self._base = {}
        self._dropped = set()
        self.end = None
        self._children = None
        self._revision = 0
        self.layout = parent.layout if parent is not None and model is parent.model else None
        self._layout_kind = parent._layout_kind if parent is not None and model is parent.model else None
        self._layout_handles = {}

    def _set_end(self, end, children=None):
        self.end, self._children = end, children
        if hasattr(self, "_completion"):
            del self._completion

    def _remember(self, fact):
        self._lookup.maps[0].setdefault(_key(fact.kind, fact.expression), []).append(fact)

    def _expression(self, expression):
        expression = Expr.coerce(expression)
        if any(i >= len(self.model.vars) for i in expression.terms):
            raise BuildError("Expression coordinate is outside this scope")
        return expression

    def _visible(self, fact):
        if not isinstance(fact, Fact):
            raise BuildError("Expected a Fact handle returned by this builder")
        scope = self
        while scope is not None:
            if isinstance(fact.reference, dict) and fact.reference.get("Local") in scope._dropped:
                raise BuildError("Local fact was dropped in this proof scope")
            if fact.scope is scope:
                break
            scope = scope.parent
        if scope is None:
            raise BuildError("Fact belongs to a sibling or unrelated proof scope")
        if isinstance(fact.reference, dict) and "Local" in fact.reference:
            ident = fact.reference["Local"]
            if self._facts.get(ident) is not fact or ident in self._dropped:
                raise BuildError(f"Local fact {ident} was dropped or is unavailable")
        if fact.reference == "Exact":
            raise BuildError("Exact is a terminal witness and cannot be a rule premise")
        return fact

    def _register(self, kind, expression, step):
        if kind not in ("Le", "Eq", "Int"):
            raise BuildError(f"Unknown fact kind {kind}")
        expression = self._expression(expression)
        ident = next(self._counter)
        step["id"] = ident
        tag = step.pop("_tag")
        self.steps.append({tag: step})
        self._revision += 1
        fact = Fact(kind, expression, {"Local": ident}, self)
        self._facts[ident] = fact
        self._remember(fact)
        return fact

    def ref(self, kind, site):
        """Model fact by original name or index (bounds and row sides are explicit)."""
        index = self.model._index(site, row=kind.startswith("Row"))
        if self.parent is not None and self.model is self.parent.model:
            return self.parent.ref(kind, index)
        key = kind, index
        if key not in self._base:
            if kind == "VarInt" and not self.integers:
                raise BuildError("VarInt is unavailable in a relaxed input domain")
            actual_kind, expression = self.model.fact(kind, index)
            self._base[key] = Fact(actual_kind, expression, {kind: index}, self)
        return self._base[key]

    def lower(self, variable):
        return self.ref("VarLower", variable)

    def upper(self, variable):
        return self.ref("VarUpper", variable)

    def integer(self, variable):
        return self.ref("VarInt", variable)

    def row(self, row, side=None):
        index = self.model.row_index[row] if isinstance(row, str) else row
        data = self.model.rows[index]
        if side is None:
            if data.lower is not None and data.lower == data.upper:
                side = "Eq"
            elif data.lower is not None and data.upper is not None:
                raise BuildError("A ranged row needs side='Lower' or side='Upper'")
            else:
                side = "Lower" if data.lower is not None else "Upper"
        return self.ref("Row" + side, index)

    def lin(self, kind, terms=(), *, constant=0, expect=None):
        """The caller supplies every premise and multiplier; no combination search."""
        if kind not in ("Le", "Eq", "Int"):
            raise BuildError(f"Unknown fact kind {kind}")
        constant = exact(constant)
        if ((kind == "Eq" and constant != 0) or (kind == "Le" and constant > 0)
                or (kind == "Int" and constant.denominator != 1)):
            raise BuildError(f"Invalid {kind} linear constant {constant}")
        result_constant = constant
        coefficients = {}
        emitted = []
        for fact, multiplier in terms:
            self._visible(fact)
            multiplier = exact(multiplier)
            allowed = fact.kind == "Eq" or (kind == "Le" and fact.kind == "Le" and multiplier >= 0) or (kind == "Int" and fact.kind == "Int" and multiplier.denominator == 1)
            if not allowed:
                raise BuildError(f"Invalid {kind} premise {fact.kind} with multiplier {multiplier}")
            result_constant += multiplier * fact.expression.constant
            for i, coefficient in fact.expression.terms.items():
                coefficients[i] = coefficients.get(i, 0) + multiplier * coefficient
            emitted.append([fact.reference, str(multiplier)])
        expression = Expr(result_constant, coefficients)
        if expect is not None and expression != Expr.coerce(expect):
            raise BuildError(f"Linear residual mismatch: got {expression}, expected {expect}")
        return self._register(kind, expression, {"_tag": "Lin", "kind": kind,
                                               "constant": str(constant), "terms": emitted})

    def eq(self, terms=(), **kwargs):
        return self.lin("Eq", terms, **kwargs)

    def le(self, terms=(), **kwargs):
        return self.lin("Le", terms, **kwargs)

    def int(self, terms=(), **kwargs):
        return self.lin("Int", terms, **kwargs)

    def combine_rows(self, kind, coefficients, *, constant=0, expect=None):
        """Combine only the rows and multipliers explicitly selected by the caller.

        Keys are row names/indices, or ``(row, 'Lower'/'Upper'/'Eq')`` pairs
        when a row side must be explicit. No combination is inferred or searched.
        """
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
        """Prove one supplied LE from declared variable bounds, without search."""
        expression = self._expression(expression)
        residual, terms = expression.constant, []
        for index, coefficient in expression.terms.items():
            variable = self.model.vars[index]
            bound = variable.upper if coefficient > 0 else variable.lower
            if bound is None:
                raise BuildError(f"box_le needs {'upper' if coefficient > 0 else 'lower'} bound for {variable.name!r}")
            residual = exact(residual + coefficient * bound)
            terms.append((self.upper(index) if coefficient > 0 else self.lower(index), abs(coefficient)))
        if residual > 0:
            raise BuildError(f"Declared bounds do not prove the supplied LE; maximum {Expr(residual).summary()}")
        return self.le(terms, constant=residual, expect=expression)

    def subset_bounds(self, fact, subsets):
        """Restrict one supplied LE/EQ to caller-selected coordinate subsets.

        Canceled positive coefficients use declared lower bounds; negative
        coefficients use upper bounds. Results are LE Facts in input order.
        Shared subset and bound-sum derivations expand to ordinary Lin steps;
        no rows, subsets, covers or stronger bounds are discovered.
        """
        from ._subsets import subset_bounds
        return subset_bounds(self, fact, subsets)

    def eq_on_fixed(self, expression, fixes=None):
        """Prove a caller-selected equality whose coordinates have known fixed values.

        ``fixes`` maps names/indices to caller-proved, one-coordinate equalities.
        Unspecified coordinates require equal finite bounds in the input model.
        The helper checks the exact constant identity before emitting any steps.
        """
        expression = self._expression(expression)
        fixes = {self.model._index(i): fact for i, fact in (fixes or {}).items()}
        residual, terms, bound_fixes = expression.constant, [], []
        for index, coefficient in expression.terms.items():
            equality = fixes.get(index)
            if equality is not None:
                self._visible(equality)
                if equality.kind != "Eq" or set(equality.expression.terms) != {index}:
                    raise BuildError("eq_on_fixed needs a one-coordinate EQ for each explicit fixing")
                multiplier = coefficient / equality.expression.terms[index]
                residual -= multiplier * equality.expression.constant
                terms.append((equality, multiplier))
            else:
                variable = self.model.vars[index]
                if variable.lower is None or variable.lower != variable.upper:
                    raise BuildError(f"eq_on_fixed needs a fixing for {variable.name!r}")
                residual += coefficient * variable.lower
                bound_fixes.append((index, coefficient))
        if residual != 0:
            raise BuildError(f"Fixed-coordinate equality has nonzero exact residual {residual}")
        for index, coefficient in bound_fixes:
            equality = self.find("Eq", self.model.var(index) - self.model.vars[index].lower)
            if not isinstance(equality, Fact):
                equality = self.eqpair(self.upper(index), self.lower(index))
            terms.append((equality, coefficient))
        return self.eq(terms, expect=expression)

    def zero_sum(self, fact, *, zeros=None, scale=1, coordinates=None):
        """Elaborate zeros from one supplied nonnegative, zero-sided sum.

        The caller selects the EQ/LE, its orientation, already proved zeros,
        and optionally the coordinates to prove. Only the selected row's
        coordinates are looked up in ``zeros`` (integer keys, then names).
        This does not select rows, discover a closure, or search for premises.

        After cancelling the supplied one-coordinate zero EQs, the constant
        must be zero and all remaining coefficients positive, with declared
        nonnegative lower bounds. A one-coordinate EQ needs no bound or sign
        condition. The result maps new coordinate indices to EQ(x[i]) facts.
        All steps are ordinary Lin/EqPair. For m input terms and k outputs
        from an n-term residual, they use O(m+k*n) premises, without scanning
        the complete zero map per row.
        """
        self._visible(fact)
        scale = exact(scale)
        if fact.kind not in ("Eq", "Le") or not scale or (fact.kind == "Le" and scale < 0):
            raise BuildError("zero_sum needs an EQ or a positively scaled LE")
        zeros = {} if zeros is None else zeros
        if not isinstance(zeros, Mapping):
            raise TypeError("zero_sum zeros must map coordinate indices or names to zero EQ facts")
        if fact.expression.constant:
            raise BuildError("zero_sum needs an exactly zero constant")

        missing, terms, remaining = object(), [(fact, scale)], {}
        for index, coefficient in fact.expression.terms.items():
            equality = zeros.get(index, missing)
            if equality is missing:
                equality = zeros.get(self.model.vars[index].name, missing)
            coefficient *= scale
            if equality is missing:
                remaining[index] = coefficient
                continue
            self._visible(equality)
            if (equality.kind != "Eq" or equality.expression.constant
                    or len(equality.expression.terms) != 1
                    or index not in equality.expression.terms):
                raise BuildError("zero_sum needs a one-coordinate zero EQ for each used fixing")
            terms.append((equality, -coefficient / equality.expression.terms[index]))

        selected = (list(remaining) if coordinates is None else
                    list(dict.fromkeys(self.model._index(i) for i in coordinates)))
        if any(index not in remaining for index in selected):
            raise BuildError("zero_sum selected coordinate is not an unfixed term of the supplied sum")
        if not selected:
            return {}
        single_eq = fact.kind == "Eq" and len(remaining) == 1
        if not single_eq:
            for index, coefficient in remaining.items():
                lower = self.model.vars[index].lower
                if coefficient <= 0 or lower is None or lower < 0:
                    raise BuildError("zero_sum needs positive coefficients and declared nonnegative lower bounds")

        # Validate all used premises and conditions before emitting any step.
        expression = Expr(0, remaining)
        reduced = fact if len(terms) == 1 and scale == 1 else self.lin(fact.kind, terms, expect=expression)
        if single_eq:
            index = selected[0]
            x, coefficient = self.model.var(index), remaining[index]
            return {index: reduced if coefficient == 1 else self.eq([(reduced, 1/coefficient)], expect=x)}

        nonnegative = {}
        for index in remaining:
            x = self.model.var(index)
            nonnegative[index] = (self.lower(index) if self.model.vars[index].lower == 0
                                  else self.box_le(-x))
        result = {}
        for index in selected:
            x, coefficient = self.model.var(index), remaining[index]
            if len(remaining) == 1 and coefficient == 1:
                upper = reduced
            else:
                upper = self.le([(reduced, 1/coefficient), *(
                    (nonnegative[other], value/coefficient)
                    for other, value in remaining.items() if other != index)], expect=x)
            result[index] = self.eqpair(upper, nonnegative[index])
        return result

    def round(self, le, integer):
        self._visible(le)
        self._visible(integer)
        if le.kind != "Le" or integer.kind != "Int" or le.expression.terms != integer.expression.terms:
            raise BuildError("Round needs LE and INT facts with identical variable terms")
        difference = le.expression.constant - integer.expression.constant
        ceiling = -((-difference.numerator) // difference.denominator)
        return self._register("Le", integer.expression + ceiling,
                              {"_tag": "Round", "le": le.reference, "integer": integer.reference})

    def parity_fix(self, variable, equality):
        """Fix a binary coordinate using one caller-supplied exact parity EQ.

        The selected coefficient must be odd, every other coefficient even,
        and the constant integral. All coordinates must be declared integral
        in this scope. The helper elaborates only Lin/Int/Round/EqPair; it does
        not select rows, combine equations, solve a parity system, or search.
        """
        self._visible(equality)
        index = self.model._index(variable)
        if not self.integers or not self.model.is_binary(index):
            raise BuildError("parity_fix requires an integer-mode binary coordinate in [0, 1]")
        expression = equality.expression
        selected = expression.terms.get(index, Fraction(0))
        if (equality.kind != "Eq" or expression.constant.denominator != 1
                or selected.denominator != 1 or selected.numerator % 2 != 1):
            raise BuildError("parity_fix needs an EQ with integral constant and odd selected coefficient")
        for coordinate, coefficient in expression.terms.items():
            if not self.model.vars[coordinate].integer:
                raise BuildError("parity_fix requires declared integral coordinates in the equality")
            if coordinate != index and (coefficient.denominator != 1 or coefficient.numerator % 2):
                raise BuildError("parity_fix requires every other coefficient to be an even integer")
        parity = (-expression.constant.numerator) % 2
        # Equality/2 is zero. Cancel the other integer terms and the even part
        # of the selected odd coefficient, leaving INT((x-parity)/2).
        half = Fraction(1, 2)
        terms = [(equality, half)]
        for coordinate, coefficient in expression.terms.items():
            if coordinate != index:
                terms.append((self.integer(coordinate), -coefficient * half))
        adjustment = (1 - selected) * half
        if adjustment:
            terms.append((self.integer(index), adjustment))
        x = self.model.var(index)
        integral_half = self.int(terms, constant=(-parity-expression.constant) * half,
                                 expect=(x-parity) * half)
        variable_data = self.model.vars[index]
        upper_half = self.le([(self.upper(index), half)], constant=(variable_data.upper-1) * half,
                             expect=(x-1) * half)
        upper = self.le([(self.round(upper_half, integral_half), 2)], expect=x-parity)
        negative_half = self.int([(integral_half, -1)], expect=(parity-x) * half)
        lower_half = self.le([(self.lower(index), half)], constant=-variable_data.lower * half,
                             expect=-x * half)
        lower = self.le([(self.round(lower_half, negative_half), 2)], expect=parity-x)
        return self.eqpair(upper, lower)

    def eqpair(self, positive, negative):
        self._visible(positive)
        self._visible(negative)
        if positive.kind != "Le" or negative.kind != "Le" or positive.expression != -negative.expression:
            raise BuildError("EqPair needs opposite LE expressions")
        return self._register("Eq", positive.expression, {"_tag": "EqPair",
                              "positive": positive.reference, "negative": negative.reference})

    def rewrite(self, fact, definitions, *, expect=None):
        """Eliminate caller-selected pivots using caller-proved equalities."""
        self._visible(fact)
        return self._rewrite_plan(fact, _PivotPlan(self, definitions), expect=expect)

    def _rewrite_plan(self, fact, plan, *, expect=None):
        self._visible(fact)
        constant, coefficients, cancellation = plan.reduce(fact.expression)
        expected = Expr(constant, coefficients) if expect is None else expect
        return self.lin(fact.kind, [(fact, 1), *cancellation], expect=expected)

    def rewrite_many(self, facts, definitions):
        """Rewrite an explicit fact sequence with one validated pivot plan."""
        plan = _PivotPlan(self, definitions)
        return [self._rewrite_plan(fact, plan) for fact in facts]

    def derive_substitution(self, goal, definitions, residual, *, kind=None):
        """Restore one explicit goal from a supplied proof of its reduced form.

        The selected ordered equations must reduce ``goal`` to exactly the
        supplied residual Fact. Reversing their cancellation coefficients then
        emits one ordinary Lin step; no residual or equation is discovered.
        """
        self._visible(residual)
        return self._derive_substitution_plan(goal, _PivotPlan(self, definitions), residual, kind=kind)

    def _derive_substitution_plan(self, goal, plan, residual, *, kind=None):
        self._visible(residual)
        goal = self._expression(goal)
        kind = residual.kind if kind is None else kind
        constant, coefficients, cancellation = plan.reduce(goal)
        if constant != residual.expression.constant or coefficients != residual.expression.terms:
            raise BuildError("Substitution residual mismatch: selected equations do not produce the supplied proved residual")
        return self.lin(kind, [(residual, 1), *((fact, -multiplier) for fact, multiplier in cancellation)],
                        expect=goal)

    def derive_substitution_many(self, items, definitions, *, kind=None):
        """Restore explicit (goal, residual) pairs with one ordered pivot plan.

        An explicit result kind is common to the batch; otherwise each item
        uses its residual's kind. Ordinary Lin premise restrictions still apply.
        """
        plan = _PivotPlan(self, definitions)
        return [self._derive_substitution_plan(goal, plan, residual, kind=kind) for goal, residual in items]

    def substitution(self, definitions, *, goals=()):
        """Rewrite affected model facts and prove supplied equality expressions.

        The caller selects every equation, pivot, and its order. A supplied
        equality goal is emitted only when this ordered cancellation leaves
        literally zero. No equations, order, goals, or combinations are found.
        This helper is available in ordinary, branch, and generated scopes.
        """
        return self._substitution_plan(_PivotPlan(self, definitions), goals)

    def _substitution_plan(self, plan, goals):
        if not plan.entries:
            return []
        def model_facts():
            for index, variable in enumerate(self.model.vars):
                for tag, present in (("VarLower", variable.lower is not None),
                                     ("VarUpper", variable.upper is not None),
                                     ("VarInt", self.integers and variable.integer)):
                    if present:
                        yield self.ref(tag, index)
            for index, row in enumerate(self.model.rows):
                tags = ["RowEq"] if row.equality else [tag for tag, present in (
                    ("RowLower", row.lower is not None), ("RowUpper", row.upper is not None)) if present]
                for tag in tags:
                    yield self.ref(tag, index)
        generated = []
        for fact in model_facts():
            if any(index in plan.positions for index in fact.expression.terms):
                generated.append(self._rewrite_plan(fact, plan))
        for goal in goals:
            expression = self._expression(goal)
            if self.find("Eq", expression) is not None:
                continue
            constant, coefficients, cancellation = plan.reduce(expression)
            if not constant and not coefficients:
                generated.append(self.eq([(fact, -multiplier) for fact, multiplier in cancellation],
                                         expect=expression))
        return generated

    def drop(self, *facts):
        ids = []
        for fact in facts:
            self._visible(fact)
            if not isinstance(fact.reference, dict) or "Local" not in fact.reference:
                raise BuildError("Only Local facts can be dropped")
            ident = fact.reference["Local"]
            ids.append(ident)
        if len(set(ids)) != len(ids):
            raise BuildError("A Drop cannot list the same local fact twice")
        for fact, ident in zip(facts, ids):
            self._dropped.add(ident)
            self._facts.maps[0].pop(ident, None)
            key = _key(fact.kind, fact.expression)
            candidates = self._lookup.maps[0].get(key)
            if candidates is not None:
                candidates[:] = [candidate for candidate in candidates if candidate is not fact]
                if not candidates:
                    del self._lookup.maps[0][key]
        self.steps.append({"Drop": {"ids": ids}})
        self._revision += 1

    def absurd(self, fact):
        self._visible(fact)
        e = fact.expression
        if e.terms or not ((fact.kind == "Le" and e.constant > 0) or (fact.kind == "Eq" and e.constant != 0)):
            raise BuildError("Absurd requires positive constant LE or nonzero constant EQ")
        return Contradiction(fact)

    def _branch(self, expression):
        child = Builder(self.model, integers=self.integers, parent=self,
                        assumptions=self.assumptions, counter=self._counter)
        assumption = Fact("Le", expression, {"Assumption": len(self.assumptions)}, child)
        child.assumptions += (assumption,)
        child._remember(assumption)
        return child, assumption

    def _split(self, expression, integer):
        expression = self._expression(expression)
        if integer is False:
            integer = None
        if integer is True:
            if expression.constant == 0 and len(expression.terms) == 1 and next(iter(expression.terms.values())) == 1:
                integer = self.integer(next(iter(expression.terms)))
            else:
                raise BuildError("Supply an explicit INT fact for a non-variable integer split")
        if integer is not None:
            self._visible(integer)
            if integer.kind != "Int" or integer.expression != expression:
                raise BuildError("Integer split witness must prove INT of the exact split expression")
        return expression, integer

    def cases(self, expression, *, kind, expect, left, right, integer=True):
        """Export one common fact from caller-authored exhaustive branch proofs."""
        if kind not in ("Le", "Eq", "Int"):
            raise BuildError(f"Unknown fact kind {kind}")
        expression, integer = self._split(expression, integer)
        expect = self._expression(expect)
        branches = []
        for assumption_expression, callback in [(expression, left), ((1 if integer else 0) - expression, right)]:
            child, assumption = self._branch(assumption_expression)
            conclusion = callback(child, assumption)
            if isinstance(conclusion, Contradiction):
                child.absurd(conclusion.fact)
                end = {"Absurd": conclusion.fact.reference}
            else:
                child._visible(conclusion)
                if conclusion.expression != expect or (conclusion.kind != kind and conclusion.kind != "Eq"):
                    raise BuildError("Case branch must prove the common requested expression and kind")
                end = {"Witness": conclusion.reference}
            branches.append({"steps": child.steps, "end": end})
        return self._register(kind, expect, {"_tag": "Cases", "kind": kind,
                              "expression": expect.to_json(), "split": expression.to_json(),
                              "integer": integer.reference if integer else None,
                              "left": branches[0], "right": branches[1]})

    def binary_value(self, variable, value, assumption):
        """Trivial branch-local equality x=value, using the actual binary bounds."""
        if value == 0:
            return self.eqpair(assumption, self.lower(variable))
        if value == 1:
            return self.eqpair(self.upper(variable), assumption)
        raise BuildError("binary_value supports 0 or 1")

    def binary_cases(self, variables, *, kind, expect, prove, integers=None):
        """Expand every supplied binary coordinate and call the explicit leaf proof.

        ``prove(scope, fixes)`` receives name -> EQ(x-bit) handles. The caller
        chooses all coordinates, the common proposition, and every leaf proof;
        this template only expands ordinary Cases, Lin, and EqPair steps.
        """
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
            self._visible(fact)
            if fact.kind != "Int" or fact.expression != self.model.var(index):
                raise BuildError("binary_cases needs INT of each exact selected coordinate")
            supplied[index] = fact
        witnesses = []
        for index in indices:
            variable = self.model.vars[index]
            if variable.lower is None or variable.upper is None or not 0 <= variable.lower <= variable.upper <= 1:
                raise BuildError("binary_cases needs declared bounds within [0,1]")
            if index not in supplied and (not self.integers or not variable.integer):
                raise BuildError("binary_cases needs an explicit INT witness for a coordinate without active declared integrality")
            witnesses.append(supplied[index] if index in supplied else self.integer(index))

        def visit(scope, position, fixes):
            if position == len(indices):
                conclusion = prove(scope, dict(fixes))
                if isinstance(conclusion, Contradiction):
                    scope.absurd(conclusion.fact)
                else:
                    scope._visible(conclusion)
                    if conclusion.expression != expect or (conclusion.kind != kind and conclusion.kind != "Eq"):
                        raise BuildError("Binary case leaf must prove the common requested expression and kind")
                return conclusion
            index = indices[position]
            variable, expression = self.model.vars[index], self.model.var(index)
            def left(child, assumption):
                lower = child.lower(index)
                if variable.lower:
                    lower = child.le([(lower, 1)], constant=-variable.lower, expect=-expression)
                fixing = child.eqpair(assumption, lower)
                return visit(child, position+1, {**fixes, variable.name: fixing})
            def right(child, assumption):
                upper = child.upper(index)
                if variable.upper != 1:
                    upper = child.le([(upper, 1)], constant=variable.upper-1, expect=expression-1)
                fixing = child.eqpair(upper, assumption)
                return visit(child, position+1, {**fixes, variable.name: fixing})
            return scope.cases(expression, kind=kind, expect=expect, integer=witnesses[position],
                               left=left, right=right)
        return visit(self, 0, {})

    def split(self, expression, *, left, right, integer=True):
        """Terminal branches may provide different complete output maps."""
        expression, integer = self._split(expression, integer)
        children = []
        for assumption_expression, callback in [(expression, left), ((1 if integer else 0) - expression, right)]:
            child, assumption = self._branch(assumption_expression)
            callback(child, assumption)
            if child.end is None:
                raise BuildError("Each terminal split branch must return a complete map or close Absurd")
            children.append(child)
        self._set_end({"Split": {"expression": expression.to_json(), "integer": integer.reference if integer else None}}, children)
        return children

    def close_absurd(self, fact):
        self.absurd(fact)
        self._set_end({"Absurd": {"fact": fact.reference}})

    def close_positive(self, fact):
        """Close a strict-improvement domain by proving its positive predicate <= 0.

        The immutable root improvement contract supplies strict positivity;
        the weak root assumption alone does not prove a contradiction. This is
        the frozen PositiveRefutation terminal, including in split branches.
        """
        root = self
        while root is not None and not hasattr(root, "improvement_claim"):
            root = root.parent
        if root is None:
            raise BuildError("close_positive requires a strict-improvement proof scope")
        self._visible(fact)
        positive = Expr.from_json(root.improvement_claim["positive"])
        if fact.kind not in ("Le", "Eq") or fact.expression != positive:
            raise BuildError("PositiveRefutation needs LE or EQ of the exact root positive predicate")
        self._set_end({"PositiveRefutation": {"fact": fact.reference}})

    def batch(self, instances, template):
        """Ordinary Python proof templates expand to ordinary checked steps."""
        return [template(self, instance) for instance in instances]

    def plotkin(self, *, bits, distance, variables, cliques):
        if (isinstance(bits, bool) or not isinstance(bits, int) or isinstance(distance, bool)
                or not isinstance(distance, int) or not 1 <= bits <= 64
                or not 1 <= distance <= 64 or 2 * distance <= bits):
            raise BuildError("Invalid Plotkin parameters")
        if not self.integers:
            raise BuildError("Plotkin requires integer input mode")
        variables = [(self.model._index(i), label) for i, label in variables]
        if len({i for i, _ in variables}) != len(variables):
            raise BuildError("Plotkin variables must be distinct")
        for i, label in variables:
            if not self.model.is_binary(i):
                raise BuildError("Plotkin requires actual binary variable domains")
            if isinstance(label, bool) or not isinstance(label, int) or not 0 <= label < 2**bits:
                raise BuildError("Plotkin label exceeds the selected bit width")
        cliques = tuple(cliques)
        membership = {i: set() for i, _ in variables}
        for clique_index, fact in enumerate(cliques):
            self._visible(fact)
            if fact.kind != "Le" or fact.expression.constant != -1:
                raise BuildError("Plotkin cliques require LE facts with constant -1")
            for i, coefficient in fact.expression.terms.items():
                lo = self.model.vars[i].lower
                if coefficient != 1 or lo is None or lo < 0:
                    raise BuildError("Plotkin clique coordinates require unit coefficients and nonnegative domains")
                if i in membership:
                    membership[i].add(clique_index)
        for index, (i, label) in enumerate(variables):
            for j, other_label in variables[index + 1:]:
                if bin(label ^ other_label).count("1") < distance and not membership[i].intersection(membership[j]):
                    raise BuildError(f"Plotkin close pair {self.model.vars[i].name!r}, {self.model.vars[j].name!r} lacks a supplied clique")
        bound = 2 * distance // (2 * distance - bits)
        expression = Expr(-bound, {i: 1 for i, _ in variables})
        return self._register("Le", expression, {"_tag": "Plotkin", "bits": bits,
                              "distance": distance, "variables": list(variables),
                              "cliques": [f.reference for f in cliques]})

    def lift(self, kind, witness):
        """Introduce an existing constructive extension and use Kernel-generated names."""
        tags = {"interval": ("Interval", "IntervalLift", "intervals"),
                "menu": ("Menu", "MenuLift", "menus"),
                "signed": ("Signed", "SignedLift", "decompositions"),
                "flow": ("Flow", "FlowLift", "witness"),
                "subflow": ("Subflow", "SubflowLift", "witness")}
        spec_tag, end_tag, end_field = tags[kind.lower()]
        if kind.lower() in ("menu", "signed") and not self.integers:
            raise BuildError(f"{kind} requires integer input mode")
        handles = {}
        def collect(value):
            if isinstance(value, Fact):
                self._visible(value)
                handles[json.dumps(value.reference, sort_keys=True)] = value
            elif isinstance(value, dict):
                for child in value.values():
                    collect(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    collect(child)
        collect(witness)
        lowered = wire(witness)
        # Expression-valued convenience fields accept ordinary exact scalars.
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
        with tempfile.TemporaryDirectory(prefix="kernel-scope-") as directory:
            path = Path(directory) / "input.mcm"
            self.model.write_mcm(path)
            prepared = self.model.kernel.json_command("prepare-extension", [path], {spec_tag: lowered})
        # Check old-scope references against precisely the kernel's premises.
        for premise in prepared["premises"]:
            fact = handles.get(json.dumps(premise["reference"], sort_keys=True))
            expression = Expr.from_json(premise["expression"], intermediate=True)
            if premise["reference"] == "Exact" and self.find(premise["kind"], expression) == "Exact":
                continue
            if fact is None or fact.expression != expression or (fact.kind != premise["kind"] and fact.kind != "Eq"):
                raise BuildError(f"{kind} premise mismatch: {premise}")
        model = Model.from_json(prepared["model"], kernel=self.model.kernel)
        child = Builder(model, integers=self.integers, parent=self,
                        assumptions=self.assumptions, counter=self._counter)
        child.generated_variables = tuple(range(len(self.model.vars), len(model.vars)))
        child.generated_rows = tuple(range(len(self.model.rows), len(model.rows)))
        child.preparation = prepared
        child.layout = prepared.get("layout")
        child._layout_kind = spec_tag
        self._set_end({end_tag: {end_field: lowered}}, [child])
        return child

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

    def _generated_instance(self, kind, index):
        if self._layout_kind != kind or not isinstance(self.layout, list):
            raise BuildError(f"This scope has no {kind} layout; use the scope returned by its constructive lift")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.layout):
            raise BuildError(f"{kind} instance index {index!r} is outside the generated layout")
        return self.layout[index]

    def interval(self, index):
        """Native per-interval variable and lower/upper row Fact handles."""
        entry = self._generated_instance("Interval", index)
        key = "Interval", index
        if key not in self._layout_handles:
            self._layout_handles[key] = SimpleNamespace(
                variable=self.model.var(entry["variable"]),
                lower_rows=tuple(self.ref("RowLower", i) for i in entry["lower_rows"]),
                upper_rows=tuple(self.ref("RowUpper", i) for i in entry["upper_rows"]))
        return self._layout_handles[key]

    def menu(self, index):
        """Native per-menu options and activation-sum/index-moment equalities."""
        entry = self._generated_instance("Menu", index)
        key = "Menu", index
        if key not in self._layout_handles:
            self._layout_handles[key] = SimpleNamespace(
                options=tuple(self.model.var(i) for i in entry["options"]),
                sum=self.ref("RowEq", entry["sum_row"]),
                moment=self.ref("RowEq", entry["moment_row"]))
        return self._layout_handles[key]

    def signed_decomposition(self, index):
        """Native positive/negative flows, activations, recovery and capacity laws."""
        entry = self._generated_instance("Signed", index)
        key = "Signed", index
        if key not in self._layout_handles:
            self._layout_handles[key] = SimpleNamespace(
                positive=self.model.var(entry["positive"]), negative=self.model.var(entry["negative"]),
                positive_activation=self.model.var(entry["positive_activation"]),
                negative_activation=self.model.var(entry["negative_activation"]),
                flow=self.ref("RowEq", entry["flow_row"]),
                activation=self.ref("RowEq", entry["activation_row"]),
                positive_capacity=self.ref("RowUpper", entry["positive_capacity_row"]),
                negative_capacity=self.ref("RowUpper", entry["negative_capacity_row"]))
        return self._layout_handles[key]

    def flow_group(self, index):
        """Native common-source commodities, conservation rows and flow recovery."""
        entry = self._generated_instance("Flow", index)
        key = "Flow", index
        if key not in self._layout_handles:
            commodities = tuple(SimpleNamespace(
                sink=item["sink"], demand=exact(item["demand"]),
                flows=tuple(self.model.var(i) for i in item["flows"]),
                balances=tuple(self.ref("RowEq", i) for i in item["balance_rows"]))
                for item in entry["commodities"])
            self._layout_handles[key] = SimpleNamespace(
                source=entry["source"], commodities=commodities,
                recovery=tuple(self.ref("RowEq", i) for i in entry["recovery_rows"]))
        return self._layout_handles[key]

    def commodity(self, group, index):
        """One commodity from a native Flow group, with no coordinate-offset arithmetic."""
        commodities = self.flow_group(group).commodities
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(commodities):
            raise BuildError(f"Flow commodity index {index!r} is outside group {group}")
        return commodities[index]

    def subflow_group(self, index):
        """Native selected subflow, conservation laws and nonnegative remainder laws."""
        entry = self._generated_instance("Subflow", index)
        key = "Subflow", index
        if key not in self._layout_handles:
            self._layout_handles[key] = SimpleNamespace(
                source=entry["source"], flows=tuple(self.model.var(i) for i in entry["flows"]),
                balances=tuple(self.ref("RowEq", i) for i in entry["balance_rows"]),
                remainder_nonnegative=tuple(self.ref("RowUpper", i) for i in entry["remainder_nonnegative_rows"]))
        return self._layout_handles[key]

    def _index_base_facts(self):
        if getattr(self, "_indexed", False):
            return
        self._indexed = True
        if self.parent is not None and self.model is self.parent.model:
            self.parent._index_base_facts()
            return
        for i, variable in enumerate(self.model.vars):
            for tag, enabled in [("VarLower", variable.lower is not None), ("VarUpper", variable.upper is not None),
                                 ("VarInt", variable.integer and self.integers)]:
                if enabled:
                    fact = self.ref(tag, i)
                    self._remember(fact)
        for i, row in enumerate(self.model.rows):
            tags = ["RowEq"] if row.lower is not None and row.lower == row.upper else [tag for tag, enabled in [("RowLower", row.lower is not None), ("RowUpper", row.upper is not None)] if enabled]
            for tag in tags:
                fact = self.ref(tag, i)
                self._remember(fact)

    def find(self, kind, expression):
        """Only tautologies and exact reuse of existing facts; no proof search."""
        if kind not in ("Le", "Eq", "Int"):
            raise BuildError(f"Unknown fact kind {kind}")
        expression = self._expression(expression)
        trivial = ((kind == "Eq" and not expression.terms and expression.constant == 0)
                   or (kind == "Le" and not expression.terms and expression.constant <= 0)
                   or (kind == "Int" and expression.constant.denominator == 1
                       and all(q.denominator == 1 and self.integers and self.model.vars[i].integer
                               for i, q in expression.terms.items())))
        if trivial:
            return "Exact"
        self._index_base_facts()
        for candidate_kind in (kind, "Eq"):
            key = _key(candidate_kind, expression)
            for layer in self._lookup.maps:
                for fact in reversed(layer.get(key, ())):
                    try:
                        self._visible(fact)
                        return fact
                    except BuildError:
                        pass
        return None

    def to_json(self):
        if self.end is None:
            raise BuildError("Proof scope has no terminal return, split, extension, or contradiction")
        end = wire(self.end)
        if self._children is not None:
            tag = next(iter(end))
            if tag == "Split":
                end[tag]["left"], end[tag]["right"] = [c.to_json() for c in self._children]
            else:
                end[tag]["body"] = self._children[0].to_json()
        return {"steps": self.steps, "end": end}
