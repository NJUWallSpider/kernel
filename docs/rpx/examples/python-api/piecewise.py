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
    x = b.add_var("x", lower=-1, upper=1)
    source = b.build()
    b = ModelBuilder("target")
    y = b.add_var("y", lower=0, upper=1)
    target = b.build()
    proof = Proof(source, target)
    left, right = proof.forward.split(x, kind="continuous")
    # The shared boundary x=0 belongs to both continuous branches.
    assert left.assumption.expression == x
    assert right.assumption.expression == -x
    left.map({"y": -x}).finish()
    right.map({"y": x}).finish()
    reverse = proof.reverse.map({"x": y})
    reverse.derive.le(reverse.lower("y") - 1)
    reverse.finish()
    return proof


def main():
    proof = build()
    with tempfile.TemporaryDirectory(prefix="rpx-example-") as directory:
        report = proof.verify(Path(directory) / "bundle")
        report.raise_for_status()
        print(report)


if __name__ == "__main__":
    main()
