"""
viz_compute_renderer.py — 运算架构图渲染器 (V6.7)

在 render_dot 基础上，把 SignalSource.op 映射为可读运算符号，
直接显示在边上。MUX 和比较目标用特殊标记。

用法:
    from .viz_compute_renderer import render_compute_dot
    dot = render_compute_dot(viz, {"title": "Compute: demo"})
"""

from __future__ import annotations

from .viz_data_models import VizData, VizNode, VizEdge
from .viz_dot_renderer import _node_attrs

from ..analyzer._dot_common import sanitize_dot_id


# pyslang OperatorName → 可读符号
_OP_SYMBOLS: dict[str, str] = {
    "Add": "+",
    "Subtract": "−",
    "Multiply": "×",
    "Divide": "÷",
    "Mod": "%",
    "BinaryAnd": "&",
    "BinaryOr": "|",
    "BinaryXor": "^",
    "BinaryNand": "~&",
    "BinaryNor": "~|",
    "BinaryXnor": "~^",
    "LogicalAnd": "&&",
    "LogicalOr": "||",
    "LogicalNot": "!",
    "LogicalShiftLeft": "<<",
    "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<",
    "ArithmeticShiftRight": ">>>",
    "Equality": "==",
    "Inequality": "!=",
    "GreaterThan": ">",
    "GreaterThanEqual": ">=",
    "LessThan": "<",
    "LessThanEqual": "<=",
    "UnaryPlus": "+",
    "UnaryMinus": "−",
    "UnaryNot": "~",
    "UnaryLogicalNot": "!",
    "UnaryBitwiseAnd": "&",
    "UnaryBitwiseOr": "|",
}


def _op_label(edge: VizEdge) -> str:
    """从边的 SignalSource 信息生成运算标签"""
    parts: list[str] = []

    # 运算符
    if edge.source_op:
        sym = _OP_SYMBOLS.get(edge.source_op, edge.source_op)
        parts.append(sym)

    # 位范围
    if edge.source_bit_start is not None and edge.source_bit_end is not None:
        if edge.source_bit_start == edge.source_bit_end:
            parts.append(f"[{edge.source_bit_start}]")
        else:
            parts.append(f"[{edge.source_bit_start}:{edge.source_bit_end}]")

    # casts
    if edge.source_casts:
        for c in edge.source_casts:
            parts.insert(0, c)

    return " ".join(parts)


def _is_mux_target(signal_id: str, edges: list[VizEdge]) -> bool:
    """判断信号是否是 MUX 目标 (多个无条件的 driver 汇聚)"""
    unconditioned = [e for e in edges if e.dst == signal_id and e.kind == "DRIVER" and not e.condition]
    return len(unconditioned) >= 2


def render_compute_dot(
    viz: VizData,
    config: dict[str, str] | None = None,
) -> str:
    """生成运算架构图 DOT

    特点:
    - 边上显示运算符号 (+, −, &, >>, etc.)
    - 位范围标注 ([7:0])
    - MUX 目标用特殊颜色标记
    - 比较/选择逻辑用虚线

    Args:
        viz: VizData 包 (需 include_edge_expression=True)
        config: {"title": "...", "layout": "LR"}

    Returns:
        DOT 字符串
    """
    cfg = config or {}
    _sid = sanitize_dot_id

    lines: list[str] = [
        "digraph compute {",
        f'  label="{cfg.get("title", "Compute Architecture")}";',
        "  labelloc=t;",
        f"  rankdir={cfg.get('layout', 'LR')};",
        "  splines=polyline;",
        "  nodesep=0.5;",
        "  ranksep=0.8;",
        '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11];',
        "  bgcolor=white;",
        '  edge [fontname="Helvetica" fontsize=10];',
        "",
    ]

    # ── nodes ──
    for node in viz.nodes:
        attrs = _node_attrs(node)
        lines.append(f'  "{_sid(node.id)}" [{"; ".join(attrs)}];')

    if viz.nodes:
        lines.append("")

    # ── edges ──
    for edge in list(viz.edges):
        if edge.kind in ("CLOCK", "RESET"):
            continue  # 运算图不需要时钟边

        edge_lines: list[str] = []

        # label: 运算符号
        label_parts: list[str] = []
        op = _op_label(edge)
        if op:
            label_parts.append(op)

        # condition (简化版)
        if edge.condition:
            cond = _simplify_condition(edge.condition)
            if cond:
                label_parts.append(f"if {cond}")

        if label_parts:
            nl = "\\n"
            edge_lines.append(f'label="{nl.join(label_parts)}"')

        # style:
        has_style = False
        if edge.condition and edge.kind == "DRIVER":
            edge_lines.append("style=dashed")
            has_style = True
        if edge.is_control_edge:
            if not has_style:
                edge_lines.append("style=dashed")
            edge_lines.append('color="#ff8833"')

        # color by op type
        if edge.source_op and not edge.condition:
            op_color = _op_color(edge.source_op)
            if op_color:
                edge_lines.append(f'color="{op_color}"')

        if edge_lines:
            lines.append(f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}" [{"; ".join(edge_lines)}];')
        else:
            lines.append(f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}";')

    lines.append("}")
    return "\n".join(lines)


def _op_color(op_name: str) -> str:
    """按运算类别分配颜色"""
    if any(x in op_name for x in ("Add", "Subtract", "Multiply", "Divide")):
        return "#cc4400"  # 算术: 橙色
    if any(x in op_name for x in ("And", "Or", "Xor", "Nand", "Nor", "Not")):
        return "#4488cc"  # 逻辑: 蓝色
    if "Shift" in op_name:
        return "#44aa44"  # 移位: 绿色
    if any(x in op_name for x in ("Greater", "Less", "Equal", "Inequal")):
        return "#cc44cc"  # 比较: 紫色
    return ""


def _simplify_condition(cond: str) -> str:
    """简化 condition 显示"""
    c = cond.strip()
    if len(c) > 30:
        c = c[:27] + "..."
    return c
