"""
pipeline_viz — 基于 SignalGraph 检测 pipeline 阶段, 生成时间周期流图

Algorithm:
  1. 从 SignalGraph 找所有 REG 节点
  2. 排除 clock/reset/1-bit control reg → 得到 pipeline reg 候选
  3. 从 PORT_IN 出发, 沿 DRIVER 边走, 遇到 REG 就切 stage
  4. 分配 time cycle (stage 0, stage 1, ...)
  5. 控制信号 (valid/stall) 标记为跨 stage 虚线
  6. 输出 DOT 格式, 每个 stage 一个 subgraph cluster
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .signal_classifier import (
    SignalClassification,
    SignalClass,
)
from ._dot_common import (
    sanitize_dot_id,
    safe_classify,
    node_width as _node_width,
)
from ..models import SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind


# [P1-5 2026-06-13] 委托给 _dot_common.sanitize_dot_id (与 dataflow_viz 统一)


@dataclass
class PipelineStage:
    """一个 pipeline stage"""
    stage_id: int
    reg_nodes: list[str]  # 该 stage 的寄存器
    comb_nodes: list[str]  # 寄存器之间的组合逻辑
    control_inputs: list[str]  # 来自其他 stage 的控制信号
    data_inputs: list[str]  # 来自前一 stage 的数据
    data_outputs: list[str]  # 输出到下一 stage 的数据
    latency: int = 1  # cycle 数


@dataclass
class PipelineInfo:
    """Pipeline 分析结果"""
    module_name: str
    stages: list[PipelineStage] = field(default_factory=list)
    total_latency: int = 0
    pipeline_regs: list[str] = field(default_factory=list)
    control_regs: list[str] = field(default_factory=list)
    state_regs: list[str] = field(default_factory=list)


def detect_pipeline(
    graph: SignalGraph,
    classification: SignalClassification | None = None,
) -> PipelineInfo:
    """检测 pipeline 结构

    Args:
        graph: SignalGraph 实例
        classification: 预计算的信号分类

    Returns:
        PipelineInfo with stages (empty if classification failed)
    """
    if classification is None:
        classification = safe_classify(graph)
        if classification is None:
            # [P0-2 2026-06-13] 修正: 返回空 PipelineInfo，不再返回 str (与签名不符)
            return PipelineInfo(module_name="")

    info = PipelineInfo(module_name="")

    # 1. 找所有 REG, 分类
    all_regs = []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node and node.kind == NodeKind.REG:
            all_regs.append((node_id, node))

    if not all_regs:
        return info

    # 2. 排除 clock/reset/state regs, 保留 pipeline regs
    for node_id, node in all_regs:
        cn = classification.nodes.get(node_id)
        sc = cn.signal_class if cn else SignalClass.UNKNOWN

        if sc in (SignalClass.CLOCK, SignalClass.RESET):
            continue

        # 检测 state register (self-loop or condition references itself)
        is_state = _is_state_register(node_id, node, graph)

        if is_state:
            info.state_regs.append(node_id)
            continue

        # 1-bit control reg
        w = abs(node.width[0] - node.width[1]) + 1 if node.width[0] >= node.width[1] else 1
        if w == 1 and sc == SignalClass.CONTROL:
            info.control_regs.append(node_id)
            continue

        # pipeline register
        info.pipeline_regs.append(node_id)

    # 3. 从 PORT_IN 出发, BFS 沿 DRIVER 边走
    stages = _build_stages(graph, classification, info)
    info.stages = stages
    info.total_latency = len(stages)

    return info


def _is_state_register(node_id: str, node: TraceNode, graph: SignalGraph) -> bool:
    """检测是否是状态机寄存器"""
    # 有 self-loop (自己驱动自己)
    for e in graph.get_edges(node_id, node_id):
        if e.kind == EdgeKind.DRIVER:
            return True

    # 名字启发式
    name_lower = node.name.lower()
    state_patterns = ["state", "fsm", "next_state", "nxt_state", "curr_state"]
    for p in state_patterns:
        if p in name_lower:
            return True

    return False


def _build_stages(
    graph: SignalGraph,
    classification: SignalClassification,
    info: PipelineInfo,
) -> list[PipelineStage]:
    """构建 pipeline stages"""
    if not info.pipeline_regs:
        return []

    # 从 PORT_IN 出发
    port_ins = [
        nid for nid in graph.nodes()
        for cn in [classification.nodes.get(nid)]
        if cn and cn.node.kind == NodeKind.PORT_IN
        and cn.signal_class not in (SignalClass.CLOCK, SignalClass.RESET)
    ]

    # 拓扑排序: 找到 PORT_IN → REG 的最短路径
    reg_distances: dict[str, int] = {}
    reg_queue = deque()

    for pid in port_ins:
        # BFS 找可达的 pipeline regs
        visited = {pid}
        queue = deque([(pid, 0)])
        while queue:
            current, dist = queue.popleft()
            for succ in graph.successors(current):
                if succ in visited:
                    continue
                if succ in info.pipeline_regs:
                    if succ not in reg_distances:
                        reg_distances[succ] = dist + 1
                        reg_queue.append(succ)
                    reg_distances[succ] = min(reg_distances.get(succ, 999), dist + 1)
                if succ not in info.pipeline_regs:
                    visited.add(succ)
                    queue.append((succ, dist + 1))

    # 按距离排序 pipeline regs → 分配 stage
    sorted_regs = sorted(info.pipeline_regs, key=lambda r: reg_distances.get(r, 999))
    stage_map: dict[str, int] = {}
    for i, reg_id in enumerate(sorted_regs):
        stage_map[reg_id] = i

    # 聚合到 stages
    max_stage = max(stage_map.values()) if stage_map else 0
    stages = []
    for si in range(max_stage + 1):
        stage_regs = [r for r, s in stage_map.items() if s == si]
        if not stage_regs:
            continue
        stage = PipelineStage(
            stage_id=si, reg_nodes=stage_regs,
            comb_nodes=[], control_inputs=[], data_inputs=[], data_outputs=[],
        )
        stages.append(stage)

    # 填充 comb nodes + data inputs/outputs
    all_data_nodes = set(classification.data_nodes)
    for stage in stages:
        for reg_id in stage.reg_nodes:
            # 前驱 → data inputs
            for pred in graph.predecessors(reg_id):
                edges = graph.get_edges(pred, reg_id)
                for e in edges:
                    if e.kind == EdgeKind.DRIVER:
                        if pred in all_data_nodes:
                            stage.data_inputs.append(pred)
            # 后继 → data outputs
            for succ in graph.successors(reg_id):
                edges = graph.get_edges(reg_id, succ)
                for e in edges:
                    if e.kind == EdgeKind.DRIVER:
                        if succ in all_data_nodes:
                            stage.data_outputs.append(succ)
                            stage.comb_nodes.append(succ)

        # 控制输入 (来自其他 stage 或控制信号的节点)
        for cid in classification.control_nodes:
            for succ in graph.successors(cid):
                if succ in stage.reg_nodes or succ in stage.comb_nodes:
                    stage.control_inputs.append(cid)

    return stages


def _all_nodes_in_stages_lookup(pipeline_info) -> set[str]:
    """[P5 2026-07-11] 收集所有 stage 内的节点 ID (reg + comb)。"""
    out: set[str] = set()
    for stage in pipeline_info.stages:
        out.update(stage.reg_nodes)
        out.update(stage.comb_nodes)
    return out


def _collect_outside_controls(classification, pipeline_info) -> list[str]:
    """[P5 2026-07-11] 收集不在 stage 内但被分类为 CONTROL 的节点。"""
    in_stages = _all_nodes_in_stages_lookup(pipeline_info)
    out = []
    for cid in classification.control_nodes:
        if cid in in_stages:
            continue
        if classification.nodes.get(cid) is None:
            continue
        out.append(cid)
    return out


def _group_controls_by_stage(
    control_nodes: list[str], pipeline_info, graph
) -> dict[str, int]:
    """[P5 2026-07-11] 对每个 control 节点, 找它主要 downstream 影响的 stage 索引.

    算法: 沿 graph 向下走, 找第一个属于某个 stage.reg_nodes 的节点, 用那个 stage 的 index.
    如果走不到任何 stage (孤立的 control), 默认为 0.
    """
    reg_to_stage = {}
    for stage in pipeline_info.stages:
        for reg_id in stage.reg_nodes:
            reg_to_stage[reg_id] = stage.stage_id

    result: dict[str, int] = {}
    for cid in control_nodes:
        # BFS 找第一个 reachable stage reg
        visited = {cid}
        queue = [cid]
        found_stage = None
        while queue:
            cur = queue.pop(0)
            if cur in reg_to_stage:
                found_stage = reg_to_stage[cur]
                break
            for succ in graph.successors(cur):
                if succ not in visited:
                    visited.add(succ)
                    queue.append(succ)
        result[cid] = found_stage if found_stage is not None else 0
    return result


def generate_pipeline_dot(
    graph: SignalGraph,
    pipeline_info: PipelineInfo,
    classification: SignalClassification | None = None,
    *,
    max_comb_per_stage: int = 8,
    max_control_nodes: int = 8,
) -> str:
    _sid = sanitize_dot_id
    """生成 pipeline flow DOT 图

    Args:
        graph: SignalGraph 实例
        pipeline_info: PipelineInfo from detect_pipeline
        classification: 预计算的分类
        max_comb_per_stage: 每个 stage 最多显示多少组合节点 (防 PNG 过高)
        max_control_nodes: 控制信号区最多显示多少节点 (防 PNG 过高)

    Returns:
        DOT 格式字符串
    """
    if classification is None:
        classification = safe_classify(graph)
        if classification is None:
            # [P0-2 2026-06-13] 修正: 用 pipeline_info.module_name (未定义变量 module_name → NameError)
            return f'// ERROR: failed to classify graph\ndigraph pipeline {{ label="Error: {pipeline_info.module_name}"; }}'


    lines = ['digraph pipeline {']
    lines.append('  rankdir=LR;')  # 左→右 = 时间流
    lines.append(f'  label="Pipeline Flow: {pipeline_info.module_name}";')
    lines.append('  labelloc=t;')
    lines.append('  fontsize=14;')
    lines.append('  ranksep=0.6;')
    lines.append('  nodesep=0.2;')
    lines.append('  splines=polyline;')
    lines.append('')
    lines.append(f'  // {len(pipeline_info.pipeline_regs)} pipeline regs, {len(pipeline_info.control_regs)} control regs')
    lines.append(f'  // {len(pipeline_info.state_regs)} state regs, {pipeline_info.total_latency} stages')
    lines.append('')

    # [P5 2026-07-11] 收集 control 信号 + 它们主要连接的 stage
    # 用于 后面 在 header row 排列 control, 并按 stage 颜色连接
    control_outside = _collect_outside_controls(classification, pipeline_info)
    control_to_stage = _group_controls_by_stage(control_outside, pipeline_info, graph)
    total_control = len(control_outside)
    control_shown = control_outside[:max_control_nodes]
    total_remaining = max(0, total_control - len(control_shown))

    # [P5 2026-07-11] Header row: control signals 上方一行
    # 颜色按主要 target stage 分组 (valid → stage N → orange, etc.)
    # 这样 control 跟 stage 视觉对应, 不再是脱节的 "孤岛 cluster"
    if control_shown:
        lines.append('  // === Control signals header row (top, color-coded by target stage) ===')
        lines.append('  subgraph cluster_control_header {')
        lines.append(f'    label="Control Signals ({total_control} total, showing {len(control_shown)})";')
        lines.append('    style="rounded,filled";')
        lines.append('    fillcolor="#fff5e6";')
        lines.append('    color="#cc8844";')
        lines.append('    fontsize=10;')
        lines.append('    rank=min;')  # 强制放最上方 (LR 模式下 = 最左)
        # [P5 改进] 颜色按 target stage 分组 (4 个颜色轮换)
        stage_colors = ["#cc6633", "#aa5599", "#5599aa", "#aa8855"]
        for i, cid in enumerate(control_shown):
            cn = classification.nodes.get(cid)
            name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else "?"
            target_stage_idx = control_to_stage.get(cid, 0) % len(stage_colors)
            color = stage_colors[target_stage_idx]
            lines.append(
                f'    "{_sid(cid)}" [label="{name}\\n→S{control_to_stage.get(cid, 0)}" '
                f'shape=box style="rounded,filled" fillcolor="{color}" fontcolor="white" penwidth=1.5 fontsize=9];'
            )
        if total_remaining > 0:
            lines.append(
                f'    // +{total_remaining} more control signals (--max-control-nodes to show more)'
            )
        lines.append('  }')
        lines.append('')

    # [Phase 6 2026-07-12] TL;DR header (after control computed, more accurate)
    lines.append(
        f'  // TL;DR: {len(pipeline_info.pipeline_regs)} pipeline regs · '
        f'{len(pipeline_info.state_regs)} state regs · {pipeline_info.total_latency} stages · '
        f'control shown: {len(control_shown)}/{total_control}'
    )

    # 每个 stage 一个 cluster
    all_nodes_in_stages = set()
    for stage in pipeline_info.stages:
        lines.append(f'  subgraph cluster_stage{stage.stage_id} {{')
        lines.append(f'    label="Stage {stage.stage_id}\\n(latency={stage.latency})";')
        lines.append('    style=dashed;')
        lines.append('    color="#226699";')
        lines.append('    fontsize=11;')

        # Pipeline registers
        for reg_id in stage.reg_nodes:
            cn = classification.nodes.get(reg_id)
            name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else "?"  if cn and cn.node.name else reg_id
            w = _node_width(cn)
            lines.append(f'    "{_sid(reg_id)}" [label="{name}\\nREG\\\\n{w}bit" shape=box style="rounded,filled" fillcolor="#4488cc" fontcolor="white" penwidth=2.5];')
            all_nodes_in_stages.add(reg_id)

        # 组合逻辑
        comb_dedup = list(dict.fromkeys(stage.comb_nodes))
        for comb_id in comb_dedup[:max_comb_per_stage]:  # [P0 fix 2026-07-10] limit comb per stage
            cn = classification.nodes.get(comb_id)
            if cn is None:
                continue
            name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else "?"
            w = _node_width(cn)
            lines.append(f'    "{_sid(comb_id)}" [label="{name}\\\n{w}bit" shape=box style="rounded,filled" fillcolor="#88bbdd" fontcolor="white" penwidth=1];')
            all_nodes_in_stages.add(comb_id)
        if len(comb_dedup) > max_comb_per_stage:
            lines.append(f'    // +{len(comb_dedup)-max_comb_per_stage} more comb nodes (--max-comb-per-stage to show more)')

        lines.append('  }')
        lines.append('')

    # [P0 fix 2026-07-10] 控制节点: 旧 layout 是独立 cluster 在最后 (突兀)
    # [P5 2026-07-11] 改为 header row 在最上方, 颜色按 target stage 分组
    # control_shown / total_control 已在上面 header row 部分收集完, 这里不再重写
    pass  # control cluster 已经渲染在 header row 部分 (在 stages 之前)

    # 边
    lines.append('  // === Data edges (stage → stage) ===')
    for stage in pipeline_info.stages:
        for reg_id in stage.reg_nodes:
            for succ in graph.successors(reg_id):
                edges = graph.get_edges(reg_id, succ)
                for e in edges:
                    if e.kind == EdgeKind.DRIVER:
                        label = e.expression[:20] if e.expression and e.expression != "?" else ""
                        lines.append(f'  "{_sid(reg_id)}" -> "{_sid(succ)}" [color="#226699" penwidth=1.5 label="{label}" fontsize=8];')

    lines.append('')
    lines.append('  // === Control edges (dashed, color-matched to target stage) ===')
    # [P5 2026-07-11] 颜色与 control 节点颜色一致 (按 target stage)
    stage_colors_edge = ["#cc6633", "#aa5599", "#5599aa", "#aa8855"]
    for cid in classification.control_nodes:
        target_stage_idx = control_to_stage.get(cid, 0) % len(stage_colors_edge)
        edge_color = stage_colors_edge[target_stage_idx]
        for succ in graph.successors(cid):
            if succ in all_nodes_in_stages:
                edges = graph.get_edges(cid, succ)
                for e in edges:
                    if e.kind == EdgeKind.DRIVER:
                        lines.append(
                            f'  "{_sid(cid)}" -> "{_sid(succ)}" '
                            f'[color="{edge_color}" style=dashed penwidth=1.2];'
                        )

    lines.append('}')
    return "\n".join(lines)


# _node_width 委托给 _dot_common.node_width (上面已 import)
