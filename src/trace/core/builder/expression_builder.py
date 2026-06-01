# ==============================================================================
# expression_builder.py - 表达式节点构建器
# ==============================================================================
# [Expression Node] 表达式 → TraceNode 转换器

from trace.core.graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode


class ExpressionBuilder:
    """表达式节点构建器

    将表达式拆分为 TraceNode 表达：
    - a + b → a → expr_1 → data (expr_1 是表达式节点)
    - calc(a, b) → a/b → func_calc_1 → data (func_calc_1 是函数调用节点)
    - sel ? a : b → sel/a/b → cond_ternary_1 → data
    """

    def __init__(self, graph: SignalGraph):
        self._graph = graph
        self._node_counter: dict[str, int] = {}  # 按前缀计数

    def _next_id(self, prefix: str) -> str:
        """生成唯一节点 ID"""
        if prefix not in self._node_counter:
            self._node_counter[prefix] = 0
        self._node_counter[prefix] += 1
        return f"{prefix}_{self._node_counter[prefix]}"

    def _create_node(self, node_id: str, name: str, kind: NodeKind, **kwargs) -> TraceNode:
        """创建节点并添加到图中"""
        # 提取已知参数，避免重复
        module = kwargs.pop("module", "")
        width = kwargs.pop("width", (0, 0))

        node = TraceNode(
            id=node_id,
            name=name,
            module=module,
            kind=kind,
            width=width,
            **kwargs,  # 剩余参数传递给 TraceNode
        )
        self._graph.add_trace_node(node)
        return node

    def build_expression(self, operands: list[str], expression: str, result: str, module: str = "") -> str | None:
        """构建表达式节点

        Args:
            operands: 操作数列表，如 ["a", "b"]
            expression: 表达式字符串，如 "a + b"
            result: 结果信号，如 "data"
            module: 模块名

        Returns:
            表达式节点 ID，如 "expr_1"
        """
        if not operands:
            return None

        # 创建表达式节点
        expr_id = self._next_id("expr")
        self._create_node(
            node_id=expr_id,
            name=expression,
            kind=NodeKind.EXPRESSION,
            module=module,
            expression=expression,
            operands=operands,
            signals=list(operands),  # 简单情况下 operands 就是 signals
        )

        # 创建边: operands → expr
        for op in operands:
            self._graph.add_trace_edge(TraceEdge(src=op, dst=expr_id, kind=EdgeKind.DRIVER))

        # 创建边: expr → result
        self._graph.add_trace_edge(TraceEdge(src=expr_id, dst=result, kind=EdgeKind.DRIVER))

        return expr_id

    def build_function_call(
        self, function_name: str, arguments: list[str], result: str, module: str = ""
    ) -> str | None:
        """构建函数调用节点

        Args:
            function_name: 函数名，如 "calc"
            arguments: 参数列表，如 ["a", "b"]
            result: 结果信号，如 "data"
            module: 模块名

        Returns:
            函数调用节点 ID，如 "func_calc_1"
        """
        if not arguments:
            return None

        # 创建函数调用节点
        func_id = self._next_id(f"func_{function_name}")
        self._create_node(
            node_id=func_id,
            name=f"{function_name}({', '.join(arguments)})",
            kind=NodeKind.FUNCTION_CALL,
            module=module,
            function_name=function_name,
            operands=list(arguments),
            signals=list(arguments),
        )

        # 创建边: arguments → func
        for arg in arguments:
            self._graph.add_trace_edge(TraceEdge(src=arg, dst=func_id, kind=EdgeKind.DRIVER))

        # 创建边: func → result
        self._graph.add_trace_edge(TraceEdge(src=func_id, dst=result, kind=EdgeKind.DRIVER, function_return=True))

        return func_id

    def build_conditional(
        self, condition: str, true_branch: str, false_branch: str, result: str, module: str = ""
    ) -> str | None:
        """构建条件表达式节点

        Args:
            condition: 条件信号，如 "sel"
            true_branch: 真分支，如 "a"
            false_branch: 假分支，如 "b"
            result: 结果信号，如 "data"
            module: 模块名

        Returns:
            条件表达式节点 ID，如 "cond_ternary_1"
        """
        # 创建条件表达式节点
        cond_id = self._next_id("cond_ternary")
        expr_str = f"{condition} ? {true_branch} : {false_branch}"

        self._create_node(
            node_id=cond_id,
            name=expr_str,
            kind=NodeKind.EXPRESSION,
            module=module,
            expression=expr_str,
            condition=condition,
            true_branch=true_branch,
            false_branch=false_branch,
            operands=[condition, true_branch, false_branch],
            signals=[condition, true_branch, false_branch],
        )

        # 创建边: condition/true/false → cond
        for src in [condition, true_branch, false_branch]:
            self._graph.add_trace_edge(TraceEdge(src=src, dst=cond_id, kind=EdgeKind.DRIVER))

        # 创建边: cond → result (带 condition 属性)
        self._graph.add_trace_edge(TraceEdge(src=cond_id, dst=result, kind=EdgeKind.DRIVER, condition=condition))

        return cond_id
