#!/usr/bin/env python3
"""Check local Markdown links in the current docs and repository entry point.

Historical evidence outside docs retains its original snapshot references.
This checks files and Markdown heading anchors without network access.
"""
from collections import Counter
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def prose(path):
    fence = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def anchors(path):
    seen = Counter()
    result = set()
    for _, line in prose(path):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            slug = re.sub(r"[^\w\- ]", "", heading[1].lower()).replace(" ", "-")
            count = seen[slug]
            seen[slug] += 1
            result.add(f"{slug}-{count}" if count else slug)
    return result


def main():
    errors = []
    checked = 0
    cache = {}
    paths = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for path in paths:
        for number, line in prose(path):
            line = re.sub(r"(`+).*?\1", "", line)
            for link in re.finditer(r"\[[^\]\n]*\]\(([^)\n]+)\)", line):
                raw = link[1].strip().strip("<>")
                url = urlsplit(raw)
                if url.scheme or url.netloc:
                    continue
                checked += 1
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                problem = None
                if not target.exists():
                    problem = "missing file"
                elif url.fragment and target.suffix == ".md":
                    if target not in cache:
                        cache[target] = anchors(target)
                    if unquote(url.fragment) not in cache[target]:
                        problem = "missing heading"
                if problem:
                    errors.append(f"{path.relative_to(ROOT)}:{number}: {problem}: {raw}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {checked} local links in {len(paths)} current Markdown documents")


if __name__ == "__main__":
    main()
