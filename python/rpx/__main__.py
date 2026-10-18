"""Documentation-only command line entry point; the Kernel executable is separate."""

import argparse
import json
from ._help import SCHEMA, compact, render_topic, resolve, search, topics


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline RPX authoring help. No proof operations are executed."
    )
    parser.add_argument(
        "--format", choices=("text", "markdown", "json"), default="text"
    )
    commands = parser.add_subparsers(dest="command")
    help_parser = commands.add_parser("help", help="Read a guide or API contract")
    help_parser.add_argument("topic", nargs="?")
    help_parser.add_argument("--list", action="store_true")
    search_parser = commands.add_parser(
        "search", help="Search offline topics using all query keywords"
    )
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    for command in (help_parser, search_parser):
        command.add_argument(
            "--format", choices=("text", "markdown", "json"), default=argparse.SUPPRESS
        )
    args = parser.parse_args(argv)
    status = 0
    if args.command == "search":
        if args.limit < 0:
            parser.error("--limit must be nonnegative")
        total, results = search(args.query, args.limit)
        payload = dict(kind="search", query=args.query, total=total, results=results)
    elif args.command == "help" and args.list:
        if args.topic:
            parser.error("--list cannot be combined with a topic")
        results = [compact(item) for item in topics().values()]
        payload = dict(kind="index", total=len(results), results=results)
    elif args.command == "help" and args.topic:
        key, suggestions = resolve(args.topic)
        if key is None:
            status = 1
            payload = dict(
                kind="error",
                message="Unknown or ambiguous topic: " + args.topic,
                suggestions=suggestions,
            )
        else:
            payload = dict(kind="topic", topic=topics()[key])
    else:
        payload = dict(
            kind="overview",
            title="RPX offline help",
            summary="Build exact models, author explicit bidirectional proofs, inspect goals, and deliver Kernel-verified bundles.",
            commands=[
                "python -m rpx help quickstart",
                "python -m rpx help agent",
                "python -m rpx help Scope.map",
                'python -m rpx search "eliminate variable"',
                "python -m rpx help --list",
            ],
        )
    payload = dict(schema=SCHEMA, **payload)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    elif payload["kind"] == "topic":
        print(render_topic(payload["topic"], args.format == "markdown"), end="")
    elif payload["kind"] in ("search", "index"):
        print("{} matches; {} shown".format(payload["total"], len(payload["results"])))
        for item in payload["results"]:
            print("{}: {}".format(item["identifier"], item["summary"]))
    elif payload["kind"] == "error":
        print(payload["message"])
        print("Suggestions: " + ", ".join(payload["suggestions"]))
    else:
        print(payload["title"] + "\n\n" + payload["summary"] + "\n")
        print("\n".join(payload["commands"]))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
