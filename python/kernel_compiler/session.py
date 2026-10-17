"""Fixed optimization equivalence, Kernel obligation plans, and RPX delivery."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import weakref
from types import SimpleNamespace

from . import _native
from .backend import Kernel, KernelError
from .expr import Expr, exact, _rational_text
from .model import Model
from .proof import Builder, BuildError, Fact, _mapping, wire


def _digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_reader_family(path):
    path = Path(path).resolve()
    if path.suffix.lower() == ".json":
        return "python_canonical_json"
    with path.open("rb") as stream:
        if stream.read(4) == b"MCM\0":
            return "kernel_mcm"
    return "kernel_lp" if path.suffix.lower() == ".lp" else "kernel_mps"


def _artifact_binding_method(reader):
    if reader == "python_canonical_json":
        return "Python canonical JSON readback and exact named formulation comparison"
    return "Kernel standard-format readback and exact named formulation comparison"


def _atomic_write(path, writer):
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


class DirectionBuilder(Builder):
    def __init__(self, session, reverse):
        self.session = session
        self.reverse = reverse
        self._native = session._native.reverse if reverse else session._native.forward
        self._children = None
        self._indexed = False
        self._facts = __import__("collections").ChainMap({})
        self._base = {}
        self._assigned = {}
        self._completion = None
        self._fact_cache = {}
        self.mapping = None

    @property
    def input(self):
        return self.session.target if self.reverse else self.session.source

    @property
    def output(self):
        return self.session.source if self.reverse else self.session.target

    @property
    def model(self):
        return self.input

    def _scope(self, scope):
        if scope is None:
            return self
        if isinstance(scope, _native.Builder):
            if not scope.descends_from(self._native):
                raise BuildError("Return scope must descend from this direction")
            return scope
        if hasattr(scope, "_native") and not isinstance(scope, _native.Builder):
            if not scope._native.descends_from(self._native):
                raise BuildError("Return scope must descend from this direction")
            return scope
        raise BuildError("Return scope must descend from this direction")

    def _completion_state(self, options):
        scope = options["scope"]
        chain = []
        current = scope._native
        while current is not None:
            chain.append((current.scope_id, current.revision))
            current = current.parent
        supplied = dict(self._assigned)
        supplied.update(options.get("witnesses") or {})
        witnesses = tuple((type(k).__name__, k, v.reference if isinstance(v, Fact) else v)
                          for k, v in sorted(supplied.items(), key=lambda kv: (type(kv[0]).__name__, str(kv[0]))))
        mapping = options.get("mapping")
        mapping_key = ("identity",) if mapping is None else tuple(mapping)
        return (tuple(chain), mapping_key, witnesses, options["auto"])

    def map(self, mapping):
        if mapping is None or mapping == "identity":
            self.mapping = "identity"
            self._native.map_identity()
        else:
            self.mapping = _mapping(self.input, self.output, mapping)
            self._native.map(self.mapping)
        if self._completion is not None:
            owner, options = self._completion
            options["mapping"] = self.mapping
            self._completed_state = None
        return self

    def check(self, label, fact):
        if isinstance(fact, Fact):
            self._visible(fact)
        self._native.check(label, fact)
        self._assigned[label] = fact
        if self._completion is not None:
            self._completed_state = None
        return fact

    def plan(self, *, scope=None, mapping=None):
        scope = self._scope(scope)
        values = _mapping(self.input, self.output, mapping) if mapping is not None else (None if self.mapping == "identity" else self.mapping)
        if values is None and self.mapping is None:
            raise BuildError("Declare the complete output map before planning obligations")
        try:
            data = self._native.plan(scope._native, values)
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None
        return [Obligation(item["index"], item["kind"], item["expression"], item["origin"]) for item in data]

    @property
    def obligations(self):
        return self.plan()

    def missing(self, *, scope=None, mapping=None, witnesses=None, auto=True):
        scope = self._scope(scope)
        values = _mapping(self.input, self.output, mapping) if mapping is not None else (None if self.mapping == "identity" else self.mapping)
        if values is None and self.mapping is None:
            raise BuildError("Declare the complete output map before planning obligations")
        try:
            data = self._native.missing(scope._native, values, witnesses, auto)
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None
        return [Obligation(item["index"], item["kind"], item["expression"], item["origin"]) for item in data]

    def complete(self, *, mapping=None, witnesses=None, scope=None, auto=True):
        scope = self._scope(scope)
        values = _mapping(self.input, self.output, mapping) if mapping is not None else (None if self.mapping == "identity" else self.mapping)
        if values is None and self.mapping is None:
            raise BuildError("Declare the complete map before complete()")
        raw_scope = scope._native if hasattr(scope, "_native") else scope
        try:
            self._native.clear_assignments()
            for selector, fact in self._assigned.items():
                self._native.check(selector, fact)
            self._native.complete(values, witnesses, raw_scope, auto)
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None
        if scope is self:
            if values is not None:
                self.mapping = values
            self._children = None
        if not isinstance(scope, _native.Builder):
            options = {"mapping": values, "witnesses": dict(witnesses or {}), "scope": scope, "auto": auto}
            scope._completion = (self, options)
            scope._completed_state = self._completion_state(options)
        return scope

    return_ = complete

    def complete_ordered(self, mapping, checks, *, scope=None, auto=True):
        scope = self._scope(scope)
        values = _mapping(self.input, self.output, mapping)
        raw_scope = scope._native if hasattr(scope, "_native") else scope
        try:
            self._native.complete_ordered(values, list(checks), raw_scope, auto)
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None
        if scope is self:
            self.mapping = values
            self._children = None
        return scope

    def substitution(self, definitions, *, goals=()):
        normalized = {self.model._index(pivot): fact for pivot, fact in definitions.items()}
        equality_goals = list(goals)
        for goal in self.missing():
            if goal.kind == "Eq" or goal.origin["kind"] == "objective.non_increasing":
                equality_goals.append(goal.expression)
        try:
            result = self._native.substitution(normalized, equality_goals)
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None
        for fact in result:
            self._facts.maps[0][fact.reference["Local"]] = fact
        return result


class Proof:
    """Two complete directional proof trees for MI optimization equivalence."""

    def __init__(self, source, target, *, kernel=None):
        self.kernel = kernel or (source.kernel if isinstance(source, Model) else None) or Kernel()
        self.source = source if isinstance(source, Model) else Model.load(source, kernel=self.kernel)
        self.target = target if isinstance(target, Model) else Model.load(target, kernel=self.kernel)
        self.source.kernel = self.target.kernel = self.kernel
        self._native = __import__("kernel_compiler._native", fromlist=["Proof"]).Proof(
            self.source._native, self.target._native)
        self.forward = DirectionBuilder(self, False)
        self.reverse = DirectionBuilder(self, True)

    def close(self):
        pass

    def _refresh(self, scope):
        if scope._completion is not None:
            owner, options = scope._completion
            if scope._completed_state != owner._completion_state(options):
                owner.complete(**options)
        for child in scope._children or ():
            self._refresh(child)

    def certificate(self):
        self._refresh(self.forward)
        self._refresh(self.reverse)
        try:
            return wire(self._native.certificate())
        except (ValueError, TypeError) as error:
            raise BuildError(str(error)) from None

    def preflight(self):
        return self._native.preflight()

    def compile(self, directory, *, committed_model=None):
        directory = Path(directory).resolve()
        paths = {"source": directory / "source.mcm", "target": directory / "target.mcm",
                 "rpa": directory / "proof.rpa", "proof": directory / "proof.rpx"}
        if committed_model is not None:
            committed_model = Path(committed_model).resolve()
            reserved = [*paths.values(), directory / "delivery.json", directory / "verification.json"]
            for output in reserved:
                if output.resolve() == committed_model or (output.exists() and committed_model.exists()
                                                           and output.samefile(committed_model)):
                    raise BuildError("Committed solver artifact aliases a generated proof file; choose a separate artifact path")
            delivered = Model.load(committed_model, kernel=self.kernel)
            if not self.target.same_formulation(delivered):
                raise BuildError("Committed solver artifact differs from the complete proof target")
        directory.mkdir(parents=True, exist_ok=True)
        compiled = self._native.compile()
        _atomic_write(paths["source"], self.source.write_mcm)
        _atomic_write(paths["target"], self.target.write_mcm)
        _atomic_text(paths["rpa"], compiled.rpa)
        _atomic_write(paths["proof"], lambda temporary: temporary.write_bytes(compiled.rpx))
        manifest = {"format": "kernel-compiler-delivery-1",
                    "pieces": [{key: str(value) for key, value in paths.items()}],
                    "artifacts": {key: {"path": str(value), "sha256": _digest(value)} for key, value in paths.items()}}
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

    def verify(self, directory, *, committed_model=None, work=None, live_facts=None):
        artifacts = self.compile(directory, committed_model=committed_model)
        directory = artifacts["proof"].parent
        report = self.kernel.verify(artifacts["source"], artifacts["target"], artifacts["proof"],
                                    work=work, live_facts=live_facts)
        delivery = json.loads((directory / "delivery.json").read_text())
        report["artifacts"] = delivery["artifacts"]
        if "artifact_binding" in delivery:
            report["artifact_audit"] = delivery["artifact_binding"]
        _atomic_text(directory / "verification.json", json.dumps(report, indent=2) + "\n")
        return report


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
