#!/usr/bin/env python3
"""graph_snapshot.py — 图快照基线工具（P0.1）

用途
----
重构 `_trace_drivers_recursive` / `GraphBuilder` 后处理 pass 时，**证明行为没变**：
  1. 重构前：`capture` 把 SignalGraph 规范化成 JSON 基线
  2. 重构后：`verify` 重新采集并与基线逐项 diff
  3. 有任何节点/边/属性差异 → 退出码 1，并列出前 N 处差异

设计约束
--------
- **只读**：只读 RTL/源文件，不写任何工程文件（输出只到 `--out`）。
- **确定性**：节点按 id 排序、边按 (src,dst,kind,assign_type,condition) 排序；
  路径归一化为仓库相对路径（避免绝对路径进基线）。
- **只取语义属性**：排除 `file` / `line`（路径相关）与 `extra`（可能含 AST/重量级对象）。
- 不做"自动 bless"：基线缺失时 `verify` 显式失败；生成基线必须显式 `capture`。

用法
----
    # 采集
    python3 tools/graph_snapshot.py capture --name inst_demo \\
        --file sim/tests/fixtures/golden_mini/inst_demo.sv \\
        --out sim/tests/golden/graph_baseline/inst_demo.json

    python3 tools/graph_snapshot.py capture --name m3 \\
        --filelist sim/tests/fixtures/minimal_3module/filelist.f --out /tmp/m3.json

    # 比对两份快照
    python3 tools/graph_snapshot.py diff a.json b.json [--json]

    # 重新采集并与基线比对（重构后回归）
    python3 tools/graph_snapshot.py verify --snapshot /tmp/m3.json \\
        --filelist sim/tests/fixtures/minimal_3module/filelist.f

退出码：0 = 无差异 / 1 = 有差异 / 2 = 输入错误
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# 必须插到最前: sys.path 里可能有其他路径下的 `trace.py`（stdlib 就有）, 会遮蔽 src/trace
SRC = REPO / "src"
if sys.path[0] != str(SRC):
    sys.path.insert(0, str(SRC))

SNAPSHOT_VERSION = 1

# 参与比对的节点属性（语义属性；不含 file/line/extra）
NODE_FIELDS = (
    "id", "kind", "module", "width",
    "is_port", "is_clock", "is_reset", "is_enable",
    "parent", "bit_range", "modport_dir",
)
# 参与比对的边属性
EDGE_FIELDS = (
    "src", "dst", "kind", "assign_type",
    "condition", "effective_condition", "clock_domain",
    "bit_slice", "confidence", "function_return", "is_function_call",
    "expression",
)

MAX_DIFF_SHOWN = 20


def _rel(path: str | Path) -> str:
    """仓库内路径 → 相对路径；仓库外保持原样。"""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def _node_dict(node) -> dict:
    d = {}
    for f in NODE_FIELDS:
        v = getattr(node, f, None)
        if f == "kind":
            v = v.name if hasattr(v, "name") else str(v)
        elif f == "width":
            w = v if isinstance(v, (tuple, list)) else (0, 0)
            v = [int(w[0]), int(w[1])] if len(w) >= 2 else [0, 0]
        d[f] = v
    return d


def _edge_dict(edge) -> dict:
    d = {}
    for f in EDGE_FIELDS:
        v = getattr(edge, f, None)
        if f == "kind":
            v = v.name if hasattr(v, "name") else str(v)
        d[f] = v
    return d


def _sort_key_edge(d: dict) -> tuple:
    return tuple(str(d.get(k, "")) for k in ("src", "dst", "kind", "assign_type", "condition"))


def build_snapshot(
    name: str,
    *,
    filelist: str | None = None,
    files: list[str] | None = None,
    source_dir: str | None = None,
    target: str | None = None,
    use_cache: bool = False,
) -> dict:
    """构建一份规范化图快照（供 CLI 与测试共用）。"""
    from trace.unified_tracer import UnifiedTracer  # 延迟导入（tools 环境）

    if source_dir:
        pattern = sorted(Path(source_dir).glob("*.sv")) + sorted(Path(source_dir).glob("*.v"))
        if not pattern:
            raise SystemExit(f"❌ --source-dir 下没有 .sv/.v 文件: {source_dir}")
        files = [str(p) for p in pattern]
    if filelist:
        tracer = UnifiedTracer(filelist=filelist, log_level="ERROR")
        input_desc = {"filelist": _rel(filelist)}
    elif files:
        tracer = UnifiedTracer(files=[str(f) for f in files], log_level="ERROR")
        input_desc = {"files": [_rel(f) for f in files]}
    else:
        raise SystemExit("❌ 需要 --filelist / --file / --source-dir 之一")

    tracer.build_graph(use_cache=use_cache, target_module=target)
    graph = tracer.get_graph()

    nodes = sorted((_node_dict(graph.get_node(n)) for n in graph.nodes()), key=lambda d: d["id"])
    # 注意: networkx 的 graph.edges() 返回 (u, v) 元组, 不是 TraceEdge 对象;
    # 真正的多边数据在 _edge_data[(u, v)] = [TraceEdge, ...]。
    edges = sorted(
        (_edge_dict(e) for pair_edges in graph._edge_data.values() for e in pair_edges),
        key=_sort_key_edge,
    )

    node_kinds: dict[str, int] = {}
    for n in nodes:
        node_kinds[n["kind"]] = node_kinds.get(n["kind"], 0) + 1
    edge_kinds: dict[str, int] = {}
    for e in edges:
        edge_kinds[e["kind"]] = edge_kinds.get(e["kind"], 0) + 1

    return {
        "version": SNAPSHOT_VERSION,
        "name": name,
        "input": input_desc,
        "target": target,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "node_kinds": dict(sorted(node_kinds.items())),
            "edge_kinds": dict(sorted(edge_kinds.items())),
        },
        "nodes": nodes,
        "edges": edges,
    }


def diff_snapshots(old: dict, new: dict) -> dict:
    """逐项比对两份快照，返回结构化差异（ok=True 表示完全一致）。"""
    old_nodes = {n["id"]: n for n in old.get("nodes", [])}
    new_nodes = {n["id"]: n for n in new.get("nodes", [])}

    node_added = sorted(set(new_nodes) - set(old_nodes))
    node_removed = sorted(set(old_nodes) - set(new_nodes))
    node_changed = []
    for nid in sorted(set(old_nodes) & set(new_nodes)):
        a, b = old_nodes[nid], new_nodes[nid]
        for f in NODE_FIELDS:
            if a.get(f) != b.get(f):
                node_changed.append({"id": nid, "field": f, "old": a.get(f), "new": b.get(f)})

    old_edges = {json.dumps(e, sort_keys=True, ensure_ascii=False) for e in old.get("edges", [])}
    new_edges = {json.dumps(e, sort_keys=True, ensure_ascii=False) for e in new.get("edges", [])}
    edge_added = sorted(new_edges - old_edges)
    edge_removed = sorted(old_edges - new_edges)

    old_sum = old.get("summary", {})
    new_sum = new.get("summary", {})
    summary_delta = {
        k: [old_sum.get(k), new_sum.get(k)]
        for k in ("nodes", "edges")
        if old_sum.get(k) != new_sum.get(k)
    }
    for k in ("node_kinds", "edge_kinds"):
        if old_sum.get(k) != new_sum.get(k):
            summary_delta[k] = [old_sum.get(k), new_sum.get(k)]

    ok = not (node_added or node_removed or node_changed or edge_added or edge_removed)
    return {
        "ok": ok,
        "nodes": {
            "added": node_added,
            "removed": node_removed,
            "changed": node_changed,
        },
        "edges": {
            "added": edge_added,
            "removed": edge_removed,
        },
        "summary_delta": summary_delta,
    }


def format_diff(d: dict) -> str:
    if d["ok"]:
        return "✅ 图快照一致（节点/边/属性零差异）"
    lines = ["❌ 图快照有差异:"]
    nd, ed = d["nodes"], d["edges"]
    if nd["added"]:
        lines.append(f"  节点新增 {len(nd['added'])}: {nd['added'][:MAX_DIFF_SHOWN]}")
    if nd["removed"]:
        lines.append(f"  节点删除 {len(nd['removed'])}: {nd['removed'][:MAX_DIFF_SHOWN]}")
    if nd["changed"]:
        lines.append(f"  节点属性变化 {len(nd['changed'])}:")
        for c in nd["changed"][:MAX_DIFF_SHOWN]:
            lines.append(f"    {c['id']} .{c['field']}: {c['old']!r} → {c['new']!r}")
    if ed["added"]:
        lines.append(f"  边新增 {len(ed['added'])}:")
        for e in ed["added"][:MAX_DIFF_SHOWN]:
            lines.append(f"    + {e}")
    if ed["removed"]:
        lines.append(f"  边删除 {len(ed['removed'])}:")
        for e in ed["removed"][:MAX_DIFF_SHOWN]:
            lines.append(f"    - {e}")
    if d["summary_delta"]:
        lines.append(f"  统计变化: {json.dumps(d['summary_delta'], ensure_ascii=False, sort_keys=True)}")
    total = (len(nd["added"]) + len(nd["removed"]) + len(nd["changed"])
             + len(ed["added"]) + len(ed["removed"]))
    lines.append(f"  合计 {total} 处差异")
    return "\n".join(lines)


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"❌ 快照不存在: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def _write(path: str, snap: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _add_input_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--filelist", help="filelist 路径")
    ap.add_argument("--file", action="append", dest="files", help="源文件（可重复）")
    ap.add_argument("--source-dir", help="目录下的 *.sv/*.v 全部作为源文件")
    ap.add_argument("--target", help="target_module（子树限定）")


def _snapshot_from_args(args) -> dict:
    return build_snapshot(
        args.name,
        filelist=args.filelist,
        files=args.files,
        source_dir=args.source_dir,
        target=args.target,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SignalGraph 快照基线工具（只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="采集快照并写入 --out")
    cap.add_argument("--name", required=True, help="快照名（写入快照）")
    _add_input_args(cap)
    cap.add_argument("--out", required=True, help="输出 JSON 路径")

    dif = sub.add_parser("diff", help="比对两份快照")
    dif.add_argument("old")
    dif.add_argument("new")
    dif.add_argument("--json", action="store_true", help="输出结构化差异 JSON")

    ver = sub.add_parser("verify", help="重新采集并与基线比对（重构回归）")
    ver.add_argument("--snapshot", required=True, help="基线快照路径")
    ver.add_argument("--name", default=None, help="快照名（默认取基线里的 name）")
    _add_input_args(ver)
    ver.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "capture":
        snap = _snapshot_from_args(args)
        _write(args.out, snap)
        s = snap["summary"]
        print(f"✅ 快照已写入 {args.out}（{s['nodes']} 节点 / {s['edges']} 边）")
        return 0

    if args.cmd == "diff":
        d = diff_snapshots(_load(args.old), _load(args.new))
        print(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) if args.json else format_diff(d))
        return 0 if d["ok"] else 1

    # verify
    base = _load(args.snapshot)
    args.name = args.name or base.get("name", Path(args.snapshot).stem)
    snap = _snapshot_from_args(args)
    d = diff_snapshots(base, snap)
    print(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) if args.json else format_diff(d))
    return 0 if d["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
