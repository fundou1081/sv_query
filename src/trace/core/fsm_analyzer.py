# ==============================================================================
# fsm_analyzer.py — 状态机提取与 DOT/Mermaid 渲染
# ==============================================================================
"""
[iter_255 T3-4] 从 `trace/unified_tracer.py` (1,403 行) 拆出: 这三个类与
`UnifiedTracer` 的门面职责无关 (它们是"从图里抽状态机 + 画图"), 放在一起
只会让 1,400 行的文件更难读。

`UnifiedTracer` 仍 re-export 这三个名字 (`from trace.core.fsm_analyzer import ...`),
既有 `from trace.unified_tracer import StateMachineInfo` 的导入路径不变。
"""
from __future__ import annotations

from dataclasses import dataclass

class StateTransition:
    """单个状态转换"""

    from_state: str
    to_state: str
    condition: str


@dataclass
class StateMachineInfo:
    """状态机信息"""

    name: str
    state_signal: str
    module: str
    states: set[str]
    transitions: list[StateTransition]
    reset_state: str

    def to_dot(self) -> str:
        """生成 DOT 格式状态图"""
        lines = [
            f"digraph {self.name} {{",
            "    rankdir=LR;",
            "    node [shape=circle];",
            f"    // State signal: {self.state_signal}",
            f"    // Reset state: {self.reset_state}",
            "",
        ]
        for state in sorted(self.states):
            if state == self.reset_state:
                lines.append(f"    {state} [style=filled, color=lightgray];")
            else:
                lines.append(f"    {state};")
        lines.append("")
        for t in sorted(self.transitions, key=lambda x: (x.from_state, x.to_state)):
            cond = t.condition if t.condition else "1"
            lines.append(f'    {t.from_state} -> {t.to_state} [label="{cond}"];')
        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """生成 Mermaid 格式状态图"""
        lines = ["stateDiagram-v2", "    direction LR", f"    [*] --> {self.reset_state}", ""]
        for t in sorted(self.transitions, key=lambda x: (x.from_state, x.to_state)):
            cond = t.condition if t.condition else ""
            if cond:
                lines.append(f"    {t.from_state} --> {t.to_state} : {cond}")
            else:
                lines.append(f"    {t.from_state} --> {t.to_state}")
        return "\n".join(lines)


class StateMachineAnalyzer:
    """状态机图生成器 - 分析控制流图中的状态转换

    从 UnifiedTracer 获取控制流图,提取状态机转换信息,生成 DOT/Mermaid 格式图.
    """

    def __init__(self, tracer):
        self.tracer = tracer
        self.graph = tracer.build_graph()

    def analyze(self, state_signal: str, module: str = None) -> StateMachineInfo:
        """分析状态机

        Args:
            state_signal: 状态寄存器信号名 (如 "state")
            module: 所在模块 (可选)

        Returns:
            StateMachineInfo 或 None
        """
        candidates = []
        for node in self.graph.nodes:
            if module and not node.startswith(module + "."):
                continue
            if node.endswith("." + state_signal) or node == state_signal:
                candidates.append(node)

        if not candidates:
            return None

        state_node = candidates[0]

        states = set()
        transitions = []
        reset_state = None

        # [FIX] 遍历所有边而不是只检查 get_edge(src, dst)
        for src_node in self.graph.nodes:
            # [FIX] 使用 get_edges 获取所有边（可能有多个不同 condition）
            edges = self.graph.get_edges(src_node, state_node)
            if not edges:
                continue

            for edge in edges:
                if "DRIVER" not in str(edge.kind):
                    continue

                condition = edge.condition or ""

                # src_node 是状态值常量 (如 fsm3.IDLE)
                to_state = self._extract_state_value(src_node)
                if not to_state:
                    continue

                # 从 condition 中提取"当前状态"
                from_state = self._extract_current_state(condition, state_signal)

                states.add(to_state)
                if from_state:
                    states.add(from_state)

                # 检查是否是复位转换
                if self._is_reset_condition(condition):
                    reset_state = from_state or to_state
                elif from_state:
                    extra_cond = self._strip_state_condition(condition, state_signal)
                    transitions.append(
                        StateTransition(
                            from_state=from_state, to_state=to_state, condition=extra_cond if extra_cond else "1"
                        )
                    )

        if not states:
            return None

        if "." in state_node:
            mod = state_node.rsplit(".", 1)[0]
        else:
            mod = module or "top"

        reset_state = reset_state or min(states)

        return StateMachineInfo(
            name=f"FSM_{state_signal.replace('.', '_')}",
            state_signal=state_signal,
            module=mod,
            states=states,
            transitions=transitions,
            reset_state=reset_state,
        )

    def _extract_state_value(self, node: str) -> str:
        if "." in node:
            return node.rsplit(".", 1)[1]
        return node

    def _extract_current_state(self, condition: str, state_signal: str) -> str:
        pattern = rf"{state_signal}\s*(?:==|===)\s*(\w+)"
        m = re.search(pattern, condition)
        if m:
            return m.group(1)
        return None

    def _is_reset_condition(self, condition: str) -> bool:
        """检查是否为复位条件

        只有纯复位条件（不包含 && 或 ||）才被认为是复位转换。
        例如：
        - "!rst_n" -> True (复位)
        - "!!rst_n" -> True (复位)
        - "!rst_n && state == IDLE" -> False (条件转换)
        """
        stripped = condition.replace(" ", "")
        # 包含 && 或 || 表示有额外条件，不是纯复位
        if "&&" in stripped or "||" in stripped:
            return False
        return "rst" in stripped.lower() or "reset" in stripped.lower()

    def _strip_state_condition(self, condition: str, state_signal: str) -> str:
        """移除条件中的 state == X 部分，只保留额外条件

        例如: "!!rst_n && state == REQ" -> "!!rst_n"
        "state == REQ" -> "1"
        "state == REQ && go" -> "go"
        "!!rst_n && state == REQ && go" -> "!!rst_n && go"
        """
        import re

        # 移除 state == X 部分
        pattern = rf"{state_signal}\s*(?:==|===)\s*\w+\s*"
        result = re.sub(pattern, "", condition).strip()

        # 清理多余的 && 和空格
        result = re.sub(r"^\s*&&\s*", "", result)
        result = re.sub(r"\s*&&\s*$", "", result)

        # 如果结果为空，返回 "1" (无条件)
        return result if result else "1"
