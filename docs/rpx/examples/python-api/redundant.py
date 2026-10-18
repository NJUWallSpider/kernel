#!/usr/bin/env python3
"""Executable rpx proof authoring example."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "python"))
from rpx import Model, ModelBuilder, Proof


def build():
    base = ROOT / "docs/rpx/examples/redundant"
    source, target = Model.read(base / "source.lp"), Model.read(base / "target.lp")
    proof = Proof(source, target)
    proof.forward.map({"y": source.vars["x"]}).finish()
    reverse = proof.reverse.map({"x": target.vars["y"]})
    reverse.derive.le(reverse.row("cap") - 1)
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
