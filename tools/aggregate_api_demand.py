#!/usr/bin/env python3
"""Aggregate the per-case compiler-API demand analyses into the document's tables.

Reads one JSON analysis per case (the `per-case/` directory) plus the case metadata
harvested from the kernel tree and the reference corpus, and writes the markdown tables
used by `docs/COMPILER_API_DEMAND.md` and a machine-readable summary.

    python3 tools/aggregate_api_demand.py \
        --per-case bench/compiler-api-demand/per-case \
        --meta bench/compiler-api-demand/case_meta.json \
        --out-dir /tmp/api-demand-tables

Per-case analyses accept two shapes for `api_needs`: objects with the seven documented
fields, or `capability || scope || priority || why || sketch || replaces || evidence`
strings. Capability names are normalised against the vocabulary in
`bench/compiler-api-demand/ANALYSIS_BRIEF.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

VOCAB = {
    "MODEL_READBACK", "SCOPE_QUERIES", "TARGET_CONSTRUCTION", "EDIT_AUDIT", "RULE_BUILDERS",
    "BATCH_TEMPLATES", "CLAIM_PLANNING", "INCREMENTAL_VERIFY", "DIAGNOSTICS", "WORK_PREFLIGHT",
    "ORACLE_CHECKS", "COUNTEREXAMPLE_TESTING", "WITNESS_CHECKING", "PROJECTION_BINDING",
    "OBJECTIVE_ALGEBRA", "MULTI_PART_ASSEMBLY", "REUSE_LIBRARY", "MODEL_SHAPE_STATS",
    "EXACT_ARITHMETIC", "LIMIT_POLICY",
}
SCOPE_KINDS = ("case_only", "shared", "universal")
NEED_FIELDS = ("capability", "scope", "priority", "why", "sketch", "replaces", "evidence")


def case_key(case: str) -> int:
    return int(re.search(r"(\d+)", case).group(1))


def clip(text, width: int) -> str:
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= width else text[: width - 1] + "…"


def normalize_capability(raw: str) -> str:
    text = str(raw).strip().strip("`")
    if text.startswith("NEW:"):
        return "NEW:" + re.split(r"[:(]", text[4:])[0].strip()[:40]
    head = re.split(r"[:（(\s]| - ", text)[0].strip()
    return head if head in VOCAB else f"OTHER:{head[:40]}"


def normalize_scope(raw: str) -> tuple[str, str]:
    text = str(raw).strip().strip("`")
    head = re.split(r"[ :(（]", text)[0].strip()
    return (head if head in SCOPE_KINDS else "shared"), text


def pick(data: dict, *keys) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return " ".join(value)
    return ""


def load(per_case: Path) -> dict[str, dict]:
    cases = {}
    for path in sorted(per_case.glob("test*.json")):
        if not re.fullmatch(r"test\d+\.json", path.name):
            continue
        case = path.stem
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            print(f"!! {case}: invalid JSON ({exc})", file=sys.stderr)
            continue
        if isinstance(data, dict) and isinstance(data.get("json"), str):
            try:  # some analysts wrote the compact tool wrapper {"case":…, "json":"…"}
                data = json.loads(data["json"])
            except json.JSONDecodeError as exc:
                print(f"!! {case}: wrapper payload is not JSON ({exc})", file=sys.stderr)
                continue
        if not isinstance(data, dict):
            print(f"!! {case}: payload is {type(data).__name__}, skipping", file=sys.stderr)
            continue
        needs = []
        for raw in data.get("api_needs", []):
            if isinstance(raw, dict):
                need = {key: raw.get(key, "") for key in NEED_FIELDS}
                try:
                    need["priority"] = int(raw.get("priority", 9))
                except (TypeError, ValueError):
                    need["priority"] = 9
            else:
                parts = [p.strip() for p in str(raw).split("||")]
                if len(parts) != 7:
                    print(f"!! {case}: need with {len(parts)} fields", file=sys.stderr)
                    parts = (parts + ["?"] * 7)[:7]
                need = dict(zip(NEED_FIELDS, parts))
                try:
                    need["priority"] = int(need["priority"])
                except ValueError:
                    need["priority"] = 9
            need["capability_raw"] = need["capability"]
            need["capability"] = normalize_capability(need["capability"])
            need["scope_kind"], need["scope_raw"] = normalize_scope(need["scope"])
            need["scope"] = need["scope_kind"]
            needs.append(need)
        data["api_needs"] = sorted(needs, key=lambda n: n["priority"])
        data["top_capability"] = normalize_capability(data.get("top_capability", ""))
        cases[case] = data
    return cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-case", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    by_case = {m["case"]: m for m in json.loads(args.meta.read_text())}
    cases = load(args.per_case)
    print(f"loaded {len(cases)} case analyses", file=sys.stderr)
    missing = [f"test{n}" for n in [8, 9] + list(range(10, 89)) if f"test{n}" not in cases]
    if missing:
        print(f"missing: {missing}", file=sys.stderr)

    rows = ["| case | reformulation | claim class | scale (vars/rows, RPA) | top capability | also demanded |",
            "|---|---|---|---|---|---|"]
    for case in sorted(cases, key=case_key):
        d = cases[case]
        meta = by_case.get(case, {})
        top = d.get("top_capability", "?")
        others = [n["capability"] for n in d["api_needs"] if n["capability"] != top]
        scale = "—"
        if meta.get("rpa"):
            scale = (f"{meta['ov']}/{meta['orr']} → {meta['v']}/{meta['rr']}; "
                     f"{meta['rpa']/1048576:.1f} MB rpa; req {meta['req']/1024:.1f} KB")
        elif meta.get("ov"):
            scale = (f"{meta['ov']}/{meta['orr']} → {meta['v']}/{meta['rr']}; "
                     f"no single proof.rpa (certificate is split into parts); req {meta['req']/1024:.1f} KB")
        rows.append(f"| {case} | {clip(pick(d, 'reformulation', 'headline', 'summary', 'edit_summary'), 150)} | "
                    f"{clip(pick(d, 'claim_class', 'class', 'claim_classes', 'kind_class_note'), 90)} | "
                    f"{scale} | `{top}` | {', '.join(f'`{o}`' for o in others[:6]) if others else '—'} |")
    (args.out_dir / "table_rows.md").write_text("\n".join(rows) + "\n")

    demand, sketches, whys, evidence = (defaultdict(list) for _ in range(4))
    scopes: dict[str, Counter] = defaultdict(Counter)
    for case, d in cases.items():
        for need in d["api_needs"]:
            cap = need["capability"]
            demand[cap].append((case, need["priority"]))
            scopes[cap][need["scope"]] += 1
            if len(sketches[cap]) < 3:
                sketches[cap].append(f"{case}: {clip(need['sketch'], 150)}")
            if len(whys[cap]) < 3:
                whys[cap].append(f"{case}: {clip(need['why'], 150)}")
            if len(evidence[cap]) < 3:
                evidence[cap].append(f"{case}: {clip(need['evidence'], 110)}")
    ranked = sorted(demand.items(), key=lambda kv: (-len(kv[1]), sum(p for _, p in kv[1])))

    cats = ["| capability | cases | share | median priority | scope mix | sketches |",
            "|---|---:|---:|---:|---|---|"]
    for cap, entries in ranked:
        prios = sorted(p for _, p in entries)
        mix = ", ".join(f"{k} {v}" for k, v in scopes[cap].most_common())
        cats.append(f"| `{cap}` | {len(entries)} | {len(entries)*100/len(cases):.0f}% | "
                    f"{prios[len(prios)//2]} | {mix} | {'; '.join(clip(s, 120) for s in sketches[cap][:2])} |")
    (args.out_dir / "table_caps.md").write_text("\n".join(cats) + "\n")

    detail = ["| capability | cases | priority 1 | priority 2 | priority 3+ |", "|---|---:|---|---|---|"]
    for cap, entries in ranked:
        detail.append(f"| `{cap}` | {len(entries)} | "
                      f"{', '.join(sorted([c for c, p in entries if p == 1], key=case_key)) or '—'} | "
                      f"{', '.join(sorted([c for c, p in entries if p == 2], key=case_key)) or '—'} | "
                      f"{', '.join(sorted([c for c, p in entries if p >= 3], key=case_key)) or '—'} |")
    (args.out_dir / "table_cap_cases.md").write_text("\n".join(detail) + "\n")

    notes = ["| capability | why (first cases) | evidence (first cases) |", "|---|---|---|"]
    for cap, entries in ranked:
        notes.append(f"| `{cap}` ({len(entries)} cases) | {'; '.join(clip(w, 170) for w in whys[cap][:2])} | "
                     f"{'; '.join(clip(e, 150) for e in evidence[cap][:2])} |")
    (args.out_dir / "table_cap_notes.md").write_text("\n".join(notes) + "\n")

    appendix = []
    for case in sorted(cases, key=case_key):
        d = cases[case]
        meta = by_case.get(case, {})
        scale = ""
        if meta.get("rpa"):
            scale = (f" · {meta['ov']}/{meta['orr']} → {meta['v']}/{meta['rr']} vars/rows · "
                     f"rpa {meta['rpa']/1048576:.1f} MB · req {meta['req']/1024:.1f} KB · "
                     f"generator {meta['preps']} ({meta['plines']} lines)")
        elif meta.get("ov"):
            scale = (f" · {meta['ov']}/{meta['orr']} → {meta['v']}/{meta['rr']} vars/rows · "
                     f"certificate split into parts (no single rpa) · "
                     f"generator {meta['preps']} ({meta['plines']} lines)")
        appendix.append(f"**{case}** — {clip(pick(d, 'reformulation', 'headline', 'summary', 'edit_summary'), 150)}{scale}")
        appendix.append("")
        claims, encoding = d.get("claims") or [], d.get("proof_encoding") or []
        if claims:
            appendix.append(f"- claims: {clip(' | '.join(str(c) for c in claims[:2]), 190)}")
        if encoding:
            appendix.append(f"- proof: {clip(' | '.join(str(c) for c in encoding[:2]), 190)}")
        if d["api_needs"]:
            appendix.append("- needs: " + " · ".join(
                f"`{n['capability']}`(p{n['priority']}) {clip(n['why'], 80)}" for n in d["api_needs"][:4]))
            appendix.append(f"- api: {clip(d['api_needs'][0]['sketch'], 150)} · "
                            f"ev: {clip(d['api_needs'][0]['evidence'], 120)}")
        if d.get("friction"):
            appendix.append(f"- friction: {clip(d['friction'][0], 190)}")
        appendix.append("")
    (args.out_dir / "appendix_cases.md").write_text("\n".join(appendix) + "\n")

    summary = {
        "cases": len(cases),
        "capabilities": [
            {"capability": cap, "cases": len(entries),
             "priority_1": sorted([c for c, p in entries if p == 1], key=case_key),
             "priority_2": sorted([c for c, p in entries if p == 2], key=case_key),
             "priority_3plus": sorted([c for c, p in entries if p >= 3], key=case_key),
             "scope_mix": dict(scopes[cap])}
            for cap, entries in ranked],
        "per_case": {case: {
            "reformulation": pick(d, 'reformulation', 'headline', 'summary', 'edit_summary'),
            "claim_class": pick(d, 'claim_class', 'class', 'claim_classes', 'kind_class_note'),
            "top_capability": d.get("top_capability", ""),
            "needs": [{k: n[k] for k in NEED_FIELDS} for n in d["api_needs"]]}
            for case, d in cases.items()},
    }
    (args.out_dir / "capability_demand.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"wrote tables for {len(cases)} cases to {args.out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
