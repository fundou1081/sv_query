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
        
        # [铁律3] 不可信则不输出 - 节点不存在时返回 uncertain
        if signal_id not in self.graph.nodes():
            return SignalChain(
                root=signal_id,
                drivers=[],
                loads=[],
                confidence="uncertain"
            )
        
        drivers = self._collect_all_drivers(signal_id)
        loads = self._find_loads(signal_id)
        
        # [铁律3] 无驱动时返回 uncertain
        confidence = "high" if drivers else "uncertain"
        
        return SignalChain(
            root=signal_id,
            drivers=drivers,
            loads=loads,
            confidence=confidence
        )
    
    def _make_id(self, signal: str, module: str = None) -> str:
        # [方案B修正] 如果 signal 包含 '.'，检查是否以 module. 开头
        if module and '.' in signal:
            # 如果已经以 module. 开头，认为是完整路径
            if signal.startswith(f"{module}."):
                return signal
            # 否则添加 module 前缀 (相对路径)
            return f"{module}.{signal}"
        if module:
            return f"{module}.{signal}"
        return signal
    
    def _collect_all_drivers(self, signal_id: str) -> List[TraceNode]:
        """[P2] 递归收集所有驱动，包括实例端口追溯"""
        drivers = []
        seen_ids = set()
        
        # 递归追溯
        self._trace_drivers_recursive(signal_id, drivers, seen_ids)
        
        return drivers
    
    def _trace_drivers_recursive(self, signal_id: str, drivers: List[TraceNode], seen_ids: set):
        """递归追溯驱动"""
        # [FIX] 环路检测：如果 signal_id 已在 seen_ids 中，说明有环路，停止追溯
        if signal_id in seen_ids:
            return
        
        if signal_id not in self.graph.nodes():
            return
        
        # 标记当前节点已访问
        seen_ids.add(signal_id)
        
        # 遍历所有指向这个 signal 的边
        for src, dst in list(self.graph.edges()):
            if dst == signal_id:
                # [NEW] 自环 (state = state) 应该被记录为驱动
                if src == dst:
                    node = self.graph.get_node(src)
                    if node:
                        drivers.append(node)
                    continue
                
                edge = self.graph.get_edge(src, dst)
                # [FIX] 只接受 DRIVER 边作为驱动
                if edge and edge.kind != EdgeKind.DRIVER:
                    # CONNECTION 边：检查 src 是否是实例端口
                    if edge.kind == EdgeKind.CONNECTION:
                        node = self.graph.get_node(src)
                        if node:
                            parts = src.split('.')
                            # 实例输出端口 (PORT_OUT): 这是实例驱动外部信号的出口
                            if len(parts) >= 3 and node.kind.name == 'PORT_OUT':
                                # 添加实例端口作为驱动
                                if node.id not in seen_ids:
                                    drivers.append(node)
                                    seen_ids.add(node.id)
                                # 继续追踪到真正的外部驱动源
                                inst_name = parts[-2]  # e.g., 'inst'
                                inst_path = '.'.join(parts[:-1])  # e.g., 'top.inst'
                                # 查找实例的输入端口
                                input_port_id = f"{inst_path}.d"  # 假设输入端口是 'd'
                                # 找谁驱动这个输入端口
                                for pred_src, pred_dst in self.graph.edges():
                                    if pred_dst == input_port_id and pred_src.startswith(inst_path.rsplit('.', 1)[0]):
                                        # 外部信号驱动实例输入，这个外部信号是真正的驱动源
                                        ext_node = self.graph.get_node(pred_src)
                                        if ext_node and ext_node.id not in seen_ids:
                                            drivers.append(ext_node)
                                            seen_ids.add(ext_node.id)
                                continue
                    # 其他边类型继续递归追溯
                    if src in self.graph.nodes() and src not in seen_ids:
                        self._trace_drivers_recursive(src, drivers, seen_ids)
                    continue
                
                node = self.graph.get_node(src)
                if node and node.id not in seen_ids:
                    drivers.append(node)
                
                # 继续递归追溯这个 src 的驱动
                # seen_ids 检查在递归函数开头进行
                if src in self.graph.nodes():
                    self._trace_drivers_recursive(src, drivers, seen_ids)
    
    def _find_drivers(self, signal_id: str) -> List[TraceNode]:
        """[兼容] 直接驱动"""
        if signal_id not in self.graph.nodes():
            return []
        
        drivers = []
        for src, dst in list(self.graph.edges()):
            if dst == signal_id:
                node = self.graph.get_node(src)
                if node:
                    drivers.append(node)
        return drivers
    
    def _find_loads(self, signal_id: str) -> List[TraceNode]:
        if signal_id not in self.graph.nodes():
            return []

        loads = []
        seen_ids = set()

        for succ in self.graph.successors(signal_id):
            node = self.graph.get_node(succ)
            if node and node.id not in seen_ids:
                loads.append(node)
                seen_ids.add(node.id)

        return loads

    def trace_fanout(self, signal: str, module: str = None) -> List[TraceNode]:
        """Trace signal fanout (all loads driven by this signal)"""
        signal_id = self._make_id(signal, module)
        if signal_id not in self.graph.nodes():
            return []
        return self._find_loads(signal_id)

    def trace_fanin(self, signal: str, module: str = None) -> List[TraceNode]:
        """Trace signal fanin (all drivers of this signal)"""
        signal_id = self._make_id(signal, module)
        return self._collect_all_drivers(signal_id)
