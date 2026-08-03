"""
viz_signal_new.py — Signal 图 (V8.0)

对标参考图: 左→右, 直角矩形的"块"感, 黑+蓝+白配色
回答: "谁和谁有关系？"
"""

from __future__ import annotations
from .viz_data_models import VizData


def _mid(s: str) -> str:
    r = []
    for ch in s:
        if ch.isalnum() or ch == "_": r.append(ch)
        else: r.append("_")
    x = "".join(r)
    if x and x[0].isdigit(): x = "s_" + x
    return "S" + x[:50]

def _short(s: str) -> str:
    return s.split(".")[-1]


def render_signal(viz: VizData, config: dict | None = None):
    cfg = config or {}
    title = cfg.get("title", "Signal Graph")
    show_width = cfg.get("show_width", True)
    hide_clk_rst = cfg.get("hide_clock_reset", True)

    out = []
    E = out.append
    E("digraph signal {")
    E(f'  rankdir=TB; bgcolor=white; label="{title}"; labelloc=t; fontsize=14; fontname="Helvetica";')
    E('  nodesep=0.4; ranksep=0.6;')
    E('  node [shape=box style=solid color=black fillcolor=white fontname="Courier" fontsize=9 penwidth=1];')
    E('  edge [color=black arrowhead=none penwidth=1];')
    E("")

    # 分组: inputs (左) / mid signals / outputs (右)
    inputs, outputs, mids, clkrst = [], [], [], []
    for n in viz.nodes:
        k = n.kind
        if k in ("PORT_IN",): inputs.append(n)
        elif k in ("PORT_OUT", "PORT_INOUT"): outputs.append(n)
        elif k in ("CLOCK", "RESET"): clkrst.append(n)
        else: mids.append(n)

    for lst in [inputs, outputs, mids, clkrst]:
        lst.sort(key=lambda n: _short(n.id))

    def _cluster(label, nodes):
        if not nodes: return
        E(f'  subgraph cluster_{_mid(label)} {{')
        E(f'    label="{label}"; fontsize=10; fontname="Helvetica";')
        E(f'    style=dashed; color="#2563eb"; bgcolor="#f8faff";')
        for n in nodes:
            nm = _short(n.id)
            if show_width and n.width and n.width != (0, 0):
                msb, lsb = n.width
                w = f"[{msb}]" if msb == lsb else f"[{msb}:{lsb}]"
                nm = f"{nm} ({w})"
            E(f'    {_mid(n.id)} [label="{nm}" fontname="Courier" fontcolor=black];')
        E("  }")
        E("")

    _cluster("Inputs", inputs)
    _cluster("Clock/Reset", clkrst if not hide_clk_rst else [])
    _cluster("Internal Signals", mids)
    _cluster("Outputs", outputs)

    # rank constraint: input→mid→output
    all_in = inputs + clkrst
    if all_in and mids:
        E(f'  {_mid(all_in[0].id)} -> {_mid(mids[0].id)} [style=invis weight=0];')
    if mids and outputs:
        E(f'  {_mid(mids[-1].id)} -> {_mid(outputs[0].id)} [style=invis weight=0];')

    # 边: 实线黑, 无箭头
    seen = set()
    for e in viz.edges:
        if hide_clk_rst and e.kind in ("CLOCK", "RESET"): continue
        key = (e.src, e.dst)
        if key in seen: continue
        seen.add(key)
        E(f'  {_mid(e.src)} -> {_mid(e.dst)};')

    E("}")
    return "\n".join(out)
