# call_graph_models.py - 函数调用图数据模型
#
# 独立于 SignalGraph，用于调用图构建和分析。

from dataclasses import dataclass, field


@dataclass
class CallNode:
    """调用图节点"""

    caller: str  # 调用者 (如 "my_seq::body")
    callee: str  # 被调用者 (如 "do_drive")
    kind: str  # "call" | "fork" | "randomize"
    line: int = 0  # 源码行号
    children: list["CallNode"] = field(default_factory=list)  # 子调用
    join_type: str = ""  # "join" | "join_none" | "join_any" (仅 fork)
    randomize_vars: list[str] = field(default_factory=list)  # randomize 的变量
    inline_constraint: str = ""  # inline constraint 文本
    pattern: str = "generic"  # "sequence" | "driver" | "generic"


@dataclass
class CallGraph:
    """完整调用图"""

    entry_point: str  # 入口函数/任务 (如 "my_seq::body")
    root: CallNode = None  # 根节点
    randomize_calls: list[CallNode] = field(default_factory=list)  # 所有 randomize 调用
    fork_points: list[CallNode] = field(default_factory=list)  # 所有 fork 点
    errors: list[str] = field(default_factory=list)  # 解析错误

    # =================================================================
    # 输出格式
    # =================================================================

    def to_mermaid(self) -> str:
        """输出 Mermaid 流程图格式"""
        lines = ["graph TD"]
        self._node_counter = 0
        if self.root:
            self._to_mermaid_node(self.root, lines, parent_id=None)
        return "\n".join(lines)

    def _to_mermaid_node(self, node: "CallNode", lines: list, parent_id: str) -> str:
        """递归生成 Mermaid 节点"""
        self._node_counter += 1
        node_id = f"n{self._node_counter}"

        # 节点标签
        if node.kind == "fork":
            label = f"[FORK/{node.join_type}]"
            lines.append(f"    {node_id}[/{label}/]")
        elif node.kind == "randomize":
            label = f"[RANDOMIZE] {node.callee}"
            if node.inline_constraint:
                label += f"<br/>{node.inline_constraint}"
            lines.append(f"    {node_id}[/{label}/]")
        else:
            label = node.callee
            if node.pattern != "generic":
                label = f"[{node.pattern.upper()}] {label}"
            lines.append(f'    {node_id}["{label}"]')

        # 连接边
        if parent_id:
            lines.append(f"    {parent_id} --> {node_id}")

        # 子节点
        for child in node.children:
            self._to_mermaid_node(child, lines, node_id)

        return node_id

    def to_dot(self) -> str:
        """输出 Graphviz DOT 格式"""
        lines = ["digraph CallGraph {"]
        lines.append("    rankdir=TB;")
        lines.append("    node [shape=box, style=filled, fillcolor=lightyellow];")
        self._node_counter = 0
        if self.root:
            self._to_dot_node(self.root, lines, parent_id=None)
        lines.append("}")
        return "\n".join(lines)

    def _to_dot_node(self, node: "CallNode", lines: list, parent_id: str) -> str:
        """递归生成 DOT 节点"""
        self._node_counter += 1
        node_id = f"n{self._node_counter}"

        # 节点样式
        if node.kind == "fork":
            attrs = f'label="[FORK/{node.join_type}]", shape=diamond, fillcolor=lightblue'
        elif node.kind == "randomize":
            label = f"[RANDOMIZE] {node.callee}"
            if node.inline_constraint:
                label += f"\n{node.inline_constraint}"
            attrs = f'label="{label}", fillcolor=lightgreen'
        else:
            label = node.callee
            if node.pattern != "generic":
                label = f"[{node.pattern.upper()}] {label}"
            attrs = f'label="{label}"'

        lines.append(f"    {node_id} [{attrs}];")

        # 连接边
        if parent_id:
            style = " [style=dashed]" if node.kind == "fork" else ""
            lines.append(f"    {parent_id} -> {node_id}{style};")

        # 子节点
        for child in node.children:
            self._to_dot_node(child, lines, node_id)

        return node_id
