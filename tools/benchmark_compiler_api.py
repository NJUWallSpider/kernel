#!/usr/bin/env python3
"""Independent native phases, process RSS and Python allocations; no speedup assumptions."""
from __future__ import annotations
import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


def synthetic(path, size):
    with path.open("w") as f:
        f.write("NAME synthetic_identity\nROWS\n N objective\n")
        for i in range(size):
            f.write(f" L row{i}\n")
        f.write("COLUMNS\n")
        for i in range(size):
            f.write(f" x{i} objective 0.125\n x{i} row{i} 1\n x{i} row{(i+1)%size} 1\n")
        f.write("RHS\n")
        for i in range(size):
            f.write(f" rhs row{i} 1\n")
        f.write("BOUNDS\n")
        for i in range(size):
            f.write(f" BV bound x{i}\n")
        f.write("ENDATA\n")
    return path


def worker(args):
    from rpx import Model, Proof, Expr, _native

    out = args.output.absolute()
    out.mkdir(parents=True, exist_ok=False)
    source = args.source or synthetic(out / "synthetic.mps", args.size)
    record = {
        "native_sha256": hashlib.sha256(
            Path(_native.__file__).read_bytes()
        ).hexdigest(),
        "source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        "schema": "rpx.performance/1",
        "status": "RUNNING",
        "coordinates": args.size,
        "source": str(source),
        "platform": platform.platform(),
        "python": sys.version,
        "started": datetime.now(timezone.utc).isoformat(),
        "phases": [],
    }

    def save():
        (out / "record.json").write_text(json.dumps(record, indent=2) + "\n")

    tracemalloc.start()

    def phase(name, fn):
        baseline = tracemalloc.get_traced_memory()[0]
        tracemalloc.reset_peak()
        start = time.perf_counter_ns()
        result = fn()
        elapsed = time.perf_counter_ns() - start
        current, peak = tracemalloc.get_traced_memory()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = (
            int(
                subprocess.check_output(
                    ["ps", "-o", "rss=", "-p", str(__import__("os").getpid())]
                ).strip()
            )
            * 1024
        )
        record["phases"].append(
            {
                "name": name,
                "wall_ns": elapsed,
                "rss_bytes": rss,
                "rss_high_water_bytes": usage.ru_maxrss
                * (1 if sys.platform == "darwin" else 1024),
                "python_allocated_delta_bytes": current - baseline,
                "python_peak_delta_bytes": max(0, peak - baseline),
            }
        )
        save()
        print(json.dumps(record["phases"][-1]), flush=True)
        return result

    try:
        model = phase("load", lambda: Model.read(source))
        record["model"] = model.stats()
        record["coordinates"] = len(model.vars)
        proof = phase("proof", lambda: Proof(model, model))
        phase(
            "mapping",
            lambda: (
                proof.forward.map(default="same_name"),
                proof.reverse.map(default="same_name"),
            ),
        )
        coefficients = array("q", [1]) * len(model.vars)
        expression = phase(
            "expression_build", lambda: Expr.dot(coefficients, model.vars)
        )
        assert len(expression.terms) == len(model.vars)
        phase("finish", lambda: (proof.forward.finish(), proof.reverse.finish()))
        size = phase("encode", proof.preflight)
        record["encoded"] = size
        bundle = phase("publish", lambda: proof.compile(out / "bundle"))
        record["verification"] = phase("verify", bundle.verify).to_dict()
        phase(
            "repeat_queries",
            lambda: (
                proof.preflight(),
                proof.preflight(),
                proof.forward.plan(),
                proof.forward.plan(),
            ),
        )
        assert proof._native.lowering_count == 1
        record["lowering_count"] = proof._native.lowering_count
        assert record["verification"]["status"] == "VERIFIED", record["verification"]
        record["status"] = "VERIFIED"
    except Exception as error:
        record["status"] = "FAILED"
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()
        tracemalloc.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, default=1000)
    parser.add_argument("--sizes", default="1000,10000,100000,1000000")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    runs = []
    for size in map(int, args.sizes.split(",")):
        path = args.output / f"synthetic-{size}"
        command = [
            sys.executable,
            __file__,
            "--worker",
            "--size",
            str(size),
            "--output",
            str(path),
        ]
        process = subprocess.run(command)
        runs.append(
            {
                "size": size,
                "returncode": process.returncode,
                "record": str(path / "record.json"),
            }
        )
    if args.source:
        path = args.output / "real"
        process = subprocess.run(
            [
                sys.executable,
                __file__,
                "--worker",
                "--source",
                str(args.source),
                "--output",
                str(path),
            ]
        )
        runs.append(
            {
                "source": str(args.source),
                "returncode": process.returncode,
                "record": str(path / "record.json"),
            }
        )
    (args.output / "summary.json").write_text(json.dumps(runs, indent=2) + "\n")
    if any(r["returncode"] for r in runs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
