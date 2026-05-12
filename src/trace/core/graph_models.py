#==============================================================================
# graph_models.py - 信号关系图模型
#==============================================================================

import networkx as nx
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Set, Dict, Optional, Tuple

class NodeKind(Enum):
    SIGNAL = auto()
    WIRE = auto()
    REG = auto()
    PORT_IN = auto()
    PORT_OUT = auto()
    PORT_INOUT = auto()
    PARAM = auto()
    CONST = auto()
    INSTANTIATED_MODULE = auto()  # 实例节点 (top.inst)
    GENERATE_BLOCK = auto()        # generate 块节点 (top.GEN)

    # [Phase1a] Class & Constraint 节点类型
    CLASS = auto()                  # class 定义节点 (packet)
    CLASS_INSTANCE = auto()          # class 实例 (top.p = new())
    CLASS_PROPERTY = auto()         # class 成员变量 (packet.addr, rand 变量)
    CONSTRAINT_BLOCK = auto()       # constraint c { ... } 命名块
    CONSTRAINT_EXPR = auto()        # 单条表达式约束
    CONSTRAINT_IF = auto()          # if 分支
    CONSTRAINT_ELSE = auto()         # else 分支
    CONSTRAINT_IMPLIES = auto()     # implication 左部 (en -> ...)
    CONSTRAINT_UNIQUE = auto()      # unique { ... }
    CONSTRAINT_SOLVE = auto()       # solve A before B
    CONSTRAINT_FOREACH = auto()     # foreach 循环
    CONSTRAINT_RANGE = auto()       # inside {0,1,2} 的集合

class EdgeKind(Enum):
    DRIVER = auto()      # 数据驱动 (q <= d)
    CLOCK = auto()       # 时钟触发 (clk -> q)
    RESET = auto()       # 异步复位 (rst_n -> q)
    CONNECTION = auto()  # 模块端口连接
    BIT_SELECT = auto()   # 位选择聚合

    # [Phase1a] Class & Constraint 边类型
    CONSTRAINS = auto()      # CLASS_PROPERTY ← 约束管控
    HAS_CONDITION = auto()   # CONSTRAINT_IF → CLASS_PROPERTY (条件变量)
    HAS_CONSEQUENT = auto()  # CONSTRAINT_IF → CONSTRAINT_EXPR (if 结果)
    HAS_ALTERNATE = auto()   # CONSTRAINT_ELSE → CONSTRAINT_EXPR (else 结果)
    HAS_LHS = auto()         # CONSTRAINT_EXPR → operand (左操作数)
    HAS_RHS = auto()          # CONSTRAINT_EXPR → operand (右操作数)
    HAS_MEMBER = auto()      # CONSTRAINT_UNIQUE → CLASS_PROPERTY (集合成员)
    HAS_LOOP_VAR = auto()    # CONSTRAINT_FOREACH → CLASS_PROPERTY (循环变量)
    HAS_BEFORE = auto()      # CONSTRAINT_SOLVE → CLASS_PROPERTY (before)
    HAS_AFTER = auto()       # CONSTRAINT_SOLVE → CLASS_PROPERTY (after)
    CONTAINS_MEMBER = auto()  # CLASS → CLASS_PROPERTY (组合/成员变量)
    IS_INSTANCE_OF = auto()   # CLASS_PROPERTY → CLASS (成员变量的类型引用)
    SUPER_CALL = auto()       # CONSTRAINT_EXPR → 被调用的父类约束 (增量扩展 super.c1)

# [铁律16] 注意：ENABLE/DATA 不作为独立边类型
# - ENABLE: 用 TraceEdge.condition 属性替代，语义更清晰
# - DATA: 与 DRIVER 重复，保留 DRIVER 即可

@dataclass
class TraceNode:
    id: str
    name: str
    module: str
    kind: NodeKind
    width: Tuple[int, int]
    bit_range: Optional[str] = None
    file: str = ""
    line: int = 0
    is_clock: bool = False
    is_reset: bool = False
    is_enable: bool = False
    is_port: bool = False
    parent: Optional[str] = None  # 方案C: 父节点ID (位选择→完整信号)
    modport_dir: Optional[str] = None  # P0-3: modport direction (input/output/inout)

@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    condition: str = ""
    clock_domain: str = ""
    modport_dir: Optional[str] = None  # P0-3: modport direction (input/output/inout)
    confidence: str = "high"

class SignalGraph(nx.DiGraph):
    def __init__(self):
        super().__init__()
        self._node_data: Dict[str, TraceNode] = {}
        self._edge_data: Dict[Tuple[str, str], TraceEdge] = {}
    
    def add_trace_node(self, node: TraceNode):
        self._node_data[node.id] = node
        super().add_node(node.id)
    
    def add_trace_edge(self, edge: TraceEdge):
        # [铁律4] 不允许创建孤儿节点：如果目标节点不存在则创建 placeholder
        for node_id in [edge.src, edge.dst]:
            if node_id not in self._node_data:
                parts = node_id.split('.', 1)
                module = parts[0] if len(parts) > 0 else ''
                name = parts[1] if len(parts) > 1 else node_id
                
                placeholder = TraceNode(
                    id=node_id,
                    name=name,
                    module=module,
                    kind=NodeKind.SIGNAL,
                    width=(0, 0)
                )
                self._node_data[node_id] = placeholder
                super().add_node(node_id)
        
        key = (edge.src, edge.dst)
        
        existing = self._edge_data.get(key)
        
        # Skip duplicate if same type AND existing has same or better semantic context
        if existing and existing.kind == edge.kind:
            # [NEW] If new edge has semantic context but existing doesn't, prefer new edge
            if (edge.clock_domain or edge.condition) and not (existing.clock_domain or existing.condition):
                self._edge_data[key] = edge
                super().add_edge(edge.src, edge.dst)
            return
        
        # Add edge (allow self-loops for register self-update)
        self._edge_data[key] = edge
        super().add_edge(edge.src, edge.dst)
    
    def set_node_modport_dir(self, node_id: str, modport_dir: str):
        """[P0-3] 设置已有节点的 modport_dir 属性"""
        if node_id in self._node_data:
            self._node_data[node_id].modport_dir = modport_dir
    
    def get_node(self, node_id: str) -> Optional[TraceNode]:
        return self._node_data.get(node_id)
    
    def get_edge(self, src: str, dst: str) -> Optional[TraceEdge]:
        return self._edge_data.get((src, dst))
    
    def find_drivers(self, signal_id: str) -> List[TraceNode]:
        return [self.get_node(n) for n in self.predecessors(signal_id)]
    
    def find_loads(self, signal_id: str) -> List[TraceNode]:
        return [self.get_node(n) for n in self.successors(signal_id)]
    
    def find_path(self, src_id: str, dst_id: str) -> List[str]:
        try:
            return nx.shortest_path(self, src_id, dst_id)
        except nx.NetworkXNoPath:
            return []
    
    def find_all_paths(self, src_id: str, dst_id: str, max_depth: int = 10) -> List[List[str]]:
        try:
            return list(nx.all_simple_paths(self, src_id, dst_id, cutoff=max_depth))
        except:
            return []
    
    def detect_cycles(self) -> List[List[str]]:
        try:
            return list(nx.simple_cycles(self))
        except:
            return []
    
    def stats(self) -> Dict:
        return {
            "nodes": self.number_of_nodes(),
            "edges": self.number_of_edges(),
        }
