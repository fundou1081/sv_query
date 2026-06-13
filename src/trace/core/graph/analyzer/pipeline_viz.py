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

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .signal_classifier import (
    SignalClassification,
    classify_graph,
    SignalClass,
)
from ..models import SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind


@dataclass
class PipelineStage:
    """一个 pipeline stage"""
    stage_id: int
    reg_nodes: List[str]  # 该 stage 的寄存器
    comb_nodes: List[str]  # 寄存器之间的组合逻辑
    control_inputs: List[str]  # 来自其他 stage 的控制信号
    data_inputs: List[str]  # 来自前一 stage 的数据
    data_outputs: List[str]  # 输出到下一 stage 的数据
    latency: int = 1  # cycle 数


@dataclass
class PipelineInfo:
    """Pipeline 分析结果"""
    module_name: str
    stages: List[PipelineStage] = field(default_factory=list)
    total_latency: int = 0
    pipeline_regs: List[str] = field(default_factory=list)
    control_regs: List[str] = field(default_factory=list)
    state_regs: List[str] = field(default_factory=list)


def detect_pipeline(
    graph: SignalGraph,
    classification: Optional[SignalClassification] = None,
) -> PipelineInfo:
    """检测 pipeline 结构

    Args:
        graph: SignalGraph 实例
        classification: 预计算的信号分类

    Returns:
        PipelineInfo with stages
    """
    if classification is None:
        classification = classify_graph(graph)

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
) -> List[PipelineStage]:
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
    reg_distances: Dict[str, int] = {}
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
    stage_map: Dict[str, int] = {}
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


def generate_pipeline_dot(
    graph: SignalGraph,
    pipeline_info: PipelineInfo,
    classification: Optional[SignalClassification] = None,
) -> str:
    """生成 pipeline flow DOT 图

    Args:
        graph: SignalGraph 实例
        pipeline_info: PipelineInfo from detect_pipeline
        classification: 预计算的分类

    Returns:
        DOT 格式字符串
    """
    if classification is None:
        classification = classify_graph(graph)

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
            name = cn.node.name if cn else reg_id
            w = _node_width(cn)
            lines.append(f'    "{reg_id}" [label="{name}\\nREG\\\\n{w}bit" shape=box style="rounded,filled" fillcolor="#4488cc" fontcolor="white" penwidth=2.5];')
            all_nodes_in_stages.add(reg_id)

        # 组合逻辑
        comb_dedup = list(dict.fromkeys(stage.comb_nodes))
        for comb_id in comb_dedup[:8]:  # 限制每 stage 显示的 comb 节点数
            cn = classification.nodes.get(comb_id)
            if cn is None:
                continue
            name = cn.node.name
            w = _node_width(cn)
            lines.append(f'    "{comb_id}" [label="{name}\\\n{w}bit" shape=box style="rounded,filled" fillcolor="#88bbdd" fontcolor="white" penwidth=1];')
            all_nodes_in_stages.add(comb_id)
        if len(stage.comb_nodes) > 8:
            lines.append(f'    // +{len(stage.comb_nodes)-8} more comb nodes')

        lines.append('  }')
        lines.append('')

    # 控制节点 (独立)
    for cid in classification.control_nodes:
        if cid in all_nodes_in_stages:
            continue
        cn = classification.nodes.get(cid)
        if cn is None:
            continue
        name = cn.node.name
        lines.append(f'  "{cid}" [label="{name}" shape=box style="rounded,filled" fillcolor="#cc8844" fontcolor="white" penwidth=1.5];')

    lines.append('')

    # 边
    lines.append('  // === Data edges (stage → stage) ===')
    for stage in pipeline_info.stages:
        for reg_id in stage.reg_nodes:
            for succ in graph.successors(reg_id):
                edges = graph.get_edges(reg_id, succ)
                for e in edges:
                    if e.kind == EdgeKind.DRIVER:
                        label = e.expression[:20] if e.expression and e.expression != "?" else ""
                        lines.append(f'  "{reg_id}" -> "{succ}" [color="#226699" penwidth=1.5 label="{label}" fontsize=8];')

    lines.append('')
    lines.append('  // === Control edges (dashed) ===')
    for cid in classification.control_nodes:
        for succ in graph.successors(cid):
            if succ in all_nodes_in_stages:
                edges = graph.get_edges(cid, succ)
                for e in edges:
                    if e.kind == EdgeKind.DRIVER:
                        lines.append(f'  "{cid}" -> "{succ}" [color="#CC6600" style=dashed penwidth=1.2];')

    lines.append('}')
    return "\n".join(lines)


def _node_width(cn) -> int:
    if cn is None:
        return 0
    w_msb, w_lsb = cn.node.width
    return abs(w_msb - w_lsb) + 1 if w_msb >= w_lsb else 1
