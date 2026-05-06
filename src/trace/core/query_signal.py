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
        """[P2增强] 支持 concat 多驱动 + hierarchy 追踪"""
        drivers = []
        
        # [P2] 首先通过 instance 连接追踪
        # 查找所有指向这个 signal 的边
        for src, dst in list(self.graph.edges()):
            if dst == signal_id:
                # 这条边指向目标信号
                node = self.graph.get_node(src)
                if node:
                    drivers.append(node)
                # 继续递归追踪这个 src
                if src in self.graph.nodes():
                    for pred in self.graph.predecessors(src):
                        n = self.graph.get_node(pred)
                        if n and n not in drivers:
                            drivers.append(n)
        
        # 直接前置驱动
        for pred in self.graph.predecessors(signal_id):
            edge = self.graph.get_edge(pred, signal_id)
            if edge and edge.kind == EdgeKind.DRIVER:
                node = self.graph.get_node(pred)
                if node:
                    # 检查是否是复合表达式
                    driver_name = node.name
                    
                    # 如果是 concat 形式 {a,b}，尝试提取多个
                    if driver_name and '{' in driver_name and '}' in driver_name:
                        # 提取内部信号
                        inner = driver_name.strip('{}').strip()
                        parts = [p.strip() for p in inner.split(',')]
                        
                        # 为每个部分查找节点
                        for part in parts:
                            # 尝试在图中查找这个信号
                            for n in self.graph.nodes():
                                if n.endswith(part) or n == part:
                                    nodedata = self.graph.get_node(n)
                                    if nodedata:
                                        drivers.append(nodedata)
                                        break
                    else:
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
