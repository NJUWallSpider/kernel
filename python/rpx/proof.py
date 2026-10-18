"""A small control plane over the sole native proof state."""

from . import _native
from .artifacts import publish_proof


class Proof:
    """Own the forward and reverse scopes for an explicit MI_OPT proof. source and target accept Model objects or model paths. Complete every leaf in both directions before compiling. Compilation writes one native certificate as RPA and RPX; only a successful fresh Kernel verification certifies the result. Example: Proof(source, target)."""

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
        """The source Model.

        ## Example
        proof.source
        """
        return self._source

    @property
    def target(self):
        """The target Model.

        ## Example
        proof.target
        """
        return self._target

    @property
    def forward(self):
        """The source-to-target root Scope.

        ## Example
        proof.forward
        """
        return self._native.forward

    @property
    def reverse(self):
        """The target-to-source root Scope.

        ## Example
        proof.reverse
        """
        return self._native.reverse

    def preflight(self):
        """Return exact compiled sizes from the immutable native snapshot after both directions finish. Reuses lowering with compile; not certification.

        ## Returns
        dict[str, int]

        ## Example
        proof.preflight()
        """
        return self._native.preflight()

    def certificate(self):
        """Return a native CertificateView for inspection of the proof; completed proofs are required when materializing certificate data.

        ## Returns
        CertificateView

        ## Example
        proof.certificate()
        """
        return self._native.certificate()

    def compile(self, directory, *, target_artifact=None):
        """Publish a self-contained Bundle to directory from a single native certificate snapshot. Both directions must be complete. target_artifact, if supplied, is copied byte-for-byte and audited. Different existing contents or aliases are rejected with ArtifactMismatchError. No Kernel certification is implied.

        ## Parameters
        directory: Path
        target_artifact: Path | None

        ## Returns
        Bundle

        ## Example
        proof.compile("build/bundle")
        """
        return publish_proof(self, directory, target_artifact=target_artifact)

    def verify(self, directory, *, target_artifact=None, **limits):
        """Compile to directory then run Bundle.verify with the supplied work/live_facts/depth budgets. Return VerificationReport; call raise_for_status to require VERIFIED. target_artifact is copied and audited.

        ## Parameters
        directory: Path
        target_artifact: Path | None
        work: int | None
        live_facts: int | None
        depth: int | None

        ## Returns
        VerificationReport

        ## Example
        proof.verify("build/bundle").raise_for_status()
        """
        return self.compile(directory, target_artifact=target_artifact).verify(**limits)


class StandardMPSAdapter:
    """Prepare a standard-MPS-compatible model and explicit equivalence proof from source. objective_auxiliary controls an auxiliary objective variable; objective_name names it. Inspect report for transformations, then verify proof(). Example: adapter = StandardMPSAdapter(model)."""

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
        """The source Model.

        ## Example
        adapter.source
        """
        return self._native.source

    @property
    def target(self):
        """The target Model.

        ## Example
        adapter.target
        """
        return self._native.target

    @property
    def report(self):
        """A dictionary describing the adapter transformations.

        ## Example
        adapter.report
        """
        return self._native.report

    def proof(self):
        """Return the explicit bidirectional adapter Proof. Compile and verify it before claiming equivalence.

        ## Returns
        Proof

        ## Example
        adapter.proof()
        """
        result = object.__new__(Proof)
        result._source, result._target = self.source, self.target
        result._native = self._native.native_proof()
        return result
