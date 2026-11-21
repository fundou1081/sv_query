#!/usr/bin/env python3
"""[P182.5] Static snapshot/cache surface inventory (evaluation only)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import click  # noqa: E402
import typer  # noqa: E402

from sv_query.cli._registry import COMMANDS  # noqa: E402
from sv_query.cli.main import app  # noqa: E402


def _leaves() -> dict[str, click.Command]:
    root = typer.main.get_command(app)
    out: dict[str, click.Command] = {}

    def walk(cmd: click.Command, prefix: str = "") -> None:
        if isinstance(cmd, click.Group):
            for name, sub in cmd.commands.items():
                walk(sub, f"{prefix}{name} ")
        else:
            out[prefix.strip()] = cmd

    walk(root)
    return out


def collect() -> dict:
    leaves = _leaves()
    rows = []
    for spec in COMMANDS:
        if not spec.listed:
            continue
        cmd = leaves.get(spec.key)
        opts = {p.name for p in cmd.params if isinstance(p, click.Option)} if cmd else set()
        rows.append({
            "name": spec.key,
            "layer": spec.layer,
            "from_snapshot": "from_snapshot" in opts,
            "no_cache": "no_cache" in opts,
        })
    core = [r for r in rows if r["layer"] == "core"]
    return {
        "listed": len(rows),
        "core": len(core),
        "core_from_snapshot": sorted(r["name"] for r in core if r["from_snapshot"]),
        "core_no_cache": sorted(r["name"] for r in core if r["no_cache"]),
        "core_without_snapshot": sorted(r["name"] for r in core if not r["from_snapshot"]),
        "snapshot_commands": sorted(r["name"] for r in core if r["name"].startswith("snapshot ")),
    }


def render(data: dict) -> None:
    print("P182.5 snapshot/cache surface (static, no CLI execution)")
    print(f"listed={data['listed']} core={data['core']}")
    print("core from-snapshot:", ", ".join(data["core_from_snapshot"]) or "-")
    print("core no-cache:", ", ".join(data["core_no_cache"]) or "-")
    print("core without from-snapshot:",
          ", ".join(data["core_without_snapshot"]) or "-")
    print("snapshot commands:", ", ".join(data["snapshot_commands"]) or "-")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = collect()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        render(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
