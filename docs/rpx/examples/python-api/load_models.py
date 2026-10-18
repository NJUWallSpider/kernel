#!/usr/bin/env python3
"""Executable rpx proof authoring example."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "python"))
from rpx import Model, ModelBuilder, Proof


def build():
    base = ROOT / "docs/rpx/examples/elimination"
    source, target = Model.read(base / "source.lp"), Model.read(base / "target.lp")
    proof = Proof(source, target)
    forward = proof.forward.map({"y": source.vars["x1"]}, default="same_name")
    forward.prove("objective.non_increasing", by=-forward.row("balance"))
    forward.finish()
    proof.reverse.map({"x0": 1 - target.vars["y"], "x1": target.vars["y"]}).finish()
    return proof


def main():
    proof = build()
    with tempfile.TemporaryDirectory(prefix="rpx-example-") as directory:
        report = proof.verify(Path(directory) / "bundle")
        report.raise_for_status()
        print(report)


if __name__ == "__main__":
    main()
