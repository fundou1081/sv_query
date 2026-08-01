"""
viz_data_builder.py — SignalGraph → VizData 转换器 (V6.7)

原则:
- 纯数据转换，不做渲染
- 接受 options dict 控制要包含的字段
- 每个画图命令传入不同的 options
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import SignalGraph
from .viz_data_models import VizData, VizEdge, VizNode


@dataclass
class VizBuildOptions:
    """控制 VizData 构建的选项"""

    # 过滤
    target_module: str = ""  # 目标模块
    max_nodes: int = 0  # 0=不限
    max_edges: int = 0

    # 节点信息
    include_node_class: bool = False  # class_ / classification
    include_node_risk: bool = False  # risk_level / risk_score
    include_node_cover: bool = False  # cover_status
    include_node_stage: bool = False  # stage_id / cycle

    # 边信息
    include_edge_expression: bool = True  # expression / bit_slice / source
    include_edge_condition: bool = True  # condition / clock / reset
    include_edge_cycle: bool = False  # edge_cycle_delta

    # 实例信息 (module/arch 用)
    include_instances: bool = False  # def_name / depth

    # chain 追踪
    input_signals: list[str] = field(default_factory=list)
    output_signals: list[str] = field(default_factory=list)
    critical_path: set[str] = field(default_factory=set)

    # 分类 (从外部注入, 避免循环依赖)
    classification: Any | None = None
    pipeline_stages: Any | None = None


def build_viz_data(
    graph: SignalGraph,
    options: VizBuildOptions | None = None,
) -> VizData:
    """从 SignalGraph 构建统一可视化数据

    Args:
        graph: SignalGraph 实例
        options: 构建选项

    Returns:
        VizData 包
    """
    opts = options or VizBuildOptions()
    viz = VizData(
        meta={
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "target_module": opts.target_module,
        }
    )

    # ── 构建节点 ──
    node_map: dict[str, VizNode] = {}
    for node_id in list(graph.nodes())[:opts.max_nodes] if opts.max_nodes else graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue

        vn = VizNode.from_trace_node(node)

        # 分类 (可选)
        if opts.include_node_class and opts.classification:
            cn = opts.classification.nodes.get(node_id)
            if cn:
                vn.class_ = cn.signal_class.name if cn.signal_class else ""
                vn.class_confidence = cn.confidence if hasattr(cn, "confidence") else 1.0

        # 风险 (可选)
        if opts.include_node_risk:
            _fill_risk(vn, node, graph)

        # coverage (可选)
        if opts.include_node_cover:
            _fill_cover(vn, node_id, graph)

        # pipeline stage (可选)
        if opts.include_node_stage and opts.pipeline_stages:
            # pipeline_stages: {stage_id: [node_ids]}
            for sid, nids in (opts.pipeline_stages or {}).items():
                if node_id in nids:
                    vn.stage_id = sid
                    break

        # chain 标记
        if node_id in opts.input_signals:
            vn.is_input = True
        if node_id in opts.output_signals:
            vn.is_output = True
        if node_id in opts.critical_path:
            vn.is_critical = True

        node_map[node_id] = vn

    viz.nodes = list(node_map.values())

    # ── 构建边 ──
    edge_count = 0
    for src, dst in list(graph.edges()):
        if opts.max_edges and edge_count >= opts.max_edges:
            break

        for edge in graph.get_edges(src, dst):
            if opts.max_edges and edge_count >= opts.max_edges:
                break

            ve = VizEdge.from_trace_edge(edge)

            # 边分类 (从 classification)
            if opts.include_node_class and opts.classification:
                ce = opts.classification.edges.get((src, dst))
                if ce and ce.edge_class:
                    ve.class_ = ce.edge_class.name
                    ve.is_control_edge = (ce.edge_class.name == "CONTROL")

            if not opts.include_edge_expression:
                ve.expression = ""
                ve.bit_slice = ""
                ve.source_signal = ""

            if not opts.include_edge_condition:
                ve.condition = ""
                ve.effective_condition = ""
                ve.clock_domain = ""

            viz.edges.append(ve)
            edge_count += 1

    viz.meta["filtered_node_count"] = viz.node_count
    viz.meta["filtered_edge_count"] = viz.edge_count
    return viz


# ── helpers ──

def _fill_risk(vn: VizNode, node, graph: SignalGraph) -> None:
    """简化的风险评分"""
    fanin = len(list(graph.predecessors(node.id)))
    fanout = len(list(graph.successors(node.id)))
    if fanin >= 5 or fanout >= 5:
        vn.risk_level = "HIGH"
        vn.risk_score = 0.7
    elif fanin >= 3 or fanout >= 3:
        vn.risk_level = "MEDIUM"
        vn.risk_score = 0.4
    else:
        vn.risk_level = "LOW"
        vn.risk_score = 0.1


def _fill_cover(vn: VizNode, node_id: str, graph: SignalGraph) -> None:
    """检查覆盖率标记"""
    node = graph.get_node(node_id)
    if node and node.extra:
        has_sva = bool(node.extra.get("sva"))
        has_cov = bool(node.extra.get("cov"))
        if has_sva and has_cov:
            vn.cover_status = "BOTH"
        elif has_sva:
            vn.cover_status = "SVA"
        elif has_cov:
            vn.cover_status = "COV"
