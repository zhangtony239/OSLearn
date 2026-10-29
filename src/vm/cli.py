"""Command line entry point for the ``vm`` tool."""

from __future__ import annotations

import argparse
import os
import sys

import yaml

from . import __version__
from .config import CONFIG_FILENAME, load_config, validate, write_config
from .errors import VMError
from .interpreter import Interpreter
from .lexer import Lexer
from .parser import Parser
from .scheduler import Scheduler

USAGE = """\
vm -- run .os pseudo-code from the Operating Systems course

usage:
  vm <path/to/file.os> [options]   run a pseudo-code file
  vm config [--path FILE] [--force]  create / self-check vm-config.yaml
  vm --version                     print the version

run options:
  --config FILE      use a specific config file (default: ./vm-config.yaml)
  --policy NAME      round_robin | random
  --quantum N        statements per time slice (round_robin)
  --seed N           random seed; -1 = fresh seed each run
  --max-steps N      hard stop for infinite loops
  --no-trace         do not print the execution trace
  --quiet            suppress warnings and the final summary
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if args[0] in ("-V", "--version", "version"):
        print(f"vm {__version__}")
        return 0
    if args[0] == "config":
        return cmd_config(args[1:])
    return cmd_run(args)


def cmd_config(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="vm config", add_help=True)
    parser.add_argument("--path", default=CONFIG_FILENAME)
    parser.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = parser.parse_args(argv)

    path = args.path
    if not os.path.exists(path) or args.force:
        write_config(path, force=True)
        print(f"created {path}")
        return 0

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        print(f"error: {path}: invalid YAML: {exc}", file=sys.stderr)
        return 1

    errors, warnings = validate(raw)
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")

    if errors:
        print(f"{path}: INVALID")
        return 1
    print(f"{path}: OK")
    return 0


def cmd_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="vm", add_help=False)
    parser.add_argument("file")
    parser.add_argument("--config", default=None)
    parser.add_argument("--policy", default=None)
    parser.add_argument("--quantum", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--no-trace", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not os.path.exists(args.file):
        print(f"vm: no such file: {args.file}", file=sys.stderr)
        return 2

    try:
        cfg = load_config(args.config or CONFIG_FILENAME)
    except VMError as exc:
        print(f"vm: {exc}", file=sys.stderr)
        return 1

    if args.policy is not None:
        cfg["scheduler"]["policy"] = args.policy
    if args.quantum is not None:
        cfg["scheduler"]["quantum"] = args.quantum
    if args.seed is not None:
        cfg["scheduler"]["seed"] = args.seed
    if args.max_steps is not None:
        cfg["scheduler"]["max_steps"] = args.max_steps
    if args.no_trace:
        cfg["trace"]["enabled"] = False

    try:
        with open(args.file, "r", encoding="utf-8") as handle:
            source = handle.read()
    except OSError as exc:
        print(f"vm: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    try:
        lexer = Lexer(
            source,
            case_insensitive=cfg["language"]["case_insensitive_keywords"],
            lenient=cfg["language"]["lenient"],
        )
        tokens = lexer.tokenize()
        parser_ = Parser(tokens, filename=args.file, lenient=cfg["language"]["lenient"])
        program = parser_.parse_program()
    except VMError as exc:
        print(f"vm: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        for warning in lexer.warnings + parser_.warnings:
            print(f"warning: {warning}", file=sys.stderr)

    stream = sys.stderr if cfg["trace"]["stream"] == "stderr" else sys.stdout
    interp = Interpreter(
        cfg,
        emit=lambda text: sys.stdout.write(text + "\n"),
        trace=lambda text: print(text, file=stream),
    )
    scheduler = Scheduler(
        interp,
        policy=cfg["scheduler"]["policy"],
        quantum=cfg["scheduler"]["quantum"],
        seed=cfg["scheduler"]["seed"],
        max_steps=cfg["scheduler"]["max_steps"],
        trace_enabled=cfg["trace"]["enabled"],
    )
    interp.sched = scheduler

    try:
        interp.run(program)
    except VMError as exc:
        print(f"vm: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        for warning in interp.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(
            f"-- {scheduler.steps} steps, {len(scheduler.processes)} process(es)",
            file=sys.stderr,
        )
        if scheduler.deadlock:
            print("-- deadlock: every remaining process is blocked", file=sys.stderr)
        if scheduler.truncated:
            print(
                f"-- stopped after max_steps={scheduler.max_steps}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
