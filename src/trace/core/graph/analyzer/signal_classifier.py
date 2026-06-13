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

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..models import SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind


class SignalClass(Enum):
    CLOCK = auto()
    RESET = auto()
    CONTROL = auto()
    DATA = auto()
    UNKNOWN = auto()


# [P1-4 2026-06-13] 默认 control/data name patterns — fallback when YAML
# config not found. Custom configs can override via set_patterns().
_DEFAULT_CONTROL_PATTERNS = [
    "valid", "ready", "stall", "ack", "req", "grant", "enable", "en",
    "sel", "select", "we", "re", "cs", "ce",
    "state", "next_state", "nxt_state",
    "done", "busy", "idle", "error", "fault",
    "start", "stop", "flush",
]

_DEFAULT_DATA_PATTERNS = [
    "data", "addr", "address", "wdata", "rdata", "mem", "pc",
    "opcode", "operand", "result", "alu",
    "fifo_wdata", "fifo_rdata",
    "shift", "count", "counter", "timer",
]


@dataclass
class ClassifyConfig:
    """[P1-4] 从 YAML 加载的分类规则, 可被 set_config() 覆盖。

    Attributes:
        control_patterns: 控制信号名子串
        data_patterns: 数据信号名子串
        source: 加载来源 ('builtin' | 'yaml:path/to/file.yaml')
    """
    control_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_CONTROL_PATTERNS))
    data_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_DATA_PATTERNS))
    source: str = "builtin"

    def with_overrides(self, control=None, data=None) -> "ClassifyConfig":
        """返一个新 config, 覆盖部分 pattern 列表。"""
        return ClassifyConfig(
            control_patterns=list(control) if control is not None else list(self.control_patterns),
            data_patterns=list(data) if data is not None else list(self.data_patterns),
            source=f"{self.source}+override",
        )


# 活跃配置 (默认 = builtin, 可以被 set_config() / load_config() 替换)
_ACTIVE_CONFIG: ClassifyConfig = ClassifyConfig()


def get_config() -> ClassifyConfig:
    """获取当前活跃的分类配置 (用于 inspection / 测试)."""
    return _ACTIVE_CONFIG


def set_config(cfg: ClassifyConfig) -> None:
    """全局设置分类配置 (慎用 — 会影响后续所有 classify_graph() 调用)."""
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = cfg


def reset_config() -> None:
    """重置为默认 builtin 配置。"""
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = ClassifyConfig()


def _auto_load_default_config() -> None:
    """[P1-4] 在 classify_graph() 首次调用时静默加载默认 YAML。

    路径探测顺序:
      1. sv_query/config/signal_classify.yaml
      2. CWD/config/signal_classify.yaml
      3. 不存在 → 不动, 用 builtin fallback
    """
    # sv_query/ 包根目录 (本文件所在位置的爷爷级别)
    # signal_classifier.py 位于 src/trace/core/graph/analyzer/
    _here = Path(__file__).resolve()
    # 1. sv_query/config/ 路径
    sv_query_root = _here.parents[4] if len(_here.parents) >= 5 else None
    candidates = []
    if sv_query_root:
        candidates.append(sv_query_root / "config" / "signal_classify.yaml")
    candidates.append(Path.cwd() / "config" / "signal_classify.yaml")
    for path in candidates:
        if path.exists():
            try:
                load_config(path)
            except Exception:
                # 静默降级到 builtin (避免背景 noise)
                pass
            return


def load_config(yaml_path) -> ClassifyConfig:
    """[P1-4] 从 YAML 文件加载分类配置并设置为活跃配置。

    详见 config/signal_classify.yaml schema。

    Args:
        yaml_path: YAML 文件路径 (str 或 Path)。

    Returns:
        加载后的 ClassifyConfig (同时被设为活跃配置)。

    Raises:
        FileNotFoundError: YAML 不存在
        ValueError: YAML 格式错
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"signal_classify YAML not found: {yaml_path}")
    text = yaml_path.read_text()
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
    except ImportError:
        data = _mini_yaml_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be dict, got {type(data).__name__}")
    rules = data.get("rules") or []
    control_patterns: List[str] = []
    data_patterns: List[str] = []
    for rule in rules:
        cls = rule.get("class")
        pats = rule.get("patterns") or []
        if cls == "control":
            control_patterns.extend(pats)
        elif cls == "data":
            data_patterns.extend(pats)
        # width_filter 类规则 (空 patterns) 不加入 name 模式列表
    cfg = ClassifyConfig(
        control_patterns=control_patterns or list(_DEFAULT_CONTROL_PATTERNS),
        data_patterns=data_patterns or list(_DEFAULT_DATA_PATTERNS),
        source=f"yaml:{yaml_path}",
    )
    set_config(cfg)
    return cfg


def _mini_yaml_load(text: str) -> dict:
    """极简 YAML parser: 只支持本文件 schema (rules: list of {class, patterns: list[str]})."""
    out: Dict = {"rules": []}
    current: Optional[Dict] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        if stripped == "rules:":
            current = None
            continue
        if stripped.startswith("- "):
            if current is None:
                # start of a new rule in the rules: section
                item: Dict = {}
                key_val = stripped[2:].split(":", 1)
                if len(key_val) == 2:
                    item[key_val[0].strip()] = key_val[1].strip()
                out["rules"].append(item)
                current = item
            else:
                # this shouldn't normally happen for our schema
                pass
        elif current is not None and ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                if not inner:
                    current[key.strip()] = []
                else:
                    current[key.strip()] = [
                        x.strip().strip('"').strip("'")
                        for x in inner.split(",")
                        if x.strip()
                    ]
            else:
                current[key.strip()] = val
    return out


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
    # [P1-4 2026-06-13] 首次调用时自动加载默认 YAML 配置 (如果存在)
    # — 避免每个调用方手动 load_config()
    if _ACTIVE_CONFIG.source == "builtin":
        _auto_load_default_config()
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

    # 规则 4: 名字启发式 (从 _ACTIVE_CONFIG 读, 可被 YAML 覆盖)
    name_lower = node.name.lower()
    cfg = _ACTIVE_CONFIG
    for pattern in cfg.control_patterns:
        if pattern in name_lower:
            # 排除 data_ready 这类名字 / valid_data 等
            if any(dp in name_lower for dp in cfg.data_patterns):
                return SignalClass.DATA, 0.6
            return SignalClass.CONTROL, 0.7
    for pattern in cfg.data_patterns:
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
