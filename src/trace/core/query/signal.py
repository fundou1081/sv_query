# ==============================================================================
# query_signal.py - Simplified Signal Query
# ==============================================================================

from dataclasses import dataclass

from ..graph.models import DriverInfo, EdgeKind, NodeKind, SignalGraph, TraceNode


@dataclass
class SignalChain:
    root: str
    drivers: list[TraceNode]
    loads: list[TraceNode]
    confidence: str


@dataclass
class DriverChain:
    """带详细信息的驱动链"""

    root: str
    drivers: list[DriverInfo]  # [方案C] 使用 DriverInfo 替代 TraceNode
    loads: list[TraceNode]
    confidence: str


class SignalTracer:
    def __init__(self, graph: SignalGraph, mig: object | None = None, use_mig: bool = True):
        """[PR3 2026-06-15] Init SignalTracer.

        Args:
            graph: SignalGraph
            mig: ModuleInstanceGraph (optional) - 跨模块 port 映射.
                 设 None 时走纯 graph 路径 (兼容旧调用).
                 设非 None 时, _collect_all_* 会在 0 results 时 fallback 走 MIG.
            use_mig: 启戆4 MIG fallback. 默认 True. 设 False 走纯 graph 路径.
        """
        self.graph = graph
        # [PR3 2026-06-15] ModuleInstanceGraph 是跨模块 port 映射.
        # 接受了 2569 个 clean port_to_internal 映射 (pulp axi_xbar_dp_ram).
        self.mig = mig
        self.use_mig = use_mig

    def trace(self, signal: str, module: str = None) -> SignalChain:
        """Trace signal drivers and loads"""
        signal_id = self._make_id(signal, module)

        # [铁律3] 不可信则不输出 - 节点不存在时返回 uncertain
        if signal_id not in self.graph.nodes():
            return SignalChain(root=signal_id, drivers=[], loads=[], confidence="uncertain")

        drivers = self._collect_all_drivers(signal_id)
        loads = self._find_loads(signal_id)

        # [铁律3] 无驱动时返回 uncertain
        confidence = "high" if drivers else "uncertain"

        return SignalChain(root=signal_id, drivers=drivers, loads=loads, confidence=confidence)

    def _make_id(self, signal: str, module: str = None) -> str:
        # [方案B修正] 如果 signal 包含 '.',检查是否以 module. 开头
        if module and "." in signal:
            # 如果已经以 module. 开头,认为是完整路径
            if signal.startswith(f"{module}."):
                return signal
            # 否则添加 module 前缀 (相对路径)
            return f"{module}.{signal}"
        if module:
            return f"{module}.{signal}"
        return signal

    def _collect_all_drivers(self, signal_id: str, max_depth: int | None = None) -> list[TraceNode]:
        """[P2] 递归收集所有驱动,包括实例端口追溯

        Args:
            signal_id: signal ID
            max_depth: None=无限递归, N=最多递归 N 层
        """
        drivers = []
        seen_ids = set()
        self._trace_drivers_recursive(signal_id, drivers, seen_ids, current_depth=0, max_depth=max_depth)
        # [PR3 2026-06-15] MIG fallback: graph 0 drivers 时走 MIG port 映射.
        # 场景: signal 是 wrapper PORT_OUT, graph 里无内部 driver 边,
        # 但 MIG 知道该 port 实际连到哪个 instance port (跨 module 边界).
        if not drivers and self.use_mig and self.mig:
            mig_drivers = self._find_drivers_via_mig(signal_id)
            for d in mig_drivers:
                if d.id not in seen_ids:
                    drivers.append(d)
                    seen_ids.add(d.id)
        return drivers

    def _trace_drivers_recursive(
        self,
        signal_id: str,
        drivers: list[TraceNode],
        seen_ids: set,
        current_depth: int = 0,
        max_depth: int | None = None,
    ):
        """递归追溯驱动

        Args:
            signal_id: 当前信号 ID
            drivers: 结果列表(inout)
            seen_ids: 已访问节点集合(inout)
            current_depth: 当前递归深度
            max_depth: None=无限递归, N=最多递归 N 层
        """
        # depth 限制检查
        if max_depth is not None and current_depth >= max_depth:
            return

        if signal_id not in self.graph.nodes():
            return

        # [方案B修正] 如果当前节点没有 incoming DRIVER 边, 检查 BIT_SELECT 子节点
        # 例如查询 'm' (modport实例) 时, 如果 'm' 没有直接驱动, 查找 'm.*' 子节点
        has_driver_edge = any(
            edge.kind == EdgeKind.DRIVER and dst == signal_id
            for src, dst, edge in [(e[0], e[1], self.graph.get_edge(e[0], e[1])) for e in self.graph.edges()]
        )
        if not has_driver_edge:
            # 查找 BIT_SELECT 子节点 (child → this_node)
            for src, dst in list(self.graph.edges()):
                if dst == signal_id:
                    edge = self.graph.get_edge(src, dst)
                    if edge and edge.kind == EdgeKind.BIT_SELECT:
                        # 子节点有驱动
                        if src not in seen_ids:
                            self._trace_drivers_recursive(src, drivers, seen_ids, current_depth, max_depth)

        # [FIX 2026-06-11] 跨 module boundary: 当 target 是 module def PORT_OUT
        # 且 0 driver 时, wrapper module 实际是 port mapping, 没内部 assign.
        # 查 port_to_internal 反向找所有 instance port, 递归追它们的 driver.
        # 例: axi_ram_wr_rd_if.s_axi_awready (wrapper) ← axi_dp_ram.a_if.s_axi_awready (instance)
        #                                 ← axi_dp_ram.b_if.s_axi_awready (另一个 instance)
        if not has_driver_edge and hasattr(self.graph, "_port_to_internal"):
            current_node = self.graph.get_node(signal_id)
            if current_node and current_node.kind.name == "PORT_OUT":
                pti = self.graph._port_to_internal
                # 反向查: 找所有 instance port 映射到当前 module def port
                instance_ports = [k for k, v in pti.items() if v == signal_id]
                for inst_port_id in instance_ports:
                    if inst_port_id in self.graph.nodes() and inst_port_id not in seen_ids:
                        # 递归到 instance port, 让它的 DRIVER 边起作用
                        self._trace_drivers_recursive(
                            inst_port_id, drivers, seen_ids, current_depth + 1, max_depth
                        )

        # 标记当前节点已访问
        seen_ids.add(signal_id)

        # 遍历所有指向这个 signal 的边
        for src, dst in list(self.graph.edges()):
            if dst == signal_id:
                # [NEW] 自环 (state = state) 应该被记录为驱动
                if src == dst:
                    node = self.graph.get_node(src)
                    if node:
                        drivers.append(node)
                    continue

                edge = self.graph.get_edge(src, dst)
                # [FIX 2026-06-11] get_edge 只返第 1 条, 可能是 CONNECTION (优先级高).
                # 但 trace 查 driver 优先看 DRIVER 边. 如果同 (src, dst) 有 DRIVER 边,
                # 用 DRIVER (e.g. wrapper_passthrough 跟 CONNECTION 同时存在).
                if edge and edge.kind != EdgeKind.DRIVER:
                    all_edges = self.graph.get_edges(src, dst)
                    driver_edge = next((e for e in all_edges if e.kind == EdgeKind.DRIVER), None)
                    if driver_edge:
                        edge = driver_edge
                # [FIX] 只接受 DRIVER 边作为驱动
                if edge and edge.kind != EdgeKind.DRIVER:
                    # CONNECTION 边:检查 src 是否是实例端口
                    if edge.kind == EdgeKind.CONNECTION:
                        node = self.graph.get_node(src)
                        if node:
                            parts = src.split(".")
                            # 实例输出端口 (PORT_OUT): 透明驱动映射点
                            if len(parts) >= 3 and node.kind.name == "PORT_OUT":
                                if node.id not in seen_ids:
                                    drivers.append(node)
                                    seen_ids.add(node.id)
                                # 追溯到外部驱动: 找到实例输入端口并递归追溯
                                inst_path = ".".join(parts[:-1])
                                port_name = parts[-1]
                                input_port_id = (
                                    f"{inst_path}.d"
                                    if port_name == "q"
                                    else f"{inst_path}.q"
                                    if port_name == "d"
                                    else None
                                )
                                if input_port_id and input_port_id in self.graph.nodes():
                                    if input_port_id not in seen_ids:
                                        self._trace_drivers_recursive(
                                            input_port_id, drivers, seen_ids, current_depth + 1, max_depth
                                        )
                                # [FIX 2026-06-11] wrapper-aware 跨 instance:
                                # 如果 src 是 wrapper module 的 instance port, 跨到 wrapper
                                # 其他 instance port, 让它们的 deep driver 链起作用.
                                # 例: src=axi_dp_ram.a_if.s_axi_awready (axi_ram_wr_rd_if instance)
                                #   跨到 axi_dp_ram.b_if.s_axi_awready (另一个 axi_ram_wr_rd_if instance)
                                #   axi_ram_wr_rd_if 是 wrapper (0 internal driver), b_if 内部有 deep
                                #   axi_ram_wr_if_inst.s_axi_awready (通过 _elaborate_wrapper_passthroughs 加边).
                                # 避免乱跨: 只跨到 kind=PORT_OUT (output 端口, backpressure 关键)
                                if (
                                    current_node_check := self.graph.get_node(src)
                                ) and current_node_check.kind.name == "PORT_OUT" and hasattr(self.graph, "_port_to_internal"):
                                    def_port = self.graph._port_to_internal.get(src)
                                    if def_port:
                                        # 找 def_port 0 driver (wrapper 标识)
                                        def_has_driver = any(
                                            e.kind == EdgeKind.DRIVER
                                            for u in self.graph.predecessors(def_port)
                                            for e in self.graph._edge_data.get((u, def_port), [])
                                        )
                                        if not def_has_driver:
                                            # 跨到 def_port 的其他 instance ports
                                            for k, v in self.graph._port_to_internal.items():
                                                if v == def_port and k != src:
                                                    if k in self.graph.nodes() and k not in seen_ids:
                                                        self._trace_drivers_recursive(
                                                            k, drivers, seen_ids, current_depth + 1, max_depth
                                                        )
                                continue
                            # PORT_IN via CONNECTION: 只有外部输入端口(无predecessors)才添加
                            if node.kind.name == "PORT_IN":
                                preds = list(self.graph.predecessors(node.id))
                                if not preds:  # 外部输入端口,无前驱
                                    if node.id not in seen_ids:
                                        drivers.append(node)
                                        seen_ids.add(node.id)
                                continue
                            # SIGNAL via CONNECTION: 中间线网,添加为驱动
                            if node.kind.name == "SIGNAL":
                                if node.id not in seen_ids:
                                    drivers.append(node)
                                    seen_ids.add(node.id)
                                continue
                    # 其他边类型继续递归追溯
                    if src in self.graph.nodes() and src not in seen_ids:
                        self._trace_drivers_recursive(src, drivers, seen_ids, current_depth + 1, max_depth)
                    continue

                node = self.graph.get_node(src)
                # [FIX] 字面量节点(CONST)不继续追溯(它是叶子节点)
                # 但如果它还没有被添加为驱动,则添加到结果
                if node and node.kind == NodeKind.CONST:
                    if node.id not in seen_ids:
                        drivers.append(node)
                        seen_ids.add(node.id)
                    continue

                if node and node.id not in seen_ids:
                    drivers.append(node)

                # 继续递归追溯这个 src 的驱动(DRIVER 边)
                # seen_ids 检查在函数开头进行,防止环路
                if src in self.graph.nodes() and src not in seen_ids:
                    self._trace_drivers_recursive(src, drivers, seen_ids, current_depth + 1, max_depth)

    def _find_drivers(self, signal_id: str) -> list[TraceNode]:
        """[兼容] 直接驱动"""
        if signal_id not in self.graph.nodes():
            return []

        drivers = []
        for src, dst in list(self.graph.edges()):
            if dst == signal_id:
                node = self.graph.get_node(src)
                if node:
                    drivers.append(node)
        return drivers

    # [PR3 2026-06-15] Binary garbage filter — 跟 L1 一致, 防止 MIG 返回 binary
    # names 污染 trace 结果.
    _BINARY_PATTERNS = ('', '<id:binary>', '_anon_', '_bad_', '_bin_')

    def _is_binary_name(self, name: str | None) -> bool:
        """检查是否是 binary garbage name (pyslang pybind11 decode 随机失败产物)."""
        if not name:
            return True
        n = str(name).strip()
        return n in self._BINARY_PATTERNS

    def _find_loads_via_mig(self, signal_id: str) -> list[TraceNode]:
        """[PR3 2026-06-15] 用 MIG 跨模块 port 映射找 loads.

        当 signal_id 是 module def port 或 instance port 时, MIG 可能知道
        对应的 internal signal (例如 'top.u_dut.clk' → 'dut.clk') 或反之.
        返回 graph 中存在的对应 node.

        Returns:
            list of TraceNode, 可能为空 (如果 MIG 不知道该信号或 mapping 不在 graph)
        """
        if not self.mig:
            return []
        loads: list[TraceNode] = []
        seen = set()

        # 1. 前向: signal_id → internal signal (例如 wrapper port → module def port)
        try:
            internal = self.mig.get_internal_signal(signal_id)
        except Exception:
            internal = None

        if internal and not self._is_binary_name(internal) and internal != signal_id:
            if internal in self.graph.nodes() and internal not in seen:
                node = self.graph.get_node(internal)
                if node:
                    loads.append(node)
                    seen.add(internal)

        # 2. 反向: 找所有 mapping 到 signal_id 的 instance ports
        #    (例如 'top.u_dut.clk' → 'dut.clk', 反向 'dut.clk' → 'top.u_dut.clk')
        try:
            pti = getattr(self.mig, "port_to_internal", {})
            for inst_port, int_sig in pti.items():
                if int_sig == signal_id and not self._is_binary_name(inst_port):
                    if inst_port in self.graph.nodes() and inst_port not in seen:
                        node = self.graph.get_node(inst_port)
                        if node:
                            loads.append(node)
                            seen.add(inst_port)
        except Exception:
            pass

        return loads

    def _find_drivers_via_mig(self, signal_id: str) -> list[TraceNode]:
        """[PR3 2026-06-15] 用 MIG 跨模块 port 映射找 drivers (反向).

        Returns:
            list of TraceNode, 可能为空
        """
        if not self.mig:
            return []
        drivers: list[TraceNode] = []
        seen = set()

        # 反向: signal_id 是 instance port 时, 找它被谁驱动
        # signal_id 例如 'top.u_dut.clk' (instance port)
        # MIG 知道 internal 是 'dut.clk' (module def port)
        try:
            internal = self.mig.get_internal_signal(signal_id)
        except Exception:
            internal = None

        if internal and not self._is_binary_name(internal) and internal != signal_id:
            # internal 是 module def port, 找它的 driver (in graph)
            if internal in self.graph.nodes() and internal not in seen:
                node = self.graph.get_node(internal)
                if node:
                    drivers.append(node)
                    seen.add(internal)
            # 同时反向查所有 instance port mapping 到该 internal (其他 instance 可能驱动同一 internal)
            try:
                pti = getattr(self.mig, "port_to_internal", {})
                for inst_port, int_sig in pti.items():
                    if int_sig == internal and not self._is_binary_name(inst_port):
                        if inst_port in self.graph.nodes() and inst_port not in seen:
                            node = self.graph.get_node(inst_port)
                            if node:
                                drivers.append(node)
                                seen.add(inst_port)
            except Exception:
                pass

        return drivers

    def _find_loads(self, signal_id: str, allowed_kinds: set | None = None) -> list[TraceNode]:
        if signal_id not in self.graph.nodes():
            return []

        loads = []
        seen_ids = set()

        # [ADD 2026-06-11 Req-12] 默认 None 走 DRIVER+CONNECTION; 指定 allowed_kinds 则照走
        if allowed_kinds is None:
            allowed_kinds = {EdgeKind.DRIVER, EdgeKind.CONNECTION}

        for succ in self.graph.successors(signal_id):
            edge = self.graph.get_edge(signal_id, succ)
            if edge and edge.kind not in allowed_kinds:
                continue
            node = self.graph.get_node(succ)
            if node and node.id not in seen_ids:
                loads.append(node)
                seen_ids.add(node.id)

        return loads

    def _collect_all_loads(self, signal_id: str, max_depth: int | None = None, allowed_kinds: set | None = None) -> list[TraceNode]:
        """递归收集所有后继(被这个信号驱动的所有节点)

        Args:
            signal_id: 信号 ID
            max_depth: None=无限递归, N=最多递归 N 层
            allowed_kinds: [Req-12] 允许的边类型集合, None=默认 DRIVER+CONNECTION
        """
        loads = []
        seen_ids = set()
        if allowed_kinds is None:
            allowed_kinds = {EdgeKind.DRIVER, EdgeKind.CONNECTION}
        self._trace_loads_recursive(signal_id, loads, seen_ids, current_depth=0, max_depth=max_depth, allowed_kinds=allowed_kinds)
        # [PR3 2026-06-15] MIG fallback: graph 0 loads 时走 MIG port 映射.
        # 场景: signal 是 wrapper PORT_IN, graph 里没出边,
        # 但 MIG 知道它被哪个 instance port 驱动.
        if not loads and self.use_mig and self.mig:
            mig_loads = self._find_loads_via_mig(signal_id)
            for l in mig_loads:
                if l.id not in seen_ids:
                    loads.append(l)
                    seen_ids.add(l.id)
        return loads

    def _trace_loads_recursive(
        self,
        signal_id: str,
        loads: list[TraceNode],
        seen_ids: set,
        current_depth: int = 0,
        max_depth: int | None = None,
        allowed_kinds: set | None = None,
    ):
        """递归追溯负载(被 signal_id 驱动的节点)

        Args:
            signal_id: 当前信号 ID
            loads: 结果列表(inout)
            seen_ids: 已访问节点集合(inout)
            current_depth: 当前递归深度
            max_depth: None=无限递归, N=最多递归 N 层
            allowed_kinds: [Req-12] 允许的边类型集合, None=默认 DRIVER+CONNECTION
        """
        if max_depth is not None and current_depth >= max_depth:
            return
        if signal_id in seen_ids:
            return
        if signal_id not in self.graph.nodes():
            return
        seen_ids.add(signal_id)

        if allowed_kinds is None:
            allowed_kinds = {EdgeKind.DRIVER, EdgeKind.CONNECTION}

        for src, dst in list(self.graph.edges()):
            if src == signal_id:
                edge = self.graph.get_edge(src, dst)
                if edge and edge.kind not in allowed_kinds:
                    continue
                node = self.graph.get_node(dst)
                if node and node.id not in seen_ids:
                    loads.append(node)
                if dst in self.graph.nodes():
                    self._trace_loads_recursive(dst, loads, seen_ids, current_depth + 1, max_depth)

    def trace_fanout(
        self,
        signal: str,
        module: str = None,
        depth: int | None = None,
        include_clock: bool = False,
        include_reset: bool = False,
        include_control: bool = False,
    ) -> list[TraceNode]:
        """Trace signal fanout (loads driven by this signal)

        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct loads only, N=recursive N levels, None=recursive all
            include_clock: [Req-12 Issue 19] True 时包含 CLOCK 边 (sensitivity list)
            include_reset: [Req-12 Issue 19] True 时包含 RESET 边
            include_control: [Req-12 Issue 19] True 时包含 CONTROL 边 (always 块引用)

        默认只走 DRIVER + CONNECTION 边. 要看全部边, 用 visualize graph.
        """
        signal_id = self._make_id(signal, module)
        if signal_id not in self.graph.nodes():
            return []
        # [ADD 2026-06-11 Req-12] 计算要包含的边类型
        allowed_kinds = {EdgeKind.DRIVER, EdgeKind.CONNECTION}
        if include_clock:
            allowed_kinds.add(EdgeKind.CLOCK)
        if include_reset:
            allowed_kinds.add(EdgeKind.RESET)
        if include_control:
            allowed_kinds.add(EdgeKind.CONTROL)
        # depth=1 用 _find_loads 过滤
        if depth == 1:
            return self._find_loads(signal_id, allowed_kinds=allowed_kinds)
        return self._collect_all_loads(signal_id, max_depth=depth, allowed_kinds=allowed_kinds)

    def trace_fanin(self, signal: str, module: str = None, depth: int | None = None) -> list[TraceNode]:
        """Trace signal fanin (drivers of this signal)

        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all
        """
        signal_id = self._make_id(signal, module)
        if depth == 1:
            return self._find_drivers(signal_id)
        return self._collect_all_drivers(signal_id, max_depth=depth)

    def trace_fanin_detailed(self, signal: str, module: str = None, depth: int | None = None) -> list[DriverInfo]:
        """[方案C] Trace signal fanin with detailed driver information

        返回 DriverInfo 列表,包含 condition, clock_domain 等详细信息

        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all

        Returns:
            List[DriverInfo] - 驱动信息列表
        """
        signal_id = self._make_id(signal, module)

        # 获取所有驱动节点
        driver_nodes = self.trace_fanin(signal_id, depth=depth)

        # 构建 driver_id -> DriverInfo 的映射
        driver_infos = []
        seen_ids = set()

        for node in driver_nodes:
            if node.id in seen_ids:
                continue
            seen_ids.add(node.id)

            # 获取边的信息
            edge = self.graph.get_edge(node.id, signal_id)

            # [P3-6-FIX] 当 edge 不存在时，说明 node 不是直接驱动 signal_id
            # 需要尝试从 node 追溯到 signal_id 的完整路径获取表达式
            expression = ""
            condition = ""
            clock_domain = ""
            assign_type = ""

            if edge:
                expression = edge.expression
                condition = edge.condition
                clock_domain = edge.clock_domain
                assign_type = edge.assign_type

                # [P1-3 完整表达式] 如果 expression 等于驱动节点 ID 本身,
                # 递归查找该节点的驱动源作为完整表达式
                if expression == node.id or expression.startswith(node.id + "["):
                    full_expr = self._resolve_full_expression(node.id)
                    if full_expr:
                        expression = full_expr
            else:
                # [FIX] edge 不存在时的处理
                # 情况1: node 是字面量，尝试解析其完整表达式
                # 情况2: node 是中间节点，尝试从其到 signal_id 的路径获取信息

                # 首先尝试 _resolve_full_expression
                full_expr = self._resolve_full_expression(node.id)
                if full_expr:
                    expression = full_expr
                elif node.id.startswith("4'b") or node.id.startswith("1'b"):
                    # 字面量节点直接用自己作为表达式
                    expression = node.id

                # 尝试从 node 的驱动边获取 condition
                # 遍历 node 的入边，找到 DRIVER 边
                for src, dst in self.graph.edges():
                    if dst == node.id:
                        node_edge = self.graph.get_edge(src, dst)
                        if node_edge and node_edge.kind.name == "DRIVER":
                            if node_edge.condition:
                                condition = node_edge.condition
                            if node_edge.clock_domain:
                                clock_domain = node_edge.clock_domain
                            if node_edge.assign_type:
                                assign_type = node_edge.assign_type
                            break

            driver_info = DriverInfo(
                node=node,
                condition=condition,
                clock_domain=clock_domain,
                assign_type=assign_type,
                distance=1,  # TODO: 计算实际距离
                expression=expression,
                bit_slice=edge.bit_slice if edge else "",
                target_signal=signal_id,  # [P3-6] 目标信号用于组装完整语句
            )
            driver_infos.append(driver_info)

        # [P3-3] 补全缺失的 clock_domain：通过后继节点的 CLOCK 边反推
        self._infer_clock_reset_for_drivers(signal_id, driver_infos)

        return driver_infos

    def _infer_clock_reset_for_drivers(self, signal_id: str, driver_infos: list[DriverInfo]):
        """ "通过后继节点的 CLOCK/RESET 边反推时钟和复位信息

        如果 DriverInfo 的 clock_domain 为空，通过检查 signal_id 的后继节点
        的 CLOCK/RESET 边来推断时钟域信息。

        Args:
            signal_id: 信号 ID
            driver_infos: DriverInfo 列表 (inout，会被修改)
        """
        # 查找 signal_id 的后继节点的时钟
        inferred_clock = None
        inferred_reset = None

        for succ in self.graph.successors(signal_id):
            for src, dst in self.graph.edges():
                if dst == succ:
                    edge = self.graph.get_edge(src, dst)
                    if edge:
                        if edge.kind.name == "CLOCK" and not inferred_clock:
                            inferred_clock = edge.clock_domain
                        elif edge.kind.name == "RESET" and not inferred_reset:
                            inferred_reset = edge.condition
                    if inferred_clock and inferred_reset:
                        break
            if inferred_clock and inferred_reset:
                break

        # 更新所有 clock_domain 为空的 DriverInfo
        for di in driver_infos:
            if not di.clock_domain and inferred_clock:
                di.clock_domain = inferred_clock
            if not di.reset_condition and inferred_reset:
                di.reset_condition = inferred_reset

    def _resolve_full_expression(self, signal_id: str) -> str:
        """递归解析完整表达式

        如果 signal_id 被另一个信号驱动,查找该信号的完整表达式。
        例如: sreg_q 驱动源是 sreg_d,sreg_d 的完整表达式是 {rx, sreg_q[10:1]}

        Args:
            signal_id: 信号 ID

        Returns:
            完整表达式字符串,如果找不到则返回空
        """
        # 避免递归循环
        visited = set()
        return self._resolve_expr_recursive(signal_id, visited)

    def _resolve_expr_recursive(self, signal_id: str, visited: set) -> str:
        """递归解析表达式 (内部方法)"""
        if signal_id in visited or signal_id.startswith(tuple("0123456789")):
            return ""
        visited.add(signal_id)

        # 查找驱动这个信号的边
        for src, dst in self.graph.edges():
            if dst == signal_id:
                edge = self.graph.get_edge(src, dst)
                if edge and edge.kind.name == "DRIVER":
                    expr = edge.expression if edge else ""

                    # 如果是占位符表达式 (来自 graph_builder 的 str(rhs_expr))
                    # 尝试递归查找更完整的表达式
                    if "Expression(" in expr or expr == src:
                        if expr == src:
                            # expression 等于 src,继续递归查找更完整的表达式
                            recursive_expr = self._resolve_expr_recursive(src, visited)
                            if recursive_expr and "Expression(" not in recursive_expr:
                                return recursive_expr
                        # 如果找不到更好的,返回原 expression
                        return expr

                    # 如果 expression 不是字面量,直接返回
                    if expr and not expr.startswith(tuple("0123456789\"'")):
                        return expr
                    return expr
        return ""

    def trace_detailed(self, signal: str, module: str = None) -> DriverChain:
        """[方案C] Trace signal with detailed driver information

        返回带详细驱动信息的 SignalChain

        Args:
            signal: signal name
            module: module name (optional, for relative paths)

        Returns:
            DriverChain - 包含 DriverInfo 列表
        """
        signal_id = self._make_id(signal, module)

        if signal_id not in self.graph.nodes():
            return DriverChain(root=signal_id, drivers=[], loads=[], confidence="uncertain")

        driver_infos = self.trace_fanin_detailed(signal_id)
        loads = self._find_loads(signal_id)

        confidence = "high" if driver_infos else "uncertain"

        return DriverChain(root=signal_id, drivers=driver_infos, loads=loads, confidence=confidence)
