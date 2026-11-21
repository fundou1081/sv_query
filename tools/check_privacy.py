#!/usr/bin/env python3
"""P193.2 public-repo privacy gate.

Rejects tracked private development assets and absolute home paths. Ignored
files (caches, local notes) are outside the public checkout and not scanned.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PREFIXES = (
    "agents/", "memory/", "docs/task_tree/", "docs/sessions/",
    "docs/archive/", "docs/refactoring/", "docs/lessons/",
    "docs/debugging_lessons/", "scripts/debug/", ".claude/", ".dsh/",
)
_AUTHOR = "fund" + "ou"
FORBIDDEN_TEXT = (f"/Users/{_AUTHOR}", f"/home/{_AUTHOR}", f"C:\\Users\\{_AUTHOR}")
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".txt", ".json", ".f", ".sv", ".sh"}


def tracked_files(repo: Path = ROOT) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def problems(repo: Path = ROOT) -> list[str]:
    found = []
    for path in tracked_files(repo):
        if path.startswith(FORBIDDEN_PREFIXES):
            found.append(f"private asset tracked: {path}")
        p = repo / path
        if p.suffix.lower() not in TEXT_SUFFIXES or not p.is_file():
            continue
        text = p.read_text(errors="ignore")
        for needle in FORBIDDEN_TEXT:
            if needle in text:
                found.append(f"absolute home path in {path}: {needle}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    found = problems(Path(args.root))
    if found:
        for item in found[:30]:
            print(f"FAIL\t{item}")
        print(f"privacy: FAIL ({len(found)} issues)")
        return 1
    print("privacy: PASS (no private assets / absolute home paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
