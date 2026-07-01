# ==============================================================================
# function_expander.py - 函数展开器
# ==============================================================================
# [Expression Node] 函数展开逻辑


from typing import Any

from trace.core.graph.models import SignalGraph, TraceEdge


class FunctionExpander:
    """函数展开器

    职责：
    1. 获取函数定义
    2. 解析函数体
    3. 替换 FUNCTION_CALL 节点为实际逻辑

    注意：当前版本仅支持概念验证，完整展开需要更多实现
    """

    def __init__(self, adapter, graph: SignalGraph):
        self._adapter = adapter
        self._graph = graph
        self._subroutine_cache: dict[str, Any] = {}

    def get_function_body(self, func_name: str) -> Any | None:
        """获取函数体

        Args:
            func_name: 函数名

        Returns:
            函数体节点，或 None
        """
        if func_name in self._subroutine_cache:
            return self._subroutine_cache[func_name]

        # 在 AST 中查找 Subroutine
        root = self._adapter.get_root()

        def find_subroutine(node: object) -> object:
            kind = node.kind
            if kind and kind.name == "Subroutine":
                name = getattr(node, "name", None)
                if name == func_name:
                    self._subroutine_cache[func_name] = node
                    return node
            return None

        # 遍历 AST
        result = self._find_node(root, find_subroutine)
        return result

    def _find_node(self, node, predicate):
        """递归查找节点"""
        if node is None:
            return None

        result = predicate(node)
        if result is not None:
            return result

        # 遍历子节点
        for attr_name in dir(node):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(node, attr_name)
                if isinstance(attr, (list, tuple)):
                    for item in attr:
                        if hasattr(item, "kind"):
                            result = self._find_node(item, predicate)
                            if result:
                                return result
                elif hasattr(attr, "kind"):
                    result = self._find_node(attr, predicate)
                    if result:
                        return result
            except Exception:
                pass

        return None

    def expand_function(self, func_call_node_id: str) -> list[TraceEdge]:
        """展开函数调用

        Args:
            func_call_node_id: FUNCTION_CALL 节点 ID，如 "func_calc_1"

        Returns:
            替换用的边列表

        注意：这是概念验证版本，返回空列表
        """
        # 获取函数调用节点
        if not self._graph.has_node(func_call_node_id):
            return []

        func_node = self._graph.get_node(func_call_node_id)

        # 获取函数名
        func_name = getattr(func_node, "function_name", None)
        if not func_name:
            return []

        # 获取函数体
        func_body = self.get_function_body(func_name)
        if func_body is None:
            return []

        # TODO: 完整实现需要：
        # 1. 解析 func_body 中的语句
        # 2. 替换参数 (formal arguments -> actual arguments)
        # 3. 追踪返回值 (calc = ...)
        # 4. 生成替换边

        # 当前版本返回空列表，表示尚未实现
        return []

    def can_expand(self, func_name: str) -> bool:
        """检查函数是否可以展开

        Args:
            func_name: 函数名

        Returns:
            True if 可展开
        """
        return self.get_function_body(func_name) is not None
