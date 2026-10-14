"""Small process boundary to the exact Rust kernel; no assembly-language frontend."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


class KernelError(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(report.get("error", report.get("message", str(report))))


class Kernel:
    """Use a built rpx binary (explicit argument, KERNEL_RPX, checkout, or PATH)."""
    def __init__(self, binary=None):
        root = Path(__file__).resolve().parents[2]
        candidates = [binary, os.environ.get("KERNEL_RPX"),
                      root / "bin/rpx", root / "target/release/rpx", root / "target/debug/rpx", shutil.which("rpx")]
        self.binary = next((Path(p).resolve() for p in candidates if p and Path(p).is_file()), None)
        if self.binary is None:
            raise FileNotFoundError("Build rpx with cargo build --release, or set KERNEL_RPX")

    def call(self, *args, check=True):
        result = subprocess.run([str(self.binary), *map(str, args)], capture_output=True, text=True)
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise KernelError({"status": "EXECUTION_FAILED", "error": result.stderr or result.stdout,
                               "exit_code": result.returncode}) from None
        if check and result.returncode:
            raise KernelError(report)
        return report

    def json_command(self, command, models, specification):
        """Read machine output through a temporary file, with paths passed without a shell."""
        with tempfile.TemporaryDirectory(prefix="kernel-compiler-") as directory:
            directory = Path(directory)
            spec, output = directory / "spec.json", directory / "result.json"
            spec.write_text(json.dumps(specification, separators=(",", ":")) + "\n")
            self.call(command, *models, spec, output)
            return json.loads(output.read_text())

    def verify(self, source, target, proof, request, *, work=None, live_facts=None):
        args = ["verify"]
        if work is not None:
            args += ["--work", str(work)]
        if live_facts is not None:
            args += ["--live-facts", str(live_facts)]
        return self.call(*args, source, target, proof, request, check=False)
