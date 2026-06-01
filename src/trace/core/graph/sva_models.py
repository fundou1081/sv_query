# sva_models.py - SVA (SystemVerilog Assertions) 数据模型
#
# 独立于 SignalGraph，用于 SVA 结构化提取和分析。

from dataclasses import dataclass, field


@dataclass
class SVASequenceNode:
    """SVA sequence 节点"""

    id: str  # "module.s1"
    name: str  # "s1"
    signals: list[str] = field(default_factory=list)  # 涉及的信号
    timing_ops: list[str] = field(default_factory=list)  # 时序操作符 (##1, ##[1:3])
    clock: str = ""  # 时钟
    source_file: str = ""
    source_line: int = 0


@dataclass
class SVAPropertyNode:
    """SVA property 节点"""

    id: str  # "module.p1"
    name: str  # "p1"
    signals: list[str] = field(default_factory=list)  # 涉及的信号
    operators: list[str] = field(default_factory=list)  # 操作符 (|->, |=>, [*n])
    disable_iff: str = ""  # disable iff 条件
    clock: str = ""  # 时钟
    sequences: list[str] = field(default_factory=list)  # 引用的 sequence id
    source_file: str = ""
    source_line: int = 0


@dataclass
class SVAAssertionNode:
    """SVA assertion 节点"""

    id: str  # "module.assert_0"
    kind: str  # "assert" | "assume" | "cover"
    property_ref: str = ""  # 引用的 property id
    signals: list[str] = field(default_factory=list)  # 涉及的信号
    message: str = ""  # 错误消息
    source_file: str = ""
    source_line: int = 0


@dataclass
class SVAGraph:
    """SVA 图"""

    sequences: dict[str, SVASequenceNode] = field(default_factory=dict)
    properties: dict[str, SVAPropertyNode] = field(default_factory=dict)
    assertions: list[SVAAssertionNode] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # 信号关联索引: signal_name → [node_id, ...]
    signal_refs: dict[str, list[str]] = field(default_factory=dict)

    def get_assertions_for_signal(self, signal: str) -> list[SVAAssertionNode]:
        """查询某个信号相关的所有 assertion"""
        refs = self.signal_refs.get(signal, [])
        result = []
        for ref in refs:
            for a in self.assertions:
                if a.id == ref or a.property_ref == ref:
                    result.append(a)
        return result

    def get_signals_for_assertion(self, assertion_id: str) -> list[str]:
        """查询某个 assertion 涉及的所有信号"""
        for a in self.assertions:
            if a.id == assertion_id:
                return a.signals
        # 查 property
        for pid, prop in self.properties.items():
            if pid == assertion_id:
                return prop.signals
        return []

    def to_dot(self) -> str:
        """输出 Graphviz DOT 格式"""
        lines = ["digraph SVAGraph {"]
        lines.append("    rankdir=TB;")
        lines.append("    node [shape=box];")

        for sid, seq in self.sequences.items():
            label = f"SEQ: {seq.name}\\n{', '.join(seq.signals)}"
            lines.append(f'    {sid} [label="{label}", fillcolor=lightyellow];')

        for pid, prop in self.properties.items():
            ops = ", ".join(prop.operators) if prop.operators else ""
            label = f"PROP: {prop.name}\\n{ops}"
            lines.append(f'    {pid} [label="{label}", fillcolor=lightblue];')

        for a in self.assertions:
            label = f"{a.kind}: {a.message[:30]}" if a.message else a.kind
            lines.append(f'    {a.id} [label="{label}", fillcolor=lightgreen];')
            if a.property_ref:
                lines.append(f"    {a.id} -> {a.property_ref};")

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """输出 Mermaid 格式"""
        lines = ["graph TD"]

        for sid, seq in self.sequences.items():
            label = f"SEQ: {seq.name}<br/>{', '.join(seq.signals)}"
            lines.append(f'    {sid}["{label}"]')

        for pid, prop in self.properties.items():
            ops = ", ".join(prop.operators) if prop.operators else ""
            label = f"PROP: {prop.name}<br/>{ops}"
            lines.append(f'    {pid}["{label}"]')

        for a in self.assertions:
            label = f"{a.kind}" + (f"<br/>{a.message[:30]}" if a.message else "")
            lines.append(f'    {a.id}["{label}"]')
            if a.property_ref:
                lines.append(f"    {a.id} --> {a.property_ref}")

        return "\n".join(lines)
