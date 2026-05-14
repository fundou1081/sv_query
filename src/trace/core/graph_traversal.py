#==============================================================================
# graph_traversal.py - 共享图遍历基类
#==============================================================================
"""
[设计原则]
- Driver 和 Load 共享底层遍历逻辑
- 只实现差异部分（方向：前驱 vs 后继）

[共享逻辑]
1. 边类型过滤（DRIVER/CONNECTION/CLOCK/RESET）
2. 递归遍历 + seen_ids 去重
3. 图导航（get_node, get_edge）

[差异点]
- Driver: dst == signal_id（找前驱）
- Load: src == signal_id（找后继）
"""
from typing import List, Set, Optional
from dataclasses import dataclass, field

from trace.core.graph.models import SignalGraph, EdgeKind, NodeKind


@dataclass
class TraceResult:
    """统一的追溯结果"""
    root: str                           # 信号 ID
    nodes: List[any]                    # 相关节点
    confidence: str                     # 置信度
    path: List[str] = field(default_factory=list)  # 追溯路径


class GraphTraversal:
    """
    统一的图遍历基类
    
    [核心逻辑]
    1. 按边类型过滤（只看 DRIVER 边）
    2. 递归收集所有满足条件的节点
    3. 使用 seen_ids 避免循环
    """
    
    def __init__(self, graph: SignalGraph):
        self.graph = graph
    
    def _find_by_edge_kind(self, signal_id: str, 
                          src_or_dst: str,
                          edge_kind: EdgeKind) -> List[any]:
        """
        按边类型查找相关节点
        
        Args:
            signal_id: 信号 ID
            src_or_dst: 'src' 查找 src==signal_id（后继）
                       'dst' 查找 dst==signal_id（前驱）
            edge_kind: 边类型（DRIVER/CLOCK/CONNECTION/RESET）
        
        Returns:
            满足条件的节点列表
        """
        results = []
        for src, dst in list(self.graph.edges()):
            # 根据方向选择比较的端点
            target = dst if src_or_dst == 'dst' else src
            if target != signal_id:
                continue
            
            edge = self.graph.get_edge(src, dst)
            if edge and edge.kind == edge_kind:
                node = self.graph.get_node(src if src_or_dst == 'dst' else dst)
                if node:
                    results.append(node)
        return results
    
    def _collect_all(self, signal_id: str,
                    direction: str,          # 'backward' | 'forward'
                    edge_kind: EdgeKind,
                    seen_ids: Optional[Set[str]] = None) -> List[any]:
        """
        递归收集所有满足条件的节点
        
        [共享逻辑]
        - 按边类型过滤
        - 递归追溯
        - seen_ids 避免循环
        
        Args:
            signal_id: 信号 ID
            direction: 'backward' 前驱追溯 | 'forward' 后继追溯
            edge_kind: 边类型
            seen_ids: 已访问节点集合（用于去重）
        
        Returns:
            所有满足条件的节点列表
        """
        if seen_ids is None:
            seen_ids = set()
        
        # 避免循环
        if signal_id in seen_ids:
            return []
        seen_ids.add(signal_id)
        
        results = []
        
        for src, dst in list(self.graph.edges()):
            # 根据方向选择比较的端点
            target = dst if direction == 'backward' else src
            if target != signal_id:
                continue
            
            edge = self.graph.get_edge(src, dst)
            # 按边类型过滤
            if not edge or edge.kind != edge_kind:
                continue
            
            # 获取另一端的节点
            other_id = src if direction == 'backward' else dst
            node = self.graph.get_node(other_id)
            
            if node and node.id not in seen_ids:
                results.append(node)
                # 递归追溯
                if other_id in self.graph.nodes():
                    sub_results = self._collect_all(
                        other_id, direction, edge_kind, seen_ids
                    )
                    results.extend(sub_results)
        
        return results
    
    def _collect_all_by_edge_kind(self, signal_id: str,
                                  direction: str,
                                  edge_kind: EdgeKind,
                                  seen_ids: Optional[Set[str]] = None) -> List[any]:
        """
        按边类型递归收集（带边类型检查的递归）
        
        [与 _collect_all 的区别]
        - _collect_all: 只接受指定 edge_kind，继续递归时也只走该类型边
        - _collect_all_by_edge_kind: 接受 CONNECTION 等边，但只计入 DRIVER 边
        """
        if seen_ids is None:
            seen_ids = set()
        
        if signal_id in seen_ids:
            return []
        seen_ids.add(signal_id)
        
        results = []
        
        for src, dst in list(self.graph.edges()):
            target = dst if direction == 'backward' else src
            if target != signal_id:
                continue
            
            edge = self.graph.get_edge(src, dst)
            if not edge:
                continue
            
            # DRIVER 边：计入结果
            if edge.kind == edge_kind:
                other_id = src if direction == 'backward' else dst
                node = self.graph.get_node(other_id)
                if node and node.id not in seen_ids:
                    results.append(node)
                    # 递归追溯
                    if other_id in self.graph.nodes():
                        sub = self._collect_all_by_edge_kind(
                            other_id, direction, edge_kind, seen_ids
                        )
                        results.extend(sub)
            # CONNECTION 边：只递归追溯，不计入
            elif edge.kind == EdgeKind.CONNECTION:
                other_id = src if direction == 'backward' else dst
                if other_id in self.graph.nodes():
                    sub = self._collect_all_by_edge_kind(
                        other_id, direction, edge_kind, seen_ids
                    )
                    results.extend(sub)
        
        return results
