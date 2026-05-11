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

class EdgeKind(Enum):
    DRIVER = auto()      # 数据驱动 (q <= d)
    CLOCK = auto()       # 时钟触发 (clk -> q)
    RESET = auto()       # 异步复位 (rst_n -> q)
    CONNECTION = auto()  # 模块端口连接
    BIT_SELECT = auto()   # 位选择聚合

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

@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    condition: str = ""
    clock_domain: str = ""
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
