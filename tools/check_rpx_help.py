#!/usr/bin/env python3
"""Validate offline help coverage/contracts; generate or check the API reference.

Run with PYTHONPATH=python after building the native extension.
"""
import argparse
import ast
import inspect
from pathlib import Path
import rpx
from rpx import lowlevel
from rpx._help import declarations, render_topic, topics, sections

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/RPX_REFERENCE.md"


def validate():
    errors = []
    records = topics()
    declarations_by_name = declarations()
    for key, item in records.items():
        if not item["summary"] or not item["sections"]:
            errors.append(key + ": missing documentation")
        for related in item["related"]:
            if related not in records:
                errors.append(key + ": broken related topic " + related)
    for module, prefix in ((rpx, ""), (lowlevel, "lowlevel.")):
        for name in module.__all__:
            obj = getattr(module, name)
            node = declarations_by_name[name]
            identifier = prefix + name
            if identifier not in records:
                errors.append(identifier + ": missing export")
            if not inspect.isclass(obj) or issubclass(obj, BaseException):
                continue
            for member, value in vars(obj).items():
                if (
                    not member.startswith("_")
                    and identifier + "." + member not in records
                ):
                    errors.append(identifier + "." + member + ": missing public member")
            operators = sections(inspect.getdoc(obj) or "").get("Operators", "")
            for line in operators.splitlines():
                if line.startswith("__") and ":" in line:
                    operator = line.split(":", 1)[0]
                    if identifier + "." + operator not in records:
                        errors.append(
                            identifier
                            + "."
                            + operator
                            + ": undocumented operator declaration"
                        )
            for member in node.body:
                if not isinstance(member, ast.FunctionDef) or member.name.startswith(
                    "__"
                ):
                    continue
                value = inspect.getattr_static(obj, member.name)
                if isinstance(value, (staticmethod, classmethod)):
                    value = value.__func__
                if isinstance(value, property) or inspect.isgetsetdescriptor(value):
                    continue
                try:
                    actual = inspect.signature(value)
                except (ValueError, TypeError):
                    errors.append(
                        identifier + "." + member.name + ": no runtime signature"
                    )
                    continue
                actual_params = {
                    k: v
                    for k, v in actual.parameters.items()
                    if k not in ("self", "cls")
                }
                declared = {
                    a.arg: a
                    for a in member.args.posonlyargs
                    + member.args.args
                    + member.args.kwonlyargs
                    if a.arg not in ("self", "cls")
                }
                kwargs = any(p.kind == p.VAR_KEYWORD for p in actual_params.values())
                if not kwargs and set(actual_params) != set(declared):
                    errors.append(
                        identifier + "." + member.name + ": parameter names differ"
                    )
                defaults = (
                    dict(
                        zip(
                            [a.arg for a in member.args.args][
                                -len(member.args.defaults) :
                            ],
                            member.args.defaults,
                        )
                    )
                    if member.args.defaults
                    else {}
                )
                defaults.update(
                    (a.arg, d)
                    for a, d in zip(member.args.kwonlyargs, member.args.kw_defaults)
                    if d is not None
                )
                for param, declaration in declared.items():
                    if param not in actual_params:
                        continue  # Named supported budgets forwarded via **limits.
                    default = defaults.get(param)
                    runtime = actual_params[param].default
                    if default is None:
                        if runtime is not inspect.Parameter.empty:
                            errors.append(
                                identifier
                                + "."
                                + member.name
                                + ": unexpected default for "
                                + param
                            )
                    elif (
                        isinstance(default, ast.Constant) and default.value is Ellipsis
                    ):
                        continue  # Explicitly unspecified sentinel in the type declaration.
                    else:
                        try:
                            expected = ast.literal_eval(default)
                        except (ValueError, TypeError):
                            continue
                        if expected != runtime:
                            errors.append(
                                identifier
                                + "."
                                + member.name
                                + ": default differs for "
                                + param
                            )
    return errors


def reference():
    header = "# RPX generated API reference\n\nGenerated from installed definitions and packaged type declarations. Do not edit.\n\nRegenerate: `PYTHONPATH=python python3 tools/check_rpx_help.py --write`.\nCheck: `PYTHONPATH=python python3 tools/check_rpx_help.py --check`.\n\nStart with `python -m rpx help quickstart`; use `python -m rpx help agent` for task navigation.\n\n"
    return header + "\n".join(
        render_topic(item, True)
        for item in topics().values()
        if item["category"] != "guide"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors = validate()
    if errors:
        raise SystemExit("\n".join(errors))
    result = reference()
    if args.write:
        OUTPUT.write_text(result, encoding="utf-8")
    elif args.check and (
        not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != result
    ):
        raise SystemExit("Generated reference is stale; run with --write")
    print(
        "PASS: {} topics, public exports, fields, signatures and related links".format(
            len(topics())
        )
    )


if __name__ == "__main__":
    main()
