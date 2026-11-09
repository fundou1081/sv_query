#!/usr/bin/env python3
"""Template: validate an explicit project boundary map.

This script deliberately does NOT import or mutate sv_query's core graph.
It documents the adapter contract; a caller can feed validated pairs to an
explicit, separately-reviewed adapter.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {"src", "dst", "kind", "evidence", "confidence"}


def main(path: str) -> int:
    data = json.loads(Path(path).read_text())
    errors = []
    for i, b in enumerate(data.get("boundaries", [])):
        missing = REQUIRED - set(b)
        if missing:
            errors.append(f"boundary[{i}] missing {sorted(missing)}")
        if not str(b.get("evidence", "")).strip():
            errors.append(f"boundary[{i}] empty evidence")
        if b.get("confidence") not in {"low", "medium", "high"}:
            errors.append(f"boundary[{i}] invalid confidence")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"validated {len(data.get('boundaries', []))} explicit boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
