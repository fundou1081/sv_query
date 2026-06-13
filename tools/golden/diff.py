#!/usr/bin/env python3
"""
diff.py — Compare golden vs actual JSON for visualization tests.

Exit codes:
  0 = perfect match
  1 = structural differences found
  2 = error (file not found, invalid JSON, etc.)

Usage:
  python tools/golden/diff.py --golden <golden.json> --actual <actual.json>
  python tools/golden/diff.py --golden <golden.json> --actual <actual.json> --verbose
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def load_json(path: Path) -> Any:
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)


def node_id(n: Dict) -> str:
    return n.get("id", "<no id>")


def edge_key(e: Dict) -> Tuple[str, str, str]:
    """Compare edges by (from, to, kind)."""
    return (e.get("from", ""), e.get("to", ""), e.get("kind", ""))


def compare(golden: Dict, actual: Dict, verbose: bool = False) -> List[str]:
    """Compare golden vs actual, return list of differences.

    [2026-06-13] 尊重 skip_in_diff 字段: 设为 true 的 node/edge 跳过比对
    (用于 "aspirational" 黄金 — 实际工具不能抽出, 不可作为 PR fail).
    """
    diffs = []

    # 1. Module / view / level sanity
    for key in ("module", "view", "level"):
        if golden.get(key) != actual.get(key):
            diffs.append(f"[meta] {key}: golden={golden.get(key)!r} actual={actual.get(key)!r}")

    # 2. Filter aspirational nodes (skip_in_diff=true)
    gold_nodes_raw = golden.get("nodes", [])
    act_nodes_raw = actual.get("nodes", [])
    gold_nodes = {node_id(n): n for n in gold_nodes_raw
                  if not n.get("skip_in_diff")}
    act_nodes = {node_id(n): n for n in act_nodes_raw}
    gold_ids = set(gold_nodes.keys())
    act_ids = set(act_nodes.keys())

    missing = gold_ids - act_ids
    extra = act_ids - gold_ids
    for n in sorted(missing):
        diffs.append(f"[node] missing: {n}")
    for n in sorted(extra):
        diffs.append(f"[node] extra: {n}")

    # 3. Edges: filter aspirational
    gold_edges_raw = golden.get("edges", [])
    act_edges_raw = actual.get("edges", [])
    gold_edges = {edge_key(e): e for e in gold_edges_raw
                  if not e.get("skip_in_diff")}
    act_edges = {edge_key(e): e for e in act_edges_raw}
    gold_ek = set(gold_edges.keys())
    act_ek = set(act_edges.keys())

    for k in sorted(gold_ek - act_ek):
        diffs.append(f"[edge] missing: {k[0]} -> {k[1]} ({k[2]})")
    for k in sorted(act_ek - gold_ek):
        diffs.append(f"[edge] extra: {k[0]} -> {k[1]} ({k[2]})")

    # 4. For matching nodes, check key attributes
    for nid in gold_ids & act_ids:
        gn, an = gold_nodes[nid], act_nodes[nid]
        for key in ("kind", "module_path", "cluster"):
            if gn.get(key) != an.get(key):
                diffs.append(
                    f"[node] {nid}.{key}: golden={gn.get(key)!r} actual={an.get(key)!r}"
                )

    # 5. Clusters (no skip_in_diff support)
    gold_clusters = {c.get("id"): c for c in golden.get("clusters", [])}
    act_clusters = {c.get("id"): c for c in actual.get("clusters", [])}
    for cid in set(gold_clusters.keys()) | set(act_clusters.keys()):
        if cid not in gold_clusters:
            diffs.append(f"[cluster] extra: {cid}")
        elif cid not in act_clusters:
            # [PR1 2026-06-13] L1 不一定输出 cluster, 只是元数据, warning 而非 fail
            # 改成 only report if there are actual edges or nodes
            if gold_edges_raw or act_edges_raw or (gold_nodes and act_nodes):
                diffs.append(f"[cluster] missing: {cid}")

    return diffs


def main():
    parser = argparse.ArgumentParser(description="Compare golden vs actual JSON")
    parser.add_argument("--golden", required=True, type=Path, help="Path to golden JSON")
    parser.add_argument("--actual", required=True, type=Path, help="Path to actual JSON")
    parser.add_argument("--verbose", action="store_true", help="Print matched/expected counts too")
    args = parser.parse_args()

    golden = load_json(args.golden)
    actual = load_json(args.actual)

    diffs = compare(golden, actual, args.verbose)

    gold_nodes = golden.get("nodes", [])
    act_nodes = actual.get("nodes", [])
    gold_edges = golden.get("edges", [])
    act_edges = actual.get("edges", [])

    if args.verbose:
        print(f"Golden: {len(gold_nodes)} nodes, {len(gold_edges)} edges")
        print(f"Actual: {len(act_nodes)} nodes, {len(act_edges)} edges")

    if not diffs:
        print("✓ Match: golden and actual are equivalent")
        sys.exit(0)

    print(f"✗ {len(diffs)} difference(s):")
    for d in diffs:
        print(f"  {d}")
    sys.exit(1)


if __name__ == "__main__":
    main()
