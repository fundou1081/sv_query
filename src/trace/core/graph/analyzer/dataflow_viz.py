"""
dataflow_viz — 基于 SignalGraph + signal_classifier 生成数据流可视化图

输出 DOT 格式, 包含:
  - 数据边 (DRIVER): 标注运算表达式 (a+b, mux select)
  - 关键控制边 (dashed): enable/valid/state → 数据目标
  - 多 driver 同目标 → MUX 标识
  - 节点着色: data=蓝色, control=橙色, clock=灰色, reset=红色
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional

from .signal_classifier import (
    SignalClassification,
    classify_graph,
    SignalClass,
    ClassifiedNode,
    ClassifiedEdge,
)
from ..models import SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind


def _sanitize_dot_id(node_id: str) -> str:
    """清理 DOT node ID/label (移除 non-ASCII / 控制字符)"""
    if not isinstance(node_id, str):
        return str(node_id)
    safe = ''.join(c for c in node_id if 0x20 <= ord(c) < 0x7F)
    safe = safe.replace('"', '').replace('{', '').replace('}', '')
    safe = safe.replace('\\', '').strip()
    return safe if safe else f'node_{(hash(node_id) & 0xFFFF):04x}' 


def generate_dataflow_dot(
    graph: SignalGraph,
    module_name: str = "",
    classification: Optional[SignalClassification] = None,
    include_ports: bool = True,
    include_clk_rst: bool = False,
) -> str:
    _sid = _sanitize_dot_id  # alias for cleaner code
    """生成数据流 DOT 图

    Args:
        graph: SignalGraph 实例
        module_name: 模块名 (用于 label)
        classification: 预计算的分类 (可选, 不传则自动计算)
        include_ports: 是否包含 PORT_IN/PORT_OUT 节点
        include_clk_rst: 是否包含 CLOCK/RESET 节点 (默认排除)

    Returns:
        DOT 格式字符串
    """
    if classification is None:
        try:
            classification = classify_graph(graph)
        except (UnicodeDecodeError, ValueError, TypeError) as e:
            # graph has binary-corrupted nodes, return minimal DOT
            return f'// ERROR: failed to classify graph: {e}\\ndigraph dataflow {{ label="Error: {module_name}"; }}'


    lines = ['digraph dataflow {']
    lines.append('  rankdir=TB;')
    lines.append(f'  label="Data Flow: {module_name}";')
    lines.append('  labelloc=t;')
    lines.append('  fontsize=14;')
    lines.append('  ranksep=0.5;')
    lines.append('  nodesep=0.3;')
    lines.append('  splines=polyline;')
    lines.append('')

    # 边收集
    data_edges = []
    control_edges = []
    edge_seen = set()

    for (src, dst, kind_str), ce in classification.edges.items():
        key = (src, dst)
        if key in edge_seen:
            continue
        edge_seen.add(key)

        if ce.edge_class == SignalClass.DATA:
            data_edges.append(ce)
        elif ce.is_control and ce.edge_class == SignalClass.CONTROL:
            control_edges.append(ce)

    # 收集涉及的节点
    used_nodes = set()
    node_incoming = defaultdict(list)
    for ce in data_edges:
        used_nodes.add(ce.src_id)
        used_nodes.add(ce.dst_id)
        node_incoming[ce.dst_id].append(ce)
    for ce in control_edges:
        used_nodes.add(ce.src_id)
        used_nodes.add(ce.dst_id)

    if include_clk_rst:
        for nid in classification.clock_nodes + classification.reset_nodes:
            used_nodes.add(nid)

    # 节点定义
    lines.append('  // === Nodes ===')
    for node_id in sorted(used_nodes):
        cn = classification.nodes.get(node_id)
        if cn is None:
            continue
        node = cn.node
        sc = cn.signal_class

        # 跳过不需要的节点
        if not include_ports and node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.PORT_INOUT):
            continue

        # 标签: name + kind + width
        w_msb, w_lsb = node.width
        w = abs(w_msb - w_lsb) + 1 if w_msb >= w_lsb else 1
        width_str = f"[{w_msb}:{w_lsb}]" if w_msb != w_lsb else f"[{w_msb}]"
        safe_name = _sanitize_dot_id(node.name)
        if safe_name and safe_name.startswith('node_'):
            safe_name = ''  # auto-generated name, skip
        label_parts = [safe_name] if safe_name else []
        if node.kind != NodeKind.SIGNAL:
            label_parts.append(node.kind.name)
        if w > 0:
            label_parts.append(f"{w}bit")
        label = "\\n".join(label_parts)

        # 颜色
        color_map = {
            SignalClass.DATA: ("#4488cc", "#226699", "white"),
            SignalClass.CONTROL: ("#cc8844", "#996622", "white"),
            SignalClass.CLOCK: ("#888888", "#666666", "white"),
            SignalClass.RESET: ("#cc4444", "#992222", "white"),
            SignalClass.UNKNOWN: ("#aaaaaa", "#888888", "black"),
        }
        fill, border, font = color_map.get(sc, ("#aaaaaa", "#888888", "black"))
        # REG 加粗边框
        penwidth = 2 if node.kind == NodeKind.REG else 1

        lines.append(
            f'  "{_sid(node_id)}" [label="{label}" shape=box '
            f'style="rounded,filled" fillcolor="{fill}" color="{border}" '
            f'fontcolor="{font}" penwidth={penwidth}];'
        )

    lines.append('')

    # 数据边 (实线, 带表达式标注)
    lines.append('  // === Data Edges ===')
    # 检测 MUX: 同一 dst 有多个 src
    mux_targets = {
        dst: srcs
        for dst, srcs in node_incoming.items()
        if len(srcs) > 1
    }

    for ce in data_edges:
        attrs = ['color="#226699"', 'style=solid', 'penwidth=1.5']
        # 表达式标注
        expr = _sanitize_dot_id(ce.edge.expression or "")
        if expr and expr not in ("?", "unknown"):
            # 截断长表达式
            label = expr[:30] + ("..." if len(expr) > 30 else "")
            attrs.append(f'label="{label}"')
            attrs.append('fontsize=9')
        # 有条件 → 虚线标注
        if ce.edge.condition:
            cond_short = _sanitize_dot_id(ce.edge.condition or "")[:25]
            attrs.append(f'xlabel="{cond_short}"')
            attrs.append('fontsize=7')
        # MUX 目标 → 加粗
        if ce.dst_id in mux_targets:
            attrs.append('penwidth=2.5')
            attrs.append('color="#224488"')
        lines.append(f'  "{_sid(ce.src_id)}" -> "{_sid(ce.dst_id)}" [{", ".join(attrs)}];')

    lines.append('')

    # 关键控制边 (虚线, 标注条件)
    lines.append('  // === Key Control Edges ===')
    for ce in control_edges:
        attrs = ['color="#CC6600"', 'style=dashed', 'penwidth=1.2']
        if ce.edge.condition:
            cond_short = _sanitize_dot_id(ce.edge.condition or "")[:25]
            attrs.append(f'xlabel="{cond_short}"')
            attrs.append('fontsize=7')
        lines.append(f'  "{_sid(ce.src_id)}" -> "{_sid(ce.dst_id)}" [{", ".join(attrs)}];')

    lines.append('')
    lines.append('  // === Legend ===')
    lines.append('  subgraph cluster_legend {')
    lines.append('    label="Legend";')
    lines.append('    fontsize=10;')
    lines.append('    style=dashed;')
    lines.append('    color="#aaaaaa";')
    lines.append('    legend_data [label="Data Signal\\n(blue, solid)" shape=box style="rounded,filled" fillcolor="#4488cc" fontcolor="white"];')
    lines.append('    legend_control [label="Control Signal\\n(orange, dashed)" shape=box style="rounded,filled" fillcolor="#cc8844" fontcolor="white"];')
    lines.append('    legend_reg [label="Register\\n(thick border)" shape=box style="rounded,filled,dashed" fillcolor="#4488cc" fontcolor="white" penwidth=3];')
    lines.append('    legend_mux [label="MUX target\\n(thick blue edge)" shape=box style="rounded,filled,dashed" fillcolor="#226699" fontcolor="white" penwidth=3];')
    lines.append('    legend_op [label="Operation\\n(edge label)" shape=none fontsize=9];')
    lines.append('  }')
    lines.append('}')

    return "\n".join(lines)
