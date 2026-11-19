#!/usr/bin/env python3
"""[P185.4] CLI command-surface ratchet.

A baseline records the declared 45/39/2/32/13 surface. `--check` fails on any
unannounced addition, removal, alias change, default-visibility change, or
envelope/layer drift. `--write-baseline` is the only explicit update path.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cli._registry import ALIASES, COMMANDS, to_json  # noqa: E402

BASELINE = ROOT / "tools" / "command_surface_baseline.json"
SCHEMA = "sv_query.command_surface.v1"


def collect() -> dict:
    listed = [c for c in COMMANDS if c.listed]
    visible = to_json()["commands"]
    return {
        "schema": SCHEMA,
        "counts": {
            "canonical": len(listed),
            "default_visible": len(visible),
            "aliases": len(ALIASES),
            "core": sum(c.layer == "core" for c in listed),
            "exp": sum(c.layer == "exp" for c in listed),
            "standard": sum(c.envelope == "standard" for c in listed),
            "direct": sum(c.envelope == "direct" for c in listed),
        },
        "canonical": sorted(c.key for c in listed),
        "hidden": sorted(c.key for c in COMMANDS if not c.listed),
        "default_visible": sorted(c["name"] for c in visible),
        "aliases": dict(sorted(ALIASES.items())),
        "by_command": {
            c.key: {
                "layer": c.layer,
                "group": c.group,
                "envelope": c.envelope,
                "listed": c.listed,
            }
            for c in COMMANDS
        },
        "core_groups": dict(sorted(Counter(
            c.group for c in listed if c.layer == "core").items())),
    }


def compare(expected: dict, actual: dict) -> list[str]:
    problems = []
    if expected.get("schema") != SCHEMA:
        problems.append(f"baseline schema={expected.get('schema')!r}, expected {SCHEMA!r}")
    if expected.get("counts") != actual["counts"]:
        problems.append(f"counts changed: {expected.get('counts')} -> {actual['counts']}")
    for key in ("canonical", "default_visible", "hidden"):
        before = set(expected.get(key, []))
        now = set(actual[key])
        missing = sorted(before - now)
        added = sorted(now - before)
        if missing:
            problems.append(f"{key} removed: {', '.join(missing)}")
        if added:
            problems.append(f"{key} added: {', '.join(added)}")
    if expected.get("aliases") != actual["aliases"]:
        problems.append(f"aliases changed: {expected.get('aliases')} -> {actual['aliases']}")
    if expected.get("core_groups") != actual["core_groups"]:
        problems.append(
            f"core_groups changed: {expected.get('core_groups')} -> {actual['core_groups']}"
        )
    before_cmds = expected.get("by_command", {})
    now_cmds = actual["by_command"]
    for name in sorted(set(before_cmds) | set(now_cmds)):
        if before_cmds.get(name) != now_cmds.get(name):
            problems.append(
                f"command metadata changed for {name}: "
                f"{before_cmds.get(name)} -> {now_cmds.get(name)}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args(argv)
    actual = collect()
    if args.write_baseline:
        BASELINE.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"wrote {BASELINE.relative_to(ROOT)}")
        return 0
    if not args.check:
        parser.error("use --check or --write-baseline")
    if not BASELINE.exists():
        try:
            shown = BASELINE.relative_to(ROOT)
        except ValueError:
            shown = BASELINE
        print(f"FAIL\tmissing {shown}")
        print("command-surface: FAIL")
        return 1
    try:
        expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL\tbaseline is not valid JSON: {exc.msg}")
        print("command-surface: FAIL")
        return 1
    problems = compare(expected, actual)
    if problems:
        for problem in problems:
            print(f"FAIL\t{problem}")
        print(f"command-surface: FAIL ({len(problems)} changes)")
        return 1
    print(
        "command-surface: PASS "
        f"({actual['counts']['canonical']} canonical, "
        f"{actual['counts']['default_visible']} visible, "
        f"{actual['counts']['aliases']} aliases, "
        f"{actual['counts']['standard']} standard, "
        f"{actual['counts']['direct']} direct)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
