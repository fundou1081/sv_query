#==============================================================================
# data_models.py - 中间语义层
# 底层: 直接使用 pyslang.SyntaxKind
#==============================================================================

from pyslang import SyntaxKind
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Callable

#==============================================================================
# I. 驱动分类器 (使用 pyslang SyntaxKind)
#==============================================================================

@dataclass
class DriverClassifier:
    """驱动分类器"""
    predicate: Callable[[int], bool]  # 输入 kind value (int)
    
    @staticmethod
    def all_drivers() -> 'DriverClassifier':
        """所有驱动: assign, <=, ="""
        return DriverClassifier(lambda k: k in {
            SyntaxKind.ContinuousAssign.value,
            SyntaxKind.NonblockingAssignmentExpression.value,
            SyntaxKind.AssignmentExpression.value,
        })
    
    @staticmethod
    def sequential() -> 'DriverClassifier':
        """时序驱动: always_ff, nonblocking"""
        return DriverClassifier(lambda k: k == SyntaxKind.NonblockingAssignmentExpression.value)
    
    @staticmethod
    def combinational() -> 'DriverClassifier':
        """组合驱动: assign, always_comb, ="""
        return DriverClassifier(lambda k: k in {
            SyntaxKind.ContinuousAssign.value,
            SyntaxKind.AssignmentExpression.value,
        })
    
    def classify(self, kind_value: int) -> bool:
        return self.predicate(kind_value)

#==============================================================================
# 信号节点
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
# 连接边
#==============================================================================

@dataclass
class ConnectionEdge:
    source: str
    sink: str
    edge_type: str = "driver"  # driver/seq_driver/comb_driver/load
    source_file: str = ""
    source_line: int = 0
    condition: Optional[str] = None

#==============================================================================
# 场景A: 信号追踪结果
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

#==============================================================================
# 场景B/C
#==============================================================================

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
# 工厂函数
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
