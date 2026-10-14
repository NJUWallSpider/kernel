#!/usr/bin/env python3
"""Replay supplied C3 mathematical choices for diagnosis, never acceptance.

Run in a separate fresh workspace with the pristine input and pinned compiler.
This does not repair, supply, or complete the failed proof.  Future fresh agents
must not receive this script, its archived cells, or reconstructed outputs.
"""
from contextlib import redirect_stdout
from pathlib import Path
import argparse
import json
import os
import sys
import time


def reconstruct(workdir):
    workdir = Path(workdir).resolve()
    archive = Path(__file__).resolve().parent
    if not (workdir / "input/model.mps").is_file():
        raise ValueError("fresh workspace needs the pristine input/model.mps")
    if workdir.name == "test16-compiler-compiler-batch-C3-20261015":
        raise ValueError("do not replay in the original agent workspace")
    sys.path.insert(0, str(workdir / "compiler/python"))
    os.environ["KERNEL_RPX"] = str(workdir / "compiler/bin/rpx")
    os.chdir(workdir)
    cells = json.loads((archive / "trajectory-python-cells.json").read_text())
    namespace = {"__name__": "__diagnostic_reconstruction__"}
    (workdir / "diagnostic").mkdir(exist_ok=True)
    timings = []
    with (workdir / "diagnostic/prefix.log").open("w") as stream, redirect_stdout(stream):
        for cell in cells:
            if cell["title"] == "Authoring exact equality certificate":
                break
            if cell.get("result", {}).get("error"):
                continue
            start = time.monotonic()
            exec(compile(cell["code"], f"archived-cell-{cell['index']}.py", "exec"), namespace)
            timings.append({"index": cell["index"], "title": cell["title"],
                            "seconds": round(time.monotonic() - start, 6)})
    record = {"diagnostic_replay_only": True, "acceptance_run": False,
              "proof_repaired_or_completed": False, "cell_timings": timings,
              "models": {name: namespace[name].stats() for name in
                         ("source", "modelA", "modelB", "modelC") if name in namespace},
              "namespace_names": sorted(namespace)}
    (workdir / "diagnostic/prefix.json").write_text(json.dumps(record, indent=2) + "\n")
    return namespace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    state = reconstruct(args.workdir)
    print(json.dumps({name: state[name].stats() for name in
                      ("source", "modelA", "modelB", "modelC") if name in state}, indent=2))
