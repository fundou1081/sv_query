# ==============================================================================
# extractor_models.py - ExtractorResult 共享数据类 (P1 cycle 9 解决循环 import)
#
# 之前 ExtractorResult 在 graph_builder.py, DriverExtractor 在 driver_extractor.py
# 都定义一份. 循环 import 出现: graph_builder → driver_extractor → graph_builder
# (通过 ExtractorResult 引用).
#
# 修复: ExtractorResult 独立成文件, 所有 Extractor (Driver/Load/Connection/Clock)
# 从这里 import.
# ==============================================================================

from dataclasses import dataclass, field

from .graph.models import TraceEdge, TraceNode


@dataclass
class ExtractorResult:
    """提取器统一结果 - 5 个 Extractor 共享

    Attributes:
        nodes: 提取的 TraceNode 列表
        edges: 提取的 TraceEdge 列表
        errors: 错误信息
        port_to_internal: 端口到内部信号的映射 (full hierarchy path)
        port_to_module_type: 端口到模块类型内部信号的映射 (semantic short name)
            e.g. 'top.u_dut.clk' → 'dut.clk'
    """
    nodes: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    port_to_internal: dict[str, str] = field(default_factory=dict)  # {inst_port_id: child_signal_id}
    port_to_module_type: dict[str, str] = field(default_factory=dict)  # {inst_port_id: <module_type>.<port_name>}
