"""Immutable, self-contained deliveries with fresh verification on every call."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from copy import deepcopy
import hashlib
import ctypes
import errno
import html
import json
import os
import shutil
import tempfile
import sys

from . import _native
from ._native import ArtifactMismatchError, KernelRejectedError, ResourceLimitError

ROLES = {
    "source": "source.mcm",
    "target": "target.mcm",
    "rpa": "proof.rpa",
    "proof": "proof.rpx",
}
BUNDLE_SCHEMA = "rpx.bundle/1"
CHAIN_SCHEMA = "rpx.chain/1"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def _record(root, name):
    path = root / name
    return {"path": name, "sha256": digest(path), "bytes": path.stat().st_size}


def _text(path, document):
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _local(root, name):
    if not isinstance(name, str):
        raise ArtifactMismatchError("artifact path must be a relative string")
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in name
        or not relative.parts
    ):
        raise ArtifactMismatchError(f"artifact path escapes delivery: {name!r}")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ArtifactMismatchError(f"artifact path escapes delivery: {name!r}")
    if not path.is_file():
        raise ArtifactMismatchError(f"missing artifact: {name}")
    return path


def _inspect(directory, schema):
    root = Path(directory).absolute()
    try:
        document = json.loads((root / "delivery.json").read_text(encoding="utf-8"))
        if document.get("schema") != schema:
            raise ArtifactMismatchError(f"expected {schema} delivery")
        records = document["artifacts"]
        if not isinstance(records, dict):
            raise ArtifactMismatchError("missing artifact records")
        for role, record in records.items():
            path = _local(root, record["path"])
            if (
                path.stat().st_size != record["bytes"]
                or digest(path) != record["sha256"]
            ):
                raise ArtifactMismatchError(f"artifact digest mismatch: {role}")
        return root, document
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ArtifactMismatchError):
            raise
        raise ArtifactMismatchError(f"invalid delivery: {error}") from error


def _rename_exclusive(source, destination):
    """Atomic publication must never replace even an empty directory."""
    if sys.platform == "win32":
        os.rename(source, destination)  # Windows rename already refuses replacement.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(destination), 4)  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            -100, os.fsencode(source), -100, os.fsencode(destination), 1
        )  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise OSError(
            errno.ENOTSUP, "atomic exclusive directory publication is unavailable"
        )
    if result:
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise ArtifactMismatchError(
                "delivery destination was created during publication"
            )
        raise OSError(code, os.strerror(code), str(destination))


def _publish(destination, prepare):
    destination = Path(destination).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ArtifactMismatchError(
            "delivery destination aliases an existing file or symlink"
        )
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    try:
        document = prepare(staging)
        _text(staging / "delivery.json", document)
        if destination.exists():
            _, existing = _inspect(destination, document["schema"])
            if existing != document:
                raise ArtifactMismatchError(
                    "destination contains a different delivery; choose a new directory"
                )
            return destination
        # A prepared nonempty directory is published in one filesystem rename.
        _rename_exclusive(staging, destination)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)


@dataclass(frozen=True)
class VerificationReport:
    _data: dict

    @property
    def status(self):
        return self._data["status"]

    @property
    def guarantee(self):
        return self._data.get("guarantee")

    @property
    def statistics(self):
        return deepcopy(self._data.get("statistics", {}))

    @property
    def kernel(self):
        return deepcopy(
            {
                k: v
                for k, v in self._data.items()
                if k not in ("artifact_audit", "artifacts")
            }
        )

    @property
    def artifact_audit(self):
        return deepcopy(self._data.get("artifact_audit", {"status": "NOT_REQUESTED"}))

    def to_dict(self):
        return deepcopy(self._data)

    def raise_for_status(self):
        if self.status == "RESOURCE_LIMIT":
            raise ResourceLimitError(
                self._data.get("message", self._data.get("error", self.status))
            )
        if self.status != "VERIFIED":
            raise KernelRejectedError(
                self._data.get("message", self._data.get("error", self.status))
            )
        return self

    def __str__(self):
        lines = [self.status + (f" · {self.guarantee}" if self.guarantee else "")]
        for name in ("obligations", "branches", "linear_terms", "work"):
            if name in self.statistics:
                lines.append(f"  {name}: {self.statistics[name]}")
        lines.append(f"  artifact audit: {self.artifact_audit['status']}")
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_html_(self):
        return "<pre>" + html.escape(str(self)) + "</pre>"


@dataclass(frozen=True)
class Bundle:
    directory: Path

    @classmethod
    def open(cls, directory):
        root, document = _inspect(directory, BUNDLE_SCHEMA)
        required = set(ROLES)
        if "target_artifact" in document and document["target_artifact"] is not True:
            raise ArtifactMismatchError(
                "target_artifact flag must be true when present"
            )
        if document.get("target_artifact"):
            required.add("target_artifact")
        if set(document["artifacts"]) != required:
            raise ArtifactMismatchError(
                "bundle must list exactly its complete proof and requested artifact"
            )
        for role, name in ROLES.items():
            if document["artifacts"][role]["path"] != name:
                raise ArtifactMismatchError(f"invalid bundle role: {role}")
        return cls(root)

    @property
    def source(self):
        return self.directory / ROLES["source"]

    @property
    def target(self):
        return self.directory / ROLES["target"]

    @property
    def rpa(self):
        return self.directory / ROLES["rpa"]

    @property
    def proof(self):
        return self.directory / ROLES["proof"]

    @property
    def manifest(self):
        return self.directory / "delivery.json"

    def verify(self, *, target_artifact=None, work=None, live_facts=None, depth=None):
        Bundle.open(self.directory)
        _, document = _inspect(self.directory, BUNDLE_SCHEMA)
        audit = {"status": "NOT_REQUESTED"}
        targets = []
        if document.get("target_artifact"):
            targets.append(
                _local(self.directory, document["artifacts"]["target_artifact"]["path"])
            )
        if target_artifact is not None:
            targets.append(Path(target_artifact))
        if targets:
            expected = _native.Model.read(self.target)
            for path in targets:
                if not expected.same_formulation(_native.Model.read(path)):
                    raise ArtifactMismatchError(
                        "target artifact differs from the complete proof target"
                    )
            audit = {
                "status": "MATCHED",
                "scope": "all named variables, bounds, integrality, rows and objective",
            }
        report = _native.verify(
            str(self.source),
            str(self.target),
            str(self.proof),
            work=work,
            live_facts=live_facts,
            depth=depth,
        )
        report["artifact_audit"] = audit
        report["artifacts"] = document["artifacts"]
        if report["status"] != "VERIFIED":
            report["guarantee"] = None
        _receipt(self.directory, report)
        return VerificationReport(report)

    def __repr__(self):
        return f"Bundle({self.directory})"

    def _repr_html_(self):
        return "<pre>" + html.escape(repr(self)) + "</pre>"


def _receipt(root, report):
    fd, name = tempfile.mkstemp(prefix=".verification.", suffix=".tmp", dir=root)
    os.close(fd)
    temporary = Path(name)
    try:
        _text(temporary, report)
        temporary.replace(root / "verification.json")
    finally:
        temporary.unlink(missing_ok=True)


def publish_proof(proof, directory, *, target_artifact=None):
    # Incomplete proofs fail before any destination is created.
    proof.preflight()

    def prepare(root):
        proof._native.write(root)
        records = {role: _record(root, name) for role, name in ROLES.items()}
        document = {"schema": BUNDLE_SCHEMA, "artifacts": records}
        if target_artifact is not None:
            source = Path(target_artifact)
            name = "target-artifact" + source.suffix.lower()
            shutil.copyfile(source, root / name)
            if not proof.target.same_formulation(_native.Model.read(root / name)):
                raise ArtifactMismatchError(
                    "target artifact differs from the complete proof target"
                )
            records["target_artifact"] = _record(root, name)
            document["target_artifact"] = True
        return document

    return Bundle.open(_publish(directory, prepare))


class Chain:
    def __init__(self, stages):
        self.stages = tuple(stages)
        if not self.stages or not all(
            isinstance(stage, Bundle) for stage in self.stages
        ):
            raise TypeError("Chain needs a nonempty sequence of Bundle objects")
        self._check_joins()

    def _check_joins(self):
        for stage in self.stages:
            Bundle.open(stage.directory)
        for before, after in zip(self.stages, self.stages[1:]):
            if not _native.Model.read(before.target).same_formulation(
                _native.Model.read(after.source)
            ):
                raise ArtifactMismatchError("adjacent chain models differ")

    def compile(self, directory, *, target_artifact=None, source_artifact=None):
        self._check_joins()
        target_artifact = (
            self.stages[-1].target if target_artifact is None else target_artifact
        )
        source_artifact = (
            self.stages[0].source if source_artifact is None else source_artifact
        )

        def prepare(root):
            paths = []
            for index, stage in enumerate(self.stages):
                name = f"stages/{index:04d}"
                # Copy the audited package, not unrelated files beside its artifacts.
                _, stage_document = _inspect(stage.directory, BUNDLE_SCHEMA)
                stage_root = root / name
                stage_root.mkdir(parents=True)
                for record in stage_document["artifacts"].values():
                    destination = stage_root / record["path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(
                        _local(stage.directory, record["path"]), destination
                    )
                _text(stage_root / "delivery.json", stage_document)
                Bundle.open(stage_root)
                paths.append(name)
            for role, external, model_path in [
                ("target_artifact", target_artifact, self.stages[-1].target),
                ("source_artifact", source_artifact, self.stages[0].source),
            ]:
                if external is None:
                    continue
                external = Path(external)
                name = role.replace("_", "-") + external.suffix.lower()
                shutil.copyfile(external, root / name)
                if not _native.Model.read(model_path).same_formulation(
                    _native.Model.read(root / name)
                ):
                    raise ArtifactMismatchError(f"{role} differs from chain endpoint")
            records = {
                p.relative_to(root).as_posix(): _record(
                    root, p.relative_to(root).as_posix()
                )
                for p in sorted(root.rglob("*"))
                if p.is_file()
            }
            return {
                "schema": CHAIN_SCHEMA,
                "stages": paths,
                "artifacts": records,
                "target_artifact": "target-artifact"
                + Path(target_artifact).suffix.lower(),
                "source_artifact": (
                    None
                    if source_artifact is None
                    else "source-artifact" + Path(source_artifact).suffix.lower()
                ),
            }

        return Chain.open(_publish(directory, prepare))

    @classmethod
    def open(cls, directory):
        root, document = _inspect(directory, CHAIN_SCHEMA)
        stages = document.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ArtifactMismatchError("missing chain stages")
        if stages != [f"stages/{i:04d}" for i in range(len(stages))]:
            raise ArtifactMismatchError(
                "chain stages must be unique, ordered package directories"
            )
        expected = set()
        for name in stages:
            manifest = str(PurePosixPath(name) / "delivery.json")
            _local(root, manifest)
            expected.add(manifest)
            _, stage = _inspect(root / name, BUNDLE_SCHEMA)
            expected.update(
                str(PurePosixPath(name) / r["path"])
                for r in stage["artifacts"].values()
            )
        for role in ("source_artifact", "target_artifact"):
            path = document.get(role)
            _local(root, path)
            expected.add(path)
        if set(document["artifacts"]) != expected or any(
            k != r["path"] for k, r in document["artifacts"].items()
        ):
            raise ArtifactMismatchError(
                "chain manifest must cover all stages and endpoint artifacts"
            )
        chain = cls(Bundle.open(root / name) for name in stages)
        chain.directory = root
        return chain

    def verify(self, **limits):
        if hasattr(self, "directory"):
            Chain.open(self.directory)
            _, document = _inspect(self.directory, CHAIN_SCHEMA)
            for role, model in [
                ("source_artifact", self.stages[0].source),
                ("target_artifact", self.stages[-1].target),
            ]:
                if document.get(role) and not _native.Model.read(
                    model
                ).same_formulation(
                    _native.Model.read(_local(self.directory, document[role]))
                ):
                    raise ArtifactMismatchError(f"{role} differs from chain endpoint")
        self._check_joins()
        reports = [stage.verify(**limits).to_dict() for stage in self.stages]
        success = all(report["status"] == "VERIFIED" for report in reports)
        return VerificationReport(
            {
                "status": (
                    "VERIFIED"
                    if success
                    else next(
                        report["status"]
                        for report in reports
                        if report["status"] != "VERIFIED"
                    )
                ),
                "guarantee": "MI_OPT" if success else None,
                "parts": reports,
                "artifact_audit": {"status": "MATCHED"},
                "composition": {
                    "ordered_chain": True,
                    "final_relation_derived": success,
                },
            }
        )
