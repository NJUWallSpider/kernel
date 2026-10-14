"""Explicit ordered proof stages.

Each stage Request is accepted by Kernel; exact joins and elementary composition
are compiler-side checks.

Composition records only elementary consequences of caller-selected existing
Requests. It neither searches for a proof nor creates a new RPX proof rule.
"""
from __future__ import annotations

import json
from pathlib import Path

from .backend import Kernel, KernelError
from .model import Model
from .proof import BuildError

ROLES = ("source", "target", "proof", "request")
OBJECTIVES = {"Equal": 0, "NonIncreasing": 1, "None": 2}
MAX_OBSERVATION_PAIRS = 10_000_000


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


def _request(path):
    value = json.loads(path.read_text())
    # Frozen Kernel also accepts the legacy directional-claim array.
    if isinstance(value, list):
        value = {"claims": value}
    if not isinstance(value, dict) or not isinstance(value.get("claims", []), list):
        raise BuildError("Invalid chain Request container")
    return value


def _paths(document, count):
    composition = document.get("composition")
    if not isinstance(composition, dict) or composition.get("ordered_chain") is not True:
        raise BuildError("Chain requires explicit composition.ordered_chain=true")
    paths = composition.get("claim_paths", {})
    if not isinstance(paths, dict):
        raise BuildError("claim_paths must map labels to one claim index per stage")
    for label, indices in paths.items():
        if not isinstance(label, str) or not label or not isinstance(indices, list) or len(indices) != count:
            raise BuildError("Each named claim path must cover every stage exactly once")
        if any(type(index) is not int or index < 0 for index in indices):
            raise BuildError("Claim path indices must be nonnegative integers")
    return paths


def _relation(claim, source_names, target_names):
    inputs, outputs = (target_names, source_names) if claim["reverse"] else (source_names, target_names)
    result = set()
    for pair in claim.get("projection", []):
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or any(type(i) is not int or i < 0 for i in pair)
                or pair[0] >= len(inputs) or pair[1] >= len(outputs)):
            raise BuildError("Invalid selected claim projection coordinates")
        result.add((inputs[pair[0]], outputs[pair[1]]))
    return result


def _compose(left, right):
    outgoing = {}
    for middle, end in right:
        outgoing.setdefault(middle, set()).add(end)
    result = set()
    for start, middle in left:
        for end in outgoing.get(middle, ()):
            result.add((start, end))
            if len(result) > MAX_OBSERVATION_PAIRS:
                raise BuildError("Chain observation composition exceeds its resource limit")
    return result


def _compose_paths(stages, paths):
    summaries = []
    for label, indices in paths.items():
        selected = []
        for stage, index in zip(stages, indices):
            claims = stage["request"].get("claims", [])
            if index >= len(claims) or not isinstance(claims[index], dict):
                raise BuildError(f"Claim path {label!r} contains an unavailable claim index")
            claim = claims[index]
            if (any(type(claim.get(field)) is not bool for field in
                    ("reverse", "input_integers", "output_integers"))
                    or claim.get("objective") not in OBJECTIVES):
                raise BuildError("Invalid selected chain claim flags or objective")
            selected.append((stage, index, claim))
        reverse = selected[0][2]["reverse"]
        if any(claim["reverse"] is not reverse for _, _, claim in selected):
            raise BuildError("A claim path must use one consistent stage direction")
        if reverse:
            selected.reverse()
        for left, right in zip(selected, selected[1:]):
            if left[2]["output_integers"] is not right[2]["input_integers"]:
                raise BuildError("Claim path has incompatible integer domains at a stage handoff")
        selection = [{"stage": stage["index"], "claim": index,
                      "input_objective_lower": claim.get("input_objective_lower")}
                     for stage, index, claim in selected]
        restrictions = [{"stage": stage["index"], "claim": index,
                         "input_objective_level": claim.get("input_objective_level"),
                         "input_halfspace": claim.get("input_halfspace")}
                        for stage, index, claim in selected if
                        claim.get("input_objective_level") is not None or claim.get("input_halfspace") is not None]
        summary = {"label": label, "direction": "reverse" if reverse else "forward",
                   "input_integers": selected[0][2]["input_integers"],
                   "output_integers": selected[-1][2]["output_integers"],
                   "selected_claims": selection, "composable": not restrictions,
                   "affine_inverse_inferred": False, "full_model_bijection_inferred": False,
                   "uncomposed_affine_projection_count": sum(len(c.get("affine_projection", [])) for _, _, c in selected)}
        if restrictions:
            summary.update(stage_local_only=True, restrictions=restrictions,
                           reason="Restricted stage claims were verified locally; no unrestricted final relation is derived")
        else:
            relation, objective = None, "Equal"
            for stage, _, claim in selected:
                edge = _relation(claim, stage["source_names"], stage["target_names"])
                relation = edge if relation is None else _compose(relation, edge)
                if OBJECTIVES[claim["objective"]] > OBJECTIVES[objective]:
                    objective = claim["objective"]
            summary.update(objective=objective, observation_relation=sorted(relation or set()),
                           observation_count=len(relation or set()))
        summaries.append(summary)
    bidirectional = []
    for forward in summaries:
        if not forward["composable"] or forward["direction"] != "forward":
            continue
        for reverse in summaries:
            if (not reverse["composable"] or reverse["direction"] != "reverse"
                    or forward["input_integers"] is not reverse["output_integers"]
                    or forward["output_integers"] is not reverse["input_integers"]):
                continue
            common = set(map(tuple, forward["observation_relation"])) & {
                (end, start) for start, end in reverse["observation_relation"]}
            optimal = forward["objective"] != "None" and reverse["objective"] != "None"
            bidirectional.append({"forward_path": forward["label"], "reverse_path": reverse["label"],
                "feasibility_correspondence": True, "equal_optimal_infima": optimal,
                "attainment_transfers_if_optimum_exists": optimal,
                "observation_relation": sorted(common), "observation_count": len(common)})
    return summaries, bidirectional


def _inspect(document, manifest, kernel, *, verify, digest_cache=None):
    from .session import _artifact_binding_method, _model_reader_family
    if not isinstance(document, dict):
        raise BuildError("Invalid ordered chain manifest container")
    pieces = document.get("pieces")
    if not isinstance(pieces, list) or not pieces:
        raise BuildError("Ordered chain requires nonempty stage pieces")
    claim_paths = _paths(document, len(pieces))
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
                         "target_names": tuple(v.name for v in target.vars), "request": _request(paths["request"])}
                stages.append(stage)
                if verify:
                    def native_path(path, model):
                        with path.open("rb") as stream:
                            return path if stream.read(4)==b"MCM\0" else model.path
                    reports.append(kernel.verify(native_path(paths["source"],source), native_path(paths["target"],target),
                                                 paths["proof"], paths["request"]))
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
        summaries, bidirectional = _compose_paths(stages, claim_paths)
        return {"status": "VERIFIED" if verify and all(r.get("status") == "VERIFIED" for r in reports) else "INCOMPLETE",
                "parts": reports, "verification_scope": "Every ordered stage Request and exact named model join",
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
                    "paths": summaries if all(r.get("status") == "VERIFIED" for r in reports) else [],
                    "bidirectional": bidirectional if all(r.get("status") == "VERIFIED" for r in reports) else [],
                    "final_relation_derived": verify and all(r.get("status") == "VERIFIED" for r in reports)
                        and any(s["composable"] for s in summaries)}}
    finally:
        if previous is not None:
            previous.close()


def verify_ordered_chain(document, manifest, *, kernel=None):
    """Check explicit stages and report only safe caller-selected compositions."""
    try:
        return _inspect(document, Path(manifest).resolve(), kernel or Kernel(), verify=True)
    except (BuildError, ValueError, KeyError, TypeError, OSError, KernelError) as error:
        return {"status": "INCOMPLETE", "parts": [], "error": str(error),
                "composition": {"ordered_chain": True, "final_relation_derived": False}}


def write_chain(stage_manifests, destination, *, committed_model, original_model=None,
                claim_paths=None, relation="Ordered caller-declared stage Requests", kernel=None):
    """Bind one piece per explicit stage without copying its large artifacts.

    Claim paths map arbitrary labels to stage-ordered Request claim indices.
    This writes/checks metadata; call verify_bundle for Kernel verification.
    """
    try:
        return _write_chain(stage_manifests,destination,committed_model=committed_model,
                            original_model=original_model,claim_paths=claim_paths,relation=relation,kernel=kernel)
    except BuildError:
        raise
    except (ValueError,KeyError,TypeError,OSError,KernelError) as error:
        raise BuildError(str(error)) from error


def _write_chain(stage_manifests, destination, *, committed_model, original_model,
                 claim_paths, relation, kernel):
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
    document = {"format": "kernel-compiler-delivery-1", "relation": relation,
                "composition": {"ordered_chain": True, "claim_paths": {} if claim_paths is None else claim_paths},
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
