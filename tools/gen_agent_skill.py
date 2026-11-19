#!/usr/bin/env python3
"""[P182.4] Generate the agent-facing capability reference and query skill.

Single source: cli/_registry.to_json() (same data as `sv_query capabilities --json`).
Generated files:
  docs/agent/CAPABILITIES_GENERATED.md
  .agents/skills/query-protocol/references/capabilities.md

Usage:
  python3 tools/gen_agent_skill.py
  python3 tools/gen_agent_skill.py --check
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DOC = ROOT / "docs" / "agent" / "CAPABILITIES_GENERATED.md"
SKILL_REF = ROOT / ".agents" / "skills" / "query-protocol" / "references" / "capabilities.md"


def _render(data: dict) -> str:
    counts = data["counts"]
    core = [c for c in data["commands"] if c["layer"] == "core"]
    lines = [
        "# Agent capabilities (generated — do not edit)",
        "",
        "> Source: `sv_query capabilities --json` / `cli._registry.to_json()`",
        "> Regenerate: `python3 tools/gen_agent_skill.py`  ",
        "> Check: `python3 tools/gen_agent_skill.py --check`",
        f"> Generated: {date.today().isoformat()}",
        "",
        "## Entry rule",
        "",
        "1. Run `sv_query capabilities --json` before choosing a command.",
        "2. Treat this table as the command index; do not invent commands.",
        "3. Use `--json`; decide success from `ok`, not only exit code.",
        "4. A `found=false` answer is data; `ok=false` is a failed query.",
        "",
        "## Counts (stable core view)",
        "",
        f"- core commands in this reference: **{len(core)}**",
        f"- all registered commands (core+exp): **{counts['total']}** "
        f"({counts['by_layer']}); `capabilities --json` 默认只列 "
        f"{len(core)} 条 core，exp 需 `--include-exp`",
        f"- core groups: {counts['core_by_group']}",
        "- `exp` commands are intentionally excluded from the stable table.",
        "",
        "## Commands",
        "",
        "| command | envelope | group | recommended | aliases | note |",
        "|---|---|---|---|---|---|",
    ]
    for cmd in sorted(core, key=lambda c: (c["group"], c["name"])):
        aliases = ", ".join(f"`{a}`" for a in cmd.get("aliases", [])) or "—"
        note = (cmd.get("note") or "").replace("|", "\\|")
        lines.append(
            f"| `{cmd['name']}` | {cmd.get('envelope', '—')} | {cmd['group']} | "
            f"{'✅' if cmd.get('recommended') else '—'} | {aliases} | {note} |"
        )
    lines += [
        "",
        "## Failure / completeness reminders",
        "",
        "- `stats` success has `result.elaboration_errors=[]`; malformed RTL is structured failure.",
        "- `drivers`/`loads`/`trace evidence`/`trace profile` unknown target are the documented",
        "  rc=0 + ok=false hybrid exceptions; other failures are rc=1.",
        "- `snapshot list` has a list root without a tag and an object root with a tag.",
        "",
    ]
    return "\n".join(lines)


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _strip_volatile(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines()
        if not line.startswith("> Generated:")
    )


def generate() -> tuple[str, str]:
    from cli._registry import to_json

    return _render(to_json()), _render(to_json())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    doc, skill_ref = generate()
    if args.check:
        problems = []
        for path, expected in ((DOC, doc), (SKILL_REF, skill_ref)):
            if not path.exists():
                problems.append(f"missing {_display(path)}")
                continue
            actual = path.read_text(encoding="utf-8")
            if _strip_volatile(actual).rstrip("\n") != _strip_volatile(expected).rstrip("\n"):
                problems.append(f"stale {_display(path)}")
        if problems:
            for problem in problems:
                print(f"FAIL\t{problem}")
            print("agent-capabilities: FAIL")
            return 1
        print("agent-capabilities: PASS")
        return 0
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SKILL_REF.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(doc + "\n", encoding="utf-8")
    SKILL_REF.write_text(skill_ref + "\n", encoding="utf-8")
    print(f"wrote {_display(DOC)}")
    print(f"wrote {_display(SKILL_REF)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
