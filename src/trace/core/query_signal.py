#==============================================================================
# query_signal.py - Simplified Signal Query
#==============================================================================

from typing import List
from dataclasses import dataclass
from .graph_models import SignalGraph, TraceNode, EdgeKind

@dataclass
class SignalChain:
    root: str
    drivers: List[TraceNode]
    loads: List[TraceNode]
    confidence: str

class SignalTracer:
    def __init__(self, graph: SignalGraph):
        self.graph = graph
    
    def trace(self, signal: str, module: str = None) -> SignalChain:
        """Trace signal drivers and loads"""
        signal_id = self._make_id(signal, module)
        drivers = self._find_drivers(signal_id)
        loads = self._find_loads(signal_id)
        confidence = "high" if drivers else "uncertain"
        
        return SignalChain(
            root=signal_id,
            drivers=drivers,
            loads=loads,
            confidence=confidence
        )
    
    def _make_id(self, signal: str, module: str = None) -> str:
        if module:
            return f"{module}.{signal}"
        return signal
    
    def _find_drivers(self, signal_id: str) -> List[TraceNode]:
        drivers = []
        for pred in self.graph.predecessors(signal_id):
            edge = self.graph.get_edge(pred, signal_id)
            if edge and edge.kind == EdgeKind.DRIVER:
                node = self.graph.get_node(pred)
                if node:
                    drivers.append(node)
        return drivers
    
    def _find_loads(self, signal_id: str) -> List[TraceNode]:
        loads = []
        for succ in self.graph.successors(signal_id):
            edge = self.graph.get_edge(signal_id, succ)
            if edge and edge.kind in [EdgeKind.DRIVER, EdgeKind.DATA]:
                node = self.graph.get_node(succ)
                if node:
                    loads.append(node)
        return loads
