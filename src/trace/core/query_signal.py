#==============================================================================
# query_signal.py - 场景A: Signal Trace
#==============================================================================

from dataclasses import dataclass, field
from typing import List, Optional, Set
from collections import deque
import networkx as nx

from graph_models import (
    SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind
)

@dataclass
class SignalChain:
    """信号完整追踪链"""
    root: str
    drivers: List[TraceNode]
    data_path: List[TraceEdge]
    loads: List[TraceNode]
    clock_path: Optional[List[TraceNode]] = None
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

class SignalTracer:
    """场景A: 信号完整链路追踪"""
    
    def __init__(self, graph: SignalGraph):
        self.graph = graph
    
    def _make_id(self, signal: str, module: str = None) -> str:
        if module:
            return f"{module}.{signal}"
        return signal
    
    def _trace_drivers_recursive(self, node_id: str, depth: int = 10) -> List[TraceNode]:
        """递归追溯驱动"""
        drivers: List[TraceNode] = []
        visited: Set[str] = set()
        queue = deque([(node_id, 0)])
        
        while queue:
            current, d = queue.popleft()
            if current in visited or d > depth:
                continue
            visited.add(current)
            
            for driver in self.graph.find_drivers(current):
                if driver:
                    drivers.append(driver)
                    queue.append((driver.id, d + 1))
        
        return drivers
    
    def _trace_loads_recursive(self, node_id: str, depth: int = 10) -> List[TraceNode]:
        """递归追溯负载"""
        loads: List[TraceNode] = []
        visited: Set[str] = set()
        queue = deque([(node_id, 0)])
        
        while queue:
            current, d = queue.popleft()
            if current in visited or d > depth:
                continue
            visited.add(current)
            
            for load in self.graph.find_loads(current):
                if load:
                    loads.append(load)
                    queue.append((load.id, d + 1))
        
        return loads
    
    def _trace_clock_path(self, node_id: str) -> Optional[List[TraceNode]]:
        """追踪时钟路径"""
        node = self.graph.get_node(node_id)
        if not node:
            return None
        
        clock_nodes = []
        for pred in self.graph.predecessors(node_id):
            pred_node = self.graph.get_node(pred)
            if pred_node and pred_node.is_clock:
                clock_nodes.append(pred_node)
        
        return clock_nodes if clock_nodes else None
    
    def _assess_confidence(self, drivers: List[TraceNode], loads: List[TraceNode]) -> str:
        if not drivers:
            return "uncertain"
        if not loads:
            return "medium"
        return "high"
    
    def _collect_caveats(self, node_id: str) -> List[str]:
        caveats = []
        node = self.graph.get_node(node_id)
        if not node:
            return [f"Node {node_id} not found"]
        
        for pred in self.graph.predecessors(node_id):
            edge = self.graph.get_edge(pred, node_id)
            if edge and edge.confidence == "uncertain":
                caveats.append(f"Uncertain edge from {pred}")
        
        if node.is_clock and not self._has_reset(node_id):
            caveats.append("Clock without reset path")
        
        return caveats
    
    def _has_reset(self, node_id: str) -> bool:
        for pred in self.graph.predecessors(node_id):
            pred_node = self.graph.get_node(pred)
            if pred_node and pred_node.is_reset:
                return True
        return False
    
    def trace(self, signal: str, module: str = None) -> SignalChain:
        node_id = self._make_id(signal, module)
        
        drivers = self._trace_drivers_recursive(node_id)
        loads = self._trace_loads_recursive(node_id)
        clock_path = self._trace_clock_path(node_id)
        
        return SignalChain(
            root=node_id,
            drivers=drivers,
            data_path=[],  # TODO: build properly
            loads=loads,
            clock_path=clock_path,
            confidence=self._assess_confidence(drivers, loads),
            caveats=self._collect_caveats(node_id)
        )
    
    def trace_fanout(self, signal: str, module: str = None) -> List[str]:
        node_id = self._make_id(signal, module)
        if not self.graph.has_node(node_id):
            return []
        return list(nx.descendants(self.graph, node_id))
    
    def trace_fanin(self, signal: str, module: str = None) -> List[str]:
        node_id = self._make_id(signal, module)
        if not self.graph.has_node(node_id):
            return []
        return list(nx.ancestors(self.graph, node_id))
