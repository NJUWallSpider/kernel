#!/usr/bin/env python3
"""Fresh solver-blind reformulation agents; no certificate or solution replay.

All mutations outside this checkout are confined to new reform_test/runs dirs.
The compiler is snapshotted before launch, so edits made while an agent runs do
not change its tools. Historical baseline artifacts are never given to agents.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = Path.home() / "Code/reform_test"
INTERPRETER = Path.home() / "miniforge3/envs/bigdata/bin/python"
BASE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PROMPT = "Analyze input/model.mps under the evaluation protocol and return your final committed result."
LOCK = threading.Lock()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def records(path):
    if not Path(path).is_file():
        return
    with Path(path).open(errors="replace") as stream:
        for line in stream:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def stamp(value):
    if isinstance(value, (float, int)):
        return value / 1000 if value > 1e11 else value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def session_metrics(run):
    """Same event/usage definitions as reform_test/scripts/eval_runs.py."""
    result = dict(llm_calls=0, tool_calls=0, tool_calls_failed=0, turns=0,
                  tokens_in=0, tokens_out=0, tokens_cache_read=0,
                  tokens_cache_write=0, tokens_total=0, cost_usd=0.0,
                  llm_time_s=0.0, llm_ttft_s=0.0, tool_time_s=0.0,
                  resolved_models=[], thinking_levels=[], model_fallback_used=False)
    starts, ends = {}, {}
    final = ""
    tool_inputs = []
    path = run / "session.jsonl"
    if not path.is_file():
        path = run / "run.json"
    for event in records(path):
        if event.get("type") == "model_change":
            result["resolved_models"].append(event.get("model"))
            result["model_fallback_used"] |= bool(event.get("resolvedModelIsFallback"))
        if event.get("type") == "thinking_level_change":
            result["thinking_levels"].append(event.get("thinkingLevel"))
        data = event.get("data") or {}
        if event.get("type") == "custom" and event.get("customType") == "tool_execution_start":
            if data.get("toolCallId"):
                starts[data["toolCallId"]] = stamp(event.get("timestamp"))
        if event.get("type") == "tool_execution_start":
            data = data or event
            if data.get("toolCallId"):
                starts[data["toolCallId"]] = stamp(event.get("timestamp"))
        message = event.get("message") or {}
        if message.get("role") == "toolResult":
            ends[message.get("toolCallId")] = stamp(message.get("timestamp"))
            result["tool_calls_failed"] += bool(message.get("isError"))
        if message.get("role") == "assistant":
            result["llm_calls"] += 1
            result["llm_time_s"] += (message.get("duration") or 0) / 1000
            result["llm_ttft_s"] += (message.get("ttft") or 0) / 1000
            usage = message.get("usage") or {}
            for key, field in (("tokens_in", "input"), ("tokens_out", "output"),
                               ("tokens_cache_read", "cacheRead"),
                               ("tokens_cache_write", "cacheWrite"),
                               ("tokens_total", "totalTokens")):
                result[key] += usage.get(field) or 0
            result["cost_usd"] += (usage.get("cost") or {}).get("total") or 0
            contents = message.get("content") or []
            text = "\n".join(c.get("text", "") for c in contents if c.get("type") == "text")
            if text:
                final = text
            for content in contents:
                if content.get("type") == "toolCall":
                    tool_inputs.append({"name": content.get("name"),
                                        "arguments": content.get("arguments")})
    result["tool_calls"] = len(starts) or len(tool_inputs)
    result["tool_time_s"] = sum(max(0, ends[k] - v) for k, v in starts.items()
                                if v is not None and ends.get(k) is not None)
    result["turns"] = sum(e.get("type") == "turn_start" for e in records(run / "run.json"))
    for key in ("llm_time_s", "llm_ttft_s", "tool_time_s", "cost_usd"):
        result[key] = round(result[key], 3)
    return result, final, tool_inputs


def path_inside(run, value, *, output=False):
    if not isinstance(value, str):
        raise ValueError("delivery path must be a string")
    candidate = (run / value).resolve()
    scope = run / "output" if output else run
    if not candidate.is_relative_to(scope.resolve()) or not candidate.is_file():
        raise ValueError(f"delivery path is missing or outside {scope.name}/: {value}")
    return candidate


def kernel_call(binary, *arguments):
    started = time.monotonic()
    process = subprocess.run([str(binary), *map(str, arguments)], capture_output=True, text=True)
    try:
        reply = json.loads(process.stdout)
    except json.JSONDecodeError:
        reply = {"status": "EXECUTION_FAILED", "message": process.stderr or process.stdout}
    return {"exit_code": process.returncode, "seconds": round(time.monotonic() - started, 4),
            "result": reply}


def canonical_model(binary, source, destination):
    if source.suffix == ".mcm":
        shutil.copyfile(source, destination)
    else:
        result = kernel_call(binary, "canonical", source, destination)
        if result["exit_code"]:
            raise ValueError(f"canonicalization failed: {result['result']}")
    exported = destination.with_suffix(".model.json")
    result = kernel_call(binary, "export-model", destination, exported)
    if result["exit_code"]:
        raise ValueError(f"model readback failed: {result['result']}")
    return json.loads(exported.read_text())


def normalized_model(model):
    """Exact semantic comparison allowing coordinate/row order and NAME changes."""
    names = [variable["name"] for variable in model["variables"]]
    if len(set(names)) != len(names):
        raise ValueError("duplicate variable names prevent standard-artifact comparison")
    rows = model["rows"]
    if len({row["name"] for row in rows}) != len(rows):
        raise ValueError("duplicate row names prevent standard-artifact comparison")
    def expression(expr):
        return {"constant": expr["constant"],
                "terms": sorted((names[index], scalar) for index, scalar in expr["terms"])}
    def normalized_row(row):
        # Standard MPS folds a row's affine constant into its RHS. Compare the
        # resulting inequality, allowing that exact representation change.
        constant = Fraction(row["expr"]["constant"])
        bounds = {side: None if row[side] is None else str(Fraction(row[side]) - constant)
                  for side in ("lower", "upper")}
        return {**row, **bounds, "expr": {**expression(row["expr"]), "constant": "0"}}
    return {"variables": sorted(model["variables"], key=lambda v: v["name"]),
            "rows": sorted((normalized_row(row) for row in rows),
                           key=lambda row: row["name"]),
            "objective": expression(model["objective"])}


def shape(model):
    return {"variables": len(model["variables"]), "rows": len(model["rows"]),
            "integers": sum(bool(v["integer"]) for v in model["variables"]),
            "nonzeros": sum(len(row["expr"]["terms"]) for row in model["rows"]),
            "objective_nonzeros": len(model["objective"]["terms"])}


def resolve_commit(run, final):
    manifest = run / "output/delivery.json"
    if manifest.is_file():
        delivery = json.loads(manifest.read_text())
        return path_inside(run, delivery["committed_model"], output=True), delivery, "delivery.json"
    models = [p for p in (run / "output").rglob("*")
              if p.is_file() and p.suffix.lower() in (".mps", ".lp")]
    mentions = re.findall(r"[\w./${}-]+\.(?:mps|lp)", final)
    for mention in reversed(mentions):
        matching = [p for p in models if p.name == Path(mention).name]
        if len(matching) == 1:
            return matching[0], None, "final answer"
    if len(models) == 1:
        return models[0], None, "single output model"
    if models:
        raise ValueError("multiple committed-model candidates require an explicit delivery manifest")
    return run / "input/model.mps", None, "no standard reformulation artifact"


def assess(run, binary, arm, *, expected_input_sha256):
    audit = run / "harness-assessment"
    audit.mkdir()
    metrics, final, tool_inputs = session_metrics(run)
    (run / "final-answer.txt").write_text(final)
    result = {"arm": arm, "metrics": metrics, "kernel_verified": False,
              "coverage_assessment_required": True, "errors": [], "pieces": []}
    # Explicit path violations are evidence, not a claim of OS sandboxing.
    outside = re.compile(r"(?:/Users/[^\s'\"]+|~/Code/[^\s'\"]+|(?:\.\./)+(?:runs|cases|tools|output)/[^\s'\"]*)")
    suspects = []
    for call in tool_inputs:
        encoded = json.dumps(call.get("arguments"), ensure_ascii=False)
        paths = [p for p in outside.findall(encoded) if not p.startswith(str(run))]
        if paths:
            suspects.append({"tool": call.get("name"), "paths": paths})
    result["transcript_scope_flags"] = suspects
    try:
        # The delivered proof must concern the pristine problem, even if an
        # agent accidentally overwrites its workspace input. run_agent captures
        # this trusted value before launch. Reassessments must likewise supply
        # a separately trusted hash, never a post-run mutable workspace manifest.
        expected = expected_input_sha256
        actual = digest(run / "input/model.mps")
        result.update(expected_input_sha256=expected, input_sha256=actual)
        if actual != expected:
            raise ValueError("original input changed after workspace construction; proof cannot be anchored to the pristine problem")
        source = canonical_model(binary, run / "input/model.mps", audit / "input.mcm")
        model, delivery, resolution = resolve_commit(run, final)
        if model.suffix.lower() not in (".lp", ".mps"):
            raise ValueError("committed_model must be a standard LP or MPS artifact")
        target = canonical_model(binary, model, audit / "committed.mcm")
        result.update(source_shape=shape(source), target_shape=shape(target),
                      committed=model != run / "input/model.mps",
                      model=str(model.relative_to(run)), model_resolution=resolution,
                      input_sha256=digest(run / "input/model.mps"), model_sha256=digest(model))
        if arm == "nomf":
            result["kernel_verification_required"] = False
        elif not delivery or not isinstance(delivery.get("pieces"), list) or not delivery["pieces"]:
            raise ValueError("compiler arm needs a nonempty output/delivery.json pieces list")
        else:
            result["relation"] = delivery.get("relation", "")
            if not result["relation"]:
                raise ValueError("delivery must state its precise relation")
            composition = delivery.get("composition")
            ordered_chain = (isinstance(composition, dict)
                             and composition.get("ordered_chain") is True)
            if ordered_chain:
                # Explicit ordered stages are a different contract from a set
                # of independent original-to-final proofs. Verify every stage
                # with its own indices and compose only safe, selected claims.
                from verify_staged_agent_delivery import inspect_delivery
                chain = inspect_delivery(run, binary, audit / "ordered-chain",
                                         expected_input_sha256=expected)
                result.update(ordered_chain=True, staged_review_version=chain["reviewer_version"],
                              staged_review=str(audit / "ordered-chain/staged-review.json"),
                              staged_review_sha256=digest(audit / "ordered-chain/staged-review.json"),
                              composed_claims=chain["composed_claims"], pieces=chain["pieces"],
                              kernel_verified=chain["status"] == "VERIFIED_CHAIN")
                if chain["errors"]:
                    raise ValueError("ordered chain review failed: " + "; ".join(chain["errors"]))
            for index, piece in enumerate([] if ordered_chain else delivery["pieces"]):
                paths = {key: path_inside(run, piece[key], output=True)
                         for key in ("source", "target", "proof", "request")}
                delivered_source = canonical_model(binary, paths["source"], audit / f"source-{index}.mcm")
                delivered_target = canonical_model(binary, paths["target"], audit / f"target-{index}.mcm")
                if normalized_model(delivered_source) != normalized_model(source):
                    raise ValueError(f"piece {index} source readback differs from original")
                if normalized_model(delivered_target) != normalized_model(target):
                    raise ValueError(f"piece {index} target differs from the committed standard artifact")
                request = json.loads(paths["request"].read_text())
                if isinstance(request, list):
                    request = {"claims": request}
                if not isinstance(request, dict):
                    raise ValueError("Request must be an object or legacy claim array")
                # Named equality allows a byte/coordinate reordered source.
                # RPX indices still refer to the delivered canonical source,
                # so substituting input.mcm here would verify the wrong model.
                verification = kernel_call(binary, "verify", audit / f"source-{index}.mcm",
                                           audit / f"target-{index}.mcm", paths["proof"], paths["request"])
                result["pieces"].append({"id": index,
                    "sha256": {key: digest(value) for key, value in paths.items()},
                    "claims": request.get("claims", []),
                    "points": request.get("points", []),
                    "improvements": request.get("improvements", []),
                    "bijections": request.get("bijections", []),
                    "verification": verification})
            if not ordered_chain:
                result["kernel_verified"] = all(p["verification"]["exit_code"] == 0
                    and p["verification"]["result"].get("status") == "VERIFIED" for p in result["pieces"])
            claims = [claim for piece in result["pieces"] for claim in piece["claims"]]
            if ordered_chain:
                result["claim_coverage_signal_scope"] = "stage_local; final contracts are in composed_claims"
            result["claim_coverage_signals"] = {
                "directional_claims": len(claims),
                "unrestricted_integer_forward": sum(not c.get("reverse")
                    and c.get("input_integers") and c.get("output_integers")
                    and c.get("input_objective_level") is None and c.get("input_halfspace") is None
                    for c in claims),
                "unrestricted_integer_reverse": sum(bool(c.get("reverse"))
                    and c.get("input_integers") and c.get("output_integers")
                    and c.get("input_objective_level") is None and c.get("input_halfspace") is None
                    for c in claims),
                "objective_unchecked": sum(c.get("objective") == "None" for c in claims),
                "restricted_claims": sum(c.get("input_objective_level") is not None
                    or c.get("input_halfspace") is not None for c in claims),
                "affine_inverse_claims": sum(c.get("inverse") is not None for c in claims),
            }
    except (ValueError, KeyError, OSError, json.JSONDecodeError, TypeError) as error:
        result["errors"].append(str(error))
    write_json(run / "assessment.json", result)
    return result


def create_workspace(batch, corpus, case, arm, interpreter, binary, api_doc):
    run = corpus / "runs" / f"{case}-{arm}-{batch.name}"
    run.mkdir()  # Never reuse or modify a historical workspace.
    for directory in ("input", "output", ".omp"):
        (run / directory).mkdir()
    shutil.copyfile(corpus / f"data/{case}.mps", run / "input/model.mps")
    (run / ".omp/config.yml").write_text(
        "python:\n  kernelMode: session\n  interpreter: " + json.dumps(str(interpreter)) + "\n")
    baseline_protocol = (corpus / "docs/NO_MIPFRAME.md").read_text()
    if arm == "compiler":
        # Keep the baseline's exploration, evidence and final-commit instructions.
        # Relax only its two prohibitions that would forbid the supplied API.
        replacements = {
            "You do NOT have access to mipframe or any other specialized model-analysis, presolve, reformulation, or optimization framework.":
                "You do NOT have access to mipframe. The supplied generic kernel_compiler proof-authoring and verification API is available; no other specialized framework is permitted.",
            "Do not use a package whose purpose is to parse, inspect, presolve, reformulate, or solve LP/MIP models. The purpose of this baseline is to test what can be achieved by reasoning directly over the MPS representation with general-purpose computational tools.":
                "Apart from the supplied kernel_compiler API, do not use a package whose purpose is to parse, inspect, presolve, reformulate, or solve LP/MIP models. Reason directly over the supplied formulation using general-purpose computational tools and your own explicit proof witnesses.",
        }
        for old, new in replacements.items():
            if old not in baseline_protocol:
                raise ValueError("nomf protocol changed; review the compiler exception before launch")
            baseline_protocol = baseline_protocol.replace(old, new, 1)
        baseline_protocol += "\n\n" + (ROOT / "docs/COMPILER_AGENT_PROTOCOL.md").read_text()
    (run / "protocol.md").write_text(baseline_protocol)
    if arm == "compiler":
        shutil.copytree(ROOT / "python/kernel_compiler", run / "compiler/python/kernel_compiler",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (run / "compiler/bin").mkdir()
        shutil.copy2(binary, run / "compiler/bin/rpx")
        shutil.copyfile(api_doc, run / "compiler/API.md")
        shutil.copyfile(ROOT / "docs/FORMAT.md", run / "compiler/FORMAT.md")
        (run / "compiler/python/tests").mkdir()
        shutil.copyfile(ROOT / "python/tests/test_proof.py", run / "compiler/python/tests/test_proof.py")
    write_json(run / "workspace-manifest.json", {"case": case, "arm": arm,
        "created": now(), "input_sha256": digest(run / "input/model.mps"),
        "protocol_sha256": digest(run / "protocol.md"), "interpreter": str(interpreter),
        "compiler_snapshot": {str(p.relative_to(run)): digest(p)
            for p in sorted((run / "compiler").rglob("*")) if p.is_file()},
        "baseline_solutions_exposed": False, "filesystem_boundary": "protocol only"})
    return run


def run_agent(run, batch, args, omp, binary, expected_input_sha256):
    arm = json.loads((run / "workspace-manifest.json").read_text())["arm"]
    command = [str(omp), "-p", "--cwd", str(run), "--session-dir", str(run / ".omp/sessions"),
               "--model", args.model, "--thinking", args.thinking, "--tools", args.tools,
               "--no-skills", "--no-extensions", "--no-rules", "--no-lsp", "--no-pty",
               "--append-system-prompt", str(run / "protocol.md"), "--mode", "json",
               "--max-time", args.max_time, PROMPT]
    env = {**os.environ, "PATH": f"{batch / 'bin'}:{BASE_PATH}"}
    if arm == "compiler":
        env["PYTHONPATH"] = str(run / "compiler/python")
        env["KERNEL_RPX"] = str(run / "compiler/bin/rpx")
    else:
        env.pop("PYTHONPATH", None)
        env.pop("KERNEL_RPX", None)
    (run / "cmd.txt").write_text(shlex.join(command) + "\n")
    started = time.monotonic()
    append_event(batch, {"event": "agent_start", "run": run.name})
    timeout = False
    with (run / "run.json").open("wb") as output, (run / "run.err").open("wb") as errors:
        process = subprocess.Popen(command, cwd=run, env=env, stdout=output, stderr=errors,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            code = process.wait(timeout=args.hard_timeout)
        except subprocess.TimeoutExpired:
            timeout = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    sessions = list((run / ".omp/sessions").rglob("*.jsonl"))
    if sessions:
        shutil.copyfile(max(sessions, key=lambda p: p.stat().st_mtime), run / "session.jsonl")
    end = {"event": "agent_end", "run": run.name, "exit_code": code,
           "wall_s": round(time.monotonic() - started, 3), "timed_out": timeout,
           "expected_input_sha256": expected_input_sha256}
    write_json(run / "execution.json", end)
    append_event(batch, end)
    assessment = assess(run, binary, arm, expected_input_sha256=expected_input_sha256)
    metrics = assessment["metrics"]
    if metrics["model_fallback_used"] or any(model and model.split("/")[-1] != args.model.split("/")[-1]
                                            for model in metrics["resolved_models"]):
        assessment["errors"].append("agent resolved a fallback or different model; matched-control comparison is invalid")
    if any(level != args.thinking for level in metrics["thinking_levels"]):
        assessment["errors"].append("agent thinking differs from the requested matched-control setting")
    write_json(run / "assessment.json", assessment)
    append_event(batch, {"event": "assessed", "run": run.name,
                        "kernel_verified": assessment["kernel_verified"],
                        "errors": assessment["errors"]})
    return {"run": run.name, "execution": end, "assessment": assessment}


def append_event(batch, event):
    event = {"ts": now(), **event}
    with LOCK:
        with (batch / "status.jsonl").open("a") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        print(json.dumps(event, ensure_ascii=False), flush=True)


def historical_metrics(corpus, cases):
    path = corpus / "results.csv"
    if not path.is_file():
        return []
    fields = ("test", "vars", "rows", "nonzeros", "integers", "agent_wall_s",
              "turns", "tool_calls", "tool_calls_failed", "tokens_total", "run_dir")
    with path.open() as stream:
        return [{key: row.get(key) for key in fields} for row in csv.DictReader(stream)
                if Path(row.get("test", "")).stem in cases
                and row.get("mipframe") in ("no", "nomf", "false", "0")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="test9,test86,test88")
    parser.add_argument("--arms", default="compiler,nomf")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--interpreter", type=Path, default=INTERPRETER)
    parser.add_argument("--kernel", type=Path, default=ROOT / "target/release/rpx")
    parser.add_argument("--api-doc", type=Path, default=ROOT / "docs/COMPILER_API.md")
    parser.add_argument("--id", default=datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--thinking", default="high")
    parser.add_argument("--tools", default="eval,read")
    parser.add_argument("--max-time", default="30m")
    parser.add_argument("--hard-timeout", type=float, default=38 * 60)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    cases, arms = args.cases.split(","), args.arms.split(",")
    if len(set(cases)) != len(cases) or len(set(arms)) != len(arms):
        parser.error("duplicate cases or arms")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.id) or args.jobs < 1:
        parser.error("id must be a path-safe label and jobs must be positive")
    if set(arms) - {"compiler", "nomf"}:
        parser.error("arms are compiler and nomf")
    for case in cases:
        if not re.fullmatch(r"test\d+", case) or not 8 <= int(case[4:]) <= 88:
            parser.error(f"case outside the previously tested demand corpus: {case}")
        if not (args.corpus / f"data/{case}.mps").is_file():
            parser.error(f"missing original model: {case}")
        if not (ROOT / f"cases/{case}/preparation.json").is_file():
            parser.error(f"missing evidence that case {case} has already been tested")
    omp = shutil.which("omp")
    if not omp or not args.interpreter.is_file() or not args.kernel.is_file():
        parser.error("omp, the pinned Python interpreter, and a built RPX kernel are required")
    if "compiler" in arms and (not args.api_doc.is_file()
            or not (ROOT / "python/kernel_compiler/__init__.py").is_file()):
        parser.error("Python compiler package and public API documentation must be ready before launch")
    batch = args.corpus / "runs" / f"compiler-batch-{args.id}"
    batch.mkdir()
    # Capture and load the independent evaluator before any agents start.
    # Later checkout edits must not change a running batch's review behavior.
    (batch / "harness").mkdir()
    for filename in ("run_compiler_agents.py", "verify_staged_agent_delivery.py"):
        shutil.copyfile(ROOT / "tools" / filename, batch / "harness" / filename)
    import verify_staged_agent_delivery  # noqa: F401: pin module before agent turns
    (batch / "bin").mkdir()
    (batch / "bin/omp").symlink_to(Path(omp).resolve())
    (batch / "kernel").mkdir()
    kernel = batch / "kernel/rpx"
    kernel.write_bytes(args.kernel.read_bytes())
    kernel.chmod(0o755)
    version = subprocess.run([omp, "--version"], capture_output=True, text=True).stdout.strip()
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    input_catalog = {case: digest(args.corpus / f"data/{case}.mps") for case in cases}
    write_json(batch / "batch.json", {"created": now(), "cases": cases, "arms": arms,
        "model": args.model, "thinking": args.thinking, "tools": args.tools,
        "max_time": args.max_time, "hard_timeout_s": args.hard_timeout,
        "omp_version": version, "omp_sha256": digest(omp), "kernel_sha256": digest(kernel),
        "git_head": git_head, "concurrency": args.jobs, "historical_baseline": historical_metrics(args.corpus, cases),
        "input_sha256": input_catalog,
        "harness_snapshot": {str(p.relative_to(batch)): digest(p)
                             for p in sorted((batch / "harness").glob("*.py"))},
        "historical_baseline_is_not_a_fresh_matched_control": True})
    workspaces = [create_workspace(batch, args.corpus, case, arm, args.interpreter,
                                  kernel, args.api_doc) for case in cases for arm in arms]
    expected_inputs = {run: input_catalog[run.name.split("-")[0]] for run in workspaces}
    if any(digest(run / "input/model.mps") != expected_inputs[run] for run in workspaces):
        raise ValueError("source changed during workspace preparation")
    if args.prepare_only:
        print(json.dumps({"status": "PREPARED_ONLY", "batch": str(batch),
                          "workspaces": [str(p) for p in workspaces]}))
        return 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_agent, run, batch, args, omp, kernel, expected_inputs[run])
                   for run in workspaces]
        results = [future.result() for future in futures]
    comparison = {"batch": str(batch), "runs": results,
                  "historical_baseline": historical_metrics(args.corpus, cases),
                  "quality_and_claim_coverage_review_required": True}
    pairs = []
    for case in cases:
        pair = {arm: next((r for r in results if r["run"].startswith(f"{case}-{arm}-")), None) for arm in arms}
        compiler, nomf = pair.get("compiler"), pair.get("nomf")
        if compiler and nomf:
            pair["wall_time_ratio_compiler_to_nomf"] = compiler["execution"]["wall_s"] / max(0.001, nomf["execution"]["wall_s"])
            pair["shape_delta_compiler_minus_nomf"] = {
                key: compiler["assessment"]["target_shape"][key] - nomf["assessment"]["target_shape"][key]
                for key in ("variables", "rows", "nonzeros", "integers")
            } if "target_shape" in compiler["assessment"] and "target_shape" in nomf["assessment"] else None
        pairs.append({"case": case, **pair})
    comparison["paired_comparisons"] = pairs
    write_json(batch / "comparison.json", comparison)
    print(batch / "comparison.json")
    compiler_results = [r for r in results if r["assessment"]["arm"] == "compiler"]
    return 0 if all(r["execution"]["exit_code"] == 0 and r["assessment"]["kernel_verified"]
                    and not r["assessment"]["errors"] for r in compiler_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
