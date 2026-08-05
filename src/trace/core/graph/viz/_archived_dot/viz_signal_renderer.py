"""
viz_signal_renderer.py — Signal 图 Mermaid 渲染器 (V7.0)

回答的问题: "谁和谁有关系？"

输出 Mermaid flowchart 格式，可直接粘贴到 GitHub/Notion/Obsidian 渲染。
设计原则:
  - 简洁: 只显示信号名 + 连接方向
  - 可读: 纯文本格式，不依赖 DOT/Graphviz
  - 不显示表达式、条件、运算符、位宽
  - CLOCK/RESET 边默认排除
"""

from __future__ import annotations
from collections import defaultdict

from .viz_data_models import VizData, VizEdge, VizNode


def _short(s: str) -> str:
    return s.split(".")[-1] if "." in s else s


def _mid(s: str) -> str:
    """Mermaid-safe node ID: 只保留字母数字下划线"""
    r = []
    for ch in _short(s):
        if ch.isalnum() or ch == "_":
            r.append(ch)
        else:
            r.append("_")
    result = "".join(r)
    if not result or result[0].isdigit():
        result = "s_" + result
    return "N" + result[:50]


def render_signal_mermaid(viz: VizData, config: dict | None = None) -> str:
    """生成 Signal 图 Mermaid flowchart。

    节点按 kind 颜色标注 (只标注首次出现的 kind)。
    边只显示 drive 关系，CLOCK/RESET 默认隐藏。
    """
    cfg = config or {}
    title = cfg.get("title", "Signal Graph")
    show_clk_rst = cfg.get("show_clock_reset", False)
    show_kind_colors = cfg.get("show_kind_colors", True)
    show_port_shape = cfg.get("show_port_shape", True)

    # ── kind → Mermaid 样式前缀 ──
    # Mermaid flowchart 不支持颜色，但可以用 subgraph 注释
    lines = [f"---\ntitle: {title}\n---", "flowchart TB", ""]

    # ── 按 kind 分组用 subgraph ──
    if show_kind_colors:
        kind_groups: dict[str, list[VizNode]] = defaultdict(list)
        for n in viz.nodes:
            kind_groups[n.kind].append(n)

        kind_labels = {
            "REG": "Registers",
            "WIRE": "Wires",
            "SIGNAL": "Signals",
            "PORT_IN": "Input Ports",
            "PORT_OUT": "Output Ports",
            "PORT_INOUT": "InOut Ports",
            "CONST": "Constants",
            "INSTANTIATED_MODULE": "Instances",
        }
        for kind, nodes in kind_groups.items():
            if not nodes:
                continue
            label = kind_labels.get(kind, kind)
            lines.append(f"  subgraph {kind}[\"{label}\"]")
            for n in nodes[:30]:  # 每个 subgraph 最多 30 个节点
                port_mark = ""
                if show_port_shape and kind in ("PORT_IN", "PORT_OUT", "PORT_INOUT"):
                    if kind == "PORT_IN":
                        port_mark = "(in) "
                    elif kind == "PORT_OUT":
                        port_mark = "(out) "
                    else:
                        port_mark = "(io) "
                lines.append(f"    {_mid(n.id)}[\"{port_mark}{_short(n.id)}\"]")
            lines.append("  end")
            lines.append("")
    else:
        for n in viz.nodes:
            lines.append(f"  {_mid(n.id)}[\"{_short(n.id)}\"]")
        lines.append("")

    # ── 边 ──
    edge_seen: set[tuple[str, str]] = set()
    for e in viz.edges:
        if not show_clk_rst and e.kind in ("CLOCK", "RESET"):
            continue
        key = (e.src, e.dst)
        if key in edge_seen:
            continue
        edge_seen.add(key)
        lines.append(f"  {_mid(e.src)} --> {_mid(e.dst)}")

    lines.append("")
    return "\n".join(lines)


# ── 兼容 DOT 接口（供可视化工具链） ──
def render_signal_dot(viz: VizData, config: dict | None = None) -> str:
    """生成 Signal 图 DOT（Graphviz 格式，供非 Mermaid 场景使用）。"""
    cfg = config or {}
    title = cfg.get("title", "Signal Graph")
    layout = cfg.get("layout", "TB")
    show_clk_rst = cfg.get("show_clock_reset", False)

    out = [
        "digraph signal {",
        f'  label="{title}"; labelloc=t; rankdir={layout};',
        "  splines=polyline; nodesep=0.4; ranksep=0.6; bgcolor=white;",
        '  node [fontname="Helvetica" fontsize=10];',
        '  edge [fontname="Helvetica" fontsize=7];',
        "",
    ]
    emit = out.append

    _KIND_COLORS = {
        "REG": ("#c8e6c9", "#2e7d32", "box"),
        "WIRE": ("#e3f2fd", "#1565c0", "ellipse"),
        "SIGNAL": ("#f3e5f5", "#6a1b9a", "ellipse"),
        "PORT_IN": ("#fff3e0", "#e65100", "invhouse"),
        "PORT_OUT": ("#fff3e0", "#e65100", "invhouse"),
        "PORT_INOUT": ("#fce4ec", "#c62828", "diamond"),
        "CONST": ("#eceff1", "#546e7a", "hexagon"),
        "INSTANTIATED_MODULE": ("#f5f5f5", "#616161", "box3d"),
    }

    def _did(s): 
        r = []
        for ch in s:
            if ch.isalnum() or ch == "_": r.append(ch)
            else: r.append(f"_{ord(ch)}_")
        return "n" + "".join(r[:60])

    def _s(s): return s.replace('"','\\"').replace('\n','\\n')

    for n in viz.nodes:
        style = _KIND_COLORS.get(n.kind, ("#f5f5f5", "#999999", "box"))
        fc, oc, shape = style
        emit(
            f'  {_did(n.id)} [label="{_s(_short(n.id))}" shape={shape} '
            f'style="filled,rounded" fillcolor="{fc}" color="{oc}" fontsize=9];'
        )

    edge_seen: set[tuple[str, str]] = set()
    for e in viz.edges:
        if not show_clk_rst and e.kind in ("CLOCK", "RESET"):
            continue
        key = (e.src, e.dst)
        if key in edge_seen:
            continue
        edge_seen.add(key)
        style = "solid" if e.kind == "DRIVER" else "dashed"
        emit(f'  {_did(e.src)} -> {_did(e.dst)} [style={style} color="#666666" arrowhead=normal];')

    emit("}")
    return "\n".join(out)
