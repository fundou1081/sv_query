#==============================================================================
# query_signal.py - Simplified Signal Query
#==============================================================================

from typing import List
from dataclasses import dataclass
from ..graph.models import SignalGraph, TraceNode, EdgeKind

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
    
    def _collect_all_drivers(self, signal_id: str, max_depth: int | None = None) -> List[TraceNode]:
        """[P2] 递归收集所有驱动，包括实例端口追溯
        
        Args:
            signal_id: signal ID
            max_depth: None=无限递归, N=最多递归 N 层
        """
        drivers = []
        seen_ids = set()
        self._trace_drivers_recursive(signal_id, drivers, seen_ids, current_depth=0, max_depth=max_depth)
        return drivers
    
    def _trace_drivers_recursive(self, signal_id: str, drivers: List[TraceNode], seen_ids: set,
                                  current_depth: int = 0, max_depth: int | None = None):
        """递归追溯驱动
        
        Args:
            signal_id: 当前信号 ID
            drivers: 结果列表（inout）
            seen_ids: 已访问节点集合（inout）
            current_depth: 当前递归深度
            max_depth: None=无限递归, N=最多递归 N 层
        """
        # depth 限制检查
        if max_depth is not None and current_depth >= max_depth:
            return

        
        if signal_id not in self.graph.nodes():
            return
        
        # [方案B修正] 如果当前节点没有 incoming DRIVER 边, 检查 BIT_SELECT 子节点
        # 例如查询 'm' (modport实例) 时, 如果 'm' 没有直接驱动, 查找 'm.*' 子节点
        has_driver_edge = any(
            edge.kind == EdgeKind.DRIVER and dst == signal_id
            for src, dst, edge in [(e[0], e[1], self.graph.get_edge(e[0], e[1])) for e in self.graph.edges()]
        )
        if not has_driver_edge:
            # 查找 BIT_SELECT 子节点 (child → this_node)
            for src, dst in list(self.graph.edges()):
                if dst == signal_id:
                    edge = self.graph.get_edge(src, dst)
                    if edge and edge.kind == EdgeKind.BIT_SELECT:
                        # 子节点有驱动
                        if src not in seen_ids:
                            self._trace_drivers_recursive(src, drivers, seen_ids, current_depth, max_depth)
        
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
                        self._trace_drivers_recursive(src, drivers, seen_ids, current_depth + 1, max_depth)
                    continue
                
                node = self.graph.get_node(src)
                if node and node.id not in seen_ids:
                    drivers.append(node)
                
                # 继续递归追溯这个 src 的驱动（DRIVER 边）
                # seen_ids 检查在函数开头进行，防止环路
                if src in self.graph.nodes() and src not in seen_ids:
                    self._trace_drivers_recursive(src, drivers, seen_ids, current_depth + 1, max_depth)
    
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

    def _collect_all_loads(self, signal_id: str, max_depth: int | None = None) -> List[TraceNode]:
        """递归收集所有后继（被这个信号驱动的所有节点）
        
        Args:
            signal_id: 信号 ID
            max_depth: None=无限递归, N=最多递归 N 层
        """
        loads = []
        seen_ids = set()
        self._trace_loads_recursive(signal_id, loads, seen_ids, current_depth=0, max_depth=max_depth)
        return loads

    def _trace_loads_recursive(self, signal_id: str, loads: List[TraceNode], seen_ids: set,
                               current_depth: int = 0, max_depth: int | None = None):
        """递归追溯负载（被 signal_id 驱动的节点）
        
        Args:
            signal_id: 当前信号 ID
            loads: 结果列表（inout）
            seen_ids: 已访问节点集合（inout）
            current_depth: 当前递归深度
            max_depth: None=无限递归, N=最多递归 N 层
        """
        if max_depth is not None and current_depth >= max_depth:
            return
        if signal_id in seen_ids:
            return
        if signal_id not in self.graph.nodes():
            return
        seen_ids.add(signal_id)

        for src, dst in list(self.graph.edges()):
            if src == signal_id:
                edge = self.graph.get_edge(src, dst)
                if edge and edge.kind not in (EdgeKind.DRIVER, EdgeKind.CONNECTION):
                    continue
                node = self.graph.get_node(dst)
                if node and node.id not in seen_ids:
                    loads.append(node)
                if dst in self.graph.nodes():
                    self._trace_loads_recursive(dst, loads, seen_ids, current_depth + 1, max_depth)

    def trace_fanout(self, signal: str, module: str = None, depth: int | None = None) -> List[TraceNode]:
        """Trace signal fanout (loads driven by this signal)
        
        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct loads only, N=recursive N levels, None=recursive all
        """
        signal_id = self._make_id(signal, module)
        if signal_id not in self.graph.nodes():
            return []
        if depth == 1:
            return self._find_loads(signal_id)
        return self._collect_all_loads(signal_id, max_depth=depth)

    def trace_fanin(self, signal: str, module: str = None, depth: int | None = None) -> List[TraceNode]:
        """Trace signal fanin (drivers of this signal)
        
        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all
        """
        signal_id = self._make_id(signal, module)
        if depth == 1:
            return self._find_drivers(signal_id)
        return self._collect_all_drivers(signal_id, max_depth=depth)
