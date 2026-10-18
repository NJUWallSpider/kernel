"""Publish, move, audit and compose portable verified deliveries."""

from pathlib import Path
from tempfile import TemporaryDirectory
from rpx import Bundle, Chain, Proof
from .quickstart import build_proof


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        proof = build_proof()
        artifact = proof.target.write_mps(root / "target.mps")
        bundle = proof.compile(root / "original", target_artifact=artifact)
        print(bundle.verify().raise_for_status())
        bundle.directory.rename(root / "moved")
        moved = Bundle.open(root / "moved")
        print(moved.verify().raise_for_status())
        identity = Proof(proof.target, proof.target)
        identity.forward.map(default="same_name").finish()
        identity.reverse.map(default="same_name").finish()
        second = identity.compile(root / "identity")
        chain = Chain([moved, second]).compile(root / "chain")
        print(chain.verify().raise_for_status())


if __name__ == "__main__":
    main()
