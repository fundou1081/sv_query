#!/usr/bin/env python3
"""P193.1 repository hygiene: reject absolute-path symlinks.

A tracked symlink such as ``sim/tests/config -> /Users/<name>/...`` is broken
for every clone and fails on Windows. This check reads the git index, so it is
independent of the current working tree.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked_symlinks(repo: Path = ROOT) -> list[tuple[str, str]]:
    out = subprocess.run(
        ["git", "ls-files", "-s"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        mode, sha, _stage = meta.split()
        if mode != "120000":
            continue
        target = subprocess.run(
            ["git", "cat-file", "blob", sha], cwd=repo, check=True,
            capture_output=True, text=True,
        ).stdout.rstrip("\n")
        rows.append((path, target))
    return rows


def find_absolute_symlinks(repo: Path = ROOT) -> list[tuple[str, str]]:
    return [(path, target) for path, target in tracked_symlinks(repo)
            if target.startswith("/") or target.startswith("\\") or
            (len(target) > 1 and target[1] == ":")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    bad = find_absolute_symlinks(Path(args.root))
    if bad:
        for path, target in bad:
            print(f"FAIL\ttracked absolute symlink: {path} -> {target}")
        print(f"repo-hygiene: FAIL ({len(bad)} absolute symlinks)")
        return 1
    print("repo-hygiene: PASS (no tracked absolute-path symlinks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
