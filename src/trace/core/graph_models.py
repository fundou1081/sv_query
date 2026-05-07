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

class EdgeKind(Enum):
    DRIVER = auto()
    DATA = auto()
    CLOCK = auto()
    RESET = auto()
    ENABLE = auto()
    CONNECTION = auto()
    BIT_SELECT = auto()

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
    parent: Optional[str] = None  # 方案C: 父节点ID (位选择→完整信号)

@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    condition: str = ""
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
        # Skip self-loops
        if edge.src == edge.dst:
            return
        
        key = (edge.src, edge.dst)
        
        existing = self._edge_data.get(key)
        
        # Skip duplicate if same type
        if existing and existing.kind == edge.kind:
            return
        
        # Add edge
        self._edge_data[key] = edge
        super().add_edge(edge.src, edge.dst)
        
        if edge.src == edge.dst:
            return
        
        # 不检查直接添加
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
