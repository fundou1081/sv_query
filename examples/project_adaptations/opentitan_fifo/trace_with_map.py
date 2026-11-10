#!/usr/bin/env python3
"""Compose a trace through explicitly declared project boundaries.

This is an example adapter, not part of sv_query core.  It runs the public CLI
with --json, then concatenates structural paths with only the boundary pairs
listed in the map.  It never discovers FIFOs or creates graph edges.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "run_cli.py"
REQUIRED = {"src", "dst", "kind", "evidence", "confidence"}


def _run(args: list[str]) -> dict:
    proc = subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"CLI exit {proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"CLI returned non-JSON: {e}") from e


def _common_args(args) -> list[str]:
    if args.from_snapshot:
        return ["--from-snapshot", args.from_snapshot]
    return ["--filelist", args.filelist] if args.filelist else ["--file", args.file]


def _path(args, src: str, dst: str) -> dict:
    if src == dst:
        return {"ok": True, "found": True, "path": [src]}
    return _run(["paths", src, dst, "--directed", "--json", *_common_args(args)])


def _frontier(args, signal: str) -> dict:
    return _run(["trace", "frontier", signal, "--direction", "fanout",
                 "--json", *_common_args(args)])


def _validate_map(data: dict) -> list[dict]:
    errors = []
    boundaries = data.get("boundaries") or []
    for i, b in enumerate(boundaries):
        missing = REQUIRED - set(b)
        if missing:
            errors.append(f"boundary[{i}] missing {sorted(missing)}")
        if not str(b.get("evidence", "")).strip():
            errors.append(f"boundary[{i}] empty evidence")
        if b.get("confidence") not in {"low", "medium", "high"}:
            errors.append(f"boundary[{i}] invalid confidence")
    if errors:
        raise ValueError("; ".join(errors))
    return boundaries


def _compose(args, boundaries: list[dict]) -> dict:
    failures = []
    for b in boundaries:
        pre = _path(args, args.src, b["src"])
        if not pre.get("found"):
            failures.append({"src": b["src"], "stage": "prefix"})
            continue
        post = _path(args, b["dst"], args.dst)
        if not post.get("found"):
            failures.append({"dst": b["dst"], "stage": "suffix"})
            continue
        chain = list(pre["path"]) + [b["dst"]] + list(post["path"][1:])
        return {
            "ok": True,
            "status": "traced",
            "from": args.src,
            "to": args.dst,
            "adapter": args.map.get("adapter", ""),
            "chain": chain,
            "segments": [
                {"kind": "structural", "path": pre["path"]},
                {"kind": "explicit_boundary", "src": b["src"], "dst": b["dst"],
                 "boundary_kind": b["kind"], "evidence": b["evidence"],
                 "confidence": b["confidence"]},
                {"kind": "structural", "path": post["path"]},
            ],
            "boundaries_used": 1,
        }
    frontier = _frontier(args, args.src)
    return {
        "ok": True,
        "status": "boundary",
        "from": args.src,
        "to": args.dst,
        "adapter": args.map.get("adapter", ""),
        "chain": [],
        "segments": [],
        "failures": failures,
        "frontier": frontier.get("result", frontier),
        "note": "no explicit boundary produced both a prefix and suffix; trace stopped",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", "-f")
    g.add_argument("--filelist")
    g.add_argument("--from-snapshot")
    ap.add_argument("--map", default=str(Path(__file__).with_name("boundary_map.json")))
    args = ap.parse_args()
    try:
        args.map = json.loads(Path(args.map).read_text())
        boundaries = _validate_map(args.map)
        result = _compose(args, boundaries)
    except (OSError, ValueError, RuntimeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "traced" else 2


if __name__ == "__main__":
    raise SystemExit(main())
