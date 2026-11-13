# uvm_models.py - UVM Testbench 结构数据模型
#
# 独立于 SignalGraph，用于 UVM testbench 结构提取。

from dataclasses import dataclass, field


@dataclass
class UVMComponent:
    """UVM 组件"""

    name: str  # 实例名 (如 "agent")
    class_name: str  # 类名 (如 "my_agent")
    base_class: str  # UVM 基类 (如 "uvm_agent")
    component_type: str  # 推断类型 (如 "agent")
    parent: str = ""  # 父组件实例名
    children: list[str] = field(default_factory=list)


@dataclass
class TLMConnection:
    """TLM 连接"""

    source_port: str  # 源端口路径 (agent.monitor.ap)
    target_port: str  # 目标端口路径 (sb.analysis_imp)
    port_type: str = ""  # "analysis" | "put" | "get" | "master" | "slave"


@dataclass
class SequenceBinding:
    """Sequence → Sequencer 绑定"""

    sequencer_path: str  # sequencer 路径
    sequence_class: str  # sequence 类名


@dataclass
class FactoryOverride:
    """Factory Override"""

    original: str  # 原始类型
    override_type: str  # 覆盖类型
    scope: str = ""  # 覆盖范围 (inst override)


@dataclass
class ConfigDBEntry:
    """Config DB 条目"""

    context: str  # 上下文 (this)
    target_path: str  # 目标路径
    field_name: str  # 字段名
    value_type: str  # 值类型
    value: str = ""  # 值描述


@dataclass
class UVMTestbench:
    """UVM Testbench 完整结构"""

    components: dict[str, UVMComponent] = field(default_factory=dict)
    connections: list[TLMConnection] = field(default_factory=list)
    sequence_bindings: list[SequenceBinding] = field(default_factory=list)
    overrides: list[FactoryOverride] = field(default_factory=list)
    config_entries: list[ConfigDBEntry] = field(default_factory=list)
    class_hierarchy: dict[str, str] = field(default_factory=dict)  # 类名 → 父类名
    errors: list[str] = field(default_factory=list)  # 解析错误

    def get_component(self, name: str) -> UVMComponent | None:
        """按实例名获取组件"""
        return self.components.get(name)

    def get_component_by_class(self, class_name: str) -> UVMComponent | None:
        """按类名获取组件"""
        for comp in self.components.values():
            if comp.class_name == class_name:
                return comp
        return None

    def get_children(self, parent_name: str) -> list[UVMComponent]:
        """获取子组件列表"""
        return [c for c in self.components.values() if c.parent == parent_name]

    # =================================================================
    # 输出格式
    # =================================================================

    def to_dot(self) -> str:
        """输出 Graphviz DOT 格式"""
        lines = ["digraph UVMTestbench {"]
        lines.append("    rankdir=TB;")
        lines.append("    node [shape=box, style=filled, fillcolor=lightyellow];")

        # 组件节点
        colors = {
            "test": "lightblue",
            "env": "lightcyan",
            "agent": "lightyellow",
            "driver": "lightpink",
            "monitor": "lightgreen",
            "sequencer": "lavender",
            "scoreboard": "lightgoldenrod",
            "sequence": "white",
        }
        for name, comp in self.components.items():
            color = colors.get(comp.component_type, "white")
            label = f"{name}\\n{comp.class_name}\\n({comp.base_class})"
            lines.append(f'    {name} [label="{label}", fillcolor={color}];')

        # 包含关系
        for name, comp in self.components.items():
            if comp.parent:
                lines.append(f'    {comp.parent} -> {name} [label="contains"];')

        # TLM 连接
        for conn in self.connections:
            label = f' [label="{conn.source_port.split(".")[-1]} → {conn.target_port.split(".")[-1]}", style=dashed, color=blue]'
            src = conn.source_port.split(".")[0]
            tgt = conn.target_port.split(".")[0]
            lines.append(f"    {src} -> {tgt}{label};")

        # Sequence 绑定
        for binding in self.sequence_bindings:
            seq_path = binding.sequencer_path.split(".")[0]
            lines.append(f'    {seq_path} [label="{seq_path}\\n[{binding.sequence_class}]", fillcolor=white];')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """输出 Mermaid 流程图格式"""
        lines = ["graph TD"]

        # 组件节点
        for name, comp in self.components.items():
            label = f"{name}<br/>{comp.class_name}<br/>({comp.base_class})"
            lines.append(f'    {name}["{label}"]')

        # 包含关系
        for name, comp in self.components.items():
            if comp.parent:
                lines.append(f"    {comp.parent} --> {name}")

        # TLM 连接
        for conn in self.connections:
            src = conn.source_port.split(".")[0]
            tgt = conn.target_port.split(".")[0]
            port_label = f"{conn.source_port.split('.')[-1]} → {conn.target_port.split('.')[-1]}"
            lines.append(f"    {src} -.->|{port_label}| {tgt}")

        # Sequence 绑定
        for binding in self.sequence_bindings:
            seq_path = binding.sequencer_path.split(".")[0]
            lines.append(f"    {seq_path} -.- |{binding.sequence_class}| {seq_path}")

        return "\n".join(lines)
