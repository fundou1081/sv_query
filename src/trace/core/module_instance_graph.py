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
import time
from typing import Any

from collections import deque

import networkx as nx

from .._safe import _safe_attr, _safe_str, safe_attr, safe_str
from .graph import contracts

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


    def to_dict(self) -> dict:
        """Serialize instance/port mapping for snapshots (P151/P158.7)."""
        module_ports = {}
        for mod, ports in getattr(self, "_module_ports", {}).items():
            module_ports[mod] = {
                name: {
                    "name": port.name,
                    "direction": port.direction,
                    "width": list(port.width) if port.width else None,
                    "internal_signal": port.internal_signal,
                    "module_type": port.module_type,
                }
                for name, port in ports.items()
            }
        return {
            "module_ports": module_ports,
            "instances": {
                iid: {
                    "id": inst.id,
                    "module_type": inst.module_type,
                    "parent": inst.parent,
                    "ports": {
                        name: {
                            "name": port.name,
                            "direction": port.direction,
                            "width": list(port.width) if port.width else None,
                            "internal_signal": port.internal_signal,
                            "module_type": port.module_type,
                        }
                        for name, port in inst.ports.items()
                    },
                }
                for iid, inst in self.instances.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleInstanceGraph":
        """Rehydrate a snapshot MIG without a semantic adapter (P151)."""
        mig = cls(adapter=None)
        mig._module_ports = {}
        for mod, raw_ports in (data or {}).get("module_ports", {}).items():
            mig._module_ports[mod] = {
                name: PortInfo(
                    name=p.get("name", name), direction=p.get("direction", ""),
                    width=tuple(p.get("width") or (0, 0)),
                    internal_signal=p.get("internal_signal", ""),
                    module_type=p.get("module_type", ""),
                )
                for name, p in (raw_ports or {}).items()
            }
        for iid, raw in (data or {}).get("instances", {}).items():
            ports = {}
            for name, p in (raw.get("ports") or {}).items():
                width = tuple(p.get("width") or (0, 0))
                ports[name] = PortInfo(
                    name=p.get("name", name), direction=p.get("direction", ""),
                    width=width,
                    internal_signal=p.get("internal_signal", ""),
                    module_type=p.get("module_type", ""),
                )
            mig.instances[iid] = ModuleInstanceNode(
                id=raw.get("id", iid), module_type=raw.get("module_type", ""),
                parent=raw.get("parent"), ports=ports,
            )
        return mig

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


@dataclass
class PathSearchResult:
    """有界路径枚举的结果 (P158.2)。

    Attributes:
        paths: 找到的路径 (可能为空)
        truncated: 是否因预算耗尽而**不完整**
        truncation_reason: 截断原因 (max_paths_reached / max_depth_reached /
            max_expansions_reached / deadline_reached); 未截断时为 ""
        expansions: 实际 DFS 展开次数 (work 计量)
        mode: "data" (directed, 只走 DRIVER/CONNECTION) 或 "structural" (无向)
    """

    paths: list[list[str]] = field(default_factory=list)
    truncated: bool = False
    truncation_reason: str = ""
    expansions: int = 0
    mode: str = "structural"


class _SearchBudget:
    """路径枚举的 work budget + wall-clock deadline (P158.2)。

    只做**记账**: 谁耗尽了预算、为什么耗尽。截断必须显式可见,
    不允许静默 cap。

    原因优先级 (硬预算 > 软上限):
      1. `deadline_reached`     — wall-clock 超时 (搜索被中止)
      2. `max_expansions_reached` — work budget 耗尽 (搜索被中止)
      3. `max_paths_reached`    — 结果数收满, 但确认还有更多路径
      4. `max_depth_reached`    — 深度上限剪掉分支 (可能漏路径)
    """

    #: 硬预算 (中止搜索) 优先于软上限 (剪枝/收满)
    _HARD = ("deadline_reached", "max_expansions_reached")
    _SOFT = ("max_paths_reached", "max_depth_reached")

    def __init__(self, max_expansions: int, deadline: float | None,
                 max_paths: int, max_depth: int):
        self.max_expansions = max_expansions
        self.deadline = deadline
        self.max_paths = max_paths
        self.max_depth = max_depth
        self.expansions = 0
        self._reasons: set[str] = set()
        self._start = time.monotonic()

    def note(self, reason: str) -> None:
        """记录截断原因 (可多个; 优先级见类 docstring)。"""
        self._reasons.add(reason)

    @property
    def reason(self) -> str:
        """返回优先级最高的截断原因 (空串 = 未截断)。"""
        for candidate in self._HARD + self._SOFT:
            if candidate in self._reasons:
                return candidate
        if self.deadline is not None and time.monotonic() > self.deadline:
            return "deadline_reached"
        return ""

    @property
    def exhausted(self) -> bool:
        """预算是否耗尽 (work budget 或 wall-clock deadline)。"""
        if self.expansions >= self.max_expansions:
            self.note("max_expansions_reached")
            return True
        if self.deadline is not None and time.monotonic() > self.deadline:
            self.note("deadline_reached")
            return True
        return False

    @property
    def truncated(self) -> bool:
        return bool(self.reason)


class PathResolver:
    """跨模块路径解析器

    协调 SignalGraph 和 ModuleInstanceGraph
    实现跨模块边界路径查找

    [P158.1] 两种模式语义**不同**, 由 edge 契约区分 (见
    `trace.core.graph.contracts`):

    - `directed=True`  → **数据路径**: 只走 data 边 (DRIVER / CONNECTION)。
      CLOCK / RESET / BIT_SELECT / MEMBER_SELECT 一律不走 → `clk → ready_q`
      不再被判为数据路径 (SEMANTIC_CONTRACTS §2.2)。
    - `directed=False` → **结构连通性**: 走全部硬件信号边 (data + control +
      structural), 双向。回答"图上是否连通", **不能**用来证明数据关系。
    """

    def __init__(self, signal_graph, module_graph: ModuleInstanceGraph):
        self.signal_graph = signal_graph
        self.module_graph = module_graph

    # ------------------------------------------------------------------
    # edge 契约 (P158.1) —— 唯一实现, 不在命令里另写一份
    # ------------------------------------------------------------------
    def _allowed_edge_kinds(self, directed: bool) -> frozenset:
        """该模式下允许穿越的 edge kind 集合。

        [P158.1] 引用 contracts 的唯一实现 (运行时读取, 不复制常量值) ——
        这样 edge 契约只有一个真源, 改契约即刻对所有消费者生效。
        """
        if directed:
            return contracts.DATA_EDGE_KINDS
        return contracts.SIGNAL_EDGE_KINDS

    def _neighbors(self, node: str, directed: bool = False) -> list[str]:
        """统一的邻接定义。

        无向模式 (默认, `directed=False`): successors + predecessors ——
        回答**结构连通性**。

        有向模式 (`directed=True`): 只走 successors, 且**不**做 MIG 虚拟跳转 ——
        SignalGraph 本身已含跨模块端口边 (父网 ↔ 实例端口), 与 `dataflow analyze`
        走同一张有向图, 因此两者结论一致 (iter_268)。

        [P158.1] 两种模式都**按 edge kind 过滤**:
        - directed 只走 data 边 (DRIVER/CONNECTION) → 不是数据路径的边被排除;
        - undirected 走全部硬件信号边 (含 CLOCK/RESET/BIT_SELECT),
          语义是结构连通性, 调用方必须标注 mode。

        [iter_237] 旧实现里 `find_path` 走 successors+predecessors + 进模块映射, 而
        `find_all_paths` 只走 successors → 两者结论互相矛盾。现在两个入口共用本方法。
        """
        allowed = self._allowed_edge_kinds(directed)
        out: list[str] = []
        try:
            succ = list(self.signal_graph.successors(node))
        except (KeyError, nx.NetworkXError) as _e:
            logger.debug("图无后继 (正常): %s", _e)
            succ = []
        out.extend(self._filter_neighbors(node, succ, allowed, forward=True))

        if directed:
            return out

        try:
            pred = list(self.signal_graph.predecessors(node))
        except (KeyError, nx.NetworkXError) as _e:
            logger.debug("图无前驱 (正常): %s", _e)
            pred = []
        out.extend(self._filter_neighbors(node, pred, allowed, forward=False))
        # [iter_272] MIG 虚拟跳 (进/出模块) 已删除:
        # 图恒为实例级, 跨模块端口边本来就在 SignalGraph 里; 而 MIG 的
        # 旧实现会把端口映射到"模块定义命名空间"的影子 id (不在图里); 单一命名
        # 空间后端口 id 就是图节点, 这两跳
        # 只会把遍历导向不存在的节点。
        return out

    def _filter_neighbors(self, node: str, candidates: list[str],
                          allowed: frozenset, forward: bool = True) -> list[str]:
        """保留与 `node` 之间存在**允许 kind** 的边的邻居。

        `forward=True`  → 边方向是 node → cand (successors)
        `forward=False` → 边方向是 cand → node (predecessors)

        注意: 一对节点之间可能有多种 kind 的边 (如 CONNECTION + DRIVER),
        只要**存在**一条允许 kind 的边就算连通; 但若某邻居只靠
        CLOCK/RESET/BIT_SELECT 边连接, 则在 directed 模式下被排除。
        """
        out: list[str] = []
        for cand in candidates:
            src, dst = (node, cand) if forward else (cand, node)
            try:
                edges = self.signal_graph.get_edges(src, dst)
            except (KeyError, nx.NetworkXError) as _e:
                logger.debug("取边失败 (正常): %s", _e)
                continue
            if any(getattr(e, "kind", None) in allowed for e in edges):
                out.append(cand)
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
                       max_depth: int = 60, directed: bool = False,
                       max_expansions: int = 200_000,
                       deadline: float | None = None) -> list[list[str]]:
        """枚举 src → dst 的所有简单路径 (与 `find_path` 共用邻接定义)。

        [P158.2] 枚举**必须有界**: `max_expansions` (work budget) + 可选
        `deadline` (wall-clock 秒)。耗尽时**不静默截断** —— 用
        `find_all_paths_detailed` 拿 `truncated` / `truncation_reason`。

        Args:
            max_paths: 结果上限 (有环图里防爆)
            max_depth: 单条路径最大节点数
            directed: True = 数据路径 (只走 data 边); False = 结构连通性
            max_expansions: DFS 展开次数上限 (work budget)
            deadline: wall-clock 截止时间 (monotonic 秒); None = 不限时
        """
        return self.find_all_paths_detailed(
            src, dst, max_paths=max_paths, max_depth=max_depth,
            directed=directed, max_expansions=max_expansions, deadline=deadline,
        ).paths

    def find_all_paths_detailed(
        self, src: str, dst: str, max_paths: int = 50,
        max_depth: int = 60, directed: bool = False,
        max_expansions: int = 200_000,
        deadline: float | None = None,
    ) -> "PathSearchResult":
        """有界枚举 src → dst 的所有简单路径, 并显式报告截断。

        [P158.2] SEMANTIC_CONTRACTS §3: 超限**不能**伪装成 `found:false` ——
        必须返回 `truncated:true` + `truncation_reason`。

        截断原因 (三选一, 互斥, 按发生顺序):
          - `max_paths_reached`   : 找到的路径数达到 `max_paths`
          - `max_depth_reached`   : 某条路径超过 `max_depth` (可能还有更长路径)
          - `max_expansions_reached`: DFS 展开次数耗尽 (work budget)
          - `deadline_reached`    : 超过 wall-clock deadline
        """
        paths: list[list[str]] = []
        # [iter_268] 与 find_path 一致: 端点就是用户给的 dst, 不做影子节点规范化。
        state = _SearchBudget(max_expansions=max_expansions, deadline=deadline,
                              max_paths=max_paths, max_depth=max_depth)
        self._dfs_paths(src, dst, paths, state, directed)
        return PathSearchResult(
            paths=paths,
            truncated=state.truncated,
            truncation_reason=state.reason,
            expansions=state.expansions,
            mode="data" if directed else "structural",
        )

    def _dfs_paths(self, src: str, dst: str, paths: list[list[str]],
                   state: "_SearchBudget", directed: bool) -> None:
        """DFS 枚举简单路径 (work budget 受限)。

        [P158.2] 收满 `max_paths` 后**继续搜索**: 只有确认还有更多路径时
        才标记 `max_paths_reached` —— 否则"恰好 N 条"会被误报成截断。

        Args:
            src/dst: 端点 (路径必须以 dst 结尾)
            paths: 结果收集器 (原地追加)
            state: 预算记账器
            directed: True = 数据路径 (只走 data 边)
        """
        def _dfs(current: str, path: list[str], visited: set) -> None:
            if state.exhausted:
                return
            if len(path) > state.max_depth:
                # 深度上限: 可能有更长的路径没被枚举 → 截断可见
                state.note("max_depth_reached")
                return
            if current == dst and len(path) > 1:
                if len(paths) < state.max_paths:
                    paths.append(path.copy())
                else:
                    # 已经收满 max_paths, 又找到一条 → 确实还有更多路径
                    state.note("max_paths_reached")
                return
            for nxt in self._neighbors(current, directed=directed):
                if state.exhausted:
                    return
                state.expansions += 1
                if state.exhausted:
                    return
                if nxt in visited:
                    continue
                visited.add(nxt)
                path.append(nxt)
                _dfs(nxt, path, visited)
                path.pop()
                visited.discard(nxt)

        _dfs(src, [src], {src})
