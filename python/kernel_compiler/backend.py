"""Native command boundary to the exact Rust kernel."""
from __future__ import annotations

from pathlib import Path

from . import _native


class KernelError(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(report.get("error", report.get("message", str(report))))


_ERRORS = frozenset(("INVALID", "RESOURCE_LIMIT", "IO_ERROR", "EXECUTION_FAILED"))


class Kernel:
    """Native exact kernel facade; no subprocess and no binary discovery."""

    def __init__(self, binary=None):
        self._native = _native.Kernel()
        self.binary = None if binary is None else Path(binary)

    def call(self, *args, check=True):
        report = self._native.call([str(arg) for arg in args])
        if check and report.get("status") in _ERRORS:
            raise KernelError(report)
        return report

    def verify(self, source, target, proof, *, work=None, live_facts=None):
        return self._native.verify(str(source), str(target), str(proof), work, live_facts)
