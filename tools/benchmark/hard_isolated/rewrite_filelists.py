#!/usr/bin/env python3
"""Rewrite hard-workspace filelists to point at the workspace copies."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path,
                    help="e.g. /tmp/lr_hard_ws containing axi/ and serv/")
    args = ap.parse_args()
    ws = args.workspace.resolve()
    for design in ("axi", "serv"):
        root = ws / design
        if not root.is_dir():
            print(f"skip missing {root}")
            continue
        files = sorted(str(p) for p in root.glob("*.v"))
        if not files:
            print(f"skip empty {root}")
            continue
        out = ws / f"{design}.f"
        out.write_text("\n".join(files) + "\n", encoding="utf-8")
        print(f"{out}: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
