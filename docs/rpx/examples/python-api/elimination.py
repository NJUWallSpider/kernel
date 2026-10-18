#!/usr/bin/env python3
"""Executable rpx proof authoring example."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "python"))
from rpx import Model, ModelBuilder, Proof


def build():
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
    proof = build()
    with tempfile.TemporaryDirectory(prefix="rpx-example-") as directory:
        report = proof.verify(Path(directory) / "bundle")
        report.raise_for_status()
        print(report)


if __name__ == "__main__":
    main()
