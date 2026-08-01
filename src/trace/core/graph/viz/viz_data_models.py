"""
viz_data_models.py — 统一可视化数据格式 (V6.7)

原则:
- 一个 VizData = {nodes, edges, meta} 供所有 6 种画图功能使用
- 每个 node/edge 有必需字段 + 可选装饰字段
- 渲染器按需取字段，不关心的忽略

用法:
    from trace.core.graph.viz import build_viz_data, VizBuildOptions, render_dot
    viz = build_viz_data(signal_graph, options)
    dot = render_dot(viz)   # 统一渲染器
"""

from dataclasses import dataclass, field
from typing import Any

from ..models import EdgeKind, NodeKind, TraceEdge, TraceNode

# ═══════════════════════════════════════════════════════
# Node
# ═══════════════════════════════════════════════════════

@dataclass
class VizNode:
    """可视化节点 — 统一格式"""

    # --- 必需 ---
    id: str
    label: str
    full_path: str
    module: str
    kind: str  # SIGNAL | REG | WIRE | PORT_IN | PORT_OUT | PORT_INOUT | CONST | INSTANCE

    # --- 信号属性 ---
    width: tuple[int, int] | None = None  # (msb, lsb)
    file: str = ""
    line: int = 0

    # --- 架构/实例 (INSTANCE node 才有) ---
    def_name: str = ""  # instance 的 module def 名
    depth: int = 0

    # --- 分类 (dataflow/pipeline 用) ---
    class_: str = ""  # DATA | CONTROL | CLOCK | RESET | UNKNOWN
    class_confidence: float = 1.0

    # --- pipeline 阶段 (pipeline 用) ---
    stage_id: int | None = None
    cycle: int | None = None

    # --- 风险 (graph 用) ---
    risk_level: str = ""  # LOW | MEDIUM | HIGH | CRITICAL
    risk_score: float = 0.0

    # --- 覆盖率 (graph 用) ---
    cover_status: str = ""  # NONE | SVA | COV | BOTH

    # --- 链追踪 (chain 用) ---
    is_input: bool = False
    is_output: bool = False
    is_critical: bool = False

    # --- 其它 ---
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_trace_node(cls, node: TraceNode) -> "VizNode":
        """从 TraceNode 转换"""
        kind_str = node.kind.name if isinstance(node.kind, NodeKind) else str(node.kind)
        return cls(
            id=node.id,
            label=node.name,
            full_path=node.id,
            module=node.module,
            kind=kind_str,
            width=node.width,
            file=node.file,
            line=node.line,
        )


# ═══════════════════════════════════════════════════════
# Edge
# ═══════════════════════════════════════════════════════

@dataclass
class VizEdge:
    """可视化边 — 统一格式

    渲染时:
    - condition 显示在边上 (如 "state == FETCH")
    - expression 显示在标签位置
    - is_control_edge → 虚线
    - source → 位精确工具提示
    """

    # --- 必需 ---
    id: str  # "src->dst"
    src: str
    dst: str
    kind: str  # DRIVER | CLOCK | RESET | CONNECTION | BIT_SELECT

    # --- 驱动表达式 ---
    expression: str = ""
    bit_slice: str = ""  # "[7:0]"

    # --- 结构化信号源 (V6.5) ---
    source_signal: str = ""  # 实际信号名
    source_bit_start: int | None = None
    source_bit_end: int | None = None
    source_op: str = ""
    source_operand_side: str = ""
    source_casts: list[str] = field(default_factory=list)
    source_is_decomposed: bool = False

    # --- 条件/时钟 ---
    condition: str = ""  # 如 "state == FETCH" — 渲染在边上！
    effective_condition: str = ""
    clock_domain: str = ""
    reset_condition: str = ""

    # --- 赋值 ---
    assign_type: str = ""  # continuous | blocking | nonblocking
    confidence: str = "high"

    # --- 分类 ---
    class_: str = ""  # 边分类
    is_control_edge: bool = False

    # --- chain 追踪 ---
    edge_cycle_delta: int = 0  # 跨几个 cycle
    is_port_connection: bool = False
    port_name: str = ""

    # --- 其它 ---
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_trace_edge(cls, edge: TraceEdge) -> "VizEdge":
        """从 TraceEdge 转换"""
        kind_str = edge.kind.name if isinstance(edge.kind, EdgeKind) else str(edge.kind)
        eid = f"{edge.src}->{edge.dst}"

        # 从 SignalSource 提取
        ss = edge.source
        return cls(
            id=eid,
            src=edge.src,
            dst=edge.dst,
            kind=kind_str,
            expression=edge.expression,
            bit_slice=edge.bit_slice,
            source_signal=ss.signal if ss else "",
            source_bit_start=ss.bit_start if ss else None,
            source_bit_end=ss.bit_end if ss else None,
            source_op=ss.op if ss else "",
            source_operand_side=ss.operand_side if ss else "",
            source_casts=list(ss.casts) if ss else [],
            source_is_decomposed=ss.is_decomposed if ss else False,
            condition=edge.condition,
            effective_condition=edge.effective_condition,
            clock_domain=edge.clock_domain,
            assign_type=edge.assign_type,
            confidence=edge.confidence,
        )


# ═══════════════════════════════════════════════════════
# VizData (顶层容器)
# ═══════════════════════════════════════════════════════

@dataclass
class VizData:
    """统一可视化数据包 — 所有画图功能的输入"""

    meta: dict[str, Any] = field(default_factory=dict)
    nodes: list[VizNode] = field(default_factory=list)
    edges: list[VizEdge] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_json(self) -> dict:
        """序列化为 JSON 兼容的字典 (纯数据，不依赖 dataclass)"""

        def _keep(v) -> bool:
            """过滤掉空默认值, 但保留 0/0.0/False (合法值)"""
            if v is None or v == "" or v == [] or v == {}:
                return False
            if isinstance(v, (int, float, bool)):
                return True  # 保留 0, 0.0, False
            return True

        return {
            "meta": self.meta,
            "nodes": [
                {k: v for k, v in n.__dict__.items() if not k.startswith("_") and _keep(v)}
                for n in self.nodes
            ],
            "edges": [
                {k: v for k, v in e.__dict__.items() if not k.startswith("_") and _keep(v)}
                for e in self.edges
            ],
        }
