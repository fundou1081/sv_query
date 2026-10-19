"""
viz_control_new.py — Control 图 (V8.0 全新构造)

参考图风格: 左→右, 直角矩形, 蓝色虚线 cluster 分目标信号
回答: "谁来控制？"

使用 control_tree.ControlTree 的数据结构 (muxes: dict, simples: list)
"""

from __future__ import annotations
from collections import defaultdict
from .viz_data_models import VizData, VizEdge
from .control_tree import build_control_tree, ControlTree, MuxNode, SimpleCondition


def _id(s: str) -> str:
    r = []
    for ch in s:
        if ch.isalnum() or ch == "_": r.append(ch)
        else: r.append("_")
    return "C" + "".join(r)[:50]

def _short(s: str) -> str: return s.split(".")[-1]


def render_control_new(viz: VizData, config: dict | None = None):
    """全新 CONTROL 图 — 参考图风格"""
    cfg = config or {}
    title = cfg.get("title", "Control Flow")

    out = []
    E = out.append
    E("digraph control {")
    E(f'  rankdir=LR; bgcolor=white; label="{title}"; labelloc=t; fontsize=14;')
    E('  nodesep=0.4; ranksep=0.8;')
    E('  node [shape=box style=solid color=black fillcolor=white fontname="Courier" fontsize=9];')
    E('  edge [color=black arrowhead=none fontsize=7];')
    E("")

    # 收集每个 dst 的条件边
    cond_edges: dict[str, list[VizEdge]] = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, "condition_chain", None) or []
        if chain:
            cond_edges[e.dst].append(e)

    for dst_id, edges in sorted(cond_edges.items()):
        dst_name = _short(dst_id)
        tree = build_control_tree(dst_id, edges)

        E(f'  subgraph cluster_{_id(dst_id)} {{')
        E(f'    label="{dst_name}"; fontsize=10; fontname="Helvetica";')
        E(f'    style=dashed; color="#2563eb"; bgcolor="#f8faff";')

        # 目标节点
        E(f'    {_id(dst_id)} [label="{dst_name}" shape=box '
          f'style=solid color=black fillcolor=white];')

        # Mux 节点 (按深度排序)
        for mux in tree.sorted_muxes():
            mux_nid = _id(mux.id)
            E(f'    {mux_nid} [label="{mux.label}" shape=diamond '
              f'style=solid color="#2563eb" fillcolor="#e8f0fe" fontsize=9];')
            # 分支边
            for branch in mux.branches:
                if isinstance(branch.child, str):
                    # leaf: 直接到目标信号
                    target_nid = _id(branch.child)
                    E(f'    {mux_nid} -> {target_nid} '
                      f'[label="{branch.condition}"];')
                elif branch.child is not None:
                    # inner mux
                    child_nid = _id(branch.child.id)
                    E(f'    {mux_nid} -> {child_nid} '
                      f'[label="{branch.condition}"];')
                else:
                    # source → mux
                    src_nid = _id(branch.source)
                    E(f'    {src_nid} [label="{_short(branch.source)}" '
                      f'shape=box style=solid color=black fillcolor=white];')
                    E(f'    {src_nid} -> {mux_nid} '
                      f'[label="{branch.condition}"];')

        # 简单条件: source → target (虚线蓝)
        for sc in tree.simples:
            src_nid = _id(sc.source)
            E(f'    {src_nid} [label="{_short(sc.source)}" '
              f'shape=box style=solid color=black fillcolor=white];')
            E(f'    {src_nid} -> {_id(dst_id)} '
              f'[label="{sc.condition}" style=dashed color="#2563eb"];')

        E("  }")
        E("")

    E("}")
    return "\n".join(out)
