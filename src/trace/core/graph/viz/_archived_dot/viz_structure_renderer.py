"""
viz_structure_renderer.py — Structure 图渲染器 (V8.0)

回答: "怎么连的？" — 实例之间的 port-port 连接关系

对标参考图风格: 左→右, 白底黑框矩形实例节点, 蓝色虚线 cluster
"""

from __future__ import annotations
from collections import defaultdict
from .viz_data_models import VizData


def _dot_id(s: str) -> str:
    r = []
    for ch in s:
        if ch.isalnum() or ch == "_": r.append(ch)
        else: r.append("_")
    return "T" + "".join(r)[:50]

def _short(s: str) -> str:
    return s.split(".")[-1]


def render_structure(viz: VizData, config: dict | None = None):
    """Structure 图 — 实例之间连接"""
    cfg = config or {}
    title = cfg.get("title", "Structure")

    out = []
    E = out.append
    
    E("digraph structure {")
    E(f'  rankdir=LR; bgcolor=white; label="{title}"; labelloc=t; fontsize=14;')
    E('  nodesep=0.5; ranksep=1.0;')
    E('  node [shape=box style=solid color=black fillcolor=white fontname="Courier" fontsize=9];')
    E('  edge [color=black arrowhead=none];')
    E("")

    # 分组: 实例节点 vs 端口节点
    instances = [n for n in viz.nodes if n.kind == "INSTANTIATED_MODULE"]
    inputs = [n for n in viz.nodes if n.kind == "PORT_IN"]
    outputs = [n for n in viz.nodes if n.kind == "PORT_OUT"]
    signals = [n for n in viz.nodes if n.kind in ("SIGNAL", "WIRE", "REG")]

    # Inputs cluster (左)
    if inputs:
        E('  subgraph cluster_inputs {')
        E('    label="Inputs"; fontsize=10; style=dashed; color="#2563eb"; bgcolor="#f8faff";')
        for n in sorted(inputs, key=lambda n: _short(n.id)):
            E(f'    {_dot_id(n.id)} [label="{_short(n.id)}" fontname="Courier"];')
        E('  }')
        E("")

    # Instances cluster (中)
    if instances:
        E('  subgraph cluster_instances {')
        E('    label="Instances"; fontsize=10; style=dashed; color="#2563eb"; bgcolor="#f8faff";')
        for n in sorted(instances, key=lambda n: _short(n.id)):
            E(f'    {_dot_id(n.id)} [label="{_short(n.id)}" shape=box3d '
              f'style=solid color=black fillcolor=white fontname="Courier" penwidth=1.5];')
        E('  }')
        E("")

    # Outputs cluster (右)
    if outputs:
        E('  subgraph cluster_outputs {')
        E('    label="Outputs"; fontsize=10; style=dashed; color="#2563eb"; bgcolor="#f8faff";')
        for n in sorted(outputs, key=lambda n: _short(n.id)):
            E(f'    {_dot_id(n.id)} [label="{_short(n.id)}" fontname="Courier"];')
        E('  }')
        E("")

    # Invisible rank edges
    if inputs and instances:
        E(f'  {_dot_id(inputs[0].id)} -> {_dot_id(instances[0].id)} [style=invis weight=0];')
    if instances and outputs:
        E(f'  {_dot_id(instances[-1].id)} -> {_dot_id(outputs[0].id)} [style=invis weight=0];')

    # 边: 信号连接关系
    seen = set()
    for e in viz.edges:
        key = (e.src, e.dst)
        if key in seen: continue
        seen.add(key)
        if e.kind in ("CLOCK", "RESET"): continue
        E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)};')

    E("}")
    return "\n".join(out)
