#==============================================================================
# data_models.py - 中间语义层
# pyslang 类型映射为语义类型
#==============================================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Literal
from enum import Enum

#==============================================================================
# 语义类型 (从 pyslang 映射)
#==============================================================================

class SemanticKind(Enum):
    """语义类型枚举"""
    # 驱动关系
    DRIVER = "driver"             # 连续赋值
    SEQ_DRIVER = "seq_driver"    # 时序逻辑 (<=)
    COMB_DRIVER = "comb_driver"  # 组合逻辑 (=)
    
    # 时钟域
    CLOCK = "clock"
    RESET = "reset"
    ENABLE = "enable"
    
    # 端口
    PORT_IN = "port_in"
    PORT_OUT = "port_out"
    PORT_INOUT = "port_inout"
    
    # 信号类型
    REG = "reg"
    WIRE = "wire"
    LOGIC = "logic"
    
    # 类型
    PARAM = "param"
    CONST = "const"

#==============================================================================
# pyslang SyntaxKind -> SemanticKind 映射表
#==============================================================================
# 在运行时初始化

def create_kind_mapping():
    """创建 pyslang kind 到语义类型的映射"""
    from pyslang import SyntaxKind
    
    mapping = {
        # 驱动关系
        SyntaxKind.ContinuousAssign: SemanticKind.DRIVER,
        
        # 时序逻辑
        SyntaxKind.NonblockingAssignmentExpression: SemanticKind.SEQ_DRIVER,
        SyntaxKind.AlwaysFFBlock: SemanticKind.SEQ_DRIVER,
        
        # 组合逻辑
        SyntaxKind.BlockingAssignmentExpression: SemanticKind.COMB_DRIVER,
        SyntaxKind.AlwaysCombBlock: SemanticKind.COMB_DRIVER,
        
        # 端口
        SyntaxKind.PortDeclaration: SemanticKind.PORT_IN,
        
        # 信号
        SyntaxKind.DataDeclaration: SemanticKind.REG,
        SyntaxKind.LogicType: SemanticKind.LOGIC,
        SyntaxKind.NetDeclaration: SemanticKind.WIRE,
        
        # 时钟/复位
        SyntaxKind.ClockingBlock: SemanticKind.CLOCK,
    }
    return mapping

#==============================================================================
# 中间语义表示 (不含 pyslang 对象)
#==============================================================================

@dataclass(frozen=True)  # 不可变
class SignalNode:
    """信号节点 (纯语义，无 pyslang)"""
    path: str          # "top.clk"
    width: int = 1
    kind: str = "wire"  # reg, wire, port
    
    def is_port(self) -> bool:
        return self.kind.startswith("port")
    
    def is_reg(self) -> bool:
        return self.kind == "reg"

@dataclass(frozen=True)
class ConnectionEdge:
    """连接边 (无 pyslang)"""
    source: str
    sink: str
    edge_type: str  # driver, data, clock, reset
    
    # 可选的调试信息 (仅字符串)
    source_file: str = ""
    source_line: int = 0

#==============================================================================
# 设计结果类型
#==============================================================================

@dataclass
class SignalChain:
    """信号追踪结果"""
    root: str
    signal_name: str
    module: str
    
    drivers: List[ConnectionEdge] = field(default_factory=list)
    loads: List[ConnectionEdge] = field(default_factory=list)
    data_path: List[str] = field(default_factory=list)
    
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)
    
    def to_json(self) -> dict:
        return {
            "root": self.root,
            "signal": self.signal_name,
            "module": self.module,
            "drivers": [{"source": d.source, "type": d.edge_type} for d in self.drivers],
            "loads": [{"sink": l.sink, "type": l.edge_type} for l in self.loads],
            "confidence": self.confidence,
            "caveats": self.caveats
        }

@dataclass
class ModuleConnections:
    """模块连接"""
    module: str
    inputs: List[ConnectionEdge] = field(default_factory=list)
    outputs: List[ConnectionEdge] = field(default_factory=list)
    internal: List[str] = field(default_factory=list)
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

@dataclass
class ClockDomainResult:
    """时钟域结果"""
    clock: str
    registers: List[str] = field(default_factory=list)
    async_crossings: List[ConnectionEdge] = field(default_factory=list)
    risk_level: str = "safe"
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

#==============================================================================
# 工厂函数
#==============================================================================
def new_signal_chain(root: str, signal: str, module: str) -> SignalChain:
    return SignalChain(root=root, signal_name=signal, module=module)

def new_module_connections(module: str) -> ModuleConnections:
    return ModuleConnections(module=module)

def new_clock_domain(clock: str) -> ClockDomainResult:
    return ClockDomainResult(clock=clock)
