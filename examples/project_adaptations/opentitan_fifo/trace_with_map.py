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
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"CLI exit {proc.returncode}") from e
        raise RuntimeError(f"CLI returned non-JSON: {e}") from e
    if proc.returncode != 0 or data.get("ok") is False:
        message = data.get("error") or proc.stderr.strip() or f"CLI exit {proc.returncode}"
        unknown = data.get("unknown")
        if unknown:
            message = f"{message}; unknown={unknown}"
        raise RuntimeError(message)
    return data


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
    if not isinstance(data, dict):
        raise ValueError("boundary map must be a JSON object")
    errors = []
    boundaries = data.get("boundaries") or []
    if not isinstance(boundaries, list):
        raise ValueError("boundary map 'boundaries' must be a list")
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
        raise ValueError("; ".join(errors))
    return boundaries


def _compose(args, boundaries: list[dict]) -> dict:
    failures = []
    viable = []
    for b in boundaries:
        pre = _path(args, args.src, b["src"])
        if not pre.get("found"):
            failures.append({"src": b["src"], "stage": "prefix"})
            continue
        post = _path(args, b["dst"], args.dst)
        if not post.get("found"):
            failures.append({"dst": b["dst"], "stage": "suffix"})
            continue
        viable.append((b, pre, post))
    if len(viable) > 1:
        return {
            "ok": True,
            "status": "ambiguous",
            "from": args.src,
            "to": args.dst,
            "adapter": args.map.get("adapter", ""),
            "proven": False,
            "ambiguous": True,
            "candidates": [
                {"src": b["src"], "dst": b["dst"],
                 "evidence": b["evidence"], "confidence": b["confidence"]}
                for b, _, _ in viable
            ],
            "chain": [],
            "segments": [],
            "boundaries_used": 0,
            "note": "multiple explicit boundaries produced prefix+suffix; no silent choice",
        }
    if len(viable) == 1:
        b, pre, post = viable[0]
        boundary_index = len(pre["path"])
        chain = list(pre["path"]) + [b["dst"]] + list(post["path"][1:])
        return {
            "ok": True,
            "status": "traced",
            "from": args.src,
            "to": args.dst,
            "adapter": args.map.get("adapter", ""),
            "proven": False,
            "asserted_relation": True,
            "chain": chain,
            "boundary_hops": [{
                "index": boundary_index,
                "src": b["src"], "dst": b["dst"],
                "boundary_kind": b["kind"], "evidence": b["evidence"],
                "confidence": b["confidence"],
            }],
            "segments": [
                {"kind": "structural", "path": pre["path"]},
                {"kind": "explicit_boundary", "src": b["src"], "dst": b["dst"],
                 "boundary_kind": b["kind"], "evidence": b["evidence"],
                 "confidence": b["confidence"]},
                {"kind": "structural", "path": post["path"]},
            ],
            "boundaries_used": 1,
            "note": "boundary is an explicit assertion, not a proven semantic relation",
        }
    frontier = _frontier(args, args.src)
    return {
        "ok": True,
        "status": "boundary",
        "from": args.src,
        "to": args.dst,
        "adapter": args.map.get("adapter", ""),
        "proven": False,
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
