#!/usr/bin/env python3
"""Rebuild and verify the manual's complete examples using the current CLI.

This is an untrusted documentation replay, not an additional acceptance authority.
All MCM/RPX and mutation files are created in a temporary directory.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "docs/rpx/examples"
EXPECTED = {"redundant": 9, "elimination": 9, "piecewise": 9}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=ROOT / "target/release/rpx")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    kernel = args.kernel.resolve()
    commands = []

    def run(arguments, status, exit_code=0):
        proc = subprocess.run([str(kernel), *map(str, arguments)],
                              text=True, capture_output=True, check=False)
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"CLI did not return JSON: {proc.stdout!r} {proc.stderr!r}") from exc
        if proc.returncode != exit_code or report.get("status") != status:
            raise RuntimeError(f"unexpected CLI result: {arguments}: {proc.returncode}: {report}")
        commands.append({"operation": arguments[0], "status": status, "exit": proc.returncode})
        return report

    def write_rpa(path, certificate):
        path.write_text("RPA 11\n" + json.dumps(certificate, indent=1) + "\n", encoding="utf-8")

    results = []
    with tempfile.TemporaryDirectory(prefix="rpx-manual-") as tmp:
        temporary = Path(tmp)
        for name, obligations in EXPECTED.items():
            fixture = FIXTURES / name
            work = temporary / name
            work.mkdir()
            source, target = work / "source.mcm", work / "target.mcm"
            proof = work / "proof.rpx"
            for model, output in (("source", source), ("target", target)):
                run(["canonical", fixture / f"{model}.lp", output], "CANONICALIZED")
            run(["assemble", fixture / "proof.rpa", proof], "ASSEMBLED")
            readable = work / "readable.rpx"
            run(["assemble", fixture / "proof.rpas", readable], "ASSEMBLED")
            if readable.read_bytes() != proof.read_bytes():
                raise RuntimeError(f"{name}: readable source differs from exact JSON proof")
            success = run(["verify", source, target, proof], "VERIFIED")
            if success["statistics"]["obligations"] != obligations:
                raise RuntimeError(f"{name}: obligation count changed: {success}")

            recovered, encoded = work / "recovered.rpa", work / "recovered.rpx"
            run(["disassemble", proof, recovered], "DISASSEMBLED")
            run(["assemble", recovered, encoded], "ASSEMBLED")
            if encoded.read_bytes() != proof.read_bytes():
                raise RuntimeError(f"{name}: disassembly/reassembly changed RPX bytes")
            run(["verify", source, target, encoded], "VERIFIED")

            certificate = json.loads((fixture / "proof.rpa").read_text().split("\n", 1)[1])
            missing = copy.deepcopy(certificate)
            terminal = missing["forward"]["end"]
            if "Split" in terminal:
                terminal = terminal["Split"]["left"]["end"]
            terminal["Return"]["checks"].pop()
            missing_text, missing_binary = work / "missing.rpa", work / "missing.rpx"
            write_rpa(missing_text, missing)
            run(["assemble", missing_text, missing_binary], "ASSEMBLED")
            missing_result = run(["verify", source, target, missing_binary], "INVALID", 2)
            if "missing obligation" not in missing_result["message"]:
                raise RuntimeError(f"{name}: unexpected missing-obligation failure: {missing_result}")

            changed = copy.deepcopy(certificate)
            changed["input_integers"] = False
            changed_text, changed_binary = work/"weaker.rpa", work/"weaker.rpx"
            write_rpa(changed_text, changed)
            request_result = run(["assemble", changed_text, changed_binary], "INVALID", 2)

            wrong = copy.deepcopy(certificate)
            recovery = wrong["reverse"]["end"]["Return"]["map"][0]
            recovery["constant"] = "0" if name == "elimination" else "1"
            wrong_text, wrong_binary = work / "wrong.rpa", work / "wrong.rpx"
            write_rpa(wrong_text, wrong)
            run(["assemble", wrong_text, wrong_binary], "ASSEMBLED")
            wrong_result = run(["verify", source, target, wrong_binary], "INVALID", 2)
            if not any(message in wrong_result["message"] for message in
                       ("obligation mismatch", "non-tautological exact obligation")):
                raise RuntimeError(f"{name}: unexpected recovery failure: {wrong_result}")

            budget = run(["verify", "--work", "0", source, target, proof], "RESOURCE_LIMIT", 3)
            results.append({
                "example": name,
                "files": {file: digest(fixture / file)
                          for file in ("source.lp", "target.lp", "proof.rpa", "proof.rpas")},
                "rpx_sha256": digest(proof), "rpx_bytes": proof.stat().st_size,
                "guarantee": success["guarantee"], "statistics": success["statistics"],
                "roundtrip": "byte-identical and VERIFIED",
                "negative_results": {"missing_obligation": missing_result,
                                     "forbidden_goal_field": request_result,
                                     "wrong_recovery": wrong_result,
                                     "zero_work": budget},
            })
    receipt = {"kernel_sha256": digest(kernel), "examples": results,
               "commands": commands, "result": "PASS"}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "examples": len(results),
                      "negative_checks": 12, "cli_commands": len(commands)}, sort_keys=True))


if __name__ == "__main__":
    main()
