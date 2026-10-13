#!/usr/bin/env python3
"""Condense one external reformulation-agent run into a bounded markdown digest.

The reference corpus lives outside this repository (default
``/Users/bhz/Code/reform_test``). Each run directory holds the solver-blind
agent's transcript (``session.jsonl`` or, for the two earliest runs, a
root-level session export), its final report (``output/report.md``) and the
independent audit script it wrote (``output/verify.py``). The digest keeps the
report verbatim and reduces the transcript to the agent's own text, its tool
calls (``eval`` code included) and its tool results, so a downstream reader can
see what the agent had to do by hand without loading the raw session.

    python3 tools/digest_reform_run.py test36 > /tmp/digest-test36.md

Options bound the output; defaults are sized for one agent reading one case.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_CORPUS = Path(os.environ.get("REFORM_TEST_ROOT", "/Users/bhz/Code/reform_test"))

# Sessions that predate the per-run session.jsonl export. Each earlier run also
# has a superseded attempt whose transcript is kept for context.
EARLY_SESSIONS = {
    "test8": ("2026-10-03T15-19-03-785Z_01a10258-e969-7339-980d-cac56faffa32.jsonl",
              ["2026-10-03T12-31-56-840Z_01a101bf-e9a8-7259-909d-6028b1c2e2a4.jsonl"]),
    "test9": ("2026-10-03T16-46-24-305Z_01a102a8-e031-73b5-9ff7-23759f722c70.jsonl",
              ["2026-10-03T16-03-03-541Z_01a10281-30f5-7667-a256-13b02b786c67.jsonl"]),
}

CAP_TEXT = 1200        # agent commentary per message
CAP_CODE = 4000        # eval code per call
CAP_RESULT = 700       # successful tool result preview
CAP_RESULT_ERR = 1800  # failing tool result (the friction signal)
CAP_REPORT = 0         # 0 = keep the final report verbatim


def clip(text: str, cap: int) -> tuple[str, bool]:
    text = text.rstrip()
    if cap and len(text) > cap:
        return text[:cap], True
    return text, False


def find_run_dir(corpus: Path, case: str) -> Path | None:
    runs = corpus / "runs"
    exact = runs / f"{case}-nomf-B1"
    if exact.is_dir():
        return exact
    for entry in sorted(runs.glob(f"{case}-*")):
        if entry.is_dir():
            return entry
    return None


def find_session(corpus: Path, case: str, run_dir: Path | None) -> tuple[Path | None, list[Path]]:
    if run_dir is not None:
        local = run_dir / "session.jsonl"
        if local.is_file():
            return local, []
    if case in EARLY_SESSIONS:
        main, earlier = EARLY_SESSIONS[case]
        main_path = corpus / main
        extra = [corpus / name for name in earlier if (corpus / name).is_file()]
        return (main_path if main_path.is_file() else None), extra
    return None, []


def csv_row(corpus: Path, case: str) -> dict[str, str] | None:
    path = corpus / "results.csv"
    if not path.is_file():
        return None
    with path.open() as handle:
        for row in csv.DictReader(handle):
            test = row.get("test", "").removesuffix(".mps")
            if test == case and row.get("mipframe") == "no":
                return row
    return None


def walk_session(path: Path) -> dict:
    """Extract the ordered agent-visible events, bounded per event."""
    events: list[dict] = []
    stats = {"messages": 0, "evals": 0, "other_calls": 0, "errors": 0,
             "truncated": 0, "eval_code_chars": 0}
    errors: list[str] = []
    with path.open(errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = record.get("type")
            if kind != "message":
                continue
            stats["messages"] += 1
            role = record.get("message", {}).get("role")
            content = record.get("message", {}).get("content")
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            if not isinstance(content, list):
                continue
            if role == "assistant":
                for item in content:
                    item_type = item.get("type")
                    if item_type in ("text", "reasoning", "thinking"):
                        text, cut = clip(str(item.get("text", "")), CAP_TEXT)
                        stats["truncated"] += cut
                        if text:
                            events.append({"kind": "agent", "text": text})
                    elif item_type == "toolCall":
                        name = item.get("name", "?")
                        args = item.get("arguments", {})
                        if name == "eval":
                            code = str(args.get("code", ""))
                            stats["evals"] += 1
                            stats["eval_code_chars"] += len(code)
                            text, cut = clip(code, CAP_CODE)
                            stats["truncated"] += cut
                            events.append({"kind": "eval", "args": {"title": args.get("title")},
                                           "text": text, "cut": cut})
                        else:
                            stats["other_calls"] += 1
                            events.append({"kind": "call", "name": name,
                                           "text": json.dumps(args, sort_keys=True)[:CAP_RESULT],
                                           "intent": item.get("intent") or args.get("i")})
            elif role == "toolResult":
                is_error = bool(record.get("message", {}).get("isError"))
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                body = "\n".join(parts)
                if is_error:
                    stats["errors"] += 1
                    head = next((ln for ln in body.splitlines() if ln.strip()), "")
                    errors.append(head.strip()[:300])
                    text, cut = clip(body, CAP_RESULT_ERR)
                else:
                    text, cut = clip(body, CAP_RESULT)
                stats["truncated"] += cut
                events.append({"kind": "result", "error": is_error, "text": text, "cut": cut})
    return {"events": events, "stats": stats, "errors": errors}


FRAMEWORK_MEMBERS = re.compile(r"\b(?:mf|mipframe)\.([A-Za-z_][A-Za-z0-9_]*)(?=\s*[\(\[])")
PRIMITIVES = (
    ("Fraction", re.compile(r"\bFraction\(")),
    ("Decimal", re.compile(r"\bDecimal\(")),
    ("re.compile", re.compile(r"\bre\.compile\(")),
    ("json.loads", re.compile(r"\bjson\.loads\(")),
    ("json.dumps", re.compile(r"\bjson\.dumps\(")),
    ("hashlib", re.compile(r"\bhashlib\.sha256\(")),
    ("subprocess", re.compile(r"\bsubprocess\.(?:run|Popen|check)")),
    ("collections", re.compile(r"\b(?:Counter|defaultdict|deque)\(")),
    ("sorted(", re.compile(r"\bsorted\(")),
)


def framework_members(events: list[dict]) -> list[str]:
    """Framework members the eval code touched.

    Every run in this corpus is a *solver-blind baseline* run, so this is normally
    empty: a hit means the agent had a framework at hand. Only `mf.`/`mipframe.`
    are counted, because a bare `m.` is usually the agent's own local variable.
    """
    seen: dict[str, int] = {}
    for event in events:
        if event["kind"] != "eval":
            continue
        for name in FRAMEWORK_MEMBERS.findall(event["text"]):
            seen[name] = seen.get(name, 0) + 1
    return [f"{name}({count})" for name, count in sorted(seen.items(), key=lambda kv: -kv[1])]


def primitive_census(events: list[dict]) -> list[str]:
    """Standard-library primitives the agent reached for, i.e. what it hand-rolled."""
    counts = {label: 0 for label, _ in PRIMITIVES}
    for event in events:
        if event["kind"] != "eval":
            continue
        for label, pattern in PRIMITIVES:
            counts[label] += len(pattern.findall(event["text"]))
    return [f"{label}({count})" for label, count in counts.items() if count]


def render(corpus: Path, case: str, opts: argparse.Namespace) -> str:
    run_dir = find_run_dir(corpus, case)
    session, earlier = find_session(corpus, case, run_dir)
    out: list[str] = []
    add = out.append

    add(f"# Reformulation agent digest: {case}")
    add("")
    add(f"- corpus: `{corpus}`")
    add(f"- run dir: `{run_dir}`" if run_dir else "- run dir: MISSING")
    add(f"- session: `{session}`" if session else "- session: MISSING")
    for path in earlier:
        add(f"- superseded attempt transcript (context only): `{path}`")
    model = (run_dir / "input/model.mps") if run_dir else None
    if model and model.is_file():
        add(f"- model: `{model}` ({model.stat().st_size:,} bytes)")
    row = csv_row(corpus, case)
    if row:
        keys = ["turns", "tool_calls", "tool_calls_failed", "tokens_in", "tokens_out",
                "tokens_total", "llm_time_s", "tool_time_s", "agent_wall_s", "cost_usd",
                "committed"]
        add("- evaluation row: " + ", ".join(f"{k}={row[k]}" for k in keys if k in row))
        add("- model shape (original): "
            + ", ".join(f"{k}={row[k]}" for k in
                        ("orig_vars", "orig_rows", "orig_nonzeros", "orig_integers") if k in row))
        add("- model shape (reformulated): "
            + ", ".join(f"{k}={row[k]}" for k in
                        ("vars", "rows", "nonzeros", "integers") if k in row))
        add("- solver outcome original -> reformulated: "
            + f"{row.get('orig_highs_status')}/{row.get('orig_highs_obj')}"
            + f" -> {row.get('highs_status')}/{row.get('highs_obj')}")
    add("")

    if run_dir:
        for name, note in (("output/report.md", "final report (verbatim)"),
                           ("output/verify.py", "agent's independent audit script (read directly)"),
                           ("output/audit.json", "agent's machine-readable audit (query with jq)")):
            path = run_dir / name
            if path.is_file():
                add(f"- `{name}`: {path.stat().st_size:,} bytes - {note}")
        add("")

    report = (run_dir / "output/report.md") if run_dir else None
    if report and report.is_file():
        add("## Final report")
        add("")
        text = report.read_text(errors="replace")
        text, cut = clip(text, CAP_REPORT)
        add(text)
        if cut:
            add("\n[report truncated]")
        add("")

    if session is None:
        add("## Transcript")
        add("")
        add("No machine-readable transcript is available for this run; the report and the")
        add("workspace artifacts under the run dir are the evidence.")
        return "\n".join(out)

    walked = walk_session(session)
    stats = walked["stats"]
    add("## Transcript")
    add("")
    add(f"- messages: {stats['messages']}, eval calls: {stats['evals']}, "
        f"other tool calls: {stats['other_calls']}, failing tool results: {stats['errors']}")
    add(f"- eval code characters: {stats['eval_code_chars']:,}")
    members = framework_members(walked["events"])
    add("- framework members touched in eval code: " + (", ".join(members[:40]) if members else "none (solver-blind baseline run)"))
    census = primitive_census(walked["events"])
    if census:
        add("- stdlib primitives the agent used in eval code (what it hand-rolled): " + ", ".join(census))
    add("")
    for event in walked["events"]:
        if event["kind"] == "agent":
            add(f"**agent**: {event['text']}")
            add("")
        elif event["kind"] == "eval":
            title = (event.get("args") or {}).get("title") or ""
            marker = " [truncated]" if event.get("cut") else ""
            add(f"**eval** ({title}){marker}:")
            add("")
            add("```python")
            add(event["text"])
            add("```")
            add("")
        elif event["kind"] == "call":
            add(f"**{event['name']}** ({event.get('intent') or ''}): `{event['text']}`")
            add("")
        else:
            label = "error" if event["error"] else "result"
            marker = " [truncated]" if event.get("cut") else ""
            add(f"**{label}**{marker}:")
            add("")
            add("```")
            add(event["text"])
            add("```")
            add("")
    if walked["errors"]:
        add("## Failing tool results (first line each)")
        add("")
        for line in dict.fromkeys(walked["errors"]):
            add(f"- {line}")
        add("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", help="case id, e.g. test36")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                        help=f"reference corpus root (default {DEFAULT_CORPUS})")
    parser.add_argument("--out", type=Path, help="write here instead of stdout")
    args = parser.parse_args(argv)
    if not args.corpus.is_dir():
        print(f"corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    digest = render(args.corpus, args.case, args)
    if args.out:
        args.out.write_text(digest)
        print(f"{args.out}: {len(digest):,} chars", file=sys.stderr)
    else:
        sys.stdout.write(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
