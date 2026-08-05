"""
viz_signal_v8.py — Signal 图全新渲染器 (V8.0)

参考图风格: 直角矩形, 黑白灰, 蓝色虚线 cluster, 边缘输入输出
回答: "谁和谁有关系？"
"""

from __future__ import annotations
from collections import defaultdict
from .viz_data_models import VizData, VizEdge, VizNode


def _mid(s: str) -> str:
    """sanitized id"""
    r = []
    for ch in s:
        if ch.isalnum() or ch == "_": r.append(ch)
        else: r.append("_")
    x = "".join(r)
    if x and x[0].isdigit(): x = "s_" + x
    return "N" + x[:50]

def _short(s: str) -> str:
    return s.split(".")[-1] if "." in s else s


# ── kind label maps ──
_KIND_LABEL = {
    "PORT_IN": "Inputs", "PORT_OUT": "Outputs", "REG": "Registers",
    "WIRE": "Wires", "SIGNAL": "Signals", "CLOCK": "Clock",
    "RESET": "Reset", "CONST": "Constants",
}


def render_signal_v8(viz: VizData, config: dict | None = None) -> str:
    """
    输出 Graphviz DOT, 左→右布局, 直角矩形, 蓝色虚线 cluster,
    输入在左, 输出在右, 中间信号居中.
    """
    cfg = config or {}
    title = cfg.get("title", "Signal Graph")
    hide_clk_rst = cfg.get("hide_clock_reset", True)
    show_width = cfg.get("show_width", True)

    out = []
    E = out.append

    # ── 全局布局: 左→右 ──
    E("digraph signal_v8 {")
    E('  rankdir=LR; bgcolor=white;')
    E(f'  label="{title}"; labelloc=t; fontsize=14;')
    E('  nodesep=0.6; ranksep=1.0;')
    E('  node [shape=box style=solid fontname="Helvetica" fontsize=10 penwidth=1 color=black fillcolor=white];')
    E('  edge [fontname="Helvetica" fontsize=8 color=black arrowhead=none penwidth=1];')
    E("")

    # ── 分组: inputs | mid signals | outputs ──
    inputs: list[VizNode] = []
    outputs: list[VizNode] = []
    mid_signals: list[VizNode] = []
    clock_reset: list[VizNode] = []
    for n in viz.nodes:
        k = n.kind
        if k in ("PORT_IN",) or (k == "CONST"):
            inputs.append(n)
        elif k in ("PORT_OUT", "PORT_INOUT"):
            outputs.append(n)
        elif k in ("CLOCK", "RESET"):
            clock_reset.append(n)
        else:
            mid_signals.append(n)

    # 排序: 按 short name
    inputs.sort(key=lambda n: _short(n.id))
    outputs.sort(key=lambda n: _short(n.id))
    mid_signals.sort(key=lambda n: _short(n.id))

    # ── 绘制: 3 个虚线 cluster (参考图风格) ──
    # cluster 1: Inputs (左)
    E(f'  subgraph cluster_input {{')
    E(f'    label="Inputs"; fontsize=11; fontname="Helvetica";')
    E(f'    style=dashed; color="#2563eb"; bgcolor="#fafaff";')
    for n in inputs:
        label = _short(n.id)
        if show_width and n.width and n.width != (0, 0):
            msb, lsb = n.width
            w = f"[{msb}]" if msb == lsb else f"[{msb}:{lsb}]"
            label = f"{label}\\n{{{w}}}"
        E(f'    {_mid(n.id)} [label="{label}" fontcolor=black];')
    E("  }")
    E("")

    # cluster 2: Signals (中)
    E(f'  subgraph cluster_signals {{')
    E(f'    label="Internal Signals"; fontsize=11; fontname="Helvetica";')
    E(f'    style=dashed; color="#2563eb"; bgcolor="#fafaff";')
    for n in mid_signals:
        label = _short(n.id)
        if show_width and n.width and n.width != (0, 0):
            msb, lsb = n.width
            w = f"[{msb}]" if msb == lsb else f"[{msb}:{lsb}]"
            label = f"{label}\\n{{{w}}}"
        E(f'    {_mid(n.id)} [label="{label}" fontcolor=black];')
    E("  }")
    E("")

    # cluster 3: Outputs (右)
    if outputs:
        E(f'  subgraph cluster_output {{')
        E(f'    label="Outputs"; fontsize=11; fontname="Helvetica";')
        E(f'    style=dashed; color="#2563eb"; bgcolor="#fafaff";')
        for n in outputs:
            label = _short(n.id)
            if show_width and n.width and n.width != (0, 0):
                msb, lsb = n.width
                w = f"[{msb}]" if msb == lsb else f"[{msb}:{lsb}]"
                label = f"{label}\\n{{{w}}}"
            E(f'    {_mid(n.id)} [label="{label}" fontcolor=black];')
        E("  }")
        E("")

    # ── 边: 黑色实线, 无箭头 ──
    #
    # 用 invisible edge 强制 rank 顺序: inputs → mid → outputs
    if inputs and mid_signals:
        E(f'  {_mid(inputs[0].id)} -> {_mid(mid_signals[0].id)} [style=invis weight=0];')
    if mid_signals and outputs:
        E(f'  {_mid(mid_signals[-1].id)} -> {_mid(outputs[0].id)} [style=invis weight=0];')

    # 实际边
    edge_seen: set[tuple[str, str]] = set()
    for e in viz.edges:
        if hide_clk_rst and e.kind in ("CLOCK", "RESET"):
            continue
        key = (e.src, e.dst)
        if key in edge_seen:
            continue
        edge_seen.add(key)
        # 统一黑色实线, 无箭头
        E(f'  {_mid(e.src)} -> {_mid(e.dst)};')

    E("}")
    return "\n".join(out)
