#!/usr/bin/env python3
"""Serial, fresh-process Model.load comparison; no solver or proof search.

The benchmark times only Model.load. Exact model readback checks run afterward.
Run with --help for paths; large inputs/snapshots stay outside this audit folder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_hashes(path):
    return {str(p.relative_to(path)): sha256(p)
            for p in sorted(Path(path).rglob("*.py"))}


def worker(arguments):
    sys.path.insert(0, arguments.pythonpath)
    from kernel_compiler import Kernel, Model

    class TimedKernel(Kernel):
        def __init__(self, binary):
            super().__init__(binary)
            self.calls = []

        def call(self, *args, **kwargs):
            start = time.perf_counter()
            result = super().call(*args, **kwargs)
            self.calls.append({"command": str(args[0]),
                               "wall_s": time.perf_counter() - start})
            return result

    kernel = TimedKernel(arguments.binary)
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = time.perf_counter()
    model = Model.load(arguments.input, kernel)
    elapsed = time.perf_counter() - start
    load_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # On Darwin ru_maxrss is bytes, and excludes the native child processes.
    unit_factor = 1 if sys.platform == "darwin" else 1024
    result = {
        "arm": arguments.arm,
        "python_version": sys.version,
        "load_wall_s": elapsed,
        "parent_peak_before_load_bytes": before * unit_factor,
        "load_parent_peak_rss_bytes": load_peak * unit_factor,
        "native_calls_during_load": kernel.calls,
        "canonical_mcm_sha256": sha256(model.path),
        "statistics": model.stats(),
    }
    # Independent native MCM bytes must match the Python model's entire exact
    # representation, including model/name/order, rational values and domains.
    encoded = model.to_mcm()
    result["python_reencoded_mcm_sha256"] = hashlib.sha256(encoded).hexdigest()
    result["exact_native_mcm_roundtrip"] = (
        result["python_reencoded_mcm_sha256"] == arguments.oracle_mcm_sha256
        == result["canonical_mcm_sha256"])
    del encoded
    if arguments.oracle_json:
        with Path(arguments.oracle_json).open() as stream:
            expected = json.load(stream)
        exact = (model.name == expected["name"]
                 and len(model.vars) == len(expected["variables"])
                 and len(model.rows) == len(expected["rows"])
                 and model.objective.to_json() == expected["objective"]
                 and all(v.to_json() == data for v, data in
                         zip(model.vars, expected["variables"]))
                 and all(r.to_json() == data for r, data in
                         zip(model.rows, expected["rows"])))
        result["exact_native_exported_json_structure"] = exact
        del expected
    result["whole_worker_parent_peak_rss_bytes_including_validation"] = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit_factor)
    model.close()
    if not result["exact_native_mcm_roundtrip"] or result.get("exact_native_exported_json_structure") is False:
        raise RuntimeError("exact native model oracle mismatch")
    print(json.dumps(result, sort_keys=True))


def native(binary, *arguments):
    proc = subprocess.run([str(binary), *map(str, arguments)],
                          text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def main(arguments):
    if arguments.worker:
        worker(arguments)
        return
    if sys.platform != "darwin":
        raise RuntimeError("This recorded comparison expects Darwin ru_maxrss bytes")
    report_path = Path(arguments.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    binary, source = Path(arguments.binary).resolve(), Path(arguments.input).resolve()
    source_hash, binary_hash = sha256(source), sha256(binary)
    expected = arguments.expected_input_sha256
    if expected and expected != source_hash:
        raise RuntimeError("pristine input SHA-256 mismatch")
    report = {
        "kind": "supplied-input Model.load microbenchmark; not end-to-end Agent speed",
        "platform": platform.platform(), "python_executable": sys.executable,
        "python_version": sys.version, "input": str(source),
        "input_sha256": source_hash, "input_bytes": source.stat().st_size,
        "native_binary": str(binary), "native_sha256": binary_hash,
        "old_checkpoint": "231e6f40ce8c01afd9d93ef1e9496f74d0100703",
        "current_git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "memory_scope": "Darwin resource.RUSAGE_SELF.ru_maxrss bytes for the Python parent only; excludes native children, not a whole-tree peak",
        "timing_scope": "Model.load only; hashing, stats, reencoding and JSON-oracle validation are afterward",
        "cache_policy": "No OS cache flush. Native oracle preparation reads the same pristine input before measurements; six serial fresh processes, interleaved old/stream.",
        "runs": [],
    }
    with tempfile.TemporaryDirectory(prefix="kernel-load-comparison-") as directory:
        directory = Path(directory)
        packages = {}
        for arm, original in (("old", arguments.old_pythonpath), ("stream", arguments.new_pythonpath)):
            original = Path(original).resolve()
            destination = directory / arm / "kernel_compiler"
            shutil.copytree(original / "kernel_compiler", destination,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            packages[arm] = destination.parent
            report[arm + "_package"] = {
                "source": str(original), "files": package_hashes(destination)}
        oracle = directory / "native.mcm"
        exported = directory / "native.json"
        report["oracle_canonical_report"] = native(binary, "canonical", source, oracle)
        report["oracle_inspect_report"] = native(binary, "inspect-model", oracle)
        report["oracle_export_report"] = native(binary, "export-model", oracle, exported)
        oracle_hash = sha256(oracle)
        report["oracle_mcm_sha256"] = oracle_hash
        report["oracle_json_sha256"] = sha256(exported)
        for label, path in (("retained_mcm", arguments.retained_mcm),
                            ("retained_json", arguments.retained_json)):
            if path:
                actual = sha256(path)
                wanted = oracle_hash if label.endswith("mcm") else report["oracle_json_sha256"]
                if actual != wanted:
                    raise RuntimeError("retained native oracle differs: " + label)
                report[label] = {"path": str(Path(path).resolve()), "sha256": actual,
                                 "matches_fresh_native_oracle": True}
        for index, arm in enumerate(("old", "stream", "old", "stream", "old", "stream")):
            command = [sys.executable, str(Path(__file__).resolve()), "--worker",
                       "--arm", arm, "--pythonpath", str(packages[arm]),
                       "--binary", str(binary), "--input", str(source),
                       "--oracle-mcm-sha256", oracle_hash]
            # One full, independent native JSON structure comparison per arm;
            # all six runs additionally compare exact reencoded MCM bytes.
            if index < 2:
                command += ["--oracle-json", str(exported)]
            result = subprocess.run(command, text=True, capture_output=True, check=True)
            run = json.loads(result.stdout)
            run["sequence"] = index + 1
            report["runs"].append(run)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"sequence": index + 1, "arm": arm,
                              "load_wall_s": run["load_wall_s"],
                              "parent_peak_rss_bytes": run["load_parent_peak_rss_bytes"],
                              "exact": run["exact_native_mcm_roundtrip"]}), flush=True)
    report["input_unchanged"] = sha256(source) == source_hash
    report["binary_unchanged"] = sha256(binary) == binary_hash
    if not report["input_unchanged"] or not report["binary_unchanged"]:
        raise RuntimeError("input or binary changed")
    report["summary"] = {}
    report["all_statistics_equal"] = all(
        r["statistics"] == report["runs"][0]["statistics"] for r in report["runs"])
    report["all_canonical_hashes_equal"] = all(
        r["canonical_mcm_sha256"] == report["oracle_mcm_sha256"] for r in report["runs"])
    if not report["all_statistics_equal"] or not report["all_canonical_hashes_equal"]:
        raise RuntimeError("models differ between benchmark arms")
    for arm in ("old", "stream"):
        runs = [r for r in report["runs"] if r["arm"] == arm]
        report["summary"][arm] = {
            "runs": len(runs),
            "median_load_wall_s": statistics.median(r["load_wall_s"] for r in runs),
            "median_load_parent_peak_rss_bytes": statistics.median(r["load_parent_peak_rss_bytes"] for r in runs),
        }
    old, new = report["summary"]["old"], report["summary"]["stream"]
    report["summary"]["stream_over_old_wall_ratio"] = new["median_load_wall_s"] / old["median_load_wall_s"]
    report["summary"]["stream_over_old_parent_peak_rss_ratio"] = new["median_load_parent_peak_rss_bytes"] / old["median_load_parent_peak_rss_bytes"]
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["summary"], sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--arm", choices=("old", "stream"))
    parser.add_argument("--pythonpath")
    parser.add_argument("--oracle-mcm-sha256")
    parser.add_argument("--oracle-json")
    parser.add_argument("--old-pythonpath")
    parser.add_argument("--new-pythonpath")
    parser.add_argument("--binary", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--expected-input-sha256")
    parser.add_argument("--retained-mcm")
    parser.add_argument("--retained-json")
    parser.add_argument("--report")
    main(parser.parse_args())
