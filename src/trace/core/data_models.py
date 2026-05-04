#==============================================================================
# data_models.py - 数据模型
# 映射 pyslang 原生语句类型
#==============================================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

#==============================================================================
# pyslang 语句类型映射
#==============================================================================
class StatementKind(Enum):
    """语句类型 (对应 pyslang SyntaxKind)"""
    
    # 连续赋值
    CONTINUOUS_ASSIGN = "continuous_assign"
    
    # 过程块
    ALWAYS_FF = "always_ff"
    ALWAYS_COMB = "always_comb"
    ALWAYS_LATCH = "always_latch"
    
    # 赋值
    BLOCKING_ASSIGN = "blocking_assign"
    NONBLOCKING_ASSIGN = "nonblocking_assign"
    
    # 条件/循环
    IF_STATEMENT = "if_statement"
    ELSE_IF_STATEMENT = "else_if_statement"
    ELSE_STATEMENT = "else_statement"
    CASE_STATEMENT = "case_statement"
    FOR_LOOP = "for_loop"
    WHILE_LOOP = "while_loop"
    FOREVER_LOOP = "forever_loop"
    
    # 其他
    PROCEDURAL_FORCE = "procedural_force"
    GATE_INST = "gate_instance"

# 用于从 pyslang 映射
PYSlangKind2Statement = {
    # 语句类型映射表 (可以在运行时补充)
}

def init_mapping():
    """初始化 pyslang -> StatementKind 映射"""
    from pyslang import SyntaxKind
    
    mapping = {
        SyntaxKind.ContinuousAssign: StatementKind.CONTINUOUS_ASSIGN,
        SyntaxKind.AlwaysFFBlock: StatementKind.ALWAYS_FF,
        SyntaxKind.AlwaysCombBlock: StatementKind.ALWAYS_COMB,
        SyntaxKind.AlwaysLatchBlock: StatementKind.ALWAYS_LATCH,
        SyntaxKind.BlockingAssignmentExpression: StatementKind.BLOCKING_ASSIGN,
        SyntaxKind.NonblockingAssignmentExpression: StatementKind.NONBLOCKING_ASSIGN,
        SyntaxKind.CaseStatement: StatementKind.CASE_STATEMENT,
        SyntaxKind.IfGenerate: StatementKind.IF_STATEMENT,
    }
    return mapping

#==============================================================================
# Confidence - 置信度
#==============================================================================
class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    UNCERTAIN = "uncertain"

class EdgeKind(Enum):
    DRIVER = "driver"
    DATA = "data"
    CLOCK = "clock"
    RESET = "reset"
    ENABLE = "enable"

#==============================================================================
# Statement - 底层语句模型 (对应 pyslang AST 节点)
#==============================================================================
@dataclass
class Statement:
    """语句基类"""
    kind: str                    # StatementKind 值
    file: str = ""
    line_start: int = 0
    line_end: int = 0
    
    @property
    def pyslang_kind(self) -> Optional[str]:
        """返回 pyslang 的 kind 值"""
        return self.kind

@dataclass
class ContinuousAssignStmt(Statement):
    """连续赋值: assign lhs = rhs;"""
    lhs: str = ""
    rhs: str = ""
    rhs_expr: str = ""
    
    def __init__(self, lhs: str = "", rhs: str = "", rhs_expr: str = "",
                 file: str = "", line: int = 0):
        super().__init__(
            kind=StatementKind.CONTINUOUS_ASSIGN.value,
            file=file, line_start=line, line_end=line
        )
        self.lhs = lhs
        self.rhs = rhs
        self.rhs_expr = rhs_expr

@dataclass
class ProceduralAssignStmt(Statement):
    """过程赋值 (always 块中)"""
    lhs: str = ""
    rhs: str = ""
    blocking: bool = False        # True: = , False: <=
    condition: Optional[str] = None
    
    def __init__(self, lhs: str = "", rhs: str = "", blocking: bool = False,
                 condition: Optional[str] = None, file: str = "", line: int = 0):
        kind = StatementKind.BLOCKING_ASSIGN.value if blocking else StatementKind.NONBLOCKING_ASSIGN.value
        super().__init__(kind=kind, file=file, line_start=line, line_end=line)
        self.lhs = lhs
        self.rhs = rhs
        self.blocking = blocking
        self.condition = condition

@dataclass
class ConditionalStmt(Statement):
    """条件语句"""
    condition: str = ""
    true_branch: List[str] = field(default_factory=list)
    false_branch: List[str] = field(default_factory=list)
    
    def __init__(self, cond: str = "", true_br: List[str] = None,
                 false_br: List[str] = None, file: str = "", line: int = 0):
        super().__init__(
            kind=StatementKind.IF_STATEMENT.value,
            file=file, line_start=line, line_end=line
        )
        self.condition = cond
        self.true_branch = true_br or []
        self.false_branch = false_br or []

#==============================================================================
# DriverInfo - 驱动信息 (包含 statement 来源)
#==============================================================================
@dataclass
class DriverInfo:
    """驱动信息"""
    signal: str                 # 驱动信号
    statement: Optional[Statement] = None  # 语句来源 [关键字段]
    edge_type: str = EdgeKind.DRIVER.value
    
    @property
    def statement_type(self) -> str:
        return self.statement.kind if self.statement else "unknown"
    
    @property
    def file(self) -> str:
        return self.statement.file if self.statement else ""
    
    @property
    def line(self) -> int:
        return self.statement.line_start if self.statement else 0
    
    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "statement_type": self.statement_type,
            "file": self.file,
            "line": self.line,
            "edge_type": self.edge_type
        }

@dataclass
class LoadInfo:
    """负载信息"""
    signal: str
    statement: Optional[Statement] = None
    edge_type: str = EdgeKind.DATA.value
    
    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "type": self.statement.kind if self.statement else "unknown",
            "edge_type": self.edge_type
        }

#==============================================================================
# SignalChain - 场景A: 信号追踪结果
#==============================================================================
@dataclass
class SignalChain:
    root: str
    signal_name: str
    module: str
    
    drivers: List[DriverInfo] = field(default_factory=list)
    loads: List[LoadInfo] = field(default_factory=list)
    data_path: List[str] = field(default_factory=list)
    
    # 位精确性
    width: int = 1
    is_bit_select: bool = False
    bit_high: Optional[int] = None
    bit_low: Optional[int] = None
    
    # 置信度 [铁律10]
    confidence: str = Confidence.HIGH.value
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "root": self.root,
            "signal": self.signal_name,
            "module": self.module,
            "drivers": [d.to_dict() for d in self.drivers],
            "loads": [l.to_dict() for l in self.loads],
            "bit_range": f"[{self.bit_high}:{self.bit_low}]" if self.is_bit_select else None,
            "confidence": self.confidence,
            "caveats": self.caveats
        }

#==============================================================================
# 模块连接
#==============================================================================
@dataclass
class PortConnection:
    name: str
    direction: str
    width: int = 1
    is_bit_select: bool = False
    connected_signals: List[str] = field(default_factory=list)

@dataclass
class ModuleConnections:
    module: str
    ports: List[PortConnection] = field(default_factory=list)
    internal_signals: List[str] = field(default_factory=list)
    sub_modules: List[str] = field(default_factory=list)
    cross_module: List[str] = field(default_factory=list)
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "module": self.module,
            "confidence": self.confidence,
            "caveats": self.caveats
        }

#==============================================================================
# 时钟域
#==============================================================================
class CrossingRisk(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class RegisterInfo:
    name: str
    statement: Statement = None
    clock_domain: str = ""

@dataclass
class ClockDomainResult:
    clock_signal: str
    reset_signal: str = ""
    registers: List[RegisterInfo] = field(default_factory=list)
    combinational: List[str] = field(default_factory=list)
    async_crossings: List[DriverInfo] = field(default_factory=list)
    risk_level: str = "safe"
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "clock": self.clock_signal,
            "risk": self.risk_level,
            "confidence": self.confidence,
            "caveats": self.caveats
        }

#==============================================================================
# 工厂函数
#==============================================================================
def new_signal_chain(root: str, signal_name: str, module: str) -> SignalChain:
    return SignalChain(root=root, signal_name=signal_name, module=module)

def new_module_connections(module: str) -> ModuleConnections:
    return ModuleConnections(module=module)

def new_clock_domain(clock: str) -> ClockDomainResult:
    return ClockDomainResult(clock_signal=clock)
