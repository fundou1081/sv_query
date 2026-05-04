#==============================================================================
# data_models.py - 语义分类层
# 底层: pyslang kind (int)
# 语义: 分类器定义
# 任务: 专用结果模型
#==============================================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Literal, Set
from enum import Enum

#==============================================================================
# I. 底层: pyslang kind 值引用 (不导入，避免耦合)
#==============================================================================

class SyntaxKind:
    """pyslang SyntaxKind 值常量"""
    ContinuousAssign = 104
    AlwaysFFBlock = 10
    AlwaysCombBlock = 9
    NonblockingAssignmentExpression = 331
    BlockingAssignmentExpression = 30
    PortDeclaration = 354

#==============================================================================
# II. 语义分类器
#==============================================================================

@dataclass
class DriverClassifier:
    """驱动关系分类器"""
    kinds: Set[int]  # pyslang kind 值集合
    
    @staticmethod
    def all_drivers() -> 'DriverClassifier':
        """所有类型的驱动"""
        return DriverClassifier({
            SyntaxKind.ContinuousAssign,
            SyntaxKind.NonblockingAssignmentExpression,
            SyntaxKind.BlockingAssignmentExpression,
        })
    
    @staticmethod
    def sequential() -> 'DriverClassifier':
        """时序驱动 (<=)"""
        return DriverClassifier({SyntaxKind.NonblockingAssignmentExpression})
    
    @staticmethod
    def combinational() -> 'DriverClassifier':
        """组合驱动 (= 或 assign)"""
        return DriverClassifier({
            SyntaxKind.ContinuousAssign,
            SyntaxKind.BlockingAssignmentExpression,
        })
    
    def classify(self, kind) -> bool:
        """判断是否属于此类驱动"""
        return kind in self.kinds

@dataclass  
class PortClassifier:
    """端口分类器"""
    kinds: Set[int]
    
    @staticmethod
    def inputs() -> 'PortClassifier':
        return PortClassifier({SyntaxKind.PortDeclaration})  # 需根据实际调整
    
    @staticmethod
    def all() -> 'PortClassifier':
        return PortClassifier({SyntaxKind.PortDeclaration})
    
    def classify(self, kind) -> bool:
        return kind in self.kinds

#==============================================================================
# III. 基础信号节点
#==============================================================================

@dataclass(frozen=True)
class SignalNode:
    """信号节点 (不可变)"""
    path: str           # "top.clk"
    width: int = 1
    is_port: bool = False
    is_reg: bool = False
    
    @property
    def module(self) -> str:
        return self.path.split('.')[0] if '.' in self.path else self.path
    
    @property
    def name(self) -> str:
        return self.path.split('.')[-1]

#==============================================================================
# IV. 连接边
#==============================================================================

@dataclass
class ConnectionEdge:
    """连接边"""
    source: str     # 路径
    sink: str       # 路径
    edge_type: str = "driver"  # driver/data/clock/reset
    
    # 可选的调试信息
    source_file: str = ""
    source_line: int = 0
    condition: Optional[str] = None  # if 条件等

#==============================================================================
# V. 任务特定结果模型
#==============================================================================

@dataclass
class SignalChain:
    """场景A: 信号追踪结果"""
    root: SignalNode
    
    # 驱动关系
    drivers: List[ConnectionEdge] = field(default_factory=list)
    loads: List[ConnectionEdge] = field(default_factory=list)
    
    # 数据路径 (拓扑)
    data_path: List[str] = field(default_factory=list)
    
    # 统计
    via_assignment: List[str] = field(default_factory=list)  # assign 驱动
    via_sequential: List[str] = field(default_factory=list)  # always_ff 驱动
    via_combinational: List[str] = field(default_factory=list)  # always_comb 驱动
    
    # 元数据
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "root": self.root.path,
            "drivers": [{"src": d.source, "type": d.edge_type} for d in self.drivers],
            "loads": [{"dst": l.sink, "type": l.edge_type} for l in self.loads],
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
    """场景B: 模块连接结果"""
    module: str
    
    # 端口连接
    inputs: List[ConnectionEdge] = field(default_factory=list)
    outputs: List[ConnectionEdge] = field(default_factory=list)
    
    # 内部信号
    internal_signals: List[str] = field(default_factory=list)
    
    # 实例连接
    instances: Dict[str, List[str]] = field(default_factory=dict)
    
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

@dataclass
class ClockDomainResult:
    """场景C: 时钟域结果"""
    clock_signal: str
    reset_signal: str = ""
    
    # 寄存器
    registers: List[str] = field(default_factory=list)
    combinational: List[str] = field(default_factory=list)
    
    # CDC
    async_crossings: List[ConnectionEdge] = field(default_factory=list)
    risk_level: str = "safe"
    
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

#==============================================================================
# VI. 工厂函数
#==============================================================================

def new_signal_node(path: str, width: int = 1, is_port: bool = False, is_reg: bool = False) -> SignalNode:
    return SignalNode(path=path, width=width, is_port=is_port, is_reg=is_reg)

def new_signal_chain(root_path: str) -> SignalChain:
    return SignalChain(root=SignalNode(path=root_path))

def new_module_connections(module: str) -> ModuleConnections:
    return ModuleConnections(module=module)

def new_clock_domain(clock: str) -> ClockDomainResult:
    return ClockDomainResult(clock_signal=clock)
