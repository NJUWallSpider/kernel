"""Sparse structural mutations for adversarial checks of an existing proof."""
from __future__ import annotations

from .backend import KernelError
from .proof import BuildError
from .session import compile_certificate


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
            # A replacement must select an existing site rather than accidentally
            # append an unrequested property under a misspelled key.
            certificate[key]
            result[key] = replacement
    else:
        result[key] = mutate(certificate[key], path[1:], replacement=replacement, delete=delete)
    return result


def attack(proof, directory, path, *, replacement=None, delete=False, expected="INVALID"):
    """Mutate a proof site; the Kernel always requires MI_OPT."""
    certificate = mutate(proof.certificate(), path, replacement=replacement, delete=delete)
    try:
        artifacts = compile_certificate(proof.source, proof.target, certificate, directory,
                                        kernel=proof.kernel)
    except KernelError as error:
        return {"expected": expected, "rejected_as_expected": error.report["status"] == expected,
                "stage": "compile", "result": error.report}
    report = proof.kernel.verify(artifacts["source"], artifacts["target"], artifacts["proof"])
    return {"expected": expected, "rejected_as_expected": report["status"] == expected,
            "stage": "verify", "result": report}
