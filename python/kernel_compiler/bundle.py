"""Explicit ordered proof stages.

Each stage certifies MI_OPT in Kernel; exact named model joins are checked here.

MI_OPT composes along the complete ordered chain. No claim selection is needed.
"""
from __future__ import annotations

import json
from pathlib import Path

from .backend import Kernel, KernelError
from .model import Model
from .proof import BuildError

ROLES = ("source", "target", "proof")


def _file(value, base):
    if not isinstance(value, (str, Path)):
        raise BuildError("Chain artifact paths must be strings or Paths")
    path = (base / value).resolve()
    if not path.is_file():
        raise BuildError(f"Chain artifact does not exist: {path}")
    return path


def _hash_record(path, cache=None):
    from .session import _digest
    if cache is None:
        value = _digest(path)
    else:
        if path not in cache:
            cache[path] = _digest(path)
        value = cache[path]
    return {"path": str(path), "sha256": value}


def _check_hash(record, base, *, expected=None, cache=None):
    if not isinstance(record, dict) or not isinstance(record.get("sha256"), str):
        raise BuildError("Missing or malformed chain artifact hash")
    path = _file(record.get("path"), base)
    if expected is not None and path != expected:
        raise BuildError(f"Chain hash record refers to a different artifact: {expected}")
    if _hash_record(path, cache)["sha256"] != record["sha256"]:
        raise BuildError(f"Chain artifact digest mismatch: {path}")
    return path


def _inspect(document, manifest, kernel, *, verify, digest_cache=None):
    from .session import _artifact_binding_method, _model_reader_family
    if not isinstance(document, dict):
        raise BuildError("Invalid ordered chain manifest container")
    if document.get("composition") != {"ordered_chain": True}:
        raise BuildError("Chain requires only composition.ordered_chain=true; claim selection is unsupported")
    pieces = document.get("pieces")
    if not isinstance(pieces, list) or not pieces:
        raise BuildError("Ordered chain requires nonempty stage pieces")
    records = document.get("artifacts")
    if not isinstance(records, dict):
        raise BuildError("Ordered chain requires complete artifact hashes")
    # Artifact bytes are streamed once per invocation, even when a stage role
    # and an extra metadata record refer to the same large file. Verification
    # starts its own fresh cache, independent of write_chain's authoring pass.
    digest_cache = {} if digest_cache is None else digest_cache
    resolved = []
    for index, piece in enumerate(pieces):
        if not isinstance(piece, dict):
            raise BuildError("Invalid ordered stage piece")
        paths = {role: _file(piece.get(role), manifest.parent) for role in ROLES}
        for role, path in paths.items():
            _check_hash(records.get(f"stages.{index}.{role}"), manifest.parent, expected=path, cache=digest_cache)
        resolved.append(paths)
    original = _file(document["original_model"], manifest.parent) if document.get("original_model") else None
    committed = _file(document.get("committed_model"), manifest.parent)
    original_reader = _model_reader_family(original) if original is not None else None
    committed_reader = _model_reader_family(committed)
    _check_hash(records.get("committed_model"), manifest.parent, expected=committed, cache=digest_cache)
    if original:
        _check_hash(records.get("original_model"), manifest.parent, expected=original, cache=digest_cache)
    for record in records.values():
        _check_hash(record, manifest.parent, cache=digest_cache)
    stages, reports, joins, previous = [], [], [], None
    try:
        for index, paths in enumerate(resolved):
            source = target = None
            try:
                # Bytes identify a model only under the same reader. MPS bytes
                # renamed .lp and MCM bytes renamed .json must still be read by
                # their declared reader, even at an identical-byte boundary.
                if (previous is not None
                        and records[f"stages.{index-1}.target"]["sha256"] == records[f"stages.{index}.source"]["sha256"]
                        and _model_reader_family(resolved[index-1]["target"]) == _model_reader_family(paths["source"])):
                    source, previous = previous, None
                else:
                    source = Model.load(paths["source"], kernel=kernel)
                    if previous is not None:
                        if not previous.same_formulation(source):
                            raise BuildError(f"Broken exact named model join before stage {index}")
                        previous.close()
                        previous = None
                if index:
                    joins.append({"left_stage": index-1, "right_stage": index, "exact_named_formulation_match": True})
                elif original:
                    with Model.load(original, kernel=kernel) as anchor:
                        if not source.same_formulation(anchor):
                            raise BuildError("First chain source differs from the declared original named formulation")
                    del anchor
                target = Model.load(paths["target"], kernel=kernel)
                if source.path is None or target.path is None:
                    raise BuildError("Stage endpoints must be Kernel-readable MCM, MPS or LP artifacts")
                stage = {"index": index, "source_names": tuple(v.name for v in source.vars),
                         "target_names": tuple(v.name for v in target.vars)}
                stages.append(stage)
                if verify:
                    def native_path(path, model):
                        with path.open("rb") as stream:
                            return path if stream.read(4)==b"MCM\0" else model.path
                    reports.append(kernel.verify(native_path(paths["source"],source), native_path(paths["target"],target),
                                                 paths["proof"]))
                source.close()
                source = None
                previous, target = target, None
            finally:
                if source is not None:
                    source.close()
                if target is not None:
                    target.close()
        with Model.load(committed, kernel=kernel) as final:
            if not previous.same_formulation(final):
                raise BuildError("Last chain target differs from the committed named formulation")
        del final
        previous.close()
        previous = None
        return {"status": "VERIFIED" if verify and all(r.get("status") == "VERIFIED" for r in reports) else "INCOMPLETE",
                "parts": reports, "verification_scope": "MI_OPT for every ordered stage and exact named model joins",
                "artifacts": records,
                "artifact_audit": {"status": "MATCHED",
                    "method": _artifact_binding_method(committed_reader),
                    "scope": "Only the final complete proof target and committed artifact; every named variable, bound, integrality declaration, row, and objective agrees; model NAME, coordinate/row order and folded row constants may differ",
                    "committed_model": records["committed_model"],
                    "proof_target": records[f"stages.{len(pieces)-1}.target"],
                    "committed_reader": committed_reader,
                    "proof_target_reader": _model_reader_family(resolved[-1]["target"])},
                "composition": {"ordered_chain": True, "joins": joins,
                    "original_anchor_checked": original is not None, "original_anchor_reader": original_reader,
                    "final_target_artifact_match": True,
                    "guarantee": "MI_OPT" if verify and all(r.get("status") == "VERIFIED" for r in reports) else None,
                    "final_relation_derived": verify and all(r.get("status") == "VERIFIED" for r in reports)}}
    finally:
        if previous is not None:
            previous.close()


def verify_ordered_chain(document, manifest, *, kernel=None):
    """Check MI_OPT for every stage and exact named model joins."""
    try:
        return _inspect(document, Path(manifest).resolve(), kernel or Kernel(), verify=True)
    except (BuildError, ValueError, KeyError, TypeError, OSError, KernelError) as error:
        return {"status": "INCOMPLETE", "parts": [], "error": str(error),
                "composition": {"ordered_chain": True, "final_relation_derived": False}}


def write_chain(stage_manifests, destination, *, committed_model, original_model=None,
                kernel=None):
    """Bind one piece per explicit stage without copying its large artifacts.

    Every stage must independently certify MI_OPT.
    This writes/checks metadata; call verify_bundle for Kernel verification.
    """
    try:
        return _write_chain(stage_manifests,destination,committed_model=committed_model,
                            original_model=original_model,kernel=kernel)
    except BuildError:
        raise
    except (ValueError,KeyError,TypeError,OSError,KernelError) as error:
        raise BuildError(str(error)) from error


def _write_chain(stage_manifests, destination, *, committed_model, original_model,
                 kernel):
    from .session import _atomic_text
    kernel = kernel or Kernel()
    if isinstance(stage_manifests,(str,bytes,Path)):
        raise BuildError("write_chain requires an explicit sequence of stage manifest paths")
    manifests = [_file(value, Path.cwd()) for value in stage_manifests]
    if not manifests:
        raise BuildError("write_chain requires at least one explicit stage manifest")
    destination = Path(destination).absolute()
    # Resolve parents, but keep the output leaf so replacement never writes
    # through an unrelated existing leaf symlink.
    destination = destination.parent.resolve() / destination.name
    pieces, records, protected, digest_cache = [], {}, list(manifests), {}
    for index, manifest in enumerate(manifests):
        stage = json.loads(manifest.read_text())
        if (not isinstance(stage,dict) or not isinstance(stage.get("pieces"), list)
                or len(stage["pieces"]) != 1 or not isinstance(stage["pieces"][0],dict)):
            raise BuildError("Each write_chain stage manifest must contain exactly one piece")
        paths = {role: _file(stage["pieces"][0].get(role), manifest.parent) for role in ROLES}
        hashes = stage.get("artifacts", {})
        if not isinstance(hashes,dict):
            raise BuildError("Stage manifest requires artifact hashes")
        for role, path in paths.items():
            _check_hash(hashes.get(role), manifest.parent, expected=path, cache=digest_cache)
            records[f"stages.{index}.{role}"] = _hash_record(path, digest_cache)
        for name, record in hashes.items():
            path = _check_hash(record, manifest.parent, cache=digest_cache)
            if name not in ROLES:
                records[f"stages.{index}.extra.{name}"] = _hash_record(path, digest_cache)
            protected.append(path)
        records[f"stages.{index}.manifest"] = _hash_record(manifest, digest_cache)
        pieces.append({role: str(path) for role, path in paths.items()})
    committed = _file(committed_model, Path.cwd())
    records["committed_model"] = _hash_record(committed, digest_cache)
    protected.append(committed)
    document = {"format": "kernel-compiler-delivery-1", "relation": "MI_OPT",
                "composition": {"ordered_chain": True},
                "pieces": pieces, "artifacts": records, "committed_model": str(committed)}
    if original_model is not None:
        original = _file(original_model, Path.cwd())
        records["original_model"] = _hash_record(original, digest_cache)
        document["original_model"] = str(original)
        protected.append(original)
    for path in protected:
        if destination.resolve() == path or (destination.exists() and destination.samefile(path)):
            raise BuildError("Chain manifest output aliases an input artifact or stage manifest")
    _inspect(document, destination, kernel, verify=False, digest_cache=digest_cache)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_text(destination, json.dumps(document, indent=2) + "\n")
    return destination
