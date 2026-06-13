"""
signal_classifier — 基于现有图元数据区分 control 信号 vs data 信号

分类依据 (优先级从高到低):
  1. Node 自带标记: is_clock / is_reset / is_enable
  2. Edge kind: CLOCK / RESET / CONNECTION
  3. Node kind: 1-bit REG (可能是 control), 多-bit REG (data)
  4. Edge condition: 有条件 = 受 control 影响
  5. 名字启发式: valid/ready/stall/ack/req/grant/enable 后缀
  6. 宽度启发式: 1-bit 可能是 control, >1-bit 可能是 data

返回:
  SignalClass.CLOCK   — 时钟信号
  SignalClass.RESET   — 复位信号
  SignalClass.CONTROL — 控制信号 (valid, enable, state, etc.)
  SignalClass.DATA    — 数据通路信号
  SignalClass.UNKNOWN — 无法判断
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set

from ..models import SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind


class SignalClass(Enum):
    CLOCK = auto()
    RESET = auto()
    CONTROL = auto()
    DATA = auto()
    UNKNOWN = auto()


# 名字启发式: 控制信号常见后缀/前缀
CONTROL_NAME_PATTERNS = [
    "valid", "ready", "stall", "ack", "req", "grant", "enable", "en",
    "sel", "select", "we", "re", "cs", "ce",
    "state", "next_state", "nxt_state",
    "done", "busy", "idle", "error", "fault",
    "start", "stop", "flush",
]

# 数据信号常见后缀/前缀
DATA_NAME_PATTERNS = [
    "data", "addr", "address", "wdata", "rdata", "mem", "pc",
    "opcode", "operand", "result", "alu",
    "fifo_wdata", "fifo_rdata",
    "shift", "count", "counter", "timer",
]


@dataclass
class ClassifiedNode:
    """带分类标签的节点"""
    node: TraceNode
    node_id: str
    signal_class: SignalClass
    confidence: float  # 0.0 - 1.0


@dataclass
class ClassifiedEdge:
    """带分类标签的边"""
    edge: TraceEdge
    src_id: str
    dst_id: str
    edge_class: SignalClass
    is_control: bool  # 是否是关键控制边 (数据流图中只保留这些)
    confidence: float


@dataclass
class SignalClassification:
    """全图分类结果"""
    nodes: Dict[str, ClassifiedNode] = field(default_factory=dict)
    edges: Dict[tuple[str, str, str], ClassifiedEdge] = field(default_factory=dict)
    clock_nodes: List[str] = field(default_factory=list)
    reset_nodes: List[str] = field(default_factory=list)
    control_nodes: List[str] = field(default_factory=list)
    data_nodes: List[str] = field(default_factory=list)


def classify_graph(graph: SignalGraph) -> SignalClassification:
    """对 SignalGraph 中的所有节点和边进行分类"""
    result = SignalClassification()

    # 1. 先分类所有节点
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        sc, conf = _classify_node(node, node_id)
        cn = ClassifiedNode(node=node, node_id=node_id, signal_class=sc, confidence=conf)
        result.nodes[node_id] = cn
        if sc == SignalClass.CLOCK:
            result.clock_nodes.append(node_id)
        elif sc == SignalClass.RESET:
            result.reset_nodes.append(node_id)
        elif sc == SignalClass.CONTROL:
            result.control_nodes.append(node_id)
        elif sc == SignalClass.DATA:
            result.data_nodes.append(node_id)

    # 2. 分类所有边, 标记关键控制边
    for src, dst in graph.edges():
        for edge in graph.get_edges(src, dst):
            sc, is_key, conf = _classify_edge(edge, src, dst, result)
            key = (src, dst, str(edge.kind))
            ce = ClassifiedEdge(
                edge=edge, src_id=src, dst_id=dst,
                edge_class=sc, is_control=is_key, confidence=conf,
            )
            result.edges[key] = ce

    return result


def _classify_node(node: TraceNode, node_id: str) -> tuple[SignalClass, float]:
    """分类单个节点"""
    # 规则 1: 显式标记
    if node.is_clock:
        return SignalClass.CLOCK, 1.0
    if node.is_reset:
        return SignalClass.RESET, 1.0

    # 规则 2: NodeKind
    if node.kind == NodeKind.PARAM:
        return SignalClass.DATA, 0.8
    if node.kind == NodeKind.CONST:
        return SignalClass.DATA, 0.9
    if node.kind == NodeKind.INSTANTIATED_MODULE:
        return SignalClass.UNKNOWN, 0.0  # 模块实例不算信号

    # 规则 3: is_enable
    if node.is_enable:
        return SignalClass.CONTROL, 0.8

    # 规则 4: 名字启发式
    name_lower = node.name.lower()
    for pattern in CONTROL_NAME_PATTERNS:
        if pattern in name_lower:
            # 排除 data_ready 这类名字 / valid_data 等
            if any(dp in name_lower for dp in DATA_NAME_PATTERNS):
                return SignalClass.DATA, 0.6
            return SignalClass.CONTROL, 0.7
    for pattern in DATA_NAME_PATTERNS:
        if pattern in name_lower:
            return SignalClass.DATA, 0.7

    # 规则 5: 宽度启发式
    w_msb, w_lsb = node.width
    w = abs(w_msb - w_lsb) + 1 if w_msb >= w_lsb else 1
    if w == 1:
        # 1-bit: 可能是 control 或 flag
        if node.kind == NodeKind.REG:
            return SignalClass.CONTROL, 0.5  # 1-bit reg → 大概率 control
        return SignalClass.CONTROL, 0.4  # 1-bit signal → 可能是 control
    if w > 1:
        return SignalClass.DATA, 0.6  # 多-bit → 大概率 data

    return SignalClass.UNKNOWN, 0.0


def _classify_edge(
    edge: TraceEdge,
    src_id: str,
    dst_id: str,
    classification: SignalClassification,
) -> tuple[SignalClass, bool, float]:
    """分类单条边, 返回 (分类, 是否是关键控制边, 置信度)"""
    # 规则 1: EdgeKind
    if edge.kind == EdgeKind.CLOCK:
        return SignalClass.CLOCK, True, 1.0
    if edge.kind == EdgeKind.RESET:
        return SignalClass.RESET, True, 1.0

    # 规则 2: 端节点分类
    src_class = classification.nodes.get(src_id)
    dst_class = classification.nodes.get(dst_id)
    src_sc = src_class.signal_class if src_class else SignalClass.UNKNOWN
    dst_sc = dst_class.signal_class if dst_class else SignalClass.UNKNOWN

    if src_sc == SignalClass.CLOCK or dst_sc == SignalClass.CLOCK:
        return SignalClass.CLOCK, True, 0.9
    if src_sc == SignalClass.RESET or dst_sc == SignalClass.RESET:
        return SignalClass.RESET, True, 0.9

    # 规则 3: 有 condition → 受 control 影响的 data 边
    has_condition = bool(edge.condition)

    # CONNECTION 边: 端口连接,不是真正的数据流
    if edge.kind == EdgeKind.CONNECTION:
        return SignalClass.DATA, False, 0.0

    # DRIVER 边: 数据流主干
    if edge.kind == EdgeKind.DRIVER:
        if src_sc == SignalClass.CONTROL and dst_sc == SignalClass.DATA:
            # control → data: 这是关键控制边 (e.g. enable → reg)
            return SignalClass.CONTROL, True, 0.8
        if src_sc == SignalClass.DATA or dst_sc == SignalClass.DATA:
            return SignalClass.DATA, False, 0.7
        # 条件驱动: 同时是 data + control
        if has_condition:
            return SignalClass.DATA, True, 0.5

    # BIT_SELECT: 位选择, 通常是 data
    if edge.kind == EdgeKind.BIT_SELECT:
        return SignalClass.DATA, False, 0.5

    return SignalClass.UNKNOWN, False, 0.0


# ---- 辅助函数 ----

def get_dataflow_edges(
    classification: SignalClassification,
    include_key_control: bool = True,
) -> List[ClassifiedEdge]:
    """获取数据流图的边列表 (data 边 + 可选关键 control 边)"""
    result = []
    for key, ce in classification.edges.items():
        if ce.edge_class == SignalClass.DATA:
            result.append(ce)
        elif include_key_control and ce.is_control:
            result.append(ce)
    return result


def get_data_path_nodes(classification: SignalClassification) -> List[str]:
    """获取数据通路相关的所有节点 ID"""
    result = []
    for node_id, cn in classification.nodes.items():
        if cn.signal_class in (SignalClass.DATA, SignalClass.CONTROL):
            result.append(node_id)
    return result
