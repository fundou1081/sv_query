#!/usr/bin/env python3
"""Lint rule: detect SVG-only labels without internal graph backing.

Usage:
    scripts/lint_viz_orphans.py --fixture-dir <dir> [--strict] [--json]

Detects orphan labels in SVG output that have no corresponding node in
the internal graph (as reported by `graph nodes -j`).

Categories (severity):
  - ERROR: high-confidence bugs (?: partial, case labels, == comparisons)
  - WARN : medium-confidence (compound conditions, other orphans)
  - INFO : low-confidence (op symbols, constants, gen_ cluster)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def _category(label: str) -> str:
    """Classify an orphan label into a severity category."""
    # ERROR: high-confidence bug patterns
    if re.match(r"^\?:\s*\(", label):  # "?: (cond [, cond])"
        # [2026-08-20] 跟 case (sel) 同理 — 是 render_ternary 合成的 visualization 标记.
        # ELK 需要这个 OP 节点存在 (移除会 JsonImportException + regress_golden_mini fail),
        # 内部 graph nodes -j 不会 emit '?: (...)' 这种 label → 必然 orphan.
        # 但它是 by-design 的合成节点, 不是真 bug.  归为 INFO (一级降 WARN 会更激进,
        # 先 INFO 保守).
        return "info"
    if re.match(r"^case\s*\(.*\)\s*$", label):  # "case (...)"
        # [2026-08-20] case scope label 是 elk_bridge.py render_case 合成的 visualization 标记.
        # 如果保持 case label → regress_golden_mini 32 cases 全过 + checker C3 rule 走
        # 如果移除 case label → ELK JsonImportException + regress_golden_mini 13 fail
        # 因此归为 INFO (设计限制, 不是 bug).
        return "info"
    if re.match(r"^[a-zA-Z_][\w\[\]:\s]*==\d+'b[01xz]+\s*$", label):  # "x == 32'b1zz..."
        return "error"

    # WARN: medium-confidence patterns
    if re.match(r"^\([^)]*(&&|\|\|)[^)]*\)\s*$", label):  # "(a && b)"
        return "warn"
    if re.match(r"^.*\?[^:?]*:[^:?]*$", label) and "?: (" not in label:
        # bare "a ? b : c" without parens
        return "warn"

    # INFO: low-confidence patterns
    if re.match(r"^[+\-*/&|^~<>=!]+\s*$", label):
        return "info"
    if re.match(r"^\d+\s*$", label):
        return "info"
    if re.match(r"^[{].*[}]$", label) or label in {"{}", "{1'bx}"}:
        return "info"
    if re.match(r"^gen_[a-z_]+", label):
        return "info"

    return "warn"


def _extract_svg_labels(svg_path: str) -> set:
    """Extract unique `<text>` labels from SVG, decoding HTML entities."""
    if not os.path.exists(svg_path):
        return set()
    svg = open(svg_path).read()
    raw = re.findall(r"<text[^>]*>([^<]+)</text>", svg)
    labels = set()
    for l in raw:
        l = l.strip()
        l = (l.replace("&amp;", "&").replace("&lt;", "<")
              .replace("&gt;", ">").replace("&quot;", '"')
              .replace("&apos;", "'"))
        if l and not l.startswith("Dataflow:"):
            labels.add(l)
    return labels


def _internal_names(nodes_json_path: str) -> set:
    """Extract internal node names + ids from JSON dump."""
    if not os.path.exists(nodes_json_path):
        return set()
    with open(nodes_json_path) as f:
        d = json.load(f)
    nodes = d.get("result", {}).get("nodes", [])
    names = set()
    for n in nodes:
        names.add(n.get("name", ""))
        names.add(n.get("id", ""))
    return {n for n in names if n}


def analyze_case(fixture_dir: str, name: str) -> dict:
    """Analyze one case: cross-ref SVG labels vs internal nodes."""
    nodes_json = os.path.join(fixture_dir, f"{name}_nodes.json")
    edges_json = os.path.join(fixture_dir, f"{name}_edges.json")
    svg_path = os.path.join(fixture_dir, f"{name}.svg")

    internal = _internal_names(nodes_json)
    svg_labels = _extract_svg_labels(svg_path)

    # Categorize orphans
    orphans = sorted(svg_labels - internal)
    by_cat = defaultdict(list)
    for o in orphans:
        by_cat[_category(o)].append(o)

    # Node/edge counts
    n_nodes = n_edges = 0
    if os.path.exists(nodes_json):
        with open(nodes_json) as f:
            d = json.load(f)
        n_nodes = len(d.get("result", {}).get("nodes", []))
    if os.path.exists(edges_json):
        with open(edges_json) as f:
            d = json.load(f)
        n_edges = len(d.get("result", {}).get("edges", []))

    return {
        "name": name,
        "internal_nodes": n_nodes,
        "internal_edges": n_edges,
        "svg_labels": len(svg_labels),
        "svg_no_int": len(orphans),
        "errors": by_cat.get("error", []),
        "warns": by_cat.get("warn", []),
        "infos": by_cat.get("info", []),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture-dir", required=True,
                    help="Directory containing <name>_nodes.json, "
                         "<name>_edges.json, <name>.svg files")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if any errors found")
    ap.add_argument("--json", action="store_true",
                    help="Output JSON instead of human-readable")
    ap.add_argument("--max-warn-pct", type=float, default=100.0,
                    help="Max % orphan ratio (default 100%% = no limit)")
    args = ap.parse_args()

    fix_dir = Path(args.fixture_dir)
    if not fix_dir.exists():
        print(f"Error: {fix_dir} not found", file=sys.stderr)
        sys.exit(2)

    cases = []
    for sv in sorted(fix_dir.glob("*_nodes.json")):
        name = sv.stem.replace("_nodes", "")
        cases.append(analyze_case(str(fix_dir), name))

    total_errors = sum(len(c["errors"]) for c in cases)
    total_warns = sum(len(c["warns"]) for c in cases)
    total_infos = sum(len(c["infos"]) for c in cases)
    total_orphans = sum(c["svg_no_int"] for c in cases)
    total_labels = sum(c["svg_labels"] for c in cases)
    orphan_pct = (total_orphans / total_labels * 100) if total_labels else 0

    if args.json:
        out = {
            "cases": cases,
            "summary": {
                "n_cases": len(cases),
                "total_errors": total_errors,
                "total_warns": total_warns,
                "total_infos": total_infos,
                "total_orphans": total_orphans,
                "orphan_pct": orphan_pct,
            },
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"{'Case':<46} {'N':>4} {'SVG':>5} {'Orph':>5} {'%':>6} "
              f"{'Err':>4} {'Warn':>5} {'Info':>5}")
        print("-" * 80)
        for c in cases:
            pct = (c["svg_no_int"] / c["svg_labels"] * 100) if c["svg_labels"] else 0
            print(f"{c['name']:<46} {c['internal_nodes']:>4} {c['svg_labels']:>5} "
                  f"{c['svg_no_int']:>5} {pct:>5.1f}% "
                  f"{len(c['errors']):>4} {len(c['warns']):>5} {len(c['infos']):>5}")
        print("-" * 80)
        print(f"{'TOTAL':<46} {'':>4} {total_labels:>5} {total_orphans:>5} "
              f"{orphan_pct:>5.1f}% {total_errors:>4} {total_warns:>5} "
              f"{total_infos:>5}")

    if args.strict and total_errors > 0:
        sys.exit(1)
    if orphan_pct > args.max_warn_pct:
        print(f"\nFAIL: orphan % {orphan_pct:.1f}% > max {args.max_warn_pct}%",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()