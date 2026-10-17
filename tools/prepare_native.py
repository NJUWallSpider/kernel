"""Native bridge for the historical exact case preparers.

Proof recipes still use the preparers' exact ``(constant, {index: Fraction})``
expressions and legacy model dictionaries.  Every rule, lift, and obligation is
executed by the native ``kernel_compiler.Builder`` / ``Proof`` implementation;
the only artifact writer is ``Proof.compile`` (RPA 12 + RPX 11).
"""
from __future__ import annotations

from collections import ChainMap
from fractions import Fraction
from pathlib import Path
import hashlib
import json

from kernel_compiler import Expr, Model, Proof, Row, Variable
from kernel_compiler.proof import BuildError, Builder as PythonBuilder, Contradiction, Fact


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def legacy_expr(expression):
    return expression.constant, dict(expression.terms)


def native_expr(expression):
    if isinstance(expression, Expr):
        return expression
    if isinstance(expression, dict):
        return Expr(Fraction(expression["constant"]), expression["terms"])
    constant, terms = expression
    return Expr(Fraction(constant), terms)


def signature(expression):
    return expression[0], tuple(sorted(expression[1].items()))


def is_exact(kind, expression):
    return (not expression[1] and
            ((kind == "Eq" and expression[0] == 0) or
             (kind == "Le" and expression[0] <= 0) or
             (kind == "Int" and expression[0].denominator == 1)))


def native_model(data):
    """Build a native model from the legacy exact model dictionary."""
    variables = [Variable(item["name"], item.get("integer", False),
                          item.get("lower"), item.get("upper"))
                 for item in data["vars"]]
    rows = []
    for item in data["rows"]:
        expression = native_expr((Fraction(0), item["terms"]))
        lower, upper = item.get("lower"), item.get("upper")
        if "sense" in item:
            rhs = Fraction(item["rhs"])
            sense = item["sense"]
            if sense == "E":
                lower = upper = rhs
            elif sense == "G":
                lower, upper = rhs, None
            elif sense == "L":
                lower, upper = None, rhs
            elif sense == "R":
                lower, upper = rhs, Fraction(item["upper"])
            else:
                raise BuildError(f"Unknown row sense {sense!r}")
        rows.append(Row(item["name"], expression, lower, upper))
    return Model(data.get("name", "MODEL"), variables, rows,
                 native_expr(data["objective"]))


def legacy_from_native(model):
    """Read-only legacy-dict view of a native model for the analysis code."""
    def field(item, name, index):
        return getattr(item, name) if hasattr(item, name) else item[index]
    variables = [{"name": field(item, "name", 0), "integer": field(item, "integer", 1),
                  "lower": field(item, "lower", 2), "upper": field(item, "upper", 3)}
                 for item in model.vars]
    rows = []
    for item in model.rows:
        name = field(item, "name", 0)
        expression = field(item, "expr", 1)
        lower = field(item, "lower", 2)
        upper = field(item, "upper", 3)
        constant = expression.constant
        if lower is not None and upper is not None and lower != upper:
            sense, rhs, out_upper = "R", lower - constant, upper - constant
        elif lower is not None and upper is not None:
            sense, rhs, out_upper = "E", lower - constant, None
        elif lower is not None:
            sense, rhs, out_upper = "G", lower - constant, None
        else:
            sense, rhs, out_upper = "L", upper - constant, None
        row = {"name": name, "sense": sense, "rhs": rhs,
               "terms": dict(expression.terms)}
        if out_upper is not None:
            row["upper"] = out_upper
        rows.append(row)
    return {"name": model.name, "vars": variables,
            "var_index": {item["name"]: index for index, item in enumerate(variables)},
            "rows": rows,
            "row_index": {item["name"]: index for index, item in enumerate(rows)},
            "objective": (model.objective.constant, dict(model.objective.terms))}


def _overlay(*values):
    maps = []
    for value in values:
        if value is None:
            continue
        maps.extend(value.maps if isinstance(value, ChainMap) else [value])
    return ChainMap({}, *maps)


class Builder:
    """Legacy-facing rule vocabulary over one native proof scope."""

    def __init__(self, direction, model=None, *, counter=None, facts=None,
                 assumptions=(), local=None, lookup=None, scope=None, owner=None):
        if not hasattr(direction, "lin"):
            raise BuildError("Pass a native DirectionBuilder; legacy Builder(model) construction is unsupported")
        self.direction = direction
        self.owner = owner or direction
        self.scope = scope or direction
        self.model = model if model is not None else legacy_from_native(self.scope.model)
        self.counter = list(counter) if counter is not None else [0]
        self.facts = _overlay(facts)
        self.local = _overlay(local)
        self.lookup = _overlay(lookup)
        self.assumption_exprs = list(assumptions)
        self._assumption_facts = []
        self._ref_cache = {}

    @property
    def steps(self):
        return self.scope.steps

    @property
    def layout(self):
        return self.scope.layout

    @property
    def assumptions(self):
        return tuple(self.assumption_exprs)

    def alloc(self):
        value = self.counter[0]
        self.counter[0] += 1
        return value

    def ref(self, reference):
        if isinstance(reference, Fact):
            return reference
        if not isinstance(reference, dict) or len(reference) != 1:
            raise BuildError(f"Expected one fact reference, got {reference!r}")
        kind, index = next(iter(reference.items()))
        if kind == "Local":
            try:
                return self.local[index]
            except KeyError:
                raise BuildError(f"Unknown local fact {index}") from None
        if kind == "Assumption":
            try:
                return self._assumption_facts[index]
            except IndexError:
                raise BuildError(f"Unknown branch assumption {index}") from None
        key=(kind,index)
        fact=self._ref_cache.get(key)
        if fact is None:
            fact=self.scope.ref(kind, index)
            self._ref_cache[key]=fact
        return fact

    def refexpr(self, reference):
        return legacy_expr(self.ref(reference).expression)

    def kind(self, reference):
        return self.ref(reference).kind

    def _local(self, fact):
        ident = self.alloc()
        self.local[ident] = fact
        self.facts[ident] = (fact.kind, legacy_expr(fact.expression))
        self.lookup[(fact.kind, signature(legacy_expr(fact.expression)))] = {"Local": ident}
        return {"Local": ident}

    def lin(self, kind, terms, expected=None, constant=0):
        native_terms = [(self.ref(reference), Fraction(coefficient))
                        for reference, coefficient in terms
                        if Fraction(coefficient) != 0]
        expect = None if expected is None else native_expr(expected)
        fact = self.scope.lin(kind, native_terms, constant=Fraction(constant), expect=expect)
        return self._local(fact)

    def eqpair(self, positive, negative):
        return self._local(self.scope.eqpair(self.ref(positive), self.ref(negative)))

    def round(self, le, integer):
        return self._local(self.scope.round(self.ref(le), self.ref(integer)))

    def parity_fix(self, variable, equality):
        return self._local(self.scope.parity_fix(self.ref(variable), self.ref(equality)))

    def plotkin(self, *, bits, distance, variables, cliques):
        return self._local(self.scope.plotkin(bits=bits, distance=distance,
                                              variables=variables, cliques=cliques))

    def drop(self, *references):
        self.scope.drop([self.ref(reference) for reference in references])

    def drop_many(self, identifiers):
        facts = [self.ref({"Local": value}) for value in identifiers]
        if facts:
            self.scope.drop(facts)
        for value in identifiers:
            self.local.pop(value, None)
            self.facts.pop(value, None)

    def absurd(self, reference):
        return self.scope.absurd(self.ref(reference))

    def find(self, kind, expression):
        value = self.scope.find(kind, native_expr(expression))
        if isinstance(value, Fact):
            return self._local(value)
        return value

    def add(self, kind, reference):
        self.lookup[(kind, signature(self.refexpr(reference)))] = reference
        return reference

    def check(self, kind, expression, reference=None):
        expression = legacy_expr(native_expr(expression))
        if is_exact(kind, expression):
            return "Exact"
        if kind == "Int" and expression[0].denominator == 1 and all(
                coefficient.denominator == 1 and self.model["vars"][index]["integer"]
                for index, coefficient in expression[1].items()):
            return "Exact"
        if reference is None:
            return self.prove(kind, expression)
        fact = self.ref(reference)
        if fact.kind not in (kind, "Eq") or fact.expression != native_expr(expression):
            raise BuildError(f"Witness does not prove {kind} {expression}")
        return reference

    def prove(self, kind, expression, terms=None, constant=0):
        expression = legacy_expr(native_expr(expression))
        if is_exact(kind, expression):
            return "Exact"
        if kind == "Int" and expression[0].denominator == 1 and all(
                coefficient.denominator == 1 and self.model["vars"][index]["integer"]
                for index, coefficient in expression[1].items()):
            return "Exact"
        cached = self.lookup.get((kind, signature(expression)))
        if cached is None and kind != "Eq":
            cached = self.lookup.get(("Eq", signature(expression)))
        if cached is not None:
            return cached
        if terms is None:
            found = self.scope.find(kind, native_expr(expression))
            if isinstance(found, Fact):
                return self._local(found)
            if kind == "Le":
                terms = []
                ceiling = expression[0]
                for index, coefficient in expression[1].items():
                    variable = self.model["vars"][index]
                    bound = variable["upper"] if coefficient > 0 else variable["lower"]
                    if bound is None:
                        raise BuildError(f"Unbounded box coordinate {variable['name']}")
                    ceiling += coefficient * bound
                    side = "VarUpper" if coefficient > 0 else "VarLower"
                    terms.append([{side: index}, abs(coefficient)])
                return self.lin("Le", terms, expression, ceiling)
        else:
            if isinstance(terms, dict):
                return terms
            if len(terms) == 1 and terms[0][1] == 1 and self.kind(terms[0][0]) in (kind, "Eq") \
                    and self.refexpr(terms[0][0]) == expression:
                return terms[0][0]
            return self.lin(kind, terms, expression, constant)
        opposite = self.lookup.get(("Eq", signature((expression[0], {k: -v for k, v in expression[1].items()}))))
        if opposite is not None:
            return self.lin(kind, [[opposite, -1]], expression)
        raise BuildError(f"No proof premise for {kind} {expression}")

    def _branch(self, expression):
        child, assumption = self.scope._branch(native_expr(expression))
        result = self._child(child, self.model)
        result.assumption_exprs = self.assumption_exprs + [legacy_expr(assumption.expression)]
        result._assumption_facts = self._assumption_facts + [assumption]
        return result, assumption

    def _child(self, scope, model=None):
        if not hasattr(scope, "ref"):
            scope = PythonBuilder._from_native(scope)
        return Builder(self.direction, self.model if model is None else model,
                       counter=self.counter, facts=self.facts, local=self.local,
                       lookup=self.lookup, scope=scope, owner=self.owner)

    def _case_call(self, callback, expected):
        def visit(child, assumption):
            branch = self._child(child, self.model)
            branch.assumption_exprs = self.assumption_exprs + [legacy_expr(assumption.expression)]
            branch._assumption_facts = self._assumption_facts + [assumption]
            result = callback(branch, {"Assumption": len(self.assumption_exprs)})
            if isinstance(result, Fact):
                return result
            if result == "Exact":
                if not is_exact("Le", legacy_expr(expected)):
                    raise BuildError("Exact branch witness requires a trivially true conclusion")
                return branch.scope.le([], expect=expected)
            if "Witness" in result:
                return branch.ref(result["Witness"])
            if "Absurd" in result:
                return branch.scope.absurd(branch.ref(result["Absurd"]))
            return branch.ref(result)
        return visit

    def cases(self, kind, expected, split, integer=None, left=None, right=None):
        # Bit-dictionary form: cases(kind, expected, bit, left, right)
        if right is None and left is not None:
            bit = split
            split = bit["expr"] if isinstance(bit, dict) else bit
            right = left
            left = integer
            integer = bit.get("integer") if isinstance(bit, dict) else None
        expected = native_expr(expected)
        split = native_expr(split)
        integer_fact = None if integer is None else self.ref(integer)
        fact = self.scope.cases(split, kind=kind, expect=expected,
                                left=self._case_call(left, expected),
                                right=self._case_call(right, expected),
                                integer=integer_fact)
        return self._local(fact)

    def split(self, expected, integer, left, right):
        raise BuildError("Legacy split callbacks are unsupported; use cases() or native split scopes")

    def menus(self, entries):
        specs = []
        for entry in entries:
            specs.append({
                "maximum_index": entry["maximum_index"],
                "activation": native_expr(entry["activation"]),
                "index": native_expr(entry["index"]),
                "checks": ["Exact" if check == "Exact" else self.ref(check)
                           for check in entry["checks"]],
            })
        child = self.scope.menus(specs)
        result = self._child(child, legacy_from_native(child.model))
        result.old_layout = child.layout
        return result

    def signed(self, entries):
        specs = []
        for entry in entries:
            specs.append({
                "capacity": Fraction(entry["capacity"]),
                "flow": native_expr(entry["flow"]),
                "activation": native_expr(entry["activation"]),
                "checks": ["Exact" if check == "Exact" else self.ref(check)
                           for check in entry["checks"]],
            })
        child = self.scope.signed(specs)
        result = self._child(child, legacy_from_native(child.model))
        result.old_layout = child.layout
        return result

    def intervals(self, entries):
        specs = []
        for entry in entries:
            specs.append({
                "lower": [native_expr(value) for value in entry["lower"]],
                "upper": [native_expr(value) for value in entry["upper"]],
                "checks": ["Exact" if check == "Exact" else self.ref(check)
                           for check in entry.get("checks", ())],
            })
        child = self.scope.intervals(specs)
        result = self._child(child, legacy_from_native(child.model))
        result.old_layout = [{"variable": item["variable"],
                              "lower": item["lower_rows"],
                              "upper": item["upper_rows"]}
                             for item in child.layout]
        return result

    def flow(self, witness):
        child = self.scope.flow(_normalize_extension(witness, self))
        result = self._child(child, legacy_from_native(child.model))
        result.old_layout = child.layout
        return result

    def subflow(self, witness):
        child = self.scope.subflow(_normalize_extension(witness, self))
        result = self._child(child, legacy_from_native(child.model))
        result.old_layout = child.layout
        return result

    def finish(self, mapping, checks):
        values = [native_expr(item) for item in mapping]
        witnesses = ["Exact" if check == "Exact" else self.ref(check) for check in checks]
        self.owner.complete_ordered(values, witnesses, scope=self.scope, auto=True)


def _normalize_extension(value, builder):
    if isinstance(value, dict):
        return {key: _normalize_extension(item, builder) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_extension(item, builder) for item in value]
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], dict):
        return native_expr(value)
    if isinstance(value, dict) or isinstance(value, Expr):
        return value
    return value


def make_proof(source, target):
    """Build one native MI-OPT proof and its two legacy-facing directions."""
    proof = Proof(native_model(source), native_model(target))
    return proof, Builder(proof.forward, source), Builder(proof.reverse, target)


def compile_case(proof, out, *, case_id, metadata=None, source=None, target=None):
    """Compile once through the public API and bind the native verification."""
    import time
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    paths = proof.compile(out)
    compiled = time.perf_counter()
    report = proof.kernel.verify(paths["source"], paths["target"], paths["proof"])
    verified = time.perf_counter()
    record = {
        "case_id": case_id,
        "status": report["status"],
        "source": {"path": str(source), "sha256": sha(source)} if source else None,
        "target": {"path": str(target), "sha256": sha(target)} if target else None,
        "artifacts": {name: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}
                      for name, path in paths.items()},
        "verification": report,
        "preparation_seconds": None,
        "timings": {"compile_seconds": compiled - started,
                    "verify_seconds": verified - compiled,
                    "compile_verify_seconds": verified - started},
    }
    if metadata:
        record.update(metadata)
    return record
