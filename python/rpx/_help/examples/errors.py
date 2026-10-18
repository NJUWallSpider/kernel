"""Trigger representative contract errors, correct them, and verify."""

from pathlib import Path
from tempfile import TemporaryDirectory
from rpx import (
    ModelBuilder,
    Proof,
    MappingError,
    CoordinateSpaceError,
    InvalidDerivationError,
    ScopeError,
    ResourceLimitError,
)


def expect_error(error, operation):
    try:
        operation()
    except error:
        return
    raise AssertionError("Expected " + error.__name__)


def main():
    b = ModelBuilder("errors")
    x = b.add_var("x", lower=0, upper=1)
    model = b.build()
    proof = Proof(model, model)
    s = proof.forward
    expect_error(MappingError, lambda: s.map({"unknown": x}))
    s.map(default="same_name")  # Correct names and complete coverage.
    edited = model.renamed("edited")
    expect_error(CoordinateSpaceError, lambda: x + edited.vars["x"])
    assert edited.vars["x"] + 1 == 1 + edited.vars["x"]  # Use one space.
    expect_error(InvalidDerivationError, lambda: s.derive.le(-s.upper(x)))
    s.derive.le(s.upper(x))  # Nonnegative multiplier for an inequality.
    old_goal = s.obligations["objective.non_increasing"]
    s.map(default="same_name")
    expect_error(ScopeError, lambda: s.prove(old_goal, by=0))
    s.prove(s.obligations["objective.non_increasing"], by=0)
    s.finish()
    expect_error(ScopeError, lambda: s.map(default="same_name"))
    # An edited proof needs a fresh Proof; never reopen a sealed scope.
    fresh = Proof(model, model)
    fresh.forward.map(default="same_name").finish()
    fresh.reverse.map(default="same_name").finish()
    proof.reverse.map(default="same_name").finish()
    with TemporaryDirectory() as directory:
        bundle = proof.compile(Path(directory) / "bundle")
        limited = bundle.verify(work=0)
        assert limited.status == "RESOURCE_LIMIT"
        expect_error(ResourceLimitError, limited.raise_for_status)
        print(bundle.verify().raise_for_status())  # Fresh verification, new budget.
        print(fresh.verify(Path(directory) / "fresh").raise_for_status())


if __name__ == "__main__":
    main()
