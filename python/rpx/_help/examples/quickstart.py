"""Eliminate x0 from x0+x1=1 and certify both directions."""

from pathlib import Path
from tempfile import TemporaryDirectory
from rpx import ModelBuilder, Proof


def build_proof():
    b = ModelBuilder("source")
    x0 = b.add_var("x0", lower=0, upper=1)
    x1 = b.add_var("x1", lower=0, upper=1)
    b.add_row("balance", x0 + x1, equal=1)
    b.minimize(x0)
    source = b.build()
    b = ModelBuilder("target")
    y = b.add_var("y", lower=0, upper=1)
    b.minimize(1 - y)
    target = b.build()
    proof = Proof(source, target)
    forward = proof.forward.map({"y": x1})
    forward.prove("objective.non_increasing", by=-forward.row("balance"))
    forward.finish()
    proof.reverse.map({"x0": 1 - y, "x1": y}).finish()
    return proof


def main():
    with TemporaryDirectory() as directory:
        report = build_proof().verify(Path(directory) / "bundle")
        report.raise_for_status()
        assert report.status == "VERIFIED"
        print(report)


if __name__ == "__main__":
    main()
