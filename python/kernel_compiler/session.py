"""Caller-bound contracts, Kernel obligation plans, and direct RPX compilation."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile

from .backend import Kernel
from .expr import Expr, exact
from .model import Model
from .proof import Builder, BuildError, Fact, wire


def _digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        if claim.get("input_objective_level") is not None or claim.get("input_halfspace") is not None:
            with tempfile.TemporaryDirectory(prefix="kernel-domain-") as directory:
                path = Path(directory) / "input.mcm"
                model.write_mcm(path)
                prepared = session.kernel.json_command("prepare-extension", [path], {"Restricted": {
                    "level": claim.get("input_objective_level"), "halfspace": claim.get("input_halfspace")}})
            model = Model.from_json(prepared["model"], kernel=session.kernel)
        super().__init__(model, integers=claim["input_integers"])
        self._assigned = {}
        self._plans = {}

    def map(self, mapping):
        self.mapping = _mapping(self.input, self.output, mapping)
        self._plans.clear()
        return self

    def check(self, label, fact):
        """Assign a caller-supplied witness to one named Kernel obligation."""
        if isinstance(fact, Fact):
            self._visible(fact)
        self._assigned[label] = fact
        return fact

    def plan(self, *, scope=None, mapping=None):
        scope = scope or self
        values = _mapping(scope.model, self.output, mapping) if mapping is not None else self.mapping
        if values is None:
            raise BuildError("Declare the complete output map before planning obligations")
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
        specification = {"claim": self.claim, "map": wire(values),
                         "inverse_map": wire(inverse_map), "inverse_level": inverse_level,
                         "compositions": []}
        cache_key = (id(scope.model), tuple(values), None if inverse_map is None else tuple(inverse_map),
                     json.dumps(specification["claim"], sort_keys=True), inverse_level)
        if cache_key in self._plans:
            return self._plans[cache_key]
        with tempfile.TemporaryDirectory(prefix="kernel-plan-") as directory:
            directory = Path(directory)
            inp, out = directory / "input.mcm", directory / "output.mcm"
            scope.model.write_mcm(inp)
            self.output.write_mcm(out)
            data = self.session.kernel.json_command("plan-return", [inp, out], specification)
        result = [Obligation(i, item["kind"], Expr.from_json(item["expression"]), item["origin"])
                  for i, item in enumerate(data)]
        self._plans[cache_key] = result
        return result

    @property
    def obligations(self):
        return self.plan()

    def missing(self, *, scope=None, mapping=None, witnesses=None, auto=True):
        scope = scope or self
        supplied = dict(self._assigned)
        supplied.update(witnesses or {})
        return [o for o in self.plan(scope=scope, mapping=mapping)
                if o.label not in supplied and o.index not in supplied
                and (not auto or scope.find(o.kind, o.expression) is None)]

    def complete(self, *, mapping=None, witnesses=None, scope=None, auto=True):
        """Fill mechanical checks from supplied witnesses, tautologies, and exact fact reuse."""
        scope = scope or self
        values = _mapping(scope.model, self.output, mapping) if mapping is not None else self.mapping
        if values is None:
            raise BuildError("Declare the complete map before complete()")
        obligations = self.plan(scope=scope, mapping=values)
        supplied = dict(self._assigned)
        supplied.update(witnesses or {})
        valid_keys = {o.label for o in obligations} | {o.index for o in obligations}
        extra = set(supplied) - valid_keys
        if extra:
            raise BuildError(f"Unknown obligation labels: {sorted(map(str, extra))[:10]}")
        checks, missing = [], []
        for obligation in obligations:
            fact = supplied.get(obligation.label, supplied.get(obligation.index))
            if fact is None and auto:
                fact = scope.find(obligation.kind, obligation.expression)
            if fact is None:
                missing.append(obligation)
                continue
            if isinstance(fact, Fact):
                scope._visible(fact)
                if fact.expression != obligation.expression or (fact.kind != obligation.kind and fact.kind != "Eq"):
                    raise BuildError(f"{obligation.label}: supplied fact disagrees with Kernel goal {obligation.kind} {obligation.expression}")
            elif fact != "Exact":
                raise BuildError(f"{obligation.label}: expected a Fact or Exact terminal witness")
            elif scope.find(obligation.kind, obligation.expression) != "Exact":
                raise BuildError(f"{obligation.label}: Exact cannot discharge this nontrivial goal")
            checks.append(wire(fact))
        if missing:
            details = "; ".join(f"{o.label}: {o.kind} {o.expression}" for o in missing[:8])
            raise BuildError(f"{len(missing)} undischarged obligations; {details}")
        if self.claim.get("inverse") is not None and scope is not self:
            raise BuildError("Affine inverse claims require root Return maps; use bijection/injectivity for constructive lifts")
        if scope is self:
            self.mapping = values
        scope.end = {"Return": {"map": wire(values), "checks": checks}}
        return scope

    return_ = complete


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
        index = len(self.claims)
        f = self.claim(integers=integers, objective=objective, projection=projection, inverse=index+1, mapping=forward)
        r = self.claim(reverse=True, integers=integers, objective=objective, projection=projection, inverse=index, mapping=reverse)
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
        self.bijections.append({"claim": {"forward_claim": forward_claim, "reverse_claim": reverse_claim},
                                "injectivity": wire(injectivity)})

    def certificate(self):
        return {"claims": [wire(c.claim) for c in self.claims], "blocks": [c.to_json() for c in self.claims],
                "points": self.points, "improvements": self.improvements, "bijections": self.bijections}

    def request(self):
        """The complete caller-declared contract; verification cannot silently omit a claim."""
        return {"claims": [wire(c.claim) for c in self.claims], "points": [p["claim"] for p in self.points],
                "improvements": [i["claim"] for i in self.improvements], "bijections": [b["claim"] for b in self.bijections]}

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
        report = self.kernel.verify(artifacts["source"], artifacts["target"], artifacts["proof"],
                                    artifacts["request"], work=work, live_facts=live_facts)
        (Path(directory) / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        return report


def compile_certificate(source, target, certificate, request, directory, *, kernel=None, committed_model=None):
    """Raw frozen Certificate escape hatch: every existing rule remains expressible."""
    kernel = kernel or (source.kernel if isinstance(source, Model) else None) or Kernel()
    source = source if isinstance(source, Model) else Model.load(source, kernel=kernel)
    target = target if isinstance(target, Model) else Model.load(target, kernel=kernel)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    paths = {"source": directory / "source.mcm", "target": directory / "target.mcm",
             "proof": directory / "proof.rpx", "request": directory / "request.json"}
    source.write_mcm(paths["source"])
    target.write_mcm(paths["target"])
    cert_path = directory / "certificate.json"
    cert_path.write_text(json.dumps(wire(certificate), separators=(",", ":")) + "\n")
    paths["request"].write_text(json.dumps(wire(request), separators=(",", ":")) + "\n")
    kernel.call("compile", cert_path, paths["proof"])
    manifest = {"format": "kernel-compiler-delivery-1", "relation": "caller-declared Kernel request",
                "pieces": [{key: str(value) for key, value in paths.items()}],
                "artifacts": {key: {"path": str(value), "sha256": _digest(value)} for key, value in paths.items()}}
    if committed_model is not None:
        manifest["committed_model"] = str(Path(committed_model).resolve())
    (directory / "delivery.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return paths


def verify_bundle(manifest, *, kernel=None):
    """Verify every caller-bound part; failure in any part keeps the bundle incomplete."""
    kernel = kernel or Kernel()
    path = Path(manifest).resolve()
    document = json.loads(path.read_text())
    reports = []
    for piece in document["pieces"]:
        paths = {key: (path.parent / piece[key]).resolve() for key in ("source", "target", "proof", "request")}
        reports.append(kernel.verify(paths["source"], paths["target"], paths["proof"], paths["request"]))
    return {"status": "VERIFIED" if reports and all(r["status"] == "VERIFIED" for r in reports) else "INCOMPLETE", "parts": reports}
