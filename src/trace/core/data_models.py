# ==============================================================================
# data_models.py - 语义分类层 (增强版)
# 每个类声明自己的 kind，更内聚
#
# [增强] 支持 DataFlow/ControlFlow 分析
# - ConnectionEdge: +timing, +assign_type, +condition_signals
# - SignalChain: +paths, +intermediate_signals, +timing_analysis, +conditions
# ==============================================================================

from dataclasses import dataclass, field

from pyslang import SyntaxKind

# ==============================================================================
# I. 语义收集器基类
# ==============================================================================


class SemanticCollector:
    """语义收集器基类 - 子类声明自己的 kind"""

    # 子类覆盖: 支持的 kind 值集合
    SUPPORTED_KINDS: set[int] = set()

    @classmethod
    def accepts(cls, kind_value: int) -> bool:
        return kind_value in cls.SUPPORTED_KINDS


# ==============================================================================
# II. 驱动分类器 (具体实现)
# ==============================================================================


class DriverCollector(SemanticCollector):
    """驱动关系收集器"""

    SUPPORTED_KINDS = {
        SyntaxKind.ContinuousAssign.value,
        SyntaxKind.NonblockingAssignmentExpression.value,
        SyntaxKind.AssignmentExpression.value,
    }


class SequentialDriverCollector(SemanticCollector):
    """时序驱动 (<=)"""

    SUPPORTED_KINDS = {
        SyntaxKind.NonblockingAssignmentExpression.value,
    }


class CombinationalDriverCollector(SemanticCollector):
    """组合驱动 (= 或 assign)"""

    SUPPORTED_KINDS = {
        SyntaxKind.ContinuousAssign.value,
        SyntaxKind.AssignmentExpression.value,
    }


# ==============================================================================
# III. 端口分类器
# ==============================================================================


class PortCollector(SemanticCollector):
    """端口收集器"""

    SUPPORTED_KINDS = set()  # 通过 visitor 单独处理


# ==============================================================================
# IV. 信号节点
# ==============================================================================


@dataclass(frozen=True)
class SignalNode:
    path: str
    width: int = 1
    is_port: bool = False
    is_reg: bool = False

    @property
    def module(self) -> str:
        return self.path.split(".")[0]

    @property
    def name(self) -> str:
        return self.path.split(".")[-1]


# ==============================================================================
# V. 连接边 [增强]
# ==============================================================================


@dataclass
class ConnectionEdge:
    source: str
    sink: str
    edge_type: str = "driver"
    source_file: str = ""
    source_line: int = 0
    condition: str | None = None

    # --- [增强] DataFlow 支持 ---
    timing: str | None = None  # '@posedge clk', '@negedge rst_n'
    assign_type: str = ""  # 'blocking', 'nonblocking', 'assign'
    condition_signals: list[str] = field(default_factory=list)  # 条件涉及的信号
    is_conditional: bool = False  # 是否有条件使能


# ==============================================================================
# VI. 控制流相关类 [新增]
# ==============================================================================


@dataclass
class ConditionInfo:
    """条件信息 [DataFlow/ControlFlow]"""

    kind: str = ""  # 'if', 'case', 'conditional_op'
    expr: str = ""  # 条件表达式原文
    signals: list[str] = field(default_factory=list)  # 条件涉及的信号

    # 分支信息
    true_branch: str = ""  # 为真时的值/语句
    false_branch: str | None = None  # 为假时的值/语句 (if)
    branches: list[str] = field(default_factory=list)  # case 分支列表

    # 覆盖信息
    is_covered: bool = False
    coverage_percentage: float = 0.0

    # 来源信息
    source_file: str = ""
    source_line: int = 0
    block_kind: str = ""  # 'always_ff', 'always_comb', 'assign'


@dataclass
class TimingAnalysisResult:
    """路径时序分析结果 [DataFlow]"""

    # 时钟域
    path_clock_domains: list[str] = field(default_factory=list)  # 路径经过的时钟域
    dominant_clock_domain: str | None = None  # 主时钟域
    cross_clock_domain: bool = False  # 是否跨时钟域

    # 寄存器
    register_stages: int = 0  # 寄存器级数
    registers_in_path: list[str] = field(default_factory=list)  # 路径中的寄存器

    # 时序
    timing_paths: list[list[str]] = field(default_factory=list)  # 寄存器→寄存器路径
    estimated_latency_cycles: int = 0  # 估计延迟（周期数）
    critical_path: list[str] | None = None  # 关键路径

    # 风险
    path_timing_risk: str = "safe"  # safe/low/medium/high/critical


@dataclass
class StateTransition:
    """状态机状态转换 [ControlFlow]"""

    from_state: str  # 源状态
    to_state: str  # 目标状态
    condition: str = ""  # 转换条件
    signals: list[str] = field(default_factory=list)  # 条件信号

    # 覆盖信息
    is_covered: bool = False
    transition_probability: float = 0.0


# ==============================================================================
# VII. 场景结果模型 [增强]
# ==============================================================================


@dataclass
class SignalChain:
    root: SignalNode

    # --- 现有字段 (保持兼容) ---
    drivers: list[ConnectionEdge] = field(default_factory=list)
    loads: list[ConnectionEdge] = field(default_factory=list)
    data_path: list[str] = field(default_factory=list)
    via_assignment: list[str] = field(default_factory=list)
    via_sequential: list[str] = field(default_factory=list)
    via_combinational: list[str] = field(default_factory=list)
    confidence: str = "high"
    caveats: list[str] = field(default_factory=list)

    # --- [增强] DataFlow 支持 ---
    paths: list[list[str]] = field(default_factory=list)  # 多跳路径列表
    intermediate_signals: set[str] = field(default_factory=set)  # 中间信号
    timing_analysis: TimingAnalysisResult | None = None  # 时序分析
    conditions: list[ConditionInfo] = field(default_factory=list)  # 条件列表
    data_flow_when: str = "always"  # 数据流成立条件 (如 "en && valid")

    # --- [增强] ControlFlow 支持 ---
    control_dependencies: dict[str, list[str]] = field(default_factory=dict)  # 控制依赖
    state_transitions: list[StateTransition] = field(default_factory=list)  # 状态转换
    branch_coverage: float = 0.0  # 分支覆盖率

    # --- 便捷属性 ---
    @property
    def latency_cycles(self) -> int:
        """路径延迟周期数"""
        return self.timing_analysis.register_stages if self.timing_analysis else 0

    @property
    def is_conditional(self) -> bool:
        """是否有条件使能"""
        return len(self.conditions) > 0

    @property
    def has_timing_analysis(self) -> bool:
        """是否有时序分析"""
        return self.timing_analysis is not None

    @property
    def has_state_machine(self) -> bool:
        """是否有状态机"""
        return len(self.state_transitions) > 0

    @property
    def enable_conditions(self) -> list[str]:
        """使能条件表达式列表"""
        return [c.expr for c in self.conditions if c.kind == "if"]

    def to_json(self) -> dict:
        return {
            "root": self.root.path,
            "drivers": [{"src": d.source, "type": d.edge_type} for d in self.drivers],
            "loads": [{"dst": load.sink, "type": load.edge_type} for load in self.loads],
            "data_path": self.data_path,
            "via": {
                "assign": self.via_assignment,
                "sequential": self.via_sequential,
                "combinational": self.via_combinational,
            },
            # --- DataFlow 增强 ---
            "paths": self.paths,
            "intermediate_signals": list(self.intermediate_signals),
            "timing_analysis": {
                "clock_domains": self.timing_analysis.path_clock_domains if self.timing_analysis else [],
                "register_stages": self.timing_analysis.register_stages if self.timing_analysis else 0,
                "latency_cycles": self.latency_cycles,
            }
            if self.timing_analysis
            else None,
            "conditions": [{"kind": c.kind, "expr": c.expr, "signals": c.signals} for c in self.conditions],
            "data_flow_when": self.data_flow_when,
            "confidence": self.confidence,
            "caveats": self.caveats,
        }


@dataclass
class ModuleConnections:
    module: str
    inputs: list[ConnectionEdge] = field(default_factory=list)
    outputs: list[ConnectionEdge] = field(default_factory=list)
    internal: list[str] = field(default_factory=list)
    instances: dict[str, list[str]] = field(default_factory=dict)
    confidence: str = "high"
    caveats: list[str] = field(default_factory=list)


@dataclass
class ClockDomainResult:
    clock_signal: str
    reset_signal: str = ""
    registers: list[str] = field(default_factory=list)
    combinational: list[str] = field(default_factory=list)
    async_crossings: list[ConnectionEdge] = field(default_factory=list)
    risk_level: str = "safe"
    confidence: str = "high"
    caveats: list[str] = field(default_factory=list)


# ==============================================================================
# VIII. 工厂函数
# ==============================================================================


def new_signal_node(path: str, width: int = 1, is_port: bool = False, is_reg: bool = False) -> SignalNode:
    return SignalNode(path=path, width=width, is_port=is_port, is_reg=is_reg)


def new_signal_chain(
    path: str,
    drivers: list = None,
    loads: list = None,
    data_path: list = None,
    via_assign: list = None,
    via_seq: list = None,
    via_comb: list = None,
    confidence: str = "high",
    caveats: list = None,
) -> SignalChain:
    node = SignalNode(path=path)
    return SignalChain(
        root=node,
        drivers=drivers or [],
        loads=loads or [],
        data_path=data_path or [],
        via_assignment=via_assign or [],
        via_sequential=via_seq or [],
        via_combinational=via_comb or [],
        confidence=confidence,
        caveats=caveats or [],
    )


def new_module_connections(module: str) -> ModuleConnections:
    return ModuleConnections(module=module)


def new_clock_domain(clock: str) -> ClockDomainResult:
    return ClockDomainResult(clock_signal=clock)


# --- 增强版工厂函数 [新增] ---


def new_timing_analysis(
    clock_domains: list[str] = None,
    register_stages: int = 0,
    registers: list[str] = None,
    latency_cycles: int = 0,
    cross_clock: bool = False,
) -> TimingAnalysisResult:
    """创建时序分析结果"""
    return TimingAnalysisResult(
        path_clock_domains=clock_domains or [],
        register_stages=register_stages,
        registers_in_path=registers or [],
        estimated_latency_cycles=latency_cycles,
        cross_clock_domain=cross_clock,
    )


def new_condition_info(
    kind: str,
    expr: str,
    signals: list[str] = None,
    true_branch: str = "",
    false_branch: str = None,
    source_file: str = "",
    source_line: int = 0,
) -> ConditionInfo:
    """创建条件信息"""
    return ConditionInfo(
        kind=kind,
        expr=expr,
        signals=signals or [],
        true_branch=true_branch,
        false_branch=false_branch,
        source_file=source_file,
        source_line=source_line,
    )


def new_state_transition(
    from_state: str, to_state: str, condition: str = "", signals: list[str] = None
) -> StateTransition:
    """创建状态转换"""
    return StateTransition(from_state=from_state, to_state=to_state, condition=condition, signals=signals or [])
