#==============================================================================
# data_models.py - 数据模型
# 包含 Statement 层级和查询结果类型
#==============================================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

#==============================================================================
# Confidence - 置信度枚举
#==============================================================================
class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    UNCERTAIN = "uncertain"

#==============================================================================
# StatementKind - 语句类型枚举 (编译原理分类)
#==============================================================================
class StatementKind(Enum):
    """语句类型"""
    # 连续赋值
    CONTINUOUS_ASSIGN = "continuous_assign"
    
    # 过程赋值
    BLOCKING_ASSIGN = "blocking_assign"
    NONBLOCKING_ASSIGN = "nonblocking_assign"
    
    # 过程块
    ALWAYS_FF = "always_ff"
    ALWAYS_COMB = "always_comb"
    ALWAYS_LATCH = "always_latch"
    
    # 条件语句
    IF_STATEMENT = "if_statement"
    ELSE_IF_STATEMENT = "else_if_statement"
    ELSE_STATEMENT = "else_statement"
    CASE_STATEMENT = "case_statement"
    
    # 其他
    PROCEDURAL_FORCE = "procedural_force"
    GATE_INST = "gate_instance"

#==============================================================================
# EdgeKind - 边类型
#==============================================================================
class EdgeKind(Enum):
    DRIVER = "driver"     # 驱动关系
    DATA = "data"        # 数据流
    CLOCK = "clock"      # 时钟
    RESET = "reset"       # 复位
    ENABLE = "enable"     # 使能

#==============================================================================
# Statement - 底层语句模型
#==============================================================================
@dataclass
class Statement:
    """语句基类"""
    kind: str                    # StatementKind 值
    file: str = ""               # 文件名
    line_start: int = 0         # 起始行
    line_end: int = 0           # 结束行
    
    def __str__(self):
        return f"{self.kind} @ {self.file}:{self.line_start}"

@dataclass
class ContinuousAssign(Statement):
    """连续赋值: assign lhs = rhs;"""
    lhs: str = ""               # 左值信号
    rhs: str = ""               # 右值信号
    rhs_expr: str = ""          # 完整表达式
    
    def __init__(self, lhs: str, rhs: str, rhs_expr: str = "", file: str = "", line: int = 0):
        super().__init__(
            kind=StatementKind.CONTINUOUS_ASSIGN.value,
            file=file,
            line_start=line,
            line_end=line
        )
        self.lhs = lhs
        self.rhs = rhs
        self.rhs_expr = rhs_expr

@dataclass  
class ProceduralAssign(Statement):
    """过程赋值: always 块中的赋值"""
    lhs: str = ""               # 左值信号
    rhs: str = ""               # 右值信号
    blocking: bool = False      # 是否阻塞赋值 (= vs <=)
    condition: Optional[str] = None  # 条件表达式
    
    def __init__(self, lhs: str, rhs: str, blocking: bool = False, 
                 condition: Optional[str] = None, file: str = "", line: int = 0):
        kind = StatementKind.BLOCKING_ASSIGN.value if blocking else StatementKind.NONBLOCKING_ASSIGN.value
        super().__init__(
            kind=kind,
            file=file,
            line_start=line,
            line_end=line
        )
        self.lhs = lhs
        self.rhs = rhs
        self.blocking = blocking
        self.condition = condition

@dataclass
class ConditionalStatement(Statement):
    """条件语句: if/else"""
    condition: str = ""
    true_branch: List[str] = field(default_factory=list)  # 条件满足时的赋值
    false_branch: List[str] = field(default_factory=list)   # else 分支的赋值
    
    def __init__(self, condition: str, true_branch: List[str] = None, 
                 false_branch: List[str] = None, file: str = "", line: int = 0):
        super().__init__(
            kind=StatementKind.IF_STATEMENT.value,
            file=file,
            line_start=line,
            line_end=line
        )
        self.condition = condition
        self.true_branch = true_branch or []
        self.false_branch = false_branch or []

#==============================================================================
# StatementFactory - 工厂类
#==============================================================================
class StatementFactory:
    """创建 Statement 的工厂方法"""
    
    @staticmethod
    def create(kind: StatementKind, **kwargs) -> Statement:
        if kind == StatementKind.CONTINUOUS_ASSIGN:
            return ContinuousAssign(**kwargs)
        elif kind in [StatementKind.BLOCKING_ASSIGN, StatementKind.NONBLOCKING_ASSIGN]:
            return ProceduralAssign(**kwargs)
        elif kind in [StatementKind.IF_STATEMENT, StatementKind.ELSE_IF_STATEMENT]:
            return ConditionalStatement(**kwargs)
        else:
            # 其他类型用基类
            return Statement(kind=kind.value, **kwargs)

#==============================================================================
# DriverInfo - 驱动信息 (包含语句来源)
#==============================================================================
@dataclass
class DriverInfo:
    """驱动信息"""
    signal: str                 # 驱动信号
    statement: Optional[Statement] = None  # 语句来源
    edge_type: str = "driver"    # 边类型
    
    @property
    def statement_type(self) -> str:
        if self.statement:
            return self.statement.kind
        return "unknown"
    
    @property
    def file(self) -> str:
        return self.statement.file if self.statement else ""
    
    @property
    def line(self) -> int:
        return self.statement.line_start if self.statement else 0
    
    @property
    def condition(self) -> Optional[str]:
        if isinstance(self.statement, ProceduralAssign):
            return self.statement.condition
        if isinstance(self.statement, ConditionalStatement):
            return self.statement.condition
        return None
    
    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "statement_type": self.statement_type,
            "file": self.file,
            "line": self.line,
            "condition": self.condition,
            "edge_type": self.edge_type
        }

#==============================================================================
# LoadInfo - 负载信息
#==============================================================================
@dataclass
class LoadInfo:
    """负载信息（与 DriverInfo 对称）"""
    signal: str
    statement: Optional[Statement] = None
    edge_type: str = "data"
    
    @property
    def statement_type(self) -> str:
        return self.statement.kind if self.statement else "unknown"
    
    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "statement_type": self.statement_type,
            "edge_type": self.edge_type
        }

#==============================================================================
# SignalChain - 场景A: 信号追踪结果
#==============================================================================
@dataclass
class SignalChain:
    """信号完整追踪链"""
    root: str
    signal_name: str
    module: str
    
    # 关系数据
    drivers: List[DriverInfo] = field(default_factory=list)
    loads: List[LoadInfo] = field(default_factory=list)
    data_path: List[str] = field(default_factory=list)
    
    # 位信息 [铁律2: 位精确性]
    width: int = 1
    is_bit_select: bool = False
    bit_high: Optional[int] = None
    bit_low: Optional[int] = None
    
    # 元数据 [铁律10]
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "root": self.root,
            "signal": self.signal_name,
            "module": self.module,
            "drivers": [d.to_dict() for d in self.drivers],
            "loads": [l.to_dict() for l in self.loads],
            "bit_range": f"[{self.bit_high}:{self.bit_low}]" if self.is_bit_select else None,
            "width": self.width,
            "confidence": self.confidence,
            "caveats": self.caveats
        }

#==============================================================================
# PortConnection - 模块端口
#==============================================================================
@dataclass
class PortConnection:
    name: str
    direction: str              # input, output, inout
    width: int = 1
    is_bit_select: bool = False
    connected_signals: List[str] = field(default_factory=list)
    statements: List[Statement] = field(default_factory=list)

#==============================================================================
# ModuleConnections - 场景B: 模块连接
#==============================================================================
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
            "ports": [
                {
                    "name": p.name,
                    "direction": p.direction,
                    "connected": p.connected_signals
                } for p in self.ports
            ],
            "confidence": self.confidence,
            "caveats": self.caveats
        }

#==============================================================================
# CrossingRisk - 跨时钟域风险
#==============================================================================
class CrossingRisk(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RegisterInfo:
    name: str
    statement: Statement = None
    clock_domain: str = ""

#==============================================================================
# ClockDomainResult - 场景C: 时钟域
#==============================================================================
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
            "reset": self.reset_signal,
            "registers": [{"name": r.name, "domain": r.clock_domain} for r in self.registers],
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "caveats": self.caveats
        }

#==============================================================================
# 全局函数: 创建空模型
#==============================================================================
def new_signal_chain(root: str, signal_name: str, module: str) -> SignalChain:
    return SignalChain(root=root, signal_name=signal_name, module=module)

def new_module_connections(module: str) -> ModuleConnections:
    return ModuleConnections(module=module)

def new_clock_domain(clock: str) -> ClockDomainResult:
    return ClockDomainResult(clock_signal=clock)
