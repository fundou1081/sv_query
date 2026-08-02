"""
viz_datapath_renderer.py — 定点数计算架构图渲染器 (V6.9 datapath)

融合 compute + timed + dataflow 的能力:
- OP 圆形节点标注运算符 (+, ×, <<, &, etc.)
- BFS stage cluster 划分时间层级
- 控制/条件边用虚线 + 条件标签
- 位宽显示在节点标签
- 按运算类别着色

输入: VizData (含 stage_id + SignalSource op/condition/width)
输出: DOT 字符串

用法:
    from .viz_datapath_renderer import render_datapath
    dot = render_datapath(viz, {"title": "Datapath: top"})
"""

from __future__ import annotations

from typing import Any

from ..analyzer._dot_common import sanitize_dot_id
from ..analyzer.stage_inferrer import infer_stages_bfs
from .viz_data_models import VizData

# ── 运算符映射 ──

_OP_SYMBOLS: dict[str, str] = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷", "Mod": "%",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "BinaryNand": "~&", "BinaryNor": "~|", "BinaryXnor": "~^",
    "LogicalAnd": "&&", "LogicalOr": "||", "LogicalNot": "!",
    "LogicalShiftLeft": "<<", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "ArithmeticShiftRight": ">>>",
    "Equality": "==", "Inequality": "!=",
    "GreaterThan": ">", "GreaterThanEqual": ">=",
    "LessThan": "<", "LessThanEqual": "<=",
    "UnaryPlus": "+", "UnaryMinus": "−",
    "UnaryNot": "~", "UnaryLogicalNot": "!",
    "UnaryBitwiseAnd": "&", "UnaryBitwiseOr": "|",
}

_OP_COLORS: dict[str, str] = {
    "Add": "#cc4400", "Subtract": "#cc4400", "Multiply": "#cc4400", "Divide": "#cc4400",
    "BinaryAnd": "#4488cc", "BinaryOr": "#4488cc", "BinaryXor": "#4488cc",
    "LogicalShiftLeft": "#44aa44", "LogicalShiftRight": "#44aa44",
    "ArithmeticShiftLeft": "#44aa44", "ArithmeticShiftRight": "#44aa44",
    "Equality": "#cc44cc", "GreaterThan": "#cc44cc", "LessThan": "#cc44cc",
}


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
    return "#888888"


# ── 节点形状 ──

_NODE_SHAPES: dict[str, str] = {
    "PORT_IN": "invhouse",
    "PORT_OUT": "invhouse",
    "REG": "box",
    "WIRE": "ellipse",
    "SIGNAL": "ellipse",
    "CONST": "hexagon",
}


def _node_fillcolor(kind: str) -> str:
    """节点填充色"""
    if kind == "PORT_IN":
        return "#ffeecc"  # 浅橙
    if kind == "PORT_OUT":
        return "#ccffee"  # 浅绿
    if kind == "REG":
        return "#e8e8ff"  # 浅蓝
    if kind == "CONST":
        return "#f5f5dc"  # 米色
    return "#ffffff"  # 白色


# ── 渲染 ──


def render_datapath(
    viz: VizData,
    config: dict[str, Any] | None = None,
) -> str:
    """生成定点数计算架构图 DOT

    Args:
        viz: VizData 包 (会自动 infer_stages_bfs 如果 stage_id 缺少)
        config: {
            "title": "...",
            "layout": "LR",     # LR or TB
            "focus": "signal_id",  # 可选：只画该信号的 N-hop 邻域
            "focus_depth": 2,   # focus 的 BFS 深度
            "show_control": True,  # 显示控制/条件边
            "show_source": False,
        }

    Returns:
        DOT 字符串
    """
    cfg = config or {}
    _sid = sanitize_dot_id

    title = cfg.get("title", "Datapath View")
    layout = cfg.get("layout", "LR")
    show_control = cfg.get("show_control", True)
    show_source = cfg.get("show_source", False)
    focus_signal = cfg.get("focus", "")
    focus_depth = cfg.get("focus_depth", 2)

    # ── Stage inference ──
    # If no nodes have stage_id, run BFS inference
    has_stages = any(n.stage_id is not None for n in viz.nodes)
    if not has_stages:
        infer_stages_bfs(viz)

    # ── Focus filter (optional) ──
    if focus_signal:
        viz = _focus_subgraph(viz, focus_signal, focus_depth)

    # ── Collect stage info ──
    stage_nodes: dict[int, list[str]] = {}
    for n in viz.nodes:
        sid = n.stage_id
        if sid is not None:
            stage_nodes.setdefault(sid, []).append(n.id)
    all_stages = sorted(stage_nodes.keys())

    if not all_stages:
        all_stages = [0]
        for n in viz.nodes:
            stage_nodes.setdefault(0, []).append(n.id)

    # ── Collect OP nodes ──
    # Dedup by (dst, op_name) so multiple operands share the same OP circle
    op_nodes: dict[str, tuple[str, str]] = {}  # op_id → (symbol, color)
    op_edges: list[dict] = []  # {src, op_id, dst, op_name, stage}
    seen_ops: set[tuple[str, str]] = set()

    for edge in viz.edges:
        if not edge.source_op or edge.kind not in ("DRIVER", ""):
            continue
        dst = edge.dst
        src = edge.src
        op_name = edge.source_op
        sym = _OP_SYMBOLS.get(op_name, op_name)
        color = _op_color(op_name)

        key = (dst, op_name)
        if key not in seen_ops:
            seen_ops.add(key)
            op_id = f"op_{op_name}_{_sid(dst)}"[:80]
            op_nodes[op_id] = (sym, color)

            # Determine which stage this OP belongs to
            # OP happens BEFORE dst: if dst is in stage N, OP in stage N-1
            dst_stage = -1
            for n in viz.nodes:
                if n.id == dst:
                    dst_stage = n.stage_id if n.stage_id is not None else -1
                    break
            if dst_stage > 0:
                op_stage = dst_stage - 1
            else:
                op_stage = 0
        else:
            op_id = f"op_{op_name}_{_sid(dst)}"[:80]
            dst_stage_for_color = -1
            for n in viz.nodes:
                if n.id == dst:
                    dst_stage_for_color = n.stage_id if n.stage_id is not None else -1
                    break
            op_stage = max(0, dst_stage_for_color - 1) if dst_stage_for_color > 0 else 0

        op_edges.append({
            "src": src,
            "op_id": op_id,
            "dst": dst,
            "op_name": op_name,
            "color": color,
            "stage": op_stage,
        })

    # Build stage→OP mapping (dedup)
    stage_op_nodes: dict[int, list[str]] = {}
    for oe in op_edges:
        stage_op_nodes.setdefault(oe["stage"], []).append(oe["op_id"])
    for sid in stage_op_nodes:
        stage_op_nodes[sid] = list(dict.fromkeys(stage_op_nodes[sid]))  # dedup

    # ── DOT output ──
    lines: list[str] = []

    lines.append("digraph datapath {")
    lines.append(f'  label="{title}";')
    lines.append("  labelloc=t;")
    lines.append(f"  rankdir={layout};")
    lines.append("  splines=polyline;")
    lines.append("  nodesep=0.4;")
    lines.append("  ranksep=0.8;")
    lines.append('  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];')
    lines.append('  edge [fontname="Helvetica" fontsize=9 color="#555555"];')
    lines.append("  bgcolor=white;")
    lines.append("  compound=true;")
    lines.append("  newrank=true;")
    lines.append("")

    # ── Legend ──
    lines.extend(_render_legend(all_stages))
    lines.append("")

    # ── Stage clusters ──
    for sid in all_stages:
        s_nodes = stage_nodes.get(sid, [])
        if not s_nodes:
            continue

        lines.append(f"  subgraph cluster_stage_{sid} {{")
        lines.append(f'    label="Stage {sid}";')
        lines.append('    style="rounded,filled";')
        lines.append('    fillcolor="#f8f8f8";')
        lines.append('    color="#cccccc";')
        lines.append("    fontsize=12;")
        lines.append("    penwidth=1;")

        # Signal nodes
        for n in viz.nodes:
            if n.id not in s_nodes:
                continue
            shape = _NODE_SHAPES.get(n.kind, "box")
            fill = _node_fillcolor(n.kind)

            # Build label: name + width + optional source
            lbl_parts = [n.label]
            if n.width and n.width != (0, 0):
                msb, lsb = n.width
                if msb == lsb:
                    lbl_parts.append(f"[{msb}]")
                else:
                    lbl_parts.append(f"[{msb}:{lsb}]")
            lbl = " ".join(lbl_parts)

            attrs = f'label="{lbl}"; shape={shape}; fillcolor="{fill}"'
            if n.kind == "REG":
                attrs += '; penwidth=2; color="#6666cc"'
            if show_source and n.file and n.line > 0:
                attrs += f'; tooltip="{n.file}:{n.line}"; URL="{n.file}#{n.line}"'

            lines.append(f'    "{_sid(n.id)}" [{attrs}];')

        # OP nodes (circles)
        for op_id in stage_op_nodes.get(sid, []):
            sym, color = op_nodes.get(op_id, ("?", "#888888"))
            lines.append(
                f'    "{_sid(op_id)}" [label="{sym}"; shape=circle; '
                f'style=filled; fillcolor="#ffffff"; color="{color}"; '
                f'penwidth=1.5; fontsize=12; fontname="Helvetica-Bold"];'
            )

        lines.append("  }")
        lines.append("")

    # ── Inter-stage rank edges (invisible, enforce ordering) ──
    if len(all_stages) >= 2:
        for i in range(len(all_stages) - 1):
            cur = all_stages[i]
            nxt = all_stages[i + 1]
            cnodes = stage_nodes.get(cur, [])
            nnodes = stage_nodes.get(nxt, [])
            if cnodes and nnodes:
                lines.append(
                    f'  "{_sid(cnodes[0])}" -> "{_sid(nnodes[0])}" '
                    f'[style=invis; weight=100; ltail="cluster_stage_{cur}"; '
                    f'lhead="cluster_stage_{nxt}"];'
                )

    # ── Data edges: src → OP → dst ──
    seen_op_dst: set[tuple[str, str]] = set()

    for oe in op_edges:
        src = oe["src"]
        dst = oe["dst"]
        op_id = oe["op_id"]
        color = oe["color"]

        # src → OP
        lines.append(f'  "{_sid(src)}" -> "{_sid(op_id)}" [color="{color}"];')

        # OP → dst (dedup)
        key = (op_id, dst)
        if key not in seen_op_dst:
            seen_op_dst.add(key)
            lines.append(f'  "{_sid(op_id)}" -> "{_sid(dst)}" [color="{color}"];')

    # ── Control/condition edges (dashed) ──
    if show_control:
        seen_data_pairs = {(oe["src"], oe["dst"]) for oe in op_edges}
        for edge in viz.edges:
            if (edge.src, edge.dst) in seen_data_pairs:
                continue
            if edge.kind in ("CLOCK", "RESET"):
                continue

            is_ctrl = edge.is_control_edge or bool(edge.condition)
            if not is_ctrl:
                continue

            edge_attrs = []
            if edge.condition and edge.condition.strip():
                cond = _simplify_condition(edge.condition)
                edge_attrs.append(f'label="if {cond}"')
                edge_attrs.append("fontsize=8")
            edge_attrs.append('style=dashed')
            edge_attrs.append('color="#ff8833"')

            lines.append(
                f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}" '
                f'[{"; ".join(edge_attrs)}];'
            )

    # ── Direct data edges (no OP — e.g. wire passthrough) ──
    seen_any_pair = {(oe["src"], oe["dst"]) for oe in op_edges}
    for edge in viz.edges:
        if (edge.src, edge.dst) in seen_any_pair:
            continue
        if edge.kind in ("CLOCK", "RESET"):
            continue
        if edge.is_control_edge and show_control:
            continue  # already rendered above
        # Simple passthrough
        lines.append(
            f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}" '
            f'[style=dotted; color="#aaaaaa"];'
        )

    lines.append("}")
    return "\n".join(lines)


# ── helpers ──


def _focus_subgraph(viz: VizData, focus_signal: str, depth: int) -> VizData:
    """对指定信号做 BFS N-hop 子图裁剪"""
    from collections import deque

    # Build adjacency
    adj: dict[str, list[str]] = {}
    for e in viz.edges:
        adj.setdefault(e.src, []).append(e.dst)
        adj.setdefault(e.dst, []).append(e.src)

    if focus_signal not in adj:
        return viz  # fallback: return full graph

    # BFS from focus
    visited: set[str] = set()
    q: deque[tuple[str, int]] = deque([(focus_signal, 0)])
    while q:
        nid, d = q.popleft()
        if nid in visited or d > depth:
            continue
        visited.add(nid)
        for nb in adj.get(nid, []):
            if nb not in visited:
                q.append((nb, d + 1))

    # Filter nodes and edges
    return VizData(
        meta={**viz.meta, "focus": focus_signal, "focus_depth": depth},
        nodes=[n for n in viz.nodes if n.id in visited],
        edges=[e for e in viz.edges if e.src in visited and e.dst in visited],
    )


def _simplify_condition(cond: str) -> str:
    """简化条件字符串以便显示在图上"""
    c = cond.strip()
    if len(c) > 40:
        c = c[:37] + "..."
    return c


def _render_legend(stages: list[int]) -> list[str]:
    """生成图例"""
    lines = [
        "  subgraph cluster_legend {",
        '    label="Legend"; style="rounded,filled"; fillcolor="#fafafa";',
        '    color="#aaaaaa"; fontsize=10;',
        '    node [shape=plaintext fontsize=9];',
    ]

    items = [
        ("○", "Data path", "#555555", "solid"),
        ("···", "Control/MUX", "#ff8833", "dashed"),
        ("┃", "Clock", "#888888", "dotted"),
        ("", "", "", ""),
    ]
    for sym, desc, clr, _sty in items:
        if not sym:
            continue
        lines.append(
            f'    legend_{sym} [label="{sym} {desc}"; '
            f'color="{clr}"; fontcolor="{clr}"];'
        )
    lines.append("  }")
    return lines
