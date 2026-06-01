# ==============================================================================
# query_load.py - Load 追溯
# ==============================================================================
"""
[功能]
- 追溯信号的后继（被哪些信号使用）
- 与 query_signal.py 对称

[与 Driver 对称]
- Driver: 谁驱动我（get_drivers）
- Load: 我驱动谁（get_loads）

[设计]
- 继承 GraphTraversal 基类
- 共享递归遍历 + 边过滤逻辑
- 只实现差异：方向（src vs dst）
"""

from dataclasses import dataclass, field

from trace.core.graph.models import EdgeKind, SignalGraph
from trace.core.graph_traversal import GraphTraversal


@dataclass
class LoadChain:
    """Load 追溯结果

    与 SignalChain 对称的结构
    """

    root: str  # 信号 ID
    loads: list[any]  # 后继节点（被这个信号驱动的）
    confidence: str = "high"  # 置信度
    path: list[str] = field(default_factory=list)


class LoadTracer(GraphTraversal):
    """
    Load 追溯器

    [与 DriverTracer 对称]
    - DriverTracer: 找前驱（谁驱动我）
    - LoadTracer: 找后继（我驱动谁）
    """

    def __init__(self, graph: SignalGraph):
        super().__init__(graph)

    def _find_loads(self, signal_id: str) -> list[any]:
        """
        查找直接后继（直接被 signal_id 驱动的节点）

        [逻辑]
        - 找 src == signal_id 的边（signal 是驱动源）
        - 只接受 DRIVER 边
        """
        return self._find_by_edge_kind(signal_id, src_or_dst="src", edge_kind=EdgeKind.DRIVER)

    def _collect_all_loads(self, signal_id: str, seen_ids: set | None = None) -> list[any]:
        """
        递归收集所有后继

        [逻辑]
        - DRIVER 边：计入结果，继续递归
        - CONNECTION 边：不计入，但继续递归追溯
        """
        return self._collect_all_by_edge_kind(
            signal_id, direction="forward", edge_kind=EdgeKind.DRIVER, seen_ids=seen_ids
        )

    def trace(self, signal_name: str, module_name: str) -> LoadChain:
        """
        追溯 signal_name 的所有后继

        Args:
            signal_name: 信号名（不含模块前缀）
            module_name: 模块名

        Returns:
            LoadChain: 包含所有后继
        """
        signal_id = f"{module_name}.{signal_name}"

        if signal_id not in self.graph.nodes():
            return LoadChain(root=signal_id, loads=[], confidence="unknown")

        # 递归收集所有后继
        loads = self._collect_all_loads(signal_id)

        # 去重
        seen = set()
        unique_loads = []
        for node in loads:
            if node.id not in seen:
                seen.add(node.id)
                unique_loads.append(node)

        confidence = self._evaluate_confidence(unique_loads)

        return LoadChain(root=signal_id, loads=unique_loads, confidence=confidence)

    def get_loads(self, signal_id: str) -> list[str]:
        """
        获取 signal_id 的所有后继节点 ID

        [简化 API]
        - 返回节点 ID 列表
        - 与 get_drivers 对称
        """
        loads = self._collect_all_loads(signal_id)
        return list(set(node.id for node in loads))

    def _evaluate_confidence(self, loads: list[any]) -> str:
        """
        评估置信度

        [规则]
        - 0 个后继: "no_load"（无负载）
        - 1 个后继: "high"
        - 多个后继: "medium"
        """
        if not loads:
            return "no_load"
        if len(loads) == 1:
            return "high"
        return "medium"
