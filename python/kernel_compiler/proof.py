"""Checked authoring helpers for the frozen Kernel proof objects.

All arithmetic here is untrusted convenience. The Rust Kernel is the acceptance
authority. Helpers only elaborate caller-supplied derivations and trivial facts.
"""
from __future__ import annotations

from collections import ChainMap
from dataclasses import dataclass
from fractions import Fraction
from itertools import count
import json
from pathlib import Path
import tempfile

from .expr import Expr, exact
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
        return str(value)
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
        fact = Fact(kind, expression, {"Local": ident}, self)
        self._facts[ident] = fact
        self._remember(fact)
        return fact

    def ref(self, kind, site):
        """Model fact by original name or index (bounds and row sides are explicit)."""
        index = (self.model.var_index[site] if kind.startswith("Var") else self.model.row_index[site]) if isinstance(site, str) else site
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

    def round(self, le, integer):
        self._visible(le)
        self._visible(integer)
        if le.kind != "Le" or integer.kind != "Int" or le.expression.terms != integer.expression.terms:
            raise BuildError("Round needs LE and INT facts with identical variable terms")
        difference = le.expression.constant - integer.expression.constant
        ceiling = -((-difference.numerator) // difference.denominator)
        return self._register("Le", integer.expression + ceiling,
                              {"_tag": "Round", "le": le.reference, "integer": integer.reference})

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
        expression = fact.expression
        terms = [(fact, 1)]
        for pivot, equality in definitions.items():
            pivot = self.model.var_index[pivot] if isinstance(pivot, str) else pivot
            self._visible(equality)
            if equality.kind != "Eq" or not equality.expression.terms.get(pivot):
                raise BuildError("Each rewrite definition must be an EQ with a nonzero selected pivot")
            multiplier = -expression.terms.get(pivot, 0) / equality.expression.terms[pivot]
            if multiplier:
                expression += multiplier * equality.expression
                terms.append((equality, multiplier))
        return self.lin(fact.kind, terms, expect=expression if expect is None else expect)

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
        self.end = {"Split": {"expression": expression.to_json(), "integer": integer.reference if integer else None}}
        self._children = children
        return children

    def close_absurd(self, fact):
        self.absurd(fact)
        self.end = {"Absurd": {"fact": fact.reference}}

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
        spec_tag, end_tag, field = tags[kind.lower()]
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
        with tempfile.TemporaryDirectory(prefix="kernel-scope-") as directory:
            path = Path(directory) / "input.mcm"
            self.model.write_mcm(path)
            prepared = self.model.kernel.json_command("prepare-extension", [path], {spec_tag: lowered})
        # Check old-scope references against precisely the kernel's premises.
        for premise in prepared["premises"]:
            fact = handles.get(json.dumps(premise["reference"], sort_keys=True))
            expression = Expr.from_json(premise["expression"])
            if fact is None or fact.expression != expression or (fact.kind != premise["kind"] and fact.kind != "Eq"):
                raise BuildError(f"{kind} premise mismatch: {premise}")
        model = Model.from_json(prepared["model"], kernel=self.model.kernel)
        child = Builder(model, integers=self.integers, parent=self,
                        assumptions=self.assumptions, counter=self._counter)
        child.generated_variables = tuple(range(len(self.model.vars), len(model.vars)))
        child.generated_rows = tuple(range(len(self.model.rows), len(model.rows)))
        child.preparation = prepared
        self.end = {end_tag: {field: lowered}}
        self._children = [child]
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
