"""Fixed optimization equivalence, Kernel obligation plans, and direct RPX compilation."""
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


class DirectionBuilder(Builder):
    def __init__(self, session, reverse):
        self.session = session
        self.input = session.target if reverse else session.source
        self.output = session.source if reverse else session.target
        self.mapping = None
        super().__init__(self.input)
        self._assigned = {}
        self._plans = {}

    def _scope(self, scope):
        scope = self if scope is None else scope
        current = scope
        while current is not None and current is not self:
            current = current.parent
        if current is None:
            raise BuildError("Return scope must descend from this direction")
        return scope

    def _completion_state(self, options):
        scope = options["scope"]
        chain = []
        while scope is not None:
            chain.append((scope, scope._revision))
            scope = scope.parent
        supplied = dict(self._assigned)
        supplied.update(options.get("witnesses") or {})
        witnesses = tuple(((type(k).__name__, k), f.kind, f.expression, json.dumps(f.reference, sort_keys=True))
                          if isinstance(f, Fact) else ((type(k).__name__, k), f)
                          for k, f in sorted(supplied.items(), key=lambda kv: (type(kv[0]).__name__, str(kv[0]))))
        return (tuple(chain), tuple(options["mapping"]), witnesses, options["auto"])

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
                if goal.kind == "Eq" or goal.origin["kind"] == "objective.non_increasing":
                    yield goal.expression
        return self._substitution_plan(plan, equality_goals())

    def _plan_spec(self, values):
        return {"map": wire(values)}

    def plan(self, *, scope=None, mapping=None):
        scope = self._scope(scope)
        values = _mapping(scope.model, self.output, mapping) if mapping is not None else self.mapping
        if values is None:
            raise BuildError("Declare the complete output map before planning obligations")
        cache_key = (scope.model, tuple(values))
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
        if scope is self:
            self.mapping = values
        scope._set_end({"Return": {"map": wire(values), "checks": checks}})
        scope._completion = (self, {"mapping": values, "witnesses": dict(witnesses or {}), "scope": scope, "auto": auto})
        scope._completed_state = self._completion_state(scope._completion[1])
        return scope

    return_ = complete


class Proof:
    """Two complete directional proof trees for MI optimization equivalence."""
    def __init__(self, source, target, *, kernel=None):
        self.kernel = kernel or (source.kernel if isinstance(source, Model) else None) or Kernel()
        self.source = source if isinstance(source, Model) else Model.load(source, kernel=self.kernel)
        self.target = target if isinstance(target, Model) else Model.load(target, kernel=self.kernel)
        self.source.kernel = self.target.kernel = self.kernel
        self.forward = DirectionBuilder(self, False)
        self.reverse = DirectionBuilder(self, True)
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

    def certificate(self):
        def refresh(scope):
            if hasattr(scope, "_completion"):
                owner, options = scope._completion
                if scope._completed_state != owner._completion_state(options):
                    owner.complete(**options)
            for child in scope._children or ():
                refresh(child)
        for direction in (self.forward, self.reverse):
            refresh(direction)
        return {"forward": self.forward.to_json(), "reverse": self.reverse.to_json()}

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
                "json_depth": depth(cert), **tally(cert), "directions": 2,
                "note": "Size counts are exact; Kernel verification reports actual work and peak live facts."}

    def compile(self, directory, *, committed_model=None):
        return compile_certificate(self.source, self.target, self.certificate(), directory,
                                   kernel=self.kernel, committed_model=committed_model)

    def verify(self, directory, *, committed_model=None, work=None, live_facts=None):
        artifacts = self.compile(directory, committed_model=committed_model)
        directory = artifacts["proof"].parent
        report = self.kernel.verify(artifacts["source"], artifacts["target"], artifacts["proof"], work=work, live_facts=live_facts)
        delivery = json.loads((directory / "delivery.json").read_text())
        report["artifacts"] = delivery["artifacts"]
        if "artifact_binding" in delivery:
            report["artifact_audit"] = delivery["artifact_binding"]
        _atomic_text(directory / "verification.json", json.dumps(report, indent=2) + "\n")
        return report


def compile_certificate(source, target, certificate, directory, *, kernel=None, committed_model=None):
    """Compile an explicit forward/reverse certificate without proof search."""
    kernel = kernel or (source.kernel if isinstance(source, Model) else None) or Kernel()
    source = source if isinstance(source, Model) else Model.load(source, kernel=kernel)
    target = target if isinstance(target, Model) else Model.load(target, kernel=kernel)
    directory = Path(directory).resolve()
    paths = {"source": directory / "source.mcm", "target": directory / "target.mcm",
             "proof": directory / "proof.rpx"}
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
    compile_report = None

    def write_proof(temporary):
        nonlocal compile_report
        arguments = ["compile"]
        budget = getattr(kernel, "compile_json_bytes", None)
        if budget is not None:
            arguments += ["--max-json-bytes", budget]
        compile_report = kernel.call(*arguments, cert_path, temporary)

    _atomic_write(paths["proof"], write_proof)
    manifest = {"format": "kernel-compiler-delivery-1",
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
    """Certify the complete same-model proof collection, or every ordered stage."""
    kernel = kernel or Kernel()
    path = Path(manifest).resolve()
    try:
        document = json.loads(path.read_text())
        if isinstance(document.get("composition"), dict) and document["composition"].get("ordered_chain") is True:
            from .bundle import verify_ordered_chain
            return verify_ordered_chain(document, path, kernel=kernel)
        for name, record in document.get("artifacts", {}).items():
            artifact = (path.parent / record["path"]).resolve()
            if _digest(artifact) != record["sha256"]:
                raise BuildError(f"Artifact digest mismatch: {name}")
        pieces = document["pieces"]
        if len(pieces) != 1:
            raise BuildError("A model pair requires one complete certificate")
        first = {key: (path.parent / pieces[0][key]).resolve() for key in ("source", "target", "proof")}
        if document.get("committed_model"):
            with Model.load(first["target"], kernel=kernel) as target, Model.load((path.parent / document["committed_model"]).resolve(), kernel=kernel) as committed:
                if not target.same_formulation(committed):
                    raise BuildError("Committed solver artifact differs from the proof target")
        report = kernel.verify(first["source"], first["target"], first["proof"])
        return {"status": report["status"], "parts": [report], "guarantee": "MI_OPT" if report["status"] == "VERIFIED" else None}
    except (BuildError, ValueError, KeyError, TypeError, OSError, KernelError) as error:
        return {"status": "INCOMPLETE", "parts": [], "error": str(error)}
