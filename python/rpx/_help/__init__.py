"""Offline documentation discovery. This module only inspects definitions."""

import ast
import difflib
import inspect
import re
from functools import lru_cache
from importlib import resources

SCHEMA = "rpx.help/1"
# Only navigation metadata lives here. Contracts come from definitions and stubs.
GUIDES = {
    "quickstart": (
        "Install and verify your first elimination proof",
        "install eliminate variable first proof",
        ["workflow", "Proof", "ModelBuilder"],
    ),
    "workflow": (
        "The proof authoring loop",
        "goals mapping finish certify",
        ["Scope.map", "Scope.prove", "Scope.finish", "delivery"],
    ),
    "ownership": (
        "Models, coordinate spaces, and exact arithmetic",
        "edit substitute stale goal sealed scope float rational",
        ["Model", "Q", "Expr", "Scope.map"],
    ),
    "derivations": (
        "Select facts and derive conclusions",
        "linear round rewrite substitution zero sum parity plotkin subset",
        ["Derive", "Fact", "LinCombination", "branches"],
    ),
    "branches": (
        "Splits and explicit Cases",
        "continuous integer assumption contradiction",
        ["Scope.split", "Derive.cases", "Cases"],
    ),
    "lifts.interval": (
        "Interval extensions",
        "lower upper construction",
        ["IntervalSpec", "Scope.lift_intervals", "Generated"],
    ),
    "lifts.menu": (
        "Menu extensions",
        "options activation index",
        ["MenuSpec", "Scope.lift_menus", "Generated"],
    ),
    "lifts.signed": (
        "Signed extensions",
        "positive negative capacity",
        ["SignedSpec", "Scope.lift_signed", "Generated"],
    ),
    "lifts.flow": (
        "Flow decomposition extensions",
        "commodities graph recovery",
        ["FlowSpec", "FlowGroup", "Scope.lift_flow", "Generated"],
    ),
    "lifts.subflow": (
        "Subflow extensions",
        "demands graph remainder",
        ["SubflowSpec", "SubflowGroup", "Scope.lift_subflow", "Generated"],
    ),
    "delivery": (
        "Bundles, Chains, audits, and verification budgets",
        "artifact portable resource limits certification",
        ["Bundle", "Chain", "VerificationReport", "Proof.compile"],
    ),
    "large-models": (
        "Bounded inspection and batch expression construction",
        "views performance million native dot quicksum",
        ["VariablesView", "Expr.dot", "quicksum"],
    ),
    "troubleshooting": (
        "Recover from common errors",
        "error mapping ownership derivation stale sealed resource",
        ["MappingError", "ScopeError", "UnprovedGoalError", "ResourceLimitError"],
    ),
    "agent": (
        "Agent task navigation and completion criteria",
        "automation discovery search workflow",
        ["quickstart", "workflow", "troubleshooting"],
    ),
}


def sections(doc):
    """Split Markdown-style named sections without executing example code."""
    result = {}
    name = "Description"
    lines = []
    for line in (doc or "").splitlines():
        if line.startswith("## "):
            result[name] = "\n".join(lines).strip()
            name, lines = line[3:].strip(), []
        else:
            lines.append(line)
    result[name] = "\n".join(lines).strip()
    return {k: v for k, v in result.items() if v}


def declarations():
    """Read packaged types as syntax, never evaluate annotations/defaults."""
    package = resources.files("rpx")
    result = {}
    for filename in (
        "_native.pyi",
        "proof.pyi",
        "artifacts.pyi",
        "lowlevel.pyi",
        "specs.py",
    ):
        tree = ast.parse(package.joinpath(filename).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                result[node.name] = node
    return result


def signature(node, name):
    constructor = isinstance(node, ast.ClassDef)
    if constructor:
        init = next(
            (
                n
                for n in node.body
                if isinstance(n, ast.FunctionDef) and n.name == "__init__"
            ),
            None,
        )
        if init is None:
            dataclass = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Name)
                and d.func.id == "dataclass"
                for d in node.decorator_list
            )
            fields = (
                [n for n in node.body if isinstance(n, ast.AnnAssign)]
                if dataclass
                else []
            )
            return (
                name + "(" + ", ".join(ast.unparse(n) for n in fields) + ")"
                if fields
                else None
            )
        node = init
    if isinstance(node, ast.AnnAssign):
        return name + ": " + ast.unparse(node.annotation)
    if not isinstance(node, ast.FunctionDef):
        return None
    if any(isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list):
        return name + ": " + (ast.unparse(node.returns) if node.returns else "Any")
    args = ast.unparse(node.args)
    args = re.sub(r"^(self|cls)(, /)?(, )?", "", args)
    result = name + "(" + args + ")"
    if node.returns and not constructor:
        result += " -> " + ast.unparse(node.returns)
    return result


def field_doc(doc, name, section="Fields"):
    content = sections(doc).get(section, "")
    match = re.search(
        r"^" + re.escape(name) + r":\s*(.+?)(?=^\w+:|\Z)", content, re.M | re.S
    )
    return match[1].strip() if match else ""


def record(identifier, category, doc, sig=None, related=()):
    parts = sections(doc)
    summary = re.split(r"(?<=\.)\s|\n", next(iter(parts.values()), ""), maxsplit=1)[0]
    return dict(
        identifier=identifier,
        category=category,
        title=identifier,
        summary=summary,
        signature=sig,
        sections=parts,
        related=list(related),
    )


@lru_cache(maxsize=1)
def topics():
    import rpx
    from rpx import lowlevel

    result = {}
    decls = declarations()
    for module, prefix, names in (
        (rpx, "", rpx.__all__),
        (lowlevel, "lowlevel.", lowlevel.__all__),
    ):
        for name in names:
            obj = getattr(module, name)
            node = decls.get(name)
            identifier = prefix + name
            doc = inspect.getdoc(obj) or ""
            result[identifier] = record(identifier, "api", doc, signature(node, name))
            if not isinstance(node, ast.ClassDef) or issubclass(obj, BaseException):
                continue
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    key = member.name
                    if key == "__init__":
                        continue
                    value = inspect.getattr_static(obj, key, None)
                    if isinstance(value, (classmethod, staticmethod)):
                        value = value.__func__
                    member_doc = (
                        (
                            field_doc(doc, key, "Operators")
                            if key.startswith("__")
                            else ""
                        )
                        or inspect.getdoc(value)
                        or ""
                    )
                    category = (
                        "property"
                        if any(
                            isinstance(d, ast.Name) and d.id == "property"
                            for d in member.decorator_list
                        )
                        else "method"
                    )
                elif isinstance(member, ast.AnnAssign) and isinstance(
                    member.target, ast.Name
                ):
                    key = member.target.id
                    member_doc = field_doc(doc, key)
                    category = "field"
                else:
                    continue
                mid = identifier + "." + key
                result[mid] = record(
                    mid, category, member_doc, signature(member, key), [identifier]
                )
    root = resources.files(__package__).joinpath("guides")
    for identifier, (title, keywords, related) in GUIDES.items():
        doc = root.joinpath(identifier + ".md").read_text(encoding="utf-8")
        item = record(identifier, "guide", doc, related=related)
        item["title"] = title
        result[identifier] = item
    return dict(sorted(result.items()))


def resolve(query):
    query = query.removeprefix("rpx.")
    all_topics = topics()
    if query in all_topics:
        return query, []
    matches = [key for key in all_topics if key.endswith("." + query)]
    if len(matches) == 1:
        return matches[0], []
    if matches:
        return None, matches
    return None, difflib.get_close_matches(query, all_topics, n=5, cutoff=0.35)


def search(query, limit=10):
    words = re.findall(r"[a-z0-9_]+", query.lower())
    matches = []
    for key, item in topics().items():
        extra = GUIDES.get(key, ("", "", []))[1]
        corpus = " ".join(
            (key, item["title"], item["summary"], extra, *item["sections"].values())
        ).lower()
        score = sum(word in corpus for word in words)
        if words and score == len(words):
            exact = key.lower() == query.lower().removeprefix("rpx.")
            matches.append(
                (not exact, -sum(word in key.lower() for word in words), key, item)
            )
    matches.sort(key=lambda match: match[:3])
    return len(matches), [compact(item) for _, _, _, item in matches[:limit]]


def compact(item):
    return {
        key: item[key]
        for key in ("identifier", "category", "title", "summary", "signature")
    }


def render_topic(item, markdown=False):
    lines = [("# " if markdown else "") + item["title"], ""]
    if item["signature"]:
        lines.extend([item["signature"], ""])
    for name, content in item["sections"].items():
        if name != "Description":
            lines.extend([("## " if markdown else "") + name, ""])
        lines.extend([content, ""])
    if item["related"]:
        lines.append("Related: " + ", ".join(item["related"]))
    return "\n".join(lines).rstrip() + "\n"
