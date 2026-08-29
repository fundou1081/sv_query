# ruff: noqa: E402
"""
module_instance_graph.py - 模块实例层级图

[铁律11] 单一职责 - 模块实例结构独立管理

职责:
1. 管理模块实例层级 (top.u_tb, top.u_dut)
2. 维护端口到内部信号的映射
3. 支持跨模块路径查找

使用方式:
  mig = ModuleInstanceGraph(adapter)
  mig.build(trees)
  internal = mig.get_internal_signal('top.u_dut.clk')  # → 'dut.clk'
"""

import logging
from typing import Any

import networkx as nx

from .._safe import _safe_attr, _safe_str

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field


@dataclass
class PortInfo:
    """端口信息"""

    name: str  # 端口名 (clk, data, etc.)
    direction: str  # input/output/inout
    width: tuple[int, int]  # (msb, lsb)
    internal_signal: str  # 内部信号名 (dut.clk)
    module_type: str  # 模块类型 (dut)


@dataclass
class ModuleInstanceNode:
    """模块实例节点"""

    id: str  # 实例ID: "top.u_dut"
    module_type: str  # 模块类型: "dut"
    parent: str | None  # 父实例: "top" 或 None
    ports: dict[str, PortInfo] = field(default_factory=dict)

    def get_port(self, port_name: str) -> PortInfo | None:
        return self.ports.get(port_name)

    def get_internal_signal(self, port_name: str) -> str | None:
        port = self.get_port(port_name)
        return port.internal_signal if port else None


class ModuleInstanceGraph:
    """模块实例层级图

    管理模块实例及其端口映射关系
    支持跨模块边界追踪
    """

    def __init__(self, adapter, signal_graph=None):
        self.adapter = adapter
        self.signal_graph = signal_graph  # 可选,用于从 SignalGraph 获取 port_to_internal
        self.instances: dict[str, ModuleInstanceNode] = {}  # instance_id → Node
        self.port_to_internal: dict[str, str] = {}  # "top.u_dut.clk" → "dut.clk" (保留用于兼容,已废弃)
        self.internal_to_port: dict[str, str] = {}  # "dut.clk" → "top.u_dut.clk" (保留用于兼容,已废弃)


    def build(self, trees: dict[str, Any] | None = None, instance_source: str = "auto") -> None:
        """构建模块实例图.

        [G3 阶段 2 2026-08-29] 只支持 SemanticAdapter (或带 get_module_instances 的适配器)
        输入 — SyntaxTree dict 旧接口已删除 (死代码, 见 build 尾部注释).

        Args:
            trees: SemanticAdapter (新接口)
            instance_source: [G3 阶段 1 2026-08-29] 实例枚举来源, 显式验证钩子
                (非 fallback — 由调用方显式指定实现):
                - "auto" (默认): SemanticAdapter 且带 _root → native 枚举
                  (native_adapter.get_module_instances_native)
                - "recursive": 强制 get_module_instances_recursive() (旧递归, 验证参照)
                - "native": 强制 native 枚举
                tools/verify_native_parity.py 用 recursive/native 做 MIG 四表 A/B diff;
                生产调用 (unified_tracer) 不传 → auto → native

        Raises:
            TypeError: trees 不是适配器 (SyntaxTree dict 旧接口已删)
        """
        if not hasattr(trees, "get_module_instances"):
            raise TypeError(
                "ModuleInstanceGraph.build 只接受 SemanticAdapter — SyntaxTree dict 旧接口已删除 (G3 阶段 2)"
            )
        # 支持 SemanticAdapter 作为参数
        if hasattr(trees, "get_module_instances"):
            # SemanticAdapter path: 使用适配器获取实例
            adapter = trees
            # [G3 阶段 1 2026-08-29] 实例枚举切 native:
            # GAP-1/2 已修 (iter_054), GAP-3/4 已拍板接受 — native 与递归等价或更正确.
            # native wrapper (_NativeInstanceWrapper) 与 SemanticInstanceWrapper 在
            # MIG.build 用到的接口 (._symbol / .name / .parent_module) 上兼容,
            # 且 MIG.build 其余代码读 pyslang symbol 本身, 不受枚举来源影响.
            use_native = (
                instance_source == "native"
                or (instance_source == "auto" and hasattr(adapter, "_root"))
            )
            if use_native:
                from .native_adapter import get_module_instances_native
                instances = get_module_instances_native(
                    adapter._root, getattr(adapter, "_target_module", None)
                )
            elif hasattr(adapter, "get_module_instances_recursive"):
                # [G3 阶段 2 2026-08-29] 生产 get_module_instances() 已切 native;
                # recursive 仅作验证参照 (verify_native_parity.py A 路径)
                instances = adapter.get_module_instances_recursive()
            else:
                instances = adapter.get_module_instances()

            # 创建实例节点并填充端口映射
            for inst_wrapper in instances:
                # 使用完整的 hierarchicalPath (如果实例在 generate 块中,路径会包含 generate 名称)
                inst_symbol = inst_wrapper._symbol if hasattr(inst_wrapper, "_symbol") else None
                if inst_symbol:
                    hierarchical_path = _safe_attr(inst_symbol, "hierarchicalPath", None)
                    instance_id = _safe_str(hierarchical_path) if hierarchical_path else inst_wrapper.name
                else:
                    instance_id = inst_wrapper.name
                inst_type = adapter.get_module_name(inst_symbol) if inst_symbol else _safe_str(inst_wrapper.type)
                parent = inst_wrapper.parent_module
                self.instances[instance_id] = ModuleInstanceNode(id=instance_id, module_type=inst_type, parent=parent)

                # 从 portConnections 填充端口映射
                if inst_symbol:
                    port_conns = getattr(inst_symbol, "portConnections", [])
                    for conn in port_conns:
                        port_sym = getattr(conn, "port", None)
                        if port_sym:
                            port_name = _safe_attr(port_sym, "name", None)
                            if port_name:
                                port_path = f"{instance_id}.{port_name}"
                                # [Bug 1 fix 2026-06-27] 改回 inst_type 语义.
                                # 之前 commit 04a9a18 改用 parent (top.clk), 让多个 instance
                                # 共享 parent wire → 共享 internal → edge 成功创建.
                                # 但测试 test_port_mapping / test_mig_port_info 期望
                                # internal_signal = module_type.port_name (e.g. dut.clk),
                                # 即 "进入 instance 后看到的内部信号名".
                                # 现恢复: internal = inst_type.port_name (e.g. dut.clk).
                                # 多 instance edge 创建改由 semantic_adapter.find_connections
                                # 单独处理 (根据 port connection 直接找目标 wire).
                                internal = f"{inst_type}.{port_name}"
                                self.port_to_internal[port_path] = internal
                                self.internal_to_port[internal] = port_path

                                # 填充 _module_ports (模块类型 -> 端口信息)
                                if not hasattr(self, "_module_ports"):
                                    self._module_ports = {}
                                if inst_type not in self._module_ports:
                                    self._module_ports[inst_type] = {}

                                # 获取端口方向 (标准化为字符串: input/output/inout)
                                direction = "unknown"
                                if hasattr(port_sym, "direction"):
                                    dir_str = str(port_sym.direction).strip()
                                    # 移除 "ArgumentDirection." 前缀
                                    if "ArgumentDirection." in dir_str:
                                        dir_str = dir_str.split(".")[-1]
                                    # 标准化方向字符串
                                    if dir_str.lower() in ("in", "input"):
                                        direction = "input"
                                    elif dir_str.lower() in ("out", "output"):
                                        direction = "output"
                                    elif dir_str.lower() in ("inout", "in_out"):
                                        direction = "inout"
                                    else:
                                        direction = dir_str.lower()

                                # 获取端口位宽
                                width = (0, 0)
                                if hasattr(port_sym, "type") and port_sym.type:
                                    port_type = port_sym.type
                                    # 尝试从 fixedRange 获取位宽
                                    if hasattr(port_type, "fixedRange") and port_type.fixedRange:
                                        fr = port_type.fixedRange
                                        left = getattr(fr, "left", 0)
                                        right = getattr(fr, "right", 0)
                                        # left/right 可能是 int 或 ConstantValue
                                        if hasattr(left, "value"):
                                            left = left.value
                                        if hasattr(right, "value"):
                                            right = right.value
                                        width = (int(left), int(right))
                                    # 备选: 从 bitWidth 获取
                                    elif hasattr(port_type, "bitWidth") and port_type.bitWidth:
                                        width = (int(port_type.bitWidth) - 1, 0)

                                self._module_ports[inst_type][port_name] = PortInfo(
                                    name=port_name,
                                    direction=direction,
                                    width=width,
                                    internal_signal=internal,
                                    module_type=inst_type,
                                )

                                # 同时填充实例节点的 ports
                                self.instances[instance_id].ports[port_name] = PortInfo(
                                    name=port_name,
                                    direction=direction,
                                    width=width,
                                    internal_signal=internal,
                                    module_type=inst_type,
                                )
            return  # Semantic AST 路径到此为止,generate 处理由 SemanticAdapter.get_module_instances 完成

        # [G3 阶段 2 2026-08-29] SyntaxTree path (Phase 0-2) 已删除 — 死代码:
        # 生产唯一调用方 unified_tracer 传 SemanticAdapter, 此分支不可达.
        # 原 16 个 helper (/_extract_instances/_iter_children/_get_module_name 等
        # ~920 行) 一并删除, 见 docs/task_tree/iterations/iter_057_g3_stage2_full_native.md.

    def get_internal_signal(self, port_path: str) -> str | None:
        """端口路径 → 内部信号

        MIG 维护自己的 port_to_internal 映射,基于模块端口定义(而非实际连接)。
        CE 的 port_to_internal 来自实际连接,用于 SignalGraph 建边。
        两者语义不同:
          - MIG: 模块 Z 有端口 X,内部信号是 Z.X(结构定义)
          - CE: 实例的端口 X 实际连接到信号 Y(实际连接)

        Args:
            port_path: "top.u_dut.clk"

        Returns:
            "dut.clk" 或 None
        """
        # MIG 自己的映射(基于模块定义)
        if self.port_to_internal:
            return self.port_to_internal.get(port_path)
        # 备用:从 SignalGraph 获取(CE 构建的连接映射)
        if self.signal_graph is not None:
            return self.signal_graph.get_internal_signal(port_path)
        return None

    def get_port_path(self, internal_signal: str) -> str | None:
        """内部信号 → 端口路径

        Args:
            internal_signal: "dut.clk"

        Returns:
            "top.u_dut.clk" 或 None
        """
        # MIG 自己的映射(基于模块定义)
        if self.internal_to_port:
            return self.internal_to_port.get(internal_signal)
        # 备用:从 SignalGraph 获取(CE 构建的连接映射)
        if self.signal_graph is not None:
            port_to_internal = self.signal_graph.get_port_to_internal()
            # 反向查找
            for inst_port, internal in port_to_internal.items():
                if internal == internal_signal:
                    return inst_port
        return None

    def get_instance(self, instance_id: str) -> ModuleInstanceNode | None:
        """获取实例节点"""
        return self.instances.get(instance_id)

    def get_child_instances(self, parent_id: str) -> list[ModuleInstanceNode]:
        """获取子实例"""
        return [inst for inst in self.instances.values() if inst.parent == parent_id]

    def get_all_instances(self) -> list[str]:
        """获取所有实例ID"""
        return list(self.instances.keys())


class PathResolver:
    """跨模块路径解析器

    协调 SignalGraph 和 ModuleInstanceGraph
    实现跨模块边界路径查找
    """

    def __init__(self, signal_graph, module_graph: ModuleInstanceGraph):
        self.signal_graph = signal_graph
        self.module_graph = module_graph

    def find_path(self, src: str, dst: str) -> list[str] | None:
        """查找从 src 到 dst 的路径

        使用 BFS 追踪跨模块路径，自动处理:
        - 跨模块边界的端口映射 (top.u_dut.clk → dut.clk)
        - 双向扩展 (successors + predecessors)
        - 通过端口映射跨越模块边界
        """
        if src == dst:
            return [src]

        # 如果 dst 是端口，记录目标映射
        dst_internal = self.module_graph.get_internal_signal(dst)
        dst_target = dst_internal if dst_internal else dst

        # BFS 队列: (current_node, path_from_src)
        # 从原始 src 开始（不要映射），这样可以访问所有相邻节点
        queue = [(src, [src])]
        visited = {src}

        while queue:
            current, path = queue.pop(0)

            # 获取所有直接相连的节点 (successors + predecessors)
            neighbors = set()
            try:
                neighbors.update(self.signal_graph.successors(current))
            except (KeyError, nx.NetworkXError) as _e:
                logger.debug("图无路径 (正常): %s", _e)
                pass
            try:
                neighbors.update(self.signal_graph.predecessors(current))
            except (KeyError, nx.NetworkXError) as _e:
                logger.debug("图无路径 (正常): %s", _e)
                pass

            for neighbor in neighbors:
                if neighbor in visited:
                    continue

                # 检查是否到达目标
                if neighbor == dst_target:
                    return path + [neighbor]

                visited.add(neighbor)

                # 如果 neighbor 是模块端口，映射到内部信号并加入队列
                # 这样可以继续追踪模块内部信号
                neighbor_internal = self.module_graph.get_internal_signal(neighbor)
                if neighbor_internal:
                    if neighbor_internal not in visited:
                        visited.add(neighbor_internal)
                        queue.append((neighbor_internal, path + [neighbor, neighbor_internal]))
                else:
                    queue.append((neighbor, path + [neighbor]))

        return None

    def find_all_paths(self, src: str, dst: str) -> list[list[str]]:
        """查找所有路径"""
        paths = []
        path = [src]
        visited = set()

        self._find_all_paths_impl(src, dst, path, visited, paths)
        return paths

    def _find_all_paths_impl(self, current: str, dst: str, path: list[str], visited: set, paths: list[list[str]]):
        """递归查找所有路径的实现 (使用 successors)"""
        if current in visited:
            return
        visited.add(current)

        if current == dst:
            paths.append(path.copy())
            visited.discard(current)
            return

        try:
            successors = list(self.signal_graph.successors(current))
        except (KeyError, nx.NetworkXError):
            successors = []

        for driven_id in successors:
            path.append(driven_id)
            self._find_all_paths_impl(driven_id, dst, path, visited, paths)
            path.pop()

        visited.discard(current)
