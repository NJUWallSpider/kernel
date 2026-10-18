#!/usr/bin/env python3
"""Audit the frozen Kernel tree and historical case payloads after Compiler work."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    baseline = json.loads((ROOT / "tests/vectors/compiler_boundary.json").read_text())
    actual = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "crates/core").rglob("*")
        if p.is_file()
    }
    if actual != set(baseline["kernel"]):
        raise SystemExit("Kernel file inventory changed")
    failures = []
    for group in baseline.values():
        for name, expected in group.items():
            h = hashlib.sha256()
            with (ROOT / name).open("rb") as stream:
                for block in iter(lambda: stream.read(1 << 20), b""):
                    h.update(block)
            if h.hexdigest() != expected:
                failures.append(name)
    if failures:
        raise SystemExit("Frozen payloads changed: " + ", ".join(failures))
    print(
        f"PASS: {len(baseline['kernel'])} Kernel files and {len(baseline['cases'])} historical case payloads unchanged"
    )


if __name__ == "__main__":
    main()
