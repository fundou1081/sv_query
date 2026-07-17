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


def _should_fold_stages(stages: list, threshold: int) -> bool:
    """[Phase 6.2 2026-07-12] Decide whether to fold stages for readability.

    Returns True if folding would reduce visual complexity meaningfully.
    """
    return len(stages) > threshold


def _build_folded_stage_groups(stages: list, fold_every: int, max_regs_per_fold: int = 3) -> list:
    """[Phase 6.2] Group consecutive stages into folds.

    Each fold contains up to `fold_every` consecutive stages and aggregates:
    - stage_ids: list[int] of stage ids in this fold
    - reg_nodes: combined reg nodes (CAPPED to max_regs_per_fold to keep viz readable)
    - reg_nodes_total: total reg count (for label)
    - comb_nodes: combined comb nodes
    - is_fold: True (marker for renderer)

    Returns a list of fold groups. If a stage is alone, it's its own group.
    """
    folds = []
    n = len(stages)
    i = 0
    while i < n:
        end = min(i + fold_every, n)
        stages_in_fold = stages[i:end]
        all_regs = [r for s in stages_in_fold for r in s.reg_nodes]
        # [Phase 6.5.2 2026-07-13] CAPPED: 只显示前 N 个 REG, 避免上百个节点堆成一团
        # 用户用 --unfold 可以看全部
        fold = {
            'stage_ids': [s.stage_id for s in stages_in_fold],
            'reg_nodes': all_regs[:max_regs_per_fold],
            'reg_nodes_total': len(all_regs),
            'comb_nodes': list(dict.fromkeys(
                c for s in stages_in_fold for c in s.comb_nodes
            )),
            'data_inputs': list(dict.fromkeys(
                c for s in stages_in_fold for c in s.data_inputs
            )),
            'data_outputs': list(dict.fromkeys(
                c for s in stages_in_fold for c in s.data_outputs
            )),
            'control_inputs': list(dict.fromkeys(
                c for s in stages_in_fold for c in s.control_inputs
            )),
            'is_fold': len(stages_in_fold) > 1,
            'start_id': stages_in_fold[0].stage_id,
            'end_id': stages_in_fold[-1].stage_id,
        }
        folds.append(fold)
        i = end
    return folds


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
    fold_threshold: int = 30,
    fold_every: int = 5,
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


    # [Phase 6.5 fix 2026-07-13] 折叠模式判定 (需要在 layout 之前)
    stages_count = len(pipeline_info.stages)
    is_folding = stages_count > fold_threshold

    lines = ['digraph pipeline {']
    # [Phase 6.5.3 fix 2026-07-13] 折叠模式用 LR + compact ranks
    # 让 cluster 内 REGs 横向排成 1 行 (rank=same), 多个 cluster 横向串联
    # 减少每 fold 节点数 (max 5), 让总宽 < 2000px
    # [Phase 6.5.5 fix 2026-07-13] 折叠模式用 TB, 5 个 fold 横排成 1 行 (5 列)
    # 非折叠模式继续 LR
    layout = 'TB' if is_folding else 'LR'
    lines.append(f'  rankdir={layout};')
    if is_folding:
        lines.append('  ranksep=0.15;')  # TB 折叠: 紧排
        lines.append('  nodesep=0.15;')
    else:
        lines.append('  ranksep=0.6;')
        lines.append('  nodesep=0.4;')
    lines.append(f'  label="Pipeline Flow: {pipeline_info.module_name}";')
    lines.append('  labelloc=t;')
    lines.append('  fontsize=14;')
    # (ranksep/nodesep already set above)
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

    # [Phase 6.2 2026-07-12] Stage folding: group consecutive stages into folds
    # when total stages > fold_threshold. Each fold cluster shows aggregated info.
    stages_to_render = pipeline_info.stages
    folded_groups = None
    if is_folding:
        # [Phase 6.5.2 fix 2026-07-13] auto-scale fold_every: ensure max 5 folds
        # 152 stages / 5 = 30 stages/fold, ~30 REGs per fold in a horizontal row
        n_stages = len(stages_to_render)
        target_folds = 10
        if fold_every < (n_stages // target_folds):
            fold_every = max(1, (n_stages + target_folds - 1) // target_folds)
            fold_note_extra = f' (auto-fold-every={fold_every})'
        else:
            fold_note_extra = ''
        folded_groups = _build_folded_stage_groups(stages_to_render, fold_every)

    # [Phase 6.4 2026-07-12] TL;DR as visible box (not just comment)
    from .viz_legend import render_tldr_box
    fold_note = f' · folded into {len(folded_groups)} groups (--unfold to expand){fold_note_extra}' if is_folding else ''
    tldr_text = (
        f'{len(pipeline_info.pipeline_regs)} pipeline regs · '
        f'{len(pipeline_info.state_regs)} state regs · '
        f'{pipeline_info.total_latency} stages{fold_note} · '
        f'control shown: {len(control_shown)}/{total_control}'
    )
    lines.extend(render_tldr_box(tldr_text))

    # 每个 stage (或 fold group) 一个 cluster
    all_nodes_in_stages = set()
    render_groups = folded_groups if is_folding else None
    items_to_render = (
        [(g, True) for g in folded_groups] if is_folding
        else [(s, False) for s in stages_to_render]
    )

    # [Phase 6.5.4 fix 2026-07-13] 折叠模式: 收集所有 REGs, 稍后一次放到一个 rank=same 行
    # 不用 cluster, 避免 graphviz 垂直堆叠多个 cluster
    fold_reg_nodes_global = []  # 全局 REG node ID 列表 (用于 rank=same)

    for item, is_fold in items_to_render:
        cluster_name = None
        if is_fold:
            stage = item  # dict (fold group)
            total_regs = stage.get('reg_nodes_total', len(stage['reg_nodes']))
            shown = len(stage['reg_nodes'])
            # Label 显示在 node 下面 (而不是 cluster 里)
            stage_label_text = f"Stages {stage['start_id']}-{stage['end_id']} ({total_regs} regs)"
            reg_nodes = stage['reg_nodes']
            comb_nodes = stage['comb_nodes']
            # [FIX 2026-07-17] 每个 fold 也作为 cluster (边框) 区分
            # 这样用户能看出来哪些 REG 同属一个 stage.
            cluster_name = f"cluster_stage{stage['start_id']}_{stage['end_id']}"
            lines.append(f'  subgraph {cluster_name} {{')
            lines.append(f'    label="Stages {stage["start_id"]}-{stage["end_id"]} ({total_regs} regs)";')
            lines.append('    style="rounded,dashed";')
            lines.append('    color="#6699cc";')
            lines.append('    fillcolor="#f0f8ff";')
            lines.append('    fontsize=11;')
        else:
            stage = item  # PipelineStage dataclass
            stage_label_text = f"Stage {stage.stage_id}"
            reg_nodes = stage.reg_nodes
            comb_dedup = list(dict.fromkeys(stage.comb_nodes))
            comb_nodes = comb_dedup[:max_comb_per_stage]
            # [非折叠模式: 每 stage 一个 cluster, 用虚线边框区分]
            cluster_name = f"cluster_stage{stage.stage_id}"
            lines.append(f'  subgraph {cluster_name} {{')
            lines.append(f'    label="{stage_label_text}";')
            lines.append('    style=dashed;')
            lines.append('    color="#226699";')
            lines.append('    fontsize=11;')

        # Pipeline registers
        for reg_id in reg_nodes:
            cn = classification.nodes.get(reg_id)
            name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else "?"  if cn and cn.node.name else reg_id
            w = _node_width(cn)
            lines.append(f'    "{_sid(reg_id)}" [label="{name}\\nREG\\\\n{w}bit" shape=box style="rounded,filled" fillcolor="#4488cc" fontcolor="white" penwidth=2.5];')
            all_nodes_in_stages.add(reg_id)

        # [Phase 6.5.4 fix 2026-07-13] 折叠模式: 不再加 per-fold rank=same
        # 改用 loop 结束后加全局 rank=same (所有 fold REGs 在一行)

        # [Phase 6.5 fix 2026-07-13] 折叠模式: 只显示 REG, 隐藏 comb (避免 overlap)
        # 在 --unfold 模式下, comb nodes 才会显示
        if is_fold:
            # Add a small note about hidden comb nodes
            total_comb = len(comb_nodes)
            if total_comb > 0:
                lines.append(
                    f'    // Folded mode: {total_comb} combinational nodes hidden '
                    f'(use --unfold to see them)'
                )
            # DO NOT continue - we still need the closing } of the cluster
        else:
            # 组合逻辑 (只在非折叠模式渲染)
            for comb_id in comb_nodes:  # [P0 fix 2026-07-10] limit comb per stage
                cn = classification.nodes.get(comb_id)
                if cn is None:
                    continue
                name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else "?"
                w = _node_width(cn)
                lines.append(f'    "{_sid(comb_id)}" [label="{name}\\\n{w}bit" shape=box style="rounded,filled" fillcolor="#88bbdd" fontcolor="white" penwidth=1];')
                all_nodes_in_stages.add(comb_id)
        # [Phase 6.2] Trim comb nodes per cluster
        shown_count = min(len(comb_nodes), max_comb_per_stage)
        if len(comb_nodes) > shown_count:
            lines.append(f'    // +{len(comb_nodes) - shown_count} more comb nodes (--max-comb-per-stage to show more)')

        # [FIX 2026-07-17] 折叠 + 非折叠模式都关闭 cluster
        # 这样图用户能看到 fold group 的边框, 一眼看出 stage 范围.
        # [rank=same 改用 subgraph 级限制位置 - 别处]
        lines.append('  }')
        lines.append('')

    # [Phase 6.5.4 fix 2026-07-13] 折叠模式: 所有 fold REGs 在同一 rank (横向单行)
    # 这是关键: 把所有 fold 的 REG 强制放到一个 rank, graphviz 会按时间顺序横排
    # 同时加 invisible edges 让 graphviz 必须按顺序排 (左→右)
    if is_folding and fold_reg_nodes_global:
        quoted = ' '.join('"' + r + '"' for r in fold_reg_nodes_global)
        lines.append(f'  {{ rank=same; {quoted} }};')

    # [FIX 2026-07-17] Cross-stage DRIVER edges: 把每个 fold 的 REGs 间的 data flow 画出来
    # 用户能看清数据流从哪里到哪里.
    if is_folding:
        # 收集所有 item 的 reg_nodes 顺序列表
        all_reg_groups = []
        for item, is_fold in items_to_render:
            if is_fold:
                all_reg_groups.append(item['reg_nodes'])
            else:
                all_reg_groups.append(item.reg_nodes)
        # 在每一对相邻 group 之间画 DRIVER 边
        for i in range(len(all_reg_groups) - 1):
            src_group = all_reg_groups[i]
            dst_group = all_reg_groups[i + 1]
            if not src_group or not dst_group:
                continue
            # 每组取第一个和最后一个 reg
            src_first = src_group[0]
            dst_last = dst_group[-1]
            # 画一条带 label 的 DRIVER 边表示数据流向
            label = f"flow_S{i}_to_S{i+1}"
            lines.append(
                f'  "{_sid(src_first)}" -> "{_sid(dst_last)}" '
                f'[color="#226699" penwidth=2 style=bold label="{label}" fontsize=8];'
            )
        # 加 invisible edges 强制水平流动
        for i in range(len(fold_reg_nodes_global) - 1):
            lines.append(
                f'  "{fold_reg_nodes_global[i]}" -> "{fold_reg_nodes_global[i+1]}" '
                f'[style=invis weight=10];'
            )
        lines.append('')

    # [P0 fix 2026-07-10] 控制节点: 旧 layout 是独立 cluster 在最后 (突兀)
    # [P5 2026-07-11] 改为 header row 在最上方, 颜色按 target stage 分组
    # control_shown / total_control 已在上面 header row 部分收集完, 这里不再重写
    pass  # control cluster 已经渲染在 header row 部分 (在 stages 之前)

    # 边
    lines.append('  // === Data edges (stage → stage) ===')
    # [Phase 6.5 fix 2026-07-13] 折叠模式: 折叠模式下完全不画跨 fold 边, 避免线团
    # 只在 --unfold 模式下显示完整边
    if is_folding:
        lines.append('  // Folded mode: cross-fold edges omitted for clarity')
        lines.append('  // Use --unfold to see all edges')
    else:
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
    # [Phase 6.5 fix 2026-07-13] 折叠模式: 也跳过 control 边 (同避免线团)
    if is_folding:
        lines.append('  // Folded mode: control edges omitted for clarity')
    else:
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

    # [FIX 2026-07-17] State registers cluster: 把state_regs画到独立cluster
    # 这样用户能看到有几个state machine, 以及它们名字.
    # 限制state_regs数量避免太大, 默认16.
    if pipeline_info.state_regs:
        max_state_shown = 16
        state_shown = pipeline_info.state_regs[:max_state_shown]
        state_total = len(pipeline_info.state_regs)
        state_extra = ''
        if state_total > max_state_shown:
            state_extra = f' (+{state_total - max_state_shown} more)'
        lines.append('')
        lines.append('  // === State Registers (FSM/state machine regs) ===')
        lines.append('  subgraph cluster_state_regs {')
        lines.append(f'    label="State Registers ({state_total} total, showing {len(state_shown)}){state_extra}";')
        lines.append('    style="rounded,filled";')
        lines.append('    fillcolor="#fff4e6";')
        lines.append('    color="#cc8844";')
        lines.append('    fontsize=10;')
        lines.append('    rank=max;')
        for sid in state_shown:
            node = graph.get_node(sid)
            name = sanitize_dot_id(node.name) if (node and node.name) else sid.split(".")[-1]
            w = node.width if node else None
            w_str = f"{w[1] - w[0] + 1}bit" if w else "?"
            lines.append(
                f'    "{_sid(sid)}" [label="{name}\\nREG\\n{w_str}" '
                f'shape=box style="rounded,filled" fillcolor="#cc8844" fontcolor="white" penwidth=1.5 fontsize=9];'
            )
        lines.append('  }')

    # [FIX 2026-07-17] State reg → stage connections: 从每个 state reg 
    # 走到它的 driver 路径上的第一个 pipeline reg, 画虚线表示 state 影响该 stage.
    if pipeline_info.state_regs and pipeline_info.stages:
        state_shown_set = set(state_shown)
        # Build map: pipeline_reg_id → stage_id
        reg_to_stage = {}
        for stage in pipeline_info.stages:
            for rid in stage.reg_nodes:
                reg_to_stage[rid] = stage.stage_id
        # For each shown state reg, find what stage it flows into
        for sid in state_shown:
            # 双向 BFS via DRIVER edges (state 可以驱动 next logic, 或者被 next logic 读)
            from collections import deque
            seen = {sid}
            queue = deque(
                list(graph.successors(sid)) + list(graph.predecessors(sid))
            )
            target_stage = None
            target_reg = None
            while queue:
                node = queue.popleft()
                if node in seen:
                    continue
                seen.add(node)
                if node in reg_to_stage:
                    target_stage = reg_to_stage[node]
                    target_reg = node
                    break
                for s in list(graph.successors(node)) + list(graph.predecessors(node)):
                    if s not in seen:
                        queue.append(s)
            if target_stage and target_reg and target_reg in all_nodes_in_stages:
                lines.append(
                    f'  "{_sid(sid)}" -> "{_sid(target_reg)}" '
                    f'[color="#cc8844" style=dashed penwidth=1.2 arrowsize=0.8 '
                    f'xlabel="affects S{target_stage}" fontsize=7 fontcolor="#cc8844"];'
                )

    # [Phase 6.3 2026-07-12] Legend overlay at bottom
    from .viz_legend import render_legend
    lines.extend(render_legend('pipeline'))

    lines.append('}')
    return "\n".join(lines)


def _group_stages_into_segments(
    stages: list, control_to_stage: dict[str, int]
) -> list[tuple[str | None, list]]:
    """[Phase 7.1 2026-07-13] 按 control_to_stage 把 stages 切分成 segment.

    算法:
    - 遍历按 stage_id 排序的 stages
    - 当 control signal target 变化时, 切分 segment
    - 没有 control targeting 的 stage 归入 ctrl=None 的 segment

    这是**连续 stage 序列** (按 graph depth 排序), 不是 CPU 架构的
    "parallel pipeline lanes". 之所以命名 segment (而非 lane), 是为了诚实:
    这些 stage 是 sequential, 不是 parallel.

    Returns:
        list of (ctrl_id_or_None, stages_in_segment)
    """
    # Build reverse map: stage_id → control_id
    stage_to_ctrl: dict[int, str] = {}
    for cid, target_stage in control_to_stage.items():
        if target_stage not in stage_to_ctrl:
            stage_to_ctrl[target_stage] = cid

    sorted_stages = sorted(stages, key=lambda s: s.stage_id)
    segments: list[tuple[str | None, list]] = []
    current_segment: list = []
    current_ctrl: str | None = None

    for stage in sorted_stages:
        ctrl = stage_to_ctrl.get(stage.stage_id)
        if ctrl != current_ctrl and current_segment:
            segments.append((current_ctrl, current_segment))
            current_segment = []
        current_ctrl = ctrl
        current_segment.append(stage)

    if current_segment:
        segments.append((current_ctrl, current_segment))

    return segments


def generate_pipeline_timing_dot(
    graph: SignalGraph,
    pipeline_info: PipelineInfo,
    classification: SignalClassification | None = None,
    *,
    max_segments: int = 8,
    max_stages_per_segment: int = 15,
) -> str:
    """[Phase 7.1 2026-07-13] Pipeline segment diagram using HTML table.

    Layout:
    - Y-axis (rows): segments = groups of consecutive stages split by control signal transitions
    - X-axis (cols): stages within each segment (subsampled)
    - Each cell shows: S<stage_id>: <reg_name>

    IMPORTANT NAMING NOTE:
    These are called 'segments' (NOT 'parallel lanes') because:
    - Stages are sorted by stage_id (which is BFS graph depth, NOT real cycles)
    - Segments are sequential groups, NOT parallel pipelines
    - Each segment may have a control signal target OR may be a no-control region

    For picorv32-style "150 stages" (where stage_id = BFS graph depth, not real cycles),
    this shows the structure as segments separated by control signal transitions.
    """
    _sid = sanitize_dot_id
    if classification is None:
        classification = safe_classify(graph)
        if classification is None:
            return f'// ERROR: failed to classify graph\ndigraph pipeline {{ label="Error: {pipeline_info.module_name}"; }}'

    # Collect control signals + map to stages
    control_outside = _collect_outside_controls(classification, pipeline_info)
    control_to_stage = _group_controls_by_stage(control_outside, pipeline_info, graph)

    # Group stages into segments
    all_segments = _group_stages_into_segments(pipeline_info.stages, control_to_stage)

    # Limit to top N segments by stage count
    all_segments_sorted = sorted(all_segments, key=lambda x: -len(x[1]))
    # [Phase 7.1 2026-07-13] Preserve ORIGINAL ORDER (not sorted by size)
    # so user sees the actual structure: no-ctrl, ctrl, no-ctrl, ctrl ...
    # But limit total segments shown (mix of large + small)
    if len(all_segments) > max_segments:
        # Take first N segments in original order
        shown_segments = all_segments[:max_segments]
        hidden_seg_count = len(all_segments) - max_segments
    else:
        shown_segments = all_segments
        hidden_seg_count = 0

    # Build segment data
    segment_data = []  # list of (seg_label_html, color, cell_texts)
    for si, (ctrl_id, seg_stages) in enumerate(shown_segments):
        # Determine segment label
        if ctrl_id and ctrl_id in classification.nodes:
            cn = classification.nodes[ctrl_id]
            ctrl_name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else ctrl_id
            # Strip module prefix
            if "." in ctrl_name:
                ctrl_name = ctrl_name.split(".", 1)[1]
            seg_label_text = f"Segment {si}: ← {ctrl_name} ({len(seg_stages)} stages)"
            seg_label_html = f"Segment {si}<BR/>← {ctrl_name}<BR/>({len(seg_stages)} stages)"
        else:
            seg_label_text = f"Segment {si}: (no control) ({len(seg_stages)} stages)"
            seg_label_html = f"Segment {si}<BR/>(no control signal target)<BR/>({len(seg_stages)} stages)"

        # Subsample cells
        if len(seg_stages) > max_stages_per_segment:
            step = max(1, len(seg_stages) // max_stages_per_segment)
            cell_stages = seg_stages[::step][:max_stages_per_segment]
            sample_note = f" (sampled {len(cell_stages)}/{len(seg_stages)})"
        else:
            cell_stages = seg_stages
            sample_note = ""

        cell_texts = []
        for stage in cell_stages:
            reg_id = stage.reg_nodes[0] if stage.reg_nodes else None
            if reg_id and reg_id in classification.nodes:
                cn2 = classification.nodes[reg_id]
                name = sanitize_dot_id(cn2.node.name) if cn2 and cn2.node.name else "?"
            else:
                name = "?"
            # Strip module prefix from name
            if "." in name:
                name = name.split(".", 1)[1]
            short_name = name[:18]
            cell_texts.append(f"S{stage.stage_id}: {short_name}")

        segment_data.append((seg_label_html, si, cell_texts, ctrl_id, seg_label_text))

    # Build HTML table
    total_regs = sum(len(s.reg_nodes) for s in pipeline_info.stages)
    max_cells = max(len(c) for _, _, c, _, _ in segment_data)

    rows = []
    rows.append('<TR>')
    rows.append('<TD BGCOLOR="#664400"><FONT COLOR="#ffffff"><B>Segment / Cell</B></FONT></TD>')
    for ci in range(max_cells):
        rows.append(f'<TD BGCOLOR="#fffbe6"><FONT COLOR="#664400"><B>S{ci+1}</B></FONT></TD>')
    rows.append('</TR>')

    seg_colors = ["#4488cc", "#cc6633", "#aa5599", "#5599aa", "#aa8855", "#8888cc", "#88cc88", "#cc8888"]

    for seg_label_html, si, cell_texts, ctrl_id, seg_label_text in segment_data:
        color = seg_colors[si % len(seg_colors)]
        rows.append('<TR>')
        rows.append(f'<TD BGCOLOR="#f0f0f5" ALIGN="LEFT"><FONT COLOR="{color}"><B>{seg_label_html}</B></FONT></TD>')
        for ci, cell_text in enumerate(cell_texts):
            rows.append(f'<TD BGCOLOR="{color}"><FONT COLOR="#ffffff" POINT-SIZE="8">{cell_text}</FONT></TD>')
        # Pad
        for _ in range(max_cells - len(cell_texts)):
            rows.append('<TD BGCOLOR="#eeeeee"> </TD>')
        rows.append('</TR>')

    table_html = (
        '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="2" CELLPADDING="4">'
        + ''.join(rows)
        + '</TABLE>'
    )

    # Title with honest description
    all_has_ctrl = sum(1 for cid, _ in all_segments if cid is not None)
    all_no_ctrl = len(all_segments) - all_has_ctrl
    has_ctrl_segs = sum(1 for _, _, _, cid, _ in segment_data if cid is not None)
    no_ctrl_segs = len(segment_data) - has_ctrl_segs

    lines = ['digraph pipeline_timing {']
    lines.append('  rankdir=LR;')
    lines.append('  labelloc=t;')
    lines.append('  fontsize=12;')
    title = (
        f'Pipeline Segment Diagram: {pipeline_info.module_name}\\n'
        f'{len(pipeline_info.stages)} stages (BFS depth, NOT real cycles) → {len(all_segments)} segments '
        f'({all_has_ctrl} with control signal, {all_no_ctrl} without)'
    )
    if hidden_seg_count > 0:
        title += f'\\n[Showing first {max_segments} of {len(all_segments)} segments in original order]'
    lines.append(f'  label="{title}";')
    lines.append('  node [shape=none];')
    lines.append('  diagram [label=<')
    lines.append('    ' + table_html)
    lines.append('  >];')
    lines.append('}')
    return "\n".join(lines)


def _group_stages_by_load_root(
    graph: SignalGraph,
    stages: list,
    info: PipelineInfo,
    classification,
) -> dict[int, str]:
    """[Phase 7.2 2026-07-13] 按 load root (输入端口) 给每个 stage 打标签.

    算法: BFS backward from each REG → 找到最近的 PORT_IN 祖先 (DRIVER 边 only).

    Returns:
        dict[stage_id, port_in_id]

    LIMITATION (调查发现 2026-07-13):
    图结构对"always块内计算结果赋值给 reg"这类场景不完整.
    例如 picorv32 中 `trap <= (cpu_state == 0 && irq_state != 0)` 这种:
    - trap reg 的 DRIVER 前驱只有字面量 (0, 1)
    - 真正的数据流 (cpu_state, irq_state) 通过组合逻辑到达 trap, 但 graph 不跟踪
    - 所以 BFS 反向找不到 port_in
    """
    from .signal_classifier import SignalClass
    from ..models import NodeKind

    port_ins = {
        nid for nid in graph.nodes()
        for cn in [classification.nodes.get(nid)]
        if cn and cn.node.kind == NodeKind.PORT_IN
        and cn.signal_class not in (SignalClass.CLOCK, SignalClass.RESET)
    }

    def driver_preds(node_id: str) -> list[str]:
        # 只走 DRIVER 边 (排除 CLOCK/RESET)
        preds = []
        for p in graph.predecessors(node_id):
            edges = graph.get_edges(p, node_id)
            for e in edges:
                if e.kind == EdgeKind.DRIVER:
                    preds.append(p)
                    break
        return preds

    reg_to_root: dict[str, str] = {}
    reg_to_dist: dict[str, int] = {}

    for reg_id in info.pipeline_regs:
        visited = {reg_id}
        queue = deque([(reg_id, 0)])
        found = False
        while queue and not found:
            current, dist = queue.popleft()
            for pred in driver_preds(current):
                if pred in visited:
                    continue
                visited.add(pred)
                if pred in port_ins:
                    reg_to_dist[reg_id] = dist + 1
                    reg_to_root[reg_id] = pred
                    found = True
                    break
                else:
                    queue.append((pred, dist + 1))

    stage_to_root: dict[int, str] = {}
    for stage in stages:
        if stage.reg_nodes:
            first_reg = stage.reg_nodes[0]
            if first_reg in reg_to_root:
                stage_to_root[stage.stage_id] = reg_to_root[first_reg]

    return stage_to_root

def _group_stages_into_load_segments(
    stages: list, stage_to_root: dict[int, str]
) -> list[tuple[str | None, list]]:
    """[Phase 7.2 2026-07-13] 按 load_root 把 stages 切分成 segment (顺序)."""
    sorted_stages = sorted(stages, key=lambda s: s.stage_id)
    segments: list[tuple[str | None, list]] = []
    current_segment: list = []
    current_root: str | None = None

    for stage in sorted_stages:
        root = stage_to_root.get(stage.stage_id)
        if root != current_root and current_segment:
            segments.append((current_root, current_segment))
            current_segment = []
        current_root = root
        current_segment.append(stage)

    if current_segment:
        segments.append((current_root, current_segment))

    return segments


def generate_pipeline_load_dot(
    graph: SignalGraph,
    pipeline_info: PipelineInfo,
    classification: SignalClassification | None = None,
    *,
    max_segments: int = 8,
    max_stages_per_segment: int = 15,
) -> str:
    """[Phase 7.2 2026-07-13] Pipeline segment diagram grouped by LOAD PATH.

    与 generate_pipeline_timing_dot 区别: 分组依据是 load root (PORT_IN) 而不是 control signal target.

    IMPORTANT: 实际可达性取决于 graph 结构. 如果 reg 不能通过 DRIVER 边追溯到 PORT_IN,
    则归入 (no load root) segment.
    """
    _sid = sanitize_dot_id
    if classification is None:
        classification = safe_classify(graph)
        if classification is None:
            return f'// ERROR\ndigraph pipeline {{ label="Error: {pipeline_info.module_name}"; }}'

    stage_to_root = _group_stages_by_load_root(graph, pipeline_info.stages, pipeline_info, classification)
    all_segments = _group_stages_into_load_segments(pipeline_info.stages, stage_to_root)

    # Prefer segments WITH load root (most useful info)
    # Take top N with root first, then fill with no-root segments if room
    with_root = sorted([(r, ss) for r, ss in all_segments if r is not None], key=lambda x: -len(x[1]))
    no_root = sorted([(r, ss) for r, ss in all_segments if r is None], key=lambda x: -len(x[1]))
    shown_segments = with_root[:max_segments]
    hidden_seg_count = len(with_root) - len(shown_segments)
    if len(shown_segments) < max_segments:
        remaining = max_segments - len(shown_segments)
        shown_segments.extend(no_root[:remaining])

    segment_data = []
    for si, (root_id, seg_stages) in enumerate(shown_segments):
        if root_id and root_id in classification.nodes:
            cn = classification.nodes[root_id]
            root_name = sanitize_dot_id(cn.node.name) if cn and cn.node.name else root_id
            if "." in root_name:
                root_name = root_name.split(".", 1)[1]
            seg_label_html = f"Segment {si}<BR/>↓ from {root_name}<BR/>({len(seg_stages)} stages)"
        else:
            seg_label_html = f"Segment {si}<BR/>(no load root)<BR/>({len(seg_stages)} stages)"

        if len(seg_stages) > max_stages_per_segment:
            step = max(1, len(seg_stages) // max_stages_per_segment)
            cell_stages = seg_stages[::step][:max_stages_per_segment]
        else:
            cell_stages = seg_stages

        cell_texts = []
        for stage in cell_stages:
            reg_id = stage.reg_nodes[0] if stage.reg_nodes else None
            if reg_id and reg_id in classification.nodes:
                cn2 = classification.nodes[reg_id]
                name = sanitize_dot_id(cn2.node.name) if cn2 and cn2.node.name else "?"
            else:
                name = "?"
            if "." in name:
                name = name.split(".", 1)[1]
            short_name = name[:18]
            cell_texts.append(f"S{stage.stage_id}: {short_name}")

        segment_data.append((seg_label_html, si, cell_texts, root_id))

    total_regs = sum(len(s.reg_nodes) for s in pipeline_info.stages)
    max_cells = max(len(c) for _, _, c, _ in segment_data) if segment_data else 0

    rows = []
    rows.append('<TR>')
    rows.append('<TD BGCOLOR="#664400"><FONT COLOR="#ffffff"><B>Load Path Segment</B></FONT></TD>')
    for ci in range(max_cells):
        rows.append(f'<TD BGCOLOR="#fffbe6"><FONT COLOR="#664400"><B>S{ci+1}</B></FONT></TD>')
    rows.append('</TR>')

    seg_colors = ["#4488cc", "#cc6633", "#aa5599", "#5599aa", "#aa8855", "#8888cc", "#88cc88", "#cc8888"]

    for seg_label_html, si, cell_texts, root_id in segment_data:
        color = seg_colors[si % len(seg_colors)]
        rows.append('<TR>')
        rows.append(f'<TD BGCOLOR="#f0f0f5" ALIGN="LEFT"><FONT COLOR="{color}"><B>{seg_label_html}</B></FONT></TD>')
        for ci, cell_text in enumerate(cell_texts):
            rows.append(f'<TD BGCOLOR="{color}"><FONT COLOR="#ffffff" POINT-SIZE="8">{cell_text}</FONT></TD>')
        for _ in range(max_cells - len(cell_texts)):
            rows.append('<TD BGCOLOR="#eeeeee"> </TD>')
        rows.append('</TR>')

    table_html = (
        '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="2" CELLPADDING="4">'
        + ''.join(rows)
        + '</TABLE>'
    )

    lines = ['digraph pipeline_load {']
    lines.append('  rankdir=LR;')
    lines.append('  labelloc=t;')
    lines.append('  fontsize=12;')
    n_with_root = sum(1 for r, _ in all_segments if r is not None)
    n_no_root = len(all_segments) - n_with_root
    title = (
        f'Pipeline Load-Path Diagram: {pipeline_info.module_name}\\n'
        f'{len(pipeline_info.stages)} stages → {len(all_segments)} load-path segments '
        f'({n_with_root} with port, {n_no_root} unreachable)'
    )
    if hidden_seg_count > 0:
        title += f'\\n[Showing top {max_segments} of {len(all_segments)} segments by stage count]'
    lines.append(f'  label="{title}";')
    lines.append('  node [shape=none];')
    lines.append('  diagram [label=<')
    lines.append('    ' + table_html)
    lines.append('  >];')
    lines.append('}')
    return "\n".join(lines)


# _node_width 委托给 _dot_common.node_width (上面已 import)

# _node_width 委托给 _dot_common.node_width (上面已 import)

# _node_width 委托给 _dot_common.node_width (上面已 import)

