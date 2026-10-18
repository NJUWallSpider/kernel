from pathlib import Path
from typing import Any, Iterable
from os import PathLike

FilePath = str | PathLike[str]

class VerificationReport:
    @property
    def status(self) -> str: ...
    @property
    def guarantee(self) -> str | None: ...
    @property
    def statistics(self) -> dict[str, Any]: ...
    @property
    def kernel(self) -> dict[str, Any]: ...
    @property
    def artifact_audit(self) -> dict[str, Any]: ...
    def to_dict(self) -> dict[str, Any]: ...
    def raise_for_status(self) -> VerificationReport: ...

class Bundle:
    directory: Path
    @classmethod
    def open(cls, directory: FilePath) -> Bundle: ...
    @property
    def source(self) -> Path: ...
    @property
    def target(self) -> Path: ...
    @property
    def rpa(self) -> Path: ...
    @property
    def proof(self) -> Path: ...
    @property
    def manifest(self) -> Path: ...
    def verify(
        self,
        *,
        target_artifact: FilePath | None = None,
        work: int | None = None,
        live_facts: int | None = None,
        depth: int | None = None
    ) -> VerificationReport: ...

class Chain:
    stages: tuple[Bundle, ...]
    directory: Path
    def __init__(self, stages: Iterable[Bundle]) -> None: ...
    @classmethod
    def open(cls, directory: FilePath) -> Chain: ...
    def compile(
        self,
        directory: FilePath,
        *,
        target_artifact: FilePath | None = None,
        source_artifact: FilePath | None = None
    ) -> Chain: ...
    def verify(
        self,
        *,
        work: int | None = None,
        live_facts: int | None = None,
        depth: int | None = None
    ) -> VerificationReport: ...
