# ==============================================================================
# query_module.py - 场景B: Module Trace
# 模块端口连接追踪
# ==============================================================================

from dataclasses import dataclass, field

from ..graph.models import NodeKind, SignalGraph, TraceEdge, TraceNode


@dataclass
class ModuleConnections:
    """模块连接关系"""

    module: str
    inputs: list[TraceEdge] = field(default_factory=list)  # 输入端口及连接
    outputs: list[TraceEdge] = field(default_factory=list)  # 输出端口及连接
    internals: list[TraceEdge] = field(default_factory=list)  # 内部信号连接
    cross_module: list[TraceEdge] = field(default_factory=list)  # 跨模块连接
    confidence: str = "high"
    caveats: list[str] = field(default_factory=list)


class ModuleTracer:
    """场景B: 模块端口连接追踪"""

    def __init__(self, graph: SignalGraph):
        self.graph = graph

    def _get_module_ports(self, module: str) -> dict[str, TraceNode]:
        """获取模块所有端口"""
        ports = {}

        for node_id, node in self.graph._node_data.items():
            if node.module == module and getattr(node, "is_port", False):
                ports[node.name] = node

        return ports

    def _classify_ports(self, ports: dict[str, TraceNode]) -> tuple:
        """分类端口: input, output, inout"""
        inputs = []
        outputs = []

        for name, node in ports.items():
            if node.kind == NodeKind.PORT_IN:
                inputs.append(node)
            elif node.kind == NodeKind.PORT_OUT:
                outputs.append(node)
            # inout 同时计入 input 和 output

        return inputs, outputs

    def _get_port_edges(self, node: TraceNode, direction: str) -> list[TraceEdge]:
        """获取端口的所有边"""
        edges = []
        node_id = node.id

        if direction == "input":
            # 外部 -> 端口 (predecessors)
            for pred in self.graph.predecessors(node_id):
                edge = self.graph.get_edge(pred, node_id)
                if edge:
                    edges.append(edge)
        else:
            # 端口 -> 外部 (successors)
            for succ in self.graph.successors(node_id):
                edge = self.graph.get_edge(node_id, succ)
                if edge:
                    edges.append(edge)

        return edges

    def _get_internal_edges(self, module: str) -> list[TraceEdge]:
        """获取内部信号连接"""
        edges = []

        for (src, dst), edge_list in self.graph._edge_data.items():
            for edge in edge_list:
                src_node = self.graph.get_node(src)
                dst_node = self.graph.get_node(dst)

                if src_node and dst_node:
                    if src_node.module == module and dst_node.module == module:
                        edges.append(edge)

        return edges

    def _get_cross_module_edges(self, module: str) -> list[TraceEdge]:
        """获取跨模块连接"""
        edges = []

        for (src, dst), edge_list in self.graph._edge_data.items():
            for edge in edge_list:
                src_node = self.graph.get_node(src)
                dst_node = self.graph.get_node(dst)

                if src_node and dst_node:
                    if src_node.module == module and dst_node.module != module:
                        edges.append(edge)
                    elif src_node.module != module and dst_node.module == module:
                        edges.append(edge)

        return edges

    def _assess_confidence(self, module: str, internals: list[TraceEdge], cross_module: list[TraceEdge]) -> str:
        """评估置信度"""
        if cross_module and any(e.confidence == "uncertain" for e in cross_module):
            return "medium"
        if internals and any(e.confidence == "uncertain" for e in internals):
            return "medium"
        return "high"

    def _collect_caveats(self, module: str, ports: dict) -> list[str]:
        """收集注意事项"""
        caveats = []

        # 检查未连接的端口
        for name, node in ports.items():
            if node.kind == NodeKind.PORT_IN:
                if not list(self.graph.predecessors(node.id)):
                    caveats.append(f"Unconnected input port: {name}")
            elif node.kind == NodeKind.PORT_OUT:
                if not list(self.graph.successors(node.id)):
                    caveats.append(f"Unconnected output port: {name}")

        return caveats

    def trace(self, module: str) -> ModuleConnections:
        """追踪模块连接"""
        result = ModuleConnections(module=module)

        # 1. 获取并分类端口
        ports = self._get_module_ports(module)
        inputs, outputs = self._classify_ports(ports)

        # 2. 提取输入端口边
        for node in inputs:
            result.inputs.extend(self._get_port_edges(node, "input"))

        # 3. 提取输出端口边
        for node in outputs:
            result.outputs.extend(self._get_port_edges(node, "output"))

        # 4. 提取内部信号连接
        result.internals = self._get_internal_edges(module)

        # 5. 提取跨模块连接
        result.cross_module = self._get_cross_module_edges(module)

        # 6. 置信度评估
        result.confidence = self._assess_confidence(module, result.internals, result.cross_module)

        # 7. 收集注意事项
        result.caveats = self._collect_caveats(module, ports)

        return result

    def trace_port(self, module: str, port_name: str) -> list[TraceEdge]:
        """追踪特定端口的连接"""
        ports = self._get_module_ports(module)

        if port_name not in ports:
            return []

        port = ports[port_name]

        if port.kind == NodeKind.PORT_IN:
            return self._get_port_edges(port, "input")
        else:
            return self._get_port_edges(port, "output")

    def find_connected_modules(self, module: str) -> list[str]:
        """查找连接的其他模块"""
        connected = set()

        for edge in self._get_cross_module_edges(module):
            src_node = self.graph.get_node(edge.src)
            dst_node = self.graph.get_node(edge.dst)

            if src_node and src_node.module != module:
                connected.add(src_node.module)
            if dst_node and dst_node.module != module:
                connected.add(dst_node.module)

        return list(connected)
