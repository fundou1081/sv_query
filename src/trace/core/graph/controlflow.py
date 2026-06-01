# ControlFlow Graph - 控制流图
# 基于 docs/CONTROL_FLOW_DESIGN.md 设计

from dataclasses import asdict

import networkx as nx

from .controlflow_models import (
    ControlBlock,
    ControlFlowEdge,
    ControlFlowEdgeKind,
    ControlFlowNode,
    ControlFlowNodeKind,
    StateMachineAnalysis,
    StateTransition,
)


class ControlFlowGraph:
    """控制流图 - 基于 NetworkX 的有向图"""

    def __init__(self, module_name: str = ""):
        self.module_name = module_name

        # NetworkX 有向图
        self.graph = nx.DiGraph()

        # 节点和边映射
        self.nodes: dict[str, ControlFlowNode] = {}
        self.edges: dict[str, ControlFlowEdge] = {}

        # 索引
        self._condition_nodes: list[ControlFlowNode] = []
        self._state_nodes: list[ControlFlowNode] = []
        self._case_structures: list[str] = []

        # 块映射: AST node id -> ControlBlock
        self._blocks: dict[int, ControlBlock] = {}

        # 变量到节点的映射
        self._var_to_conditions: dict[str, list[str]] = {}  # var -> [node_id]

    def add_node(self, node: ControlFlowNode) -> None:
        """添加节点"""
        self.nodes[node.id] = node
        self.graph.add_node(node.id, **asdict(node))

        # 索引
        if node.kind == ControlFlowNodeKind.CONDITION:
            self._condition_nodes.append(node)
        elif node.kind == ControlFlowNodeKind.STATE:
            self._state_nodes.append(node)

        # 更新变量索引
        for var in node.condition_vars:
            if var not in self._var_to_conditions:
                self._var_to_conditions[var] = []
            self._var_to_conditions[var].append(node.id)

    def add_edge(self, edge: ControlFlowEdge) -> None:
        """添加边"""
        self.edges[edge.id] = edge
        # 添加到 NetworkX 图 (如果节点不存在，先创建空节点)
        if edge.from_node not in self.graph:
            self.graph.add_node(edge.from_node)
        if edge.to_node not in self.graph:
            self.graph.add_node(edge.to_node)
        self.graph.add_edge(edge.from_node, edge.to_node, **asdict(edge))

    def get_node(self, node_id: str) -> ControlFlowNode | None:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> list[ControlFlowEdge]:
        """获取从某节点发出的所有边"""
        result = []
        for edge_id, edge in self.edges.items():
            if edge.from_node == node_id:
                result.append(edge)
        return result

    def get_edges_to(self, node_id: str) -> list[ControlFlowEdge]:
        """获取指向某节点的所有边"""
        result = []
        for edge_id, edge in self.edges.items():
            if edge.to_node == node_id:
                result.append(edge)
        return result

    def get_condition_dependencies(self, var: str) -> list[str]:
        """获取变量的控制依赖 (哪些条件节点依赖这个变量)"""
        return self._var_to_conditions.get(var, [])

    def get_condition_vars(self) -> set[str]:
        """获取所有作为条件的变量"""
        return set(self._var_to_conditions.keys())

    def find_control_blocks(
        self,
        control_vars: list[str],
        data_vars: list[str],
    ) -> list[ControlBlock]:
        """查找同时包含控制变量和数据变量的代码块"""
        blocks = []

        for block in self._blocks.values():
            # 检查控制变量
            has_control = any(v in block.control_vars for v in control_vars)
            # 检查数据变量
            has_data = any(v in block.data_vars for v in data_vars)

            if has_control and has_data:
                blocks.append(block)

        return blocks

    def add_control_block(self, block: ControlBlock) -> None:
        """添加控制块"""
        if block.ast_node is not None:
            self._blocks[id(block.ast_node)] = block

    def get_control_block(self, ast_node) -> ControlBlock | None:
        """根据 AST 节点获取控制块"""
        return self._blocks.get(id(ast_node))

    def get_state_machine(self, state_var: str) -> StateMachineAnalysis | None:
        """获取状态机信息"""
        # 查找所有 case(state_var) 的节点
        case_nodes = [
            n
            for n in self._condition_nodes
            if n.condition_vars and state_var in n.condition_vars and n.kind == ControlFlowNodeKind.CONDITION
        ]

        if not case_nodes:
            return None

        # 从 case 节点构建状态机
        case_node = case_nodes[0]

        # 收集所有状态
        states = set()
        transitions = []

        # 获取 case 的分支
        for edge in self.get_edges_from(case_node.id):
            if edge.kind == ControlFlowEdgeKind.CASE_MATCH:
                # 获取目标节点
                target = self.get_node(edge.to_node)
                if target and target.state_value:
                    states.add(target.state_value)
                    # 状态转换
                    transitions.append(
                        StateTransition(
                            from_state=case_node.condition_expr,
                            to_state=target.state_value,
                            condition=edge.condition_expr or "",
                        )
                    )

        if not states:
            return None

        return StateMachineAnalysis(
            name=state_var,
            all_states=list(states),
            transitions=transitions,
        )

    def check_missing_else(self) -> list[ControlBlock]:
        """检查缺失 else 的 if 语句"""
        results = []

        for block in self._blocks.values():
            if block.kind == "if" and not block.has_else:
                results.append(block)

        return results

    def check_missing_default(self) -> list[ControlBlock]:
        """检查缺失 default 的 case 语句"""
        results = []

        for block in self._blocks.values():
            if block.kind == "case" and not block.has_else:
                results.append(block)

        return results

    @property
    def condition_nodes(self) -> list[ControlFlowNode]:
        """所有条件节点"""
        return self._condition_nodes

    @property
    def state_nodes(self) -> list[ControlFlowNode]:
        """所有状态节点"""
        return self._state_nodes

    def __repr__(self) -> str:
        return f"ControlFlowGraph(module={self.module_name}, nodes={len(self.nodes)}, edges={len(self.edges)})"
