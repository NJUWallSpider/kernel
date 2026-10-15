"""Caller-bound contracts, Kernel obligation plans, and direct RPX compilation."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import weakref
from types import SimpleNamespace

from .backend import Kernel, KernelError
from .expr import Expr, exact, _rational_text
from .model import Model
from .proof import Builder, BuildError, Fact, _PivotPlan, wire
from .request_summary import summarize_request


class _ProofJSONEncoder(json.JSONEncoder):
    """Encode proof leaves on demand without copying their container tree."""
    def default(self, value):
        if isinstance(value, Fact):
            return value.reference
        if isinstance(value, Expr):
            return value.to_json()
        if isinstance(value, Fraction):
            return _rational_text(value)
        return super().default(value)


def _digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_reader_family(path):
    """Match Model.load's dispatch, including its JSON-before-magic rule."""
    path = Path(path).resolve()
    if path.suffix.lower() == ".json":
        return "python_canonical_json"
    with path.open("rb") as stream:
        if stream.read(4) == b"MCM\0":
            return "kernel_mcm"
    # Native canonicalize_path uses case-insensitive ASCII LP suffix matching.
    return "kernel_lp" if path.suffix.lower() == ".lp" else "kernel_mps"


def _artifact_binding_method(reader):
    if reader == "python_canonical_json":
        return "Python canonical JSON readback and exact named formulation comparison"
    return "Kernel standard-format readback and exact named formulation comparison"


def _atomic_write(path, writer):
    """Replace an owned output node without writing through existing links."""
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        writer(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_text(path, content):
    _atomic_write(path, lambda temporary: temporary.write_text(content))


@dataclass(frozen=True)
class Obligation:
    index: int
    kind: str
    expression: Expr
    origin: dict

    @property
    def label(self):
        site = self.origin.get("name", self.origin.get("index"))
        return self.origin["kind"] + (f"[{site}]" if site is not None else "") + (f"#{self.origin['group']}" if "group" in self.origin else "")


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


class ClaimBuilder(Builder):
    def __init__(self, session, index, claim, mapping):
        self.session = session
        self.index = index
        self.claim = claim
        self.input = session.target if claim["reverse"] else session.source
        self.output = session.source if claim["reverse"] else session.target
        self.mapping = _mapping(self.input, self.output, mapping) if mapping is not None else None
        model = self.input
        prepared = None
        if claim.get("input_objective_level") is not None or claim.get("input_halfspace") is not None:
            with tempfile.TemporaryDirectory(prefix="kernel-domain-") as directory:
                path = Path(directory) / "input.mcm"
                model.write_mcm(path)
                prepared = session.kernel.json_command("prepare-extension", [path], {"Restricted": {
                    "level": claim.get("input_objective_level"), "halfspace": claim.get("input_halfspace")}})
            model = Model.from_json(prepared["model"], kernel=session.kernel)
        super().__init__(model, integers=claim["input_integers"])
        self.domain = SimpleNamespace(objective_level=None, halfspace=None, positive=None)
        if prepared is not None:
            equality_row = prepared.get("equality_row")
            if equality_row is not None:
                self.domain.objective_level = self.row(equality_row)
            if claim.get("input_halfspace") is not None:
                self.domain.halfspace = self.row(len(model.rows)-1)
        self._assigned = {}
        self._plans = {}

    def _scope(self, scope):
        scope = self if scope is None else scope
        current = scope
        while current is not None and current is not self:
            current = current.parent
        if current is None:
            raise BuildError("Return scope must descend from this directional claim")
        return scope

    @property
    def contract(self):
        """The explicit directional claim (also available as .claim)."""
        return self.claim

    def _completion_state(self, options):
        scope = options["scope"]
        chain = []
        while scope is not None:
            chain.append((scope, scope._revision))
            scope = scope.parent
        inverse = self.claim.get("inverse")
        opposing = self.session.claims[inverse] if inverse is not None else None
        compositions = tuple(tuple(self.session.claims[p["claim"]["forward_claim"]].mapping or ())
                             for p in self.session.bijections if p["claim"]["reverse_claim"] == self.index)
        supplied = dict(self._assigned)
        supplied.update(options.get("witnesses") or {})
        witnesses = tuple(((type(k).__name__, k), f.kind, f.expression, json.dumps(f.reference, sort_keys=True))
                          if isinstance(f, Fact) else ((type(k).__name__, k), f)
                          for k, f in sorted(supplied.items(), key=lambda kv: (type(kv[0]).__name__, str(kv[0]))))
        return (tuple(chain), tuple(options["mapping"]), json.dumps(self.claim, sort_keys=True),
                tuple(opposing.mapping or ()) if opposing else None,
                json.dumps(opposing.claim, sort_keys=True) if opposing else None, compositions, witnesses,
                json.dumps([self.improvement_claim, self.margin], sort_keys=True) if hasattr(self, "improvement_claim") else None,
                options["auto"])

    def map(self, mapping):
        self.mapping = _mapping(self.input, self.output, mapping)
        self._plans.clear()
        if hasattr(self, "_completion"):
            owner, options = self._completion
            options["mapping"] = self.mapping
        return self

    def check(self, label, fact):
        """Assign a caller-supplied witness to one named Kernel obligation."""
        if isinstance(fact, Fact):
            self._visible(fact)
        self._assigned[label] = fact
        return fact

    def substitution(self, definitions, *, goals=()):
        """Rewrite affected model facts and caller/Kernel equality goals.

        One validated plan preserves the supplied pivot order across all facts
        and goals. Its sparse cancellation only elaborates selected equations;
        no equation, pivot, map, or combination is discovered.
        """
        # Preserve this convenience method's existing name/index alias
        # canonicalization: last equation wins at the first key's position.
        normalized = {self.model._index(pivot): fact for pivot, fact in definitions.items()}
        plan = _PivotPlan(self, normalized)
        def equality_goals():
            yield from goals
            for goal in self.missing():
                if goal.kind == "Eq":
                    yield goal.expression
        return self._substitution_plan(plan, equality_goals())

    def _opposing_maps(self):
        inverse = self.claim.get("inverse")
        inverse_map = None
        inverse_level = None
        if inverse is not None:
            if inverse >= len(self.session.claims):
                raise BuildError("Opposing inverse claim has not been declared")
            other = self.session.claims[inverse]
            inverse_map = other.mapping
            inverse_level = other.claim.get("input_objective_level")
            if inverse_map is None:
                raise BuildError("Declare the opposing complete map before planning inverse obligations")
        compositions = []
        for pair in self.session.bijections:
            if pair["claim"]["reverse_claim"] == self.index:
                forward = self.session.claims[pair["claim"]["forward_claim"]]
                if forward.mapping is None:
                    raise BuildError("A constructive bijection needs a declared root forward map")
                compositions.append(forward.mapping)
        return inverse_map, inverse_level, compositions

    def _plan_spec(self, values):
        inverse_map, inverse_level, compositions = self._opposing_maps()
        specification = {"claim": self.claim, "map": wire(values),
                         "inverse_map": wire(inverse_map), "inverse_level": inverse_level,
                         "compositions": wire(compositions)}
        if hasattr(self, "improvement_claim"):
            specification["improvement"] = {"claim": self.improvement_claim, "margin": self.margin}
        return specification

    def plan(self, *, scope=None, mapping=None):
        scope = self._scope(scope)
        values = _mapping(scope.model, self.output, mapping) if mapping is not None else self.mapping
        if values is None:
            raise BuildError("Declare the complete output map before planning obligations")
        inverse_map, inverse_level, compositions = self._opposing_maps()
        cache_key = (scope.model, tuple(values), None if inverse_map is None else tuple(inverse_map),
                     tuple(tuple(m) for m in compositions), json.dumps(self.claim, sort_keys=True), inverse_level,
                     json.dumps([self.improvement_claim, self.margin], sort_keys=True) if hasattr(self, "improvement_claim") else None)
        if cache_key in self._plans:
            return self._plans[cache_key]
        data = self.session.kernel.json_command("plan-return", [self.session._model_path(scope.model),
                    self.session._model_path(self.output)], self._plan_spec(values))
        result = [Obligation(i, item["kind"], Expr.from_json(item["expression"], intermediate=True), item["origin"])
                  for i, item in enumerate(data)]
        self._plans[cache_key] = result
        return result

    @property
    def obligations(self):
        return self.plan()

    def missing(self, *, scope=None, mapping=None, witnesses=None, auto=True):
        scope = self._scope(scope)
        values = _mapping(scope.model, self.output, mapping) if mapping is not None else self.mapping
        if values is None:
            raise BuildError("Declare the complete output map before planning obligations")
        result = self._resolve(scope, values, witnesses, auto)
        return [Obligation(o["index"], o["kind"], Expr.from_json(o["expression"], intermediate=True), o["origin"])
                for o in result["missing"]]

    def _resolve(self, scope, values, witnesses, auto):
        supplied = dict(self._assigned)
        supplied.update(witnesses or {})
        def typed(fact):
            scope._visible(fact)
            return {"kind": fact.kind, "expression": fact.expression.to_json(), "reference": fact.reference}
        facts = []
        if auto:
            for fact in scope._facts.values():
                try:
                    facts.append(typed(fact))
                except BuildError:
                    continue
            facts.extend(typed(fact) for fact in scope.assumptions)
        assignments = []
        for selector, fact in supplied.items():
            if isinstance(selector, bool) or not isinstance(selector, (int, str)):
                raise BuildError("An obligation selector must be an index or label")
            if not isinstance(fact, Fact) and fact != "Exact":
                raise BuildError(f"{selector}: expected a Fact or Exact terminal witness")
            assignments.append({"index" if isinstance(selector, int) else "label": selector,
                                "fact": typed(fact) if isinstance(fact, Fact) else "Exact"})
        try:
            return self.session.kernel.json_command("resolve-return", [self.session._model_path(scope.model),
                self.session._model_path(self.output)], {"plan": self._plan_spec(values), "facts": facts,
                                                       "assignments": assignments, "auto": auto})
        except KernelError as error:
            if error.report.get("status") == "INVALID":
                raise BuildError(str(error)) from error
            raise

    def complete(self, *, mapping=None, witnesses=None, scope=None, auto=True):
        """Fill mechanical checks from supplied witnesses, tautologies, and exact fact reuse."""
        scope = self._scope(scope)
        values = _mapping(scope.model, self.output, mapping) if mapping is not None else self.mapping
        if values is None:
            raise BuildError("Declare the complete map before complete()")
        result = self._resolve(scope, values, witnesses, auto)
        checks = result["checks"]
        missing = [Obligation(o["index"], o["kind"], Expr.from_json(o["expression"], intermediate=True), o["origin"])
                   for o in result["missing"]]
        if missing:
            details = "; ".join(f"{o.label}: {o.kind} {o.expression.summary()}" for o in missing[:8])
            raise BuildError(f"{len(missing)} undischarged obligations; {details}")
        if self.claim.get("inverse") is not None and scope is not self:
            raise BuildError("Affine inverse claims require root Return maps; use bijection/injectivity for constructive lifts")
        if scope is self:
            self.mapping = values
        scope._set_end({"Return": {"map": wire(values), "checks": checks}})
        if hasattr(self, "improvement_claim"):
            scope.end = {"ImproveReturn": {"map": wire(values), "checks": checks, "margin": self.margin}}
        scope._completion = (self, {"mapping": values, "witnesses": dict(witnesses or {}), "scope": scope, "auto": auto})
        scope._completed_state = self._completion_state(scope._completion[1])
        return scope

    return_ = complete


class InjectivityBuilder(Builder):
    """Fresh complete paired domain and Kernel-owned equality goals."""
    def __init__(self, model, goals, *, integers):
        super().__init__(model, integers=integers)
        self.goals = tuple(Expr.from_json(goal, intermediate=True) for goal in goals)
        self.checks = None

    def complete(self, witnesses=None, *, auto=True):
        witnesses = witnesses or {}
        if set(witnesses) - set(range(len(self.goals))):
            raise BuildError("Unknown injectivity coordinate witness")
        checks, missing = [], []
        for index, goal in enumerate(self.goals):
            fact = witnesses.get(index)
            if fact is None and auto:
                fact = self.find("Eq", goal)
            if fact is None:
                missing.append(index)
                continue
            if isinstance(fact, Fact):
                self._visible(fact)
                if fact.kind != "Eq" or fact.expression != goal:
                    raise BuildError(f"Injectivity coordinate {index} needs EQ {goal}")
            elif fact != "Exact" or self.find("Eq", goal) != "Exact":
                raise BuildError(f"Invalid injectivity witness {index}")
            checks.append(wire(fact))
        if missing:
            raise BuildError(f"Missing injectivity coordinates {missing[:10]} ({len(missing)} total)")
        self.checks = checks
        return self

    def to_json(self):
        if self.checks is None:
            raise BuildError("Complete every injectivity equality before adding the bijection")
        return {"steps": self.steps, "checks": self.checks}


class Proof:
    """A model pair with explicit directional contracts and user-authored derivations."""
    def __init__(self, source, target, *, kernel=None):
        self.kernel = kernel or (source.kernel if isinstance(source, Model) else None) or Kernel()
        self.source = source if isinstance(source, Model) else Model.load(source, kernel=self.kernel)
        self.target = target if isinstance(target, Model) else Model.load(target, kernel=self.kernel)
        self.source.kernel = self.target.kernel = self.kernel
        self.claims = []
        self.points = []
        self.improvements = []
        self.bijections = []
        self._improvement_builders = []
        self._model_cache = {}
        self._model_directory = None
        self._model_finalizer = None

    def _model_path(self, model):
        # Structural Models are immutable. Cache only files owned by this Proof,
        # never an externally writable source pathname.
        if model not in self._model_cache:
            if self._model_directory is None:
                self._model_directory = Path(tempfile.mkdtemp(prefix="kernel-model-cache-"))
                self._model_finalizer = weakref.finalize(self, shutil.rmtree, self._model_directory, True)
            path = self._model_directory / f"model-{len(self._model_cache)}.mcm"
            model.write_mcm(path)
            self._model_cache[model] = path
        return self._model_cache[model]

    def close(self):
        if self._model_directory is not None:
            self._model_finalizer()
            self._model_directory = None
            self._model_cache.clear()

    def claim(self, *, reverse=False, integers=True, input_integers=None, output_integers=None,
              objective="Equal", projection=(), affine_projection=(), inverse=None,
              input_objective_lower=None, input_objective_level=None, input_halfspace=None, mapping=None):
        inp, out = (self.target, self.source) if reverse else (self.source, self.target)
        if projection == "retained":
            projection = [(inp.var_index[v.name], j) for j, v in enumerate(out.vars) if v.name in inp.var_index]
        else:
            projection = [(inp.var_index[i] if isinstance(i, str) else i,
                           out.var_index[o] if isinstance(o, str) else o) for i, o in projection]
        if objective not in ("Equal", "NonIncreasing", "None"):
            raise BuildError("objective must be Equal, NonIncreasing, or None")
        contract = {"reverse": reverse, "input_integers": integers if input_integers is None else input_integers,
                    "output_integers": integers if output_integers is None else output_integers,
                    "objective": objective, "projection": projection, "inverse": inverse}
        if affine_projection:
            contract["affine_projection"] = wire(affine_projection)
        for key, value in [("input_objective_lower", input_objective_lower), ("input_objective_level", input_objective_level)]:
            if value is not None:
                contract[key] = str(exact(value))
        if input_halfspace is not None:
            contract["input_halfspace"] = Expr.coerce(input_halfspace).to_json()
        builder = ClaimBuilder(self, len(self.claims), contract, mapping)
        self.claims.append(builder)
        return builder

    def bijection(self, forward, reverse, *, integers=True, objective="Equal", projection="retained"):
        """Two complete affine maps with both inverse compositions requested."""
        if projection != "retained":
            projection = tuple(projection)
        index = len(self.claims)
        f = self.claim(integers=integers, objective=objective, projection=projection, inverse=index+1, mapping=forward)
        reversed_projection = [(out, inp) for inp, out in projection] if projection != "retained" else projection
        r = self.claim(reverse=True, integers=integers, objective=objective,
                       projection=reversed_projection, inverse=index, mapping=reverse)
        return f, r

    def correspondence(self, forward=None, reverse=None, *, integers=True, projection=(),
                       forward_objective="NonIncreasing", reverse_objective="Equal"):
        """Caller-declared total directions, with optional deferred complete maps.

        Supply branch/lift maps later through complete(scope=..., mapping=...).
        Observations and inverse identities remain separate contract choices.
        """
        if projection != "retained":
            projection = tuple(projection)
        f = self.claim(integers=integers, objective=forward_objective, projection=projection, mapping=forward)
        reversed_projection = [(out, inp) for inp, out in projection] if projection != "retained" else projection
        r = self.claim(reverse=True, integers=integers, objective=reverse_objective,
                       projection=reversed_projection, mapping=reverse)
        return f, r

    def feasible_point(self, values, *, target=False, integers=True, objective=None):
        model = self.target if target else self.source
        if isinstance(values, dict):
            if set(values) != set(model.var_index):
                raise BuildError("A point must specify every model variable")
            values = [values[v.name] for v in model.vars]
        if len(values) != len(model.vars):
            raise BuildError("A point must specify every model variable")
        claim = {"Feasible": {"target": target, "integers": integers,
                              "objective": None if objective is None else str(exact(objective))}}
        self.points.append({"claim": claim, "values": [str(exact(v)) for v in values]})
        return len(self.points)-1

    def add_point(self, claim, values, *, refutation=None):
        witness = {"claim": wire(claim), "values": [str(exact(v)) for v in values]}
        if refutation is not None:
            witness["refutation"] = refutation.to_json() if isinstance(refutation, Builder) else wire(refutation)
        self.points.append(witness)

    def add_improvement(self, claim, block):
        self.improvements.append({"claim": wire(claim), "block": block.to_json() if isinstance(block, Builder) else wire(block)})

    def add_bijection(self, forward_claim, reverse_claim, injectivity):
        if not (0 <= forward_claim < len(self.claims) and 0 <= reverse_claim < len(self.claims)):
            raise BuildError("Bijection indices must name declared directional claims")
        self.bijections.append({"claim": {"forward_claim": forward_claim, "reverse_claim": reverse_claim},
                                "injectivity": injectivity.to_json() if isinstance(injectivity, InjectivityBuilder) else wire(injectivity)})
        for claim in self.claims:
            claim._plans.clear()

    def injectivity(self, forward_claim):
        """Prepare the Kernel's complete double-input domain for a root affine map."""
        claim = self.claims[forward_claim] if isinstance(forward_claim, int) else forward_claim
        if claim not in self.claims or claim.mapping is None:
            raise BuildError("Injectivity requires this Proof's declared complete forward map")
        with tempfile.TemporaryDirectory(prefix="kernel-injectivity-") as directory:
            directory = Path(directory)
            inp, out = directory / "input.mcm", directory / "output.mcm"
            claim.input.write_mcm(inp)
            claim.output.write_mcm(out)
            prepared = self.kernel.json_command("prepare-injectivity", [inp, out], {"map": wire(claim.mapping)})
        builder = InjectivityBuilder(Model.from_json(prepared["model"], kernel=self.kernel), prepared["equalities"],
                                     integers=claim.claim["input_integers"])
        builder.preparation = prepared
        return builder

    def improvement(self, positive, *, target=False, integers=True, margin=None, mapping=None):
        """A caller-authored strictly improving map on a same-model positive domain."""
        if margin is None:
            margin = {"Predicate": "1"}
        lowered_margin = wire(margin)
        if set(lowered_margin) not in ({"Predicate"}, {"Constant"}):
            raise BuildError("Improvement margin is {'Predicate': q} or {'Constant': q}")
        value = exact(next(iter(lowered_margin.values())))
        if value <= 0:
            raise BuildError("Improvement margin must be positive")
        lowered_margin = {next(iter(lowered_margin)): str(value)}
        model = self.target if target else self.source
        local = Proof(model, model, kernel=self.kernel)
        builder = local.claim(integers=integers, objective="NonIncreasing", mapping=mapping)
        positive = builder._expression(positive)
        builder.improvement_claim = {"target": target, "integers": integers,
                                     "positive": positive.to_json()}
        builder.margin = lowered_margin
        # The verifier seeds exactly this weak consequence of the strict root
        # domain before executing any step or adding a branch assumption.
        assumption = Fact("Le", -positive, {"Assumption": 0}, builder)
        builder.assumptions = (assumption,)
        builder._remember(assumption)
        builder.domain.positive = assumption
        self._improvement_builders.append(builder)
        return builder

    def certificate(self):
        def refresh(scope):
            if hasattr(scope, "_completion"):
                owner, options = scope._completion
                if scope._completed_state != owner._completion_state(options):
                    owner.complete(**options)
            for child in scope._children or ():
                refresh(child)
        for claim in [*self.claims, *self._improvement_builders]:
            refresh(claim)
        return {"claims": [wire(c.claim) for c in self.claims], "blocks": [c.to_json() for c in self.claims],
                "points": self.points, "improvements": [*self.improvements,
                    *({"claim": c.improvement_claim, "block": c.to_json()} for c in self._improvement_builders)],
                "bijections": self.bijections}

    def request(self):
        """The complete caller-declared contract; verification cannot silently omit a claim."""
        return {"claims": [wire(c.claim) for c in self.claims], "points": [p["claim"] for p in self.points],
                "improvements": [*(i["claim"] for i in self.improvements), *(c.improvement_claim for c in self._improvement_builders)],
                "bijections": [b["claim"] for b in self.bijections]}

    def contract_summary(self, *, max_items=8):
        """Bounded caller-declared scope; no completion, planning, or map copy."""
        request = {"claims": [c.claim for c in self.claims], "points": [p["claim"] for p in self.points],
                   "improvements": [*(i["claim"] for i in self.improvements),
                                    *(c.improvement_claim for c in self._improvement_builders)],
                   "bijections": [b["claim"] for b in self.bijections]}
        return summarize_request(self.source, self.target, request, max_items=max_items)

    def preflight(self):
        cert = self.certificate()
        def depth(value):
            children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
            return 1 + max((depth(c) for c in children), default=0)
        def tally(value):
            total = {"steps": 0, "checks": 0, "maps": 0, "linear_premises": 0}
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ("steps", "checks", "map"):
                        total[{"steps":"steps", "checks":"checks", "map":"maps"}[key]] += len(item)
                    if key == "Lin":
                        total["linear_premises"] += len(item["terms"])
                    part = tally(item)
                    for name in total:
                        total[name] += part[name]
            elif isinstance(value, list):
                for item in value:
                    part = tally(item)
                    for name in total:
                        total[name] += part[name]
            return total
        return {"certificate_json_bytes": len(json.dumps(cert, separators=(",", ":")).encode()),
                "json_depth": depth(cert), **tally(cert), "claims": len(self.claims),
                "note": "Size counts are exact; Kernel verification reports actual work and peak live facts."}

    def compile(self, directory, *, committed_model=None):
        return compile_certificate(self.source, self.target, self.certificate(), self.request(), directory,
                                   kernel=self.kernel, committed_model=committed_model)

    def verify(self, directory, *, committed_model=None, work=None, live_facts=None):
        artifacts = self.compile(directory, committed_model=committed_model)
        directory = artifacts["proof"].parent
        report = self.kernel.verify(artifacts["source"], artifacts["target"], artifacts["proof"],
                                    artifacts["request"], work=work, live_facts=live_facts)
        delivery = json.loads((directory / "delivery.json").read_text())
        report["artifacts"] = delivery["artifacts"]
        report["request_summary"] = delivery["request_summary"]
        if "artifact_binding" in delivery:
            report["artifact_audit"] = delivery["artifact_binding"]
        _atomic_text(directory / "verification.json", json.dumps(report, indent=2) + "\n")
        return report


def compile_certificate(source, target, certificate, request, directory, *, kernel=None, committed_model=None):
    """Raw frozen Certificate escape hatch: every existing rule remains expressible."""
    kernel = kernel or (source.kernel if isinstance(source, Model) else None) or Kernel()
    source = source if isinstance(source, Model) else Model.load(source, kernel=kernel)
    target = target if isinstance(target, Model) else Model.load(target, kernel=kernel)
    directory = Path(directory).resolve()
    paths = {"source": directory / "source.mcm", "target": directory / "target.mcm",
             "proof": directory / "proof.rpx", "request": directory / "request.json"}
    if committed_model is not None:
        committed_model = Path(committed_model).resolve()
        reserved = [*paths.values(), *(directory / name for name in
                    ("certificate.json", "delivery.json", "verification.json"))]
        for output in reserved:
            if output.resolve() == committed_model or (output.exists() and committed_model.exists()
                                                       and output.samefile(committed_model)):
                raise BuildError("Committed solver artifact aliases a generated proof file; choose a separate artifact path")
        delivered = Model.load(committed_model, kernel=kernel)
        if not target.same_formulation(delivered):
            raise BuildError("Committed solver artifact differs from the complete proof target")
    directory.mkdir(parents=True, exist_ok=True)
    _atomic_write(paths["source"], source.write_mcm)
    _atomic_write(paths["target"], target.write_mcm)
    cert_path = directory / "certificate.json"
    _atomic_text(cert_path, json.dumps(certificate, cls=_ProofJSONEncoder, separators=(",", ":")) + "\n")
    _atomic_text(paths["request"], json.dumps(request, cls=_ProofJSONEncoder, separators=(",", ":")) + "\n")
    compile_report = None

    def write_proof(temporary):
        nonlocal compile_report
        arguments = ["compile"]
        budget = getattr(kernel, "compile_json_bytes", None)
        if budget is not None:
            arguments += ["--max-json-bytes", budget]
        compile_report = kernel.call(*arguments, cert_path, temporary)

    _atomic_write(paths["proof"], write_proof)
    try:
        summary = summarize_request(source, target, request)
    except (IndexError, KeyError, TypeError, ValueError, AttributeError, StopIteration) as error:
        # Optional metadata must not replace Kernel's native invalid-Request
        # feedback, including future/raw Request fields unknown to Python.
        summary = {"status": "UNAVAILABLE", "reason": str(error)[:256],
                   "note": "Kernel still verifies the complete Request; no scope is inferred."}
    manifest = {"format": "kernel-compiler-delivery-1", "relation": "caller-declared Kernel request",
                "request_summary": summary,
                "pieces": [{key: str(value) for key, value in paths.items()}],
                "artifacts": {key: {"path": str(value), "sha256": _digest(value)} for key, value in paths.items()}}
    if isinstance(compile_report, dict) and "compile_limits" in compile_report:
        # Other compile-report fields can contain the atomic temporary path.
        # The manifest binds the final proof path and only records its budget.
        manifest["compile_limits"] = compile_report["compile_limits"]
    if committed_model is not None:
        manifest["committed_model"] = str(committed_model)
        manifest["artifacts"]["committed_model"] = {"path": str(committed_model), "sha256": _digest(committed_model)}
        manifest["artifact_binding"] = {
            "status": "MATCHED",
            "method": _artifact_binding_method(_model_reader_family(committed_model)),
            "scope": "Every named variable, bound, integrality declaration, row, and objective; model NAME and coordinate order may differ",
            "committed_model": manifest["artifacts"]["committed_model"],
            "proof_target": manifest["artifacts"]["target"],
        }
    _atomic_text(directory / "delivery.json", json.dumps(manifest, indent=2) + "\n")
    return paths


def verify_bundle(manifest, *, kernel=None):
    """Verify every caller-bound part; failure in any part keeps the bundle incomplete."""
    kernel = kernel or Kernel()
    path = Path(manifest).resolve()
    document = json.loads(path.read_text())
    if isinstance(document.get("composition"), dict) and document["composition"].get("ordered_chain") is True:
        from .bundle import verify_ordered_chain
        return verify_ordered_chain(document, path, kernel=kernel)
    reports = []
    for name, record in document.get("artifacts", {}).items():
        artifact = (path.parent / record["path"]).resolve()
        if _digest(artifact) != record["sha256"]:
            return {"status": "INCOMPLETE", "parts": [], "error": f"Artifact digest mismatch: {name}"}
    for piece in document["pieces"]:
        paths = {key: (path.parent / piece[key]).resolve() for key in ("source", "target", "proof", "request")}
        if document.get("committed_model"):
            target = Model.load(paths["target"], kernel=kernel)
            committed = Model.load((path.parent / document["committed_model"]).resolve(), kernel=kernel)
            if not target.same_formulation(committed):
                return {"status": "INCOMPLETE", "parts": reports,
                        "error": "Committed solver artifact differs from a proof target"}
        reports.append(kernel.verify(paths["source"], paths["target"], paths["proof"], paths["request"]))
    return {"status": "VERIFIED" if reports and all(r["status"] == "VERIFIED" for r in reports) else "INCOMPLETE", "parts": reports}
