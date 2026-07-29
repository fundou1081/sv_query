"""
viz_dot_renderer.py — 统一 DOT 渲染器 (V6.7)

输入: VizData
输出: DOT 字符串

原则:
- 纯数据驱动，不做过滤/分析
- 所有 6 种画图功能共用这一个渲染器
- 装饰字段 (condition, risk, class) 有就渲染，没有就跳过
"""

from __future__ import annotations

from typing import Any

from ..analyzer._dot_common import sanitize_dot_id, signal_class_color
from .viz_data_models import VizData, VizNode, VizEdge


# ── DOT 配置默认值 ──

DEFAULT_CONFIG: dict[str, Any] = {
    "layout": "TB",  # TB | LR
    "layout_engine": "dot",  # dot | neato | fdp
    "node_spacing": 0.4,
    "rank_spacing": 0.6,
    "edge_labels": True,  # 显示边标签 (condition/expression)
    "show_clock_reset": False,  # 显示 CLOCK/RESET 边
    "cluster_by_module": False,  # 按模块分组 cluster
    "cluster_prefix": "",  # cluster 标签前缀
}


def render_dot(
    viz: VizData,
    config: dict[str, Any] | None = None,
) -> str:
    """从 VizData 生成 DOT 图

    Args:
        viz: 统一可视化数据包
        config: DOT 渲染选项 (兼容 DEFAULT_CONFIG)

    Returns:
        DOT 格式字符串
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    _sid = sanitize_dot_id
    lines: list[str] = []

    # ── header ──
    title = viz.meta.get("title", "Signal Graph")
    lines.append(f"digraph viz {{")
    lines.append(f'  label="{title}";')
    lines.append("  labelloc=t;")
    lines.append(f"  rankdir={cfg['layout']};")
    lines.append("  splines=spline;")
    lines.append(f"  nodesep={cfg['node_spacing']};")
    lines.append(f"  ranksep={cfg['rank_spacing']};")
    lines.append('  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];')
    lines.append("  bgcolor=white;")
    lines.append("  newrank=true;  // [V6.8] enforce cluster rank ordering")
    if cfg["layout_engine"] in ("neato", "fdp"):
        lines.append("  overlap=false;")
        lines.append("  ratio=1.0;")
    lines.append("")

    # ── nodes ──
    show_src = cfg.get("show_source", False)
    for node in viz.nodes:
        attrs = _node_attrs(node, show_source=show_src)
        lines.append(f'  "{_sid(node.id)}" [{"; ".join(attrs)}];')

    if viz.nodes:
        lines.append("")

    # ── edges ──
    for edge in viz.edges:
        if not cfg["show_clock_reset"] and edge.kind in ("CLOCK", "RESET"):
            continue
        attrs = _edge_attrs(edge, cfg)
        if not attrs:
            lines.append(f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}";')
        else:
            lines.append(f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}" [{"; ".join(attrs)}];')

    lines.append("}")
    return "\n".join(lines)


# ── private: node attribute builder ──

_KIND_SHAPES: dict[str, str] = {
    "REG": "box",
    "SIGNAL": "ellipse",
    "WIRE": "ellipse",
    "PORT_IN": "invhouse",
    "PORT_OUT": "invhouse",
    "PORT_INOUT": "diamond",
    "CONST": "hexagon",
    "INSTANTIATED_MODULE": "box3d",
    "INSTANCE": "box3d",
}

_CLASS_COLORS: dict[str, str] = {
    "DATA": "#4477cc",
    "CONTROL": "#ff8833",
    "CLOCK": "#888888",
    "RESET": "#cc4444",
}


def _node_attrs(node: VizNode, show_source: bool = False) -> list[str]:
    """构建单个节点的 DOT 属性列表"""
    attrs: list[str] = []

    # label
    label_parts = [node.label]
    if node.kind and node.kind not in ("SIGNAL", "WIRE"):
        label_parts.append(f"[{node.kind}]")
    if node.width and node.width != (0, 0):
        msb, lsb = node.width
        if msb == lsb:
            label_parts.append(f"[{msb}]")
        else:
            label_parts.append(f"[{msb}:{lsb}]")
    attrs.append(f'label="{" ".join(label_parts)}"')

    # show_source: only add tooltip/URL when explicitly enabled
    if show_source and node.file and node.line > 0:
        attrs.append(f'tooltip="{node.file}:{node.line}"')
        attrs.append(f'URL="{node.file}#{node.line}"')

    # shape
    shape = _KIND_SHAPES.get(node.kind, "box")
    attrs.append(f"shape={shape}")

    # color: class > risk > kind
    if node.class_ and node.class_ in _CLASS_COLORS:
        clr = _CLASS_COLORS[node.class_]
        attrs.append(f'fillcolor="{clr}22"')
        attrs.append(f'color="{clr}"')
    elif node.risk_level == "CRITICAL":
        attrs.append('fillcolor="#ff000044"')
        attrs.append('color="#ff0000"')
    elif node.risk_level == "HIGH":
        attrs.append('fillcolor="#ff660044"')
        attrs.append('color="#ff6600"')
    elif node.risk_level == "MEDIUM":
        attrs.append('fillcolor="#ffcc0044"')
        attrs.append('color="#cc8800"')
    else:
        attrs.append('fillcolor="#f0f0f0"')
        attrs.append('color="#888888"')

    # penwidth for critical nodes
    if node.is_critical:
        attrs.append("penwidth=2.5")

    return attrs


def _edge_attrs(edge: VizEdge, cfg: dict) -> list[str]:
    """构建单条边的 DOT 属性列表"""
    attrs: list[str] = []

    # label: condition or expression
    if cfg.get("edge_labels", True):
        label_parts: list[str] = []
        if edge.condition and edge.condition.strip():
            if _is_simple_condition(edge.condition):
                label_parts.append(edge.condition.strip())
            else:
                # 长条件 → 截断
                label_parts.append(edge.condition.strip()[:40])
        if edge.expression and edge.expression.strip() and edge.expression != edge.src.split(".")[-1]:
            expr = edge.expression.strip()
            label_parts.append(expr[:30])
        if label_parts:
            sep = "\\n"
            attrs.append(f'label="{sep.join(label_parts)}"')
            attrs.append("fontsize=9")

    # style: control edge → dashed, clock/reset → dotted
    if edge.is_control_edge:
        attrs.append("style=dashed")
    elif edge.kind in ("CLOCK", "RESET"):
        attrs.append("style=dotted")
    elif edge.kind == "CONNECTION":
        attrs.append("style=solid")

    # color: class > kind
    if edge.class_ and edge.class_ in _CLASS_COLORS:
        attrs.append(f'color="{_CLASS_COLORS[edge.class_]}"')
    elif edge.is_control_edge:
        attrs.append('color="#ff8833"')
    elif edge.kind == "CLOCK":
        attrs.append('color="#888888"')
    elif edge.kind == "RESET":
        attrs.append('color="#cc4444"')

    # arrowhead
    if edge.kind == "BIT_SELECT":
        attrs.append('arrowhead="open"')

    return attrs


def _is_simple_condition(cond: str) -> bool:
    """是否为简单条件（可显示在边上）"""
    return len(cond) < 50 and not cond.startswith("(")
