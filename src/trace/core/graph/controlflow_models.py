# ControlFlow 数据模型
# 基于 docs/CONTROL_FLOW_DESIGN.md 设计

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ControlFlowNodeKind(Enum):
    """控制流节点类型"""

    # 条件节点
    CONDITION = auto()  # if/case/三元条件
    CONDITION_TRUE = auto()  # if 的 then 分支
    CONDITION_FALSE = auto()  # if 的 else 分支
    CONDITION_DEFAULT = auto()  # case 的 default

    # 分支节点
    CASE_ITEM = auto()  # case 的某个项

    # 状态节点
    STATE = auto()  # 状态机状态
    STATE_ENTRY = auto()  # 进入状态
    STATE_EXIT = auto()  # 退出状态

    # 合并节点
    MERGE = auto()  # if/case 后的汇合

    # 块节点
    BLOCK = auto()  # 代码块
    SEQUENCE = auto()  # 顺序执行


class ControlFlowEdgeKind(Enum):
    """控制流边类型"""

    # 条件分支
    COND_TRUE = auto()  # 条件为真时的边
    COND_FALSE = auto()  # 条件为假时的边

    # case 分支
    CASE_MATCH = auto()  # case 匹配某值
    CASE_DEFAULT = auto()  # case default

    # 状态转换
    STATE_TRANSITION = auto()  # 状态转换

    # 执行顺序
    SEQUENCE = auto()  # 顺序执行
    FALL_THROUGH = auto()  # 穿透执行（无 break）


class BranchKind(Enum):
    """分支类型"""

    IF = auto()
    CASE = auto()
    TERNARY = auto()


@dataclass
class Location:
    """源码位置"""

    file: str = ""
    line: int = 0
    column: int = 0

    def __str__(self):
        return f"{self.file}:{self.line}:{self.column}"


@dataclass
class Branch:
    """分支信息"""

    kind: BranchKind
    condition: str  # 分支条件 "en", "sel == 0"
    value: str | None = None  # case 的值 "0", "1", "default"
    action: str = ""  # 执行的动作 "q <= d"
    covered: bool = False  # 是否覆盖
    signal_sources: list[str] = field(default_factory=list)  # 信号的来源


@dataclass
class ControlBlock:
    """控制块 - 同时包含控制变量和数据变量"""

    # 位置
    file: str = ""
    line: int = 0
    column: int = 0
    end_line: int = 0

    # 控制信息
    condition_expr: str = ""  # "en && valid"
    control_vars: list[str] = field(default_factory=list)  # ["en", "valid"]

    # 数据信息
    data_vars: list[str] = field(default_factory=list)  # ["q", "data_out"]
    data_stmts: list[str] = field(default_factory=list)  # ["q <= d", "data_out <= src"]

    # 块的 AST 节点
    ast_node: Any | None = None

    # 块类型
    kind: str = "if"  # 'if', 'case', 'ternary'

    # 分支信息 (if/case)
    branches: list[Branch] = field(default_factory=list)

    # 嵌套的子块
    nested_blocks: list["ControlBlock"] = field(default_factory=list)

    @property
    def has_else(self) -> bool:
        """是否有 else 分支"""
        return any(not b.condition for b in self.branches) or any(b.value == "default" for b in self.branches)

    @property
    def location(self) -> Location:
        return Location(file=self.file, line=self.line, column=self.column)


@dataclass
class ControlFlowNode:
    """控制流节点"""

    id: str  # 唯一 ID: "module:line:col:kind"
    kind: ControlFlowNodeKind
    name: str  # 可读名称: "if (en)", "state=IDLE"

    # 位置
    file: str = ""
    line: int = 0
    column: int = 0

    # 条件信息（如果是 CONDITION 节点）
    condition_expr: str | None = None  # "en && valid"
    condition_vars: list[str] = field(default_factory=list)  # ["en", "valid"]

    # 状态信息（如果是 STATE 节点）
    state_value: str | None = None  # "IDLE"

    # case 信息（如果是 CASE_ITEM 节点）
    case_value: str | None = None  # "0", "default"

    # 关联的 AST 节点
    ast_node: Any | None = None


@dataclass
class ControlFlowEdge:
    """控制流边"""

    id: str
    kind: ControlFlowEdgeKind

    # 源节点和目标节点
    from_node: str  # 源节点 ID
    to_node: str  # 目标节点 ID

    # 边条件（条件分支边）
    condition_expr: str | None = None  # "en", "sel == 0"

    # 优先级（case/if 优先级）
    priority: int = 0

    # AST 信息
    ast_node: Any | None = None


@dataclass
class BranchResult:
    """分支结果"""

    condition: str  # 分支条件 "en", "sel == 0"
    action: str = ""  # 执行的动作 "q <= d"
    covered: bool = False  # 是否覆盖
    signal_sources: list[str] = field(default_factory=list)  # 信号的来源


@dataclass
class Contradiction:
    """矛盾条件"""

    type: str = ""  # 'impossible_condition', 'duplicate_case'
    expr: str = ""  # "en && !en"
    reason: str = ""  # "en && !en is always false"
    location: Location | None = None
    severity: str = "warning"  # 'error', 'warning'
    suggestion: str = ""  # "Remove impossible condition"


@dataclass
class LintWarning:
    """代码审查警告"""

    severity: str = "warning"  # 'error', 'warning', 'info'
    rule: str = ""  # 'LATCH_WARNING', 'INCOMPLETE_CASE'

    file: str = ""
    line: int = 0
    column: int = 0

    message: str = ""  # "if without else may cause latch"
    suggestion: str = ""  # "Add else branch with default value"


@dataclass
class StateTransition:
    """状态转换"""

    from_state: str  # 源状态
    to_state: str  # 目标状态
    condition: str = ""  # 转换条件
    signals: list[str] = field(default_factory=list)  # 条件涉及的信号

    # 覆盖信息
    is_covered: bool = False
    transition_probability: float = 0.0


@dataclass
class StateMachineAnalysis:
    """状态机分析结果"""

    name: str = ""  # "top.state"

    # 状态集合
    all_states: list[str] = field(default_factory=list)
    reachable_states: list[str] = field(default_factory=list)

    # 死锁检测
    has_deadlock: bool = False
    deadlock_states: list[str] = field(default_factory=list)
    deadlock_reason: str = ""

    # 无法到达的状态
    unreachable_states: list[str] = field(default_factory=list)

    # 状态转换
    transitions: list[StateTransition] = field(default_factory=list)

    # 覆盖率
    coverage: float = 0.0


@dataclass
class Z3Result:
    """Z3 求解结果"""

    satisfiable: bool = True
    model: dict[str, Any] | None = None
    contradictions: list[Contradiction] = field(default_factory=list)
    unreachable_states: list[str] = field(default_factory=list)


@dataclass
class ControlFlowResult:
    """控制流分析结果"""

    # 输入
    control_var: str = ""  # "en"
    data_var: str = ""  # "q"

    # 控制块信息
    control_block: ControlBlock | None = None

    # 条件分析
    condition_expr: str = ""  # "en && valid"
    condition_vars: list[str] = field(default_factory=list)  # ["en", "valid"]
    condition_sources: dict[str, str] = field(default_factory=dict)  # {"en": "top.u_ctrl.en"}

    # 分支分析
    branches: list[BranchResult] = field(default_factory=list)

    # 数据流条件
    data_flow_when: str = ""  # "en == 1"

    # Z3 分析 (如果有矛盾条件)
    z3_analysis: Z3Result | None = None

    # 警告
    warnings: list[LintWarning] = field(default_factory=list)

    # === 死锁/可达性 ===
    state_machine_analysis: StateMachineAnalysis | None = None

    # === 矛盾条件 ===
    contradictions: list[Contradiction] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0 or len(self.contradictions) > 0

    @property
    def is_deadlock_free(self) -> bool:
        if self.state_machine_analysis:
            return not self.state_machine_analysis.has_deadlock
        return True
