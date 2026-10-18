"""A small control plane over the sole native proof state."""

from . import _native
from .artifacts import publish_proof


class Proof:
    __slots__ = ("_native", "_source", "_target")

    def __init__(self, source, target):
        self._source = (
            source if isinstance(source, _native.Model) else _native.Model.read(source)
        )
        self._target = (
            target if isinstance(target, _native.Model) else _native.Model.read(target)
        )
        self._native = _native.Proof(self.source, self.target)

    @property
    def source(self):
        return self._source

    @property
    def target(self):
        return self._target

    @property
    def forward(self):
        return self._native.forward

    @property
    def reverse(self):
        return self._native.reverse

    def preflight(self):
        return self._native.preflight()

    def certificate(self):
        return self._native.certificate()

    def compile(self, directory, *, target_artifact=None):
        return publish_proof(self, directory, target_artifact=target_artifact)

    def verify(self, directory, *, target_artifact=None, **limits):
        return self.compile(directory, target_artifact=target_artifact).verify(**limits)


class StandardMPSAdapter:
    __slots__ = ("_native",)

    def __init__(
        self, source, *, objective_auxiliary=True, objective_name="__mps_objective"
    ):
        self._native = _native.StandardMPSAdapter(
            source,
            objective_auxiliary=objective_auxiliary,
            objective_name=objective_name,
        )

    @property
    def source(self):
        return self._native.source

    @property
    def target(self):
        return self._native.target

    @property
    def report(self):
        return self._native.report

    def proof(self):
        result = object.__new__(Proof)
        result._source, result._target = self.source, self.target
        result._native = self._native.native_proof()
        return result
