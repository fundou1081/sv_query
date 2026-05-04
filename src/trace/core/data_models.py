#==============================================================================
# data_models.py - 语义分类层
# 每个类声明自己的 kind，更内聚
#==============================================================================

from pyslang import SyntaxKind
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Callable, Type

#==============================================================================
# I. 语义收集器基类
#==============================================================================

class SemanticCollector:
    """语义收集器基类 - 子类声明自己的 kind"""
    
    # 子类覆盖: 支持的 kind 值集合
    SUPPORTED_KINDS: Set[int] = set()
    
    @classmethod
    def accepts(cls, kind_value: int) -> bool:
        return kind_value in cls.SUPPORTED_KINDS

#==============================================================================
# II. 驱动分类器 (具体实现)
#==============================================================================

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

#==============================================================================
# III. 端口分类器
#==============================================================================

class PortCollector(SemanticCollector):
    """端口收集器"""
    SUPPORTED_KINDS = set()  # 通过 visitor 单独处理

#==============================================================================
# IV. 信号节点
#==============================================================================

@dataclass(frozen=True)
class SignalNode:
    path: str
    width: int = 1
    is_port: bool = False
    is_reg: bool = False
    
    @property
    def module(self) -> str:
        return self.path.split('.')[0]
    
    @property
    def name(self) -> str:
        return self.path.split('.')[-1]

#==============================================================================
# V. 连接边
#==============================================================================

@dataclass
class ConnectionEdge:
    source: str
    sink: str
    edge_type: str = "driver"
    source_file: str = ""
    source_line: int = 0
    condition: Optional[str] = None

#==============================================================================
# VI. 场景结果模型
#==============================================================================

@dataclass
class SignalChain:
    root: SignalNode
    drivers: List[ConnectionEdge] = field(default_factory=list)
    loads: List[ConnectionEdge] = field(default_factory=list)
    data_path: List[str] = field(default_factory=list)
    via_assignment: List[str] = field(default_factory=list)
    via_sequential: List[str] = field(default_factory=list)
    via_combinational: List[str] = field(default_factory=list)
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "root": self.root.path,
            "drivers": [{"src": d.source, "type": d.edge_type} for d in self.drivers],
            "loads": [{"dst": l.sink, "type": l.edge_type} for l in self.loads],
            "data_path": self.data_path,
            "via": {
                "assign": self.via_assignment,
                "sequential": self.via_sequential,
                "combinational": self.via_combinational,
            },
            "confidence": self.confidence,
            "caveats": self.caveats
        }

@dataclass
class ModuleConnections:
    module: str
    inputs: List[ConnectionEdge] = field(default_factory=list)
    outputs: List[ConnectionEdge] = field(default_factory=list)
    internal: List[str] = field(default_factory=list)
    instances: Dict[str, List[str]] = field(default_factory=dict)
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

@dataclass
class ClockDomainResult:
    clock_signal: str
    reset_signal: str = ""
    registers: List[str] = field(default_factory=list)
    combinational: List[str] = field(default_factory=list)
    async_crossings: List[ConnectionEdge] = field(default_factory=list)
    risk_level: str = "safe"
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

#==============================================================================
# VII. 工厂函数
#==============================================================================

def new_signal_node(path: str, width: int = 1, is_port: bool = False, is_reg: bool = False) -> SignalNode:
    return SignalNode(path=path, width=width, is_port=is_port, is_reg=is_reg)

def new_signal_chain(path: str, drivers: List = None, loads: List = None, 
                  data_path: List = None, via_assign: List = None,
                  via_seq: List = None, via_comb: List = None,
                  confidence: str = "high", caveats: List = None) -> SignalChain:
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
        caveats=caveats or []
    )

def new_module_connections(module: str) -> ModuleConnections:
    return ModuleConnections(module=module)

def new_clock_domain(clock: str) -> ClockDomainResult:
    return ClockDomainResult(clock_signal=clock)
