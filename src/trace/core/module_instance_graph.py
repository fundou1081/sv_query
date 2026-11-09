# ruff: noqa: E402
"""
module_instance_graph.py - 模块实例层级图

[铁律11] 单一职责 - 模块实例结构独立管理

职责:
1. 管理模块实例层级 (top.u_tb, top.u_dut)
2. 维护实例端口信息（方向/位宽/实例级端口 id）
3. 支持层级与跨模块路径查找

使用方式:
  mig = ModuleInstanceGraph(adapter)
  mig.build(trees)
  port = mig.get_instance('top.u_dut').get_port('clk')  # → PortInfo
"""

import logging
from typing import Any

from collections import deque

import networkx as nx

from .._safe import _safe_attr, _safe_str, safe_attr, safe_str

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


class ModuleInstanceGraph:
    """模块实例层级图

    管理模块实例及其端口映射关系
    支持跨模块边界追踪
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self.instances: dict[str, ModuleInstanceNode] = {}  # instance_id → Node


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
                                # [iter_284 / PLAN P1.2] 单一命名空间: 端口的"内部信号"
                                # 就是实例级端口节点本身 (top.u_dut.clk), 不再存
                                # 模块定义短名 (dut.clk) —— 那是双命名空间最后残留。
                                internal = port_path

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
                                # [iter_183] safe_attr: .type getter 在非 utf8
                                # identifier 下抛 (hasattr 也不安全 — 只吞 AttributeError)
                                port_type = safe_attr(port_sym, "type", None)
                                if port_type:
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

    def _neighbors(self, node: str, directed: bool = False) -> list[str]:
        """统一的邻接定义。

        无向模式 (默认, `directed=False`): successors + predecessors +
        跨模块端口映射(两个方向) —— 回答**结构连通性**。

        有向模式 (`directed=True`): 只走 successors, 且**不**做 MIG 虚拟跳转 ——
        SignalGraph 本身已含跨模块端口边 (父网 ↔ 实例端口), 与 `dataflow analyze`
        走同一张有向图, 因此两者结论一致 (iter_268)。

        [iter_237] 旧实现里 `find_path` 走 successors+predecessors + 进模块映射, 而
        `find_all_paths` 只走 successors → 两者结论互相矛盾。现在两个入口共用本方法。
        """
        out: list[str] = []
        try:
            out.extend(self.signal_graph.successors(node))
        except (KeyError, nx.NetworkXError) as _e:
            logger.debug("图无后继 (正常): %s", _e)

        if directed:
            return out

        try:
            out.extend(self.signal_graph.predecessors(node))
        except (KeyError, nx.NetworkXError) as _e:
            logger.debug("图无前驱 (正常): %s", _e)
        # [iter_272] MIG 虚拟跳 (进/出模块) 已删除:
        # 图恒为实例级, 跨模块端口边本来就在 SignalGraph 里; 而 MIG 的
        # 旧实现会把端口映射到"模块定义命名空间"的影子 id (不在图里); 单一命名
        # 空间后端口 id 就是图节点, 这两跳
        # 只会把遍历导向不存在的节点。
        return out

    def find_path(self, src: str, dst: str, directed: bool = False) -> list[str] | None:
        """查找从 src 到 dst 的一条路径 (BFS, 跨模块感知)。

        返回**最短跳数**的那一条 (可能经由实例节点而非模块内部); 要走遍所有
        路线 (含穿越模块内部) 用 `find_all_paths`。

        Args:
            src/dst: 信号 id (如 "inst_demo.in_a" / "sub_adder.sum");
                     用 `svq graph nodes --json` 列可用 id。
        """
        if src == dst:
            return [src]
        # [iter_268] 不再把 dst 规范化为"模块内部信号"(模块定义命名空间影子节点)。
        # 旧实现 `dst_target = get_internal_signal(dst) or dst` 会让返回路径的
        # **最后一项不等于用户请求的 dst** (POC 实测 65~78/120 个采样对端点漂移),
        # 甚至越过 dst 继续走到影子节点。契约: 路径必须以 dst 结尾。
        queue: deque[tuple[str, list[str]]] = deque([(src, [src])])
        visited = {src}
        while queue:
            current, path = queue.popleft()
            for neighbor in self._neighbors(current, directed=directed):
                if neighbor in visited:
                    continue
                if neighbor == dst:
                    return path + [neighbor]
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
        return None

    def find_all_paths(self, src: str, dst: str, max_paths: int = 50,
                       max_depth: int = 60, directed: bool = False) -> list[list[str]]:
        """枚举 src → dst 的所有简单路径 (与 `find_path` 共用邻接定义)。

        Args:
            max_paths: 结果上限 (有环图里防爆; 调用方应据此标注 truncated)
            max_depth: 单条路径最大节点数
        """
        paths: list[list[str]] = []
        # [iter_268] 与 find_path 一致: 端点就是用户给的 dst, 不做影子节点规范化。

        def _dfs(current: str, path: list[str], visited: set) -> None:
            if len(paths) >= max_paths or len(path) > max_depth:
                return
            if current == dst and len(path) > 1:
                paths.append(path.copy())
                return
            for nxt in self._neighbors(current, directed=directed):
                if nxt in visited:
                    continue
                visited.add(nxt)
                path.append(nxt)
                _dfs(nxt, path, visited)
                path.pop()
                visited.discard(nxt)

        _dfs(src, [src], {src})
        return paths
