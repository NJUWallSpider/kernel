"""Sparse structural mutations for adversarial checks of an existing proof."""
from __future__ import annotations

from .proof import BuildError


def mutate(certificate, path, *, replacement=None, delete=False):
    """Copy only containers on a selected path; never deepcopy a large proof."""
    path = tuple(path)
    if not path:
        if delete:
            raise BuildError("Cannot delete the entire certificate")
        return replacement
    key = path[0]
    if not isinstance(certificate, (dict, list)):
        raise BuildError("Mutation path crosses a scalar")
    result = certificate.copy()
    if len(path) == 1:
        if delete:
            del result[key]
        else:
            certificate[key]
            result[key] = replacement
    else:
        result[key] = mutate(certificate[key], path[1:], replacement=replacement, delete=delete)
    return result


def attack(proof, directory, path, *, replacement=None, delete=False, expected="INVALID"):
    """Mutate a native proof site; the Kernel always requires MI_OPT."""
    try:
        compiled = proof._native.attack([str(item) for item in path], replacement, delete)
    except (ValueError, TypeError) as error:
        return {"expected": expected, "rejected_as_expected": expected == "INVALID",
                "stage": "compile", "result": {"status": "INVALID", "message": str(error)}}
    directory = __import__("pathlib").Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    source, target = directory / "source.mcm", directory / "target.mcm"
    proof_path = directory / "proof.rpx"
    proof.source.write_mcm(source)
    proof.target.write_mcm(target)
    proof_path.write_bytes(compiled.rpx)
    report = proof.kernel.verify(source, target, proof_path)
    return {"expected": expected, "rejected_as_expected": report["status"] == expected,
            "stage": "verify", "result": report}
