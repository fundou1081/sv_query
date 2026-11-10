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
    if not isinstance(data, dict):
        print("boundary map must be a JSON object", file=sys.stderr)
        return 1
    boundaries = data.get("boundaries") or []
    if not isinstance(boundaries, list):
        print("boundary map 'boundaries' must be a list", file=sys.stderr)
        return 1
    errors = []
    seen = set()
    for i, b in enumerate(boundaries):
        if not isinstance(b, dict):
            errors.append(f"boundary[{i}] must be an object")
            continue
        missing = REQUIRED - set(b)
        if missing:
            errors.append(f"boundary[{i}] missing {sorted(missing)}")
            continue
        for key in ("src", "dst", "kind"):
            if not str(b.get(key, "")).strip():
                errors.append(f"boundary[{i}] empty {key}")
        if b["src"] == b["dst"]:
            errors.append(f"boundary[{i}] src == dst")
        pair = (b["src"], b["dst"])
        if pair in seen:
            errors.append(f"boundary[{i}] duplicate pair")
        seen.add(pair)
        if not str(b.get("evidence", "")).strip():
            errors.append(f"boundary[{i}] empty evidence")
        if b.get("confidence") not in {"low", "medium", "high"}:
            errors.append(f"boundary[{i}] invalid confidence")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"validated {len(boundaries)} explicit boundaries")
    return 0
