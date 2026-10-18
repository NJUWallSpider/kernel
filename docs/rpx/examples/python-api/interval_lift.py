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
    x = b.add_var("x", lower=0, upper=1)
    y = b.add_var("y", lower=0)
    b.add_row("cap", y - x, upper=0)
    source = b.build()
    b = ModelBuilder("target")
    tx = b.add_var("x", lower=0, upper=1)
    target = b.build()
    proof = Proof(source, target)
    proof.forward.map(default="same_name").finish()
    reverse = proof.reverse
    lift = reverse.lift_interval(lower=0, upper=tx, because=reverse.lower("x"))
    lift.scope.map({"y": lift.variable}, default="same_name").finish()
    return proof


def main():
    proof = build()
    with tempfile.TemporaryDirectory(prefix="rpx-example-") as directory:
        report = proof.verify(Path(directory) / "bundle")
        report.raise_for_status()
        print(report)


if __name__ == "__main__":
    main()
