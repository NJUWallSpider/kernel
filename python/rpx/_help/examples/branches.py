"""Verify continuous split, integer split and explicit Cases examples."""

from pathlib import Path
from tempfile import TemporaryDirectory
from rpx import ModelBuilder, Proof, Q


def build_proof(mode):
    b = ModelBuilder("branches")
    x = b.add_var("x", integer=True, lower=0, upper=1)
    model = b.build()
    proof = Proof(model, model)
    s = proof.forward
    if mode == "cases":
        cases = s.derive.cases(x, kind="Le", expect=x - 1, integer=s.integer(x))
        cases.left.conclude(cases.left.derive.le(cases.left.assumption - 1))
        cases.right.conclude(cases.right.upper(x))
        assert cases.finish().expression == x - 1
        s.map(default="same_name").finish()
    else:
        options = (
            dict(at=Q(1, 2))
            if mode == "continuous"
            else dict(at=0, kind="integer", because=s.integer(x))
        )
        left, right = s.split(x, **options)
        left.map(default="same_name").finish()
        right.map(default="same_name").finish()
    proof.reverse.map(default="same_name").finish()
    return proof


def main():
    with TemporaryDirectory() as directory:
        for mode in ("continuous", "integer", "cases"):
            print(
                mode,
                build_proof(mode)
                .verify(Path(directory) / mode)
                .raise_for_status()
                .status,
            )


if __name__ == "__main__":
    main()
