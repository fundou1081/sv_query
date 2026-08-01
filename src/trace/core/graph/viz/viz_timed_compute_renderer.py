"""
viz_timed_compute_renderer.py — 时间轴运算架构图 (V6.7)

输入: VizData (含 pipeline_stages + SignalSource op)
输出: DOT 字符串

渲染规则:
- 时间轴从左到右 (rankdir=LR)
- 每个 pipeline stage 是一个 vertical cluster (subgraph)
- stage 内: 输入数据 → [OP 节点] → 输出寄存
- OP 节点用小圆圈/椭圆, 标注运算符号 (+, ×, >>, &, etc.)
- 寄存器节点 (REG) 用方框, 是 stage 边界
- 非 REG 的组合逻辑输出放在同一个 stage cluster 内
"""

from __future__ import annotations

from ..analyzer._dot_common import sanitize_dot_id
from .viz_data_models import VizData

_OP_SHAPES: dict[str, str] = {
    "Add": "circle", "Subtract": "circle", "Multiply": "circle", "Divide": "circle",
    "BinaryAnd": "circle", "BinaryOr": "circle", "BinaryXor": "circle",
    "LogicalShiftLeft": "circle", "LogicalShiftRight": "circle",
    "ArithmeticShiftLeft": "circle", "ArithmeticShiftRight": "circle",
    "Equality": "circle", "GreaterThan": "circle", "LessThan": "circle",
}

_OP_SYMBOLS: dict[str, str] = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "BinaryNand": "~&", "BinaryNor": "~|",
    "LogicalShiftLeft": "<<", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "ArithmeticShiftRight": ">>>",
    "Equality": "=", "GreaterThan": ">", "LessThan": "<",
}

_OP_COLORS: dict[str, str] = {
    "Add": "#cc4400", "Subtract": "#cc4400", "Multiply": "#cc4400", "Divide": "#cc4400",
    "BinaryAnd": "#4488cc", "BinaryOr": "#4488cc", "BinaryXor": "#4488cc",
    "LogicalShiftLeft": "#44aa44", "LogicalShiftRight": "#44aa44",
    "ArithmeticShiftLeft": "#44aa44", "ArithmeticShiftRight": "#44aa44",
    "Equality": "#cc44cc", "GreaterThan": "#cc44cc", "LessThan": "#cc44cc",
}


def render_timed_compute(
    viz: VizData,
    config: dict | None = None,
) -> str:
    """生成带时间轴的计算架构图 DOT

    Args:
        viz: VizData (需含 include_node_stage + pipeline_stages + include_edge_expression)
        config: {"title": "...", "max_stages": 8}

    Returns:
        DOT 字符串
    """
    cfg = config or {}
    _sid = sanitize_dot_id

    title = cfg.get("title", "Timed Compute")
    max_stages = cfg.get("max_stages", 8)

    lines = [
        "digraph timed_compute {",
        f'  label="{title}"; labelloc=t;',
        "  rankdir=LR;",
        "  splines=polyline;",
        "  nodesep=0.3; ranksep=0.8;",
        '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];',
        '  edge [fontname="Helvetica" fontsize=9 color="#555555"];',
        "  bgcolor=white;",
        "  compound=true;",
        "  newrank=true;  // [V6.8] enforce left-to-right across clusters",
        "",
    ]

    # ── 收集 stage 信息 ──
    # stage_map: node_id → stage_id
    stage_nodes: dict[int, list[str]] = {}
    for n in viz.nodes:
        sid = n.stage_id
        if sid is not None:
            stage_nodes.setdefault(sid, []).append(n.id)

    if not stage_nodes:
        lines.append("  // no pipeline stages found")
        lines.append("}")
        return "\n".join(lines)

    # ── define all_stages early (used by OP node collector below) ──
    all_stages = sorted(stage_nodes.keys())[:max_stages]
    stage_op_nodes: dict[int, list[str]] = {}  # initialize here

    # ── 收集 op nodes ──
    # 对每个 (dst, op_name) 只创建一个 OP 节点 (不是每个 src)
    # 多个操作数汇聚到同一个 OP 节点
    op_nodes: dict[str, str] = {}     # op_id → op_symbol
    op_edges: list[dict] = []          # {src, op_id, dst, op_name, color}
    # 用 (dst, op_name) 作为 key 避免重复 OP
    seen_ops: set[tuple[str, str]] = set()

    for edge in viz.edges:
        if not edge.source_op or edge.kind != "DRIVER":
            continue
        dst = edge.dst
        src = edge.src
        op_name = edge.source_op
        sym = _OP_SYMBOLS.get(op_name, op_name)

        key = (dst, op_name)
        if key not in seen_ops:
            seen_ops.add(key)
            op_id = f"op_{op_name}_{_sid(dst)}"[:80]
            op_nodes[op_id] = sym

            # Find which stage this belongs to
            # OP happens BEFORE the REG: if dst is a REG in stage N,
            # the OP happens in stage N-1 (the comb stage)
            _OP_COLORS.get(op_name, "#888888")
            op_stage = -1
            for sid in all_stages:
                if dst in stage_nodes.get(sid, []):
                    op_stage = sid
                    break
            # If dst is a REG, push OP one stage back
            dst_node = None
            for n in viz.nodes:
                if n.id == dst:
                    dst_node = n
                    break
            if dst_node and dst_node.kind == "REG" and op_stage > 0:
                op_stage -= 1
            stage_op_nodes.setdefault(max(0, op_stage), []).append(op_id)
        else:
            # Reuse existing OP node
            op_id = f"op_{op_name}_{_sid(dst)}"[:80]

        op_edges.append({
            "src": src,
            "op_id": op_id,
            "dst": dst,
            "op_name": op_name,
            "color": _OP_COLORS.get(op_name, "#888888"),
        })

    # ── 按 stage 渲染 ──
    all_stages = sorted(stage_nodes.keys())[:max_stages]

    # 收集每个 stage 的 OP 节点
    stage_op_nodes: dict[int, list[str]] = {}
    for oe in op_edges:
        dst = oe["dst"]
        # 找到 dst 属于哪个 stage
        for sid in all_stages:
            if dst in stage_nodes.get(sid, []):
                stage_op_nodes.setdefault(sid, []).append(oe["op_id"])
                break

    # 渲染 stage clusters
    for sid in all_stages:
        s_nodes = stage_nodes.get(sid, [])
        if not s_nodes:
            continue

        lines.append(f"  subgraph cluster_stage_{sid} {{")
        lines.append(f'    label="Cycle {sid}";')
        lines.append("    style=filled; fillcolor=\"#f8f8f8\";")
        lines.append("    color=\"#cccccc\";")
        lines.append("    fontsize=11;")
        # [V6.8] Force nodes within this stage to the same graphviz rank
        lines.append('    rank=same;')

        # Stage 节点
        for n in viz.nodes:
            if n.id not in s_nodes:
                continue
            kind = n.kind
            extra = ""
            if kind == "REG":
                extra = ' penwidth=2 fillcolor="#e8e8ff"'
            elif "PORT_IN" in kind:
                extra = ' fillcolor="#ffeecc"'
            elif "PORT_OUT" in kind:
                extra = ' fillcolor="#ccffee"'
            lines.append(
                f'    "{_sid(n.id)}" [label="{n.label}"; shape=box{extra}];'
            )

        # OP 节点
        for op_id in stage_op_nodes.get(sid, []):
            sym = op_nodes[op_id]
            lines.append(
                f'    "{_sid(op_id)}" [label="{sym}"; shape=circle '
                f'style=filled fillcolor="#ffffff" penwidth=1.5 '
                f'fontsize=12 fontname="Helvetica-Bold"];'
            )

        lines.append("  }")
        lines.append("")

    # [V6.8] Invisible rank edges: force left-to-right stage ordering
    # Between consecutive stages, add an invisible edge to enforce rank order
    if len(all_stages) >= 2:
        for i in range(len(all_stages) - 1):
            cur_sid = all_stages[i]
            next_sid = all_stages[i + 1]
            cur_nodes = stage_nodes.get(cur_sid, [])
            next_nodes = stage_nodes.get(next_sid, [])
            # Pick first node from each stage as a rank anchor
            if cur_nodes and next_nodes:
                lines.append(
                    f'  "{_sid(cur_nodes[0])}" -> "{_sid(next_nodes[0])}" '
                    f'[style=invis; weight=100];'
                )

    # ── edges: source → OP node, OP node → destination ──
    seen_op_dst: set[tuple[str, str]] = set()  # (op_id, dst) dedup
    # Detects feedback: dst stage < src stage → backwards edge
    node_to_stage: dict[str, int] = {}
    for sid in all_stages:
        for nid in stage_nodes.get(sid, []):
            node_to_stage[nid] = sid

    for oe in op_edges:
        op_id = oe["op_id"]
        src = oe["src"]
        dst = oe["dst"]
        src_stage = node_to_stage.get(src, -1)
        dst_stage = node_to_stage.get(dst, -1)
        is_feedback = src_stage >= 0 and dst_stage >= 0 and src_stage > dst_stage

        # source → OP
        edge_attrs = f'color="{oe["color"]}"'
        if is_feedback:
            edge_attrs += ' constraint=false dir=back'
        lines.append(
            f'  "{_sid(src)}" -> "{_sid(op_id)}" [{edge_attrs}];'
        )
        # OP → destination (only once per op_id+dst)
        key = (op_id, dst)
        if key not in seen_op_dst:
            seen_op_dst.add(key)
            d_attrs = f'color="{oe["color"]}"'
            if is_feedback:
                d_attrs += ' constraint=false dir=back'
            lines.append(
                f'  "{_sid(op_id)}" -> "{_sid(dst)}" [{d_attrs}];'
            )

    # Non-op edges (direct connections like stage1→stage2, 2→result)
    seen_op_pairs = {(oe["src"], oe["dst"]) for oe in op_edges}
    for edge in viz.edges:
        if edge.kind != "DRIVER" or (edge.src, edge.dst) in seen_op_pairs:
            continue
        # Only draw if no OP node was created for this pair
        lines.append(
            f'  "{_sid(edge.src)}" -> "{_sid(edge.dst)}" '
            f'[style=dotted color="#aaaaaa"];'
        )

    lines.append("}")
    return "\n".join(lines)
