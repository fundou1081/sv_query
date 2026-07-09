# ==============================================================================
# graph_builder.py - Builder Layer
# ==============================================================================

from __future__ import annotations

import logging

import pyslang

from .base import PyslangAdapter
from .builder.subroutine_expander import SubroutineExpander
from .clock_domain_extractor import ClockDomainExtractor  # [P1 cycle 9c] re-export 保兼容
from .connection_extractor import ConnectionExtractor  # [P1 cycle 9b] re-export 保兼容
from .driver_extractor import DriverExtractor  # [P1 cycle 8] re-export 保兼容
from .extractor_models import ExtractorResult  # [P1 cycle 9] 共享 (避免循环 import)
from .graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode
from .load_extractor import LoadExtractor  # [P1 cycle 9] re-export 保兼容

logger = logging.getLogger(__name__)

# [P1 cycle 9] ExtractorResult 移到了 extractor_models.py
# 这里 re-export 保持向后兼容 (from trace.core.graph_builder import ExtractorResult)
__all__ = [
    "ExtractorResult",
    "GraphBuilder",
    "DriverExtractor",
    "LoadExtractor",
    "ConnectionExtractor",
    "ClockDomainExtractor",
]

class GraphBuilder:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.graph = SignalGraph()
        self._extractors = {
            "driver": DriverExtractor(adapter),
            "load": LoadExtractor(adapter),
            "connection": ConnectionExtractor(adapter),
            "clock": ClockDomainExtractor(adapter),
        }
        # SubroutineExpander for function/task call expansion
        self._subroutine_expander = SubroutineExpander(adapter)
        # [FIX] Track struct members for expansion
        # Key: struct variable id (e.g., "module.pkt2")
        # Value: set of member names (e.g., {"addr", "data", "valid"})
        self._struct_members: dict[str, set[str]] = {}

    def build(self) -> SignalGraph:
        self._extract_all_nodes()
        self._extract_all_edges()
        self._mark_special_signals()
        self._create_hierarchical_bit_nodes()
        self._collect_struct_members()  # [NEW] Collect struct member information
        self._expand_struct_assignments()  # [NEW] Expand struct assignments to member assignments
        self._upgrade_reg_nodes()  # Must be after _create_hierarchical_bit_nodes
        # [FIX 2026-06-11] Wrapper module port mapping pass:
        # wrapper module (e.g. axi_ram_wr_rd_if) 内部 instance 的 port (e.g. axi_ram_wr_if)
        # 通过 .s_axi_awready(s_axi_awready) port mapping 接到 wrapper 自己的 port.
        # graph builder 只跑了顶层 elaboration, 缺这层. 加 post-process pass 补上.
        self._elaborate_wrapper_passthroughs()

        return self.graph

    def _collect_struct_members(self):
        """收集所有 struct 变量的成员信息

        通过分析节点名模式 xxx.member 来识别 struct 类型变量的成员。
        例如: test_interface.pkt1.addr, test_interface.pkt1.data 等。

        启发式: 如果一个路径如 test_interface.pkt1 存在，且有子节点如
        test_interface.pkt1.addr/test_interface.pkt1.data，则 test_interface.pkt1 是 struct。
        """
        import re

        # 先收集所有可能的 (parent, member) 对
        potential_members = []
        for node_id in list(self.graph.nodes()):
            # 匹配 xxx.member 模式
            match = re.match(r"^(.+)\.([^.]+)$", node_id)
            if match:
                parent_path = match.group(1)  # e.g., test_interface.pkt1
                member_name = match.group(2)  # e.g., addr, data, valid
                potential_members.append((parent_path, member_name))

        # 找所有可能是 struct 变量的路径
        # 条件: parent_path 本身也是一个节点，且有多个成员
        parent_counts = {}
        for parent_path, member_name in potential_members:
            if parent_path not in parent_counts:
                parent_counts[parent_path] = set()
            parent_counts[parent_path].add(member_name)

        # 只有当 parent_path 本身也是一个节点时，才认为它是 struct
        for parent_path, members in parent_counts.items():
            if parent_path in self.graph.nodes() and len(members) > 1:
                # parent_path 是一个节点，且有多个成员，它可能是 struct
                self._struct_members[parent_path] = members

        # [DEBUG]
        # print(f"[DEBUG] _collect_struct_members: {self._struct_members}")

    def _expand_struct_assignments(self):
        """展开 struct 整体赋值为成员赋值

        当检测到 assign dst = src 时（src 是已知的 struct 类型，dst 也应该是同类型的 struct），
        自动展开为: assign dst.member = src.member (对每个成员)

        这确保了 dataflow 可以追踪: data_in → pkt1.data → pkt2.data → data_out
        """

        # 找出需要展开的 struct 整体赋值
        # 边类型是 DRIVER，且 src 是已知的 struct 变量
        edges_to_expand = []

        for src_id, dst_id in list(self.graph.edges()):
            edge = self.graph.get_edge(src_id, dst_id)
            if not edge or edge.kind != EdgeKind.DRIVER:
                continue

            # 检查 src 是否是 struct 变量
            src_is_struct = src_id in self._struct_members and len(self._struct_members.get(src_id, set())) > 1

            if src_is_struct:
                # src 是 struct，检查 dst 是否也是 struct
                # 如果 dst 不是 struct，我们仍需要展开（dst 通过赋值继承了 src 的类型）
                dst_is_struct = dst_id in self._struct_members and len(self._struct_members.get(dst_id, set())) > 1
                members = self._struct_members[src_id]

                # 如果 dst 不是 struct，注册它
                if not dst_is_struct:
                    self._struct_members[dst_id] = set(members)

                edges_to_expand.append((src_id, dst_id, members))

        # 为每个 struct 整体赋值，展开为成员赋值
        for src_struct, dst_struct, members in edges_to_expand:
            for member in members:
                src_member_id = f"{src_struct}.{member}"
                dst_member_id = f"{dst_struct}.{member}"

                # 确保成员节点存在
                if src_member_id not in self.graph.nodes():
                    src_node = self.graph.get_node(src_struct)
                    if src_node:
                        self.graph.add_trace_node(
                            TraceNode(
                                id=src_member_id,
                                name=member,
                                module=src_node.module,
                                kind=NodeKind.SIGNAL,
                                width=src_node.width,
                            )
                        )

                if dst_member_id not in self.graph.nodes():
                    dst_node = self.graph.get_node(dst_struct)
                    if dst_node:
                        self.graph.add_trace_node(
                            TraceNode(
                                id=dst_member_id,
                                name=member,
                                module=dst_node.module,
                                kind=NodeKind.SIGNAL,
                                width=dst_node.width,
                            )
                        )

                # 创建成员赋值边: src.member → dst.member
                # 检查边是否已存在
                existing = self.graph.get_edge(src_member_id, dst_member_id)
                if not existing:
                    edge = TraceEdge(
                        src=src_member_id,
                        dst=dst_member_id,
                        kind=EdgeKind.DRIVER,
                        assign_type=edge.assign_type,
                        expression=f"{src_struct}.{member}",
                    )
                    self.graph.add_trace_edge(edge)

        # [NEW] 为所有 struct 变量创建 MEMBER_SELECT 边
        # 类似 BIT_SELECT: data_out.data → data_out
        # 这允许从成员追溯到父 struct
        for struct_id, members in self._struct_members.items():
            if struct_id not in self.graph.nodes():
                continue

            for member in members:
                member_id = f"{struct_id}.{member}"
                if member_id in self.graph.nodes():
                    # 检查 MEMBER_SELECT 边是否已存在
                    existing = self.graph.get_edge(member_id, struct_id)
                    if not existing:
                        member_edge = TraceEdge(
                            src=member_id,
                            dst=struct_id,
                            kind=EdgeKind.BIT_SELECT,  # 复用 BIT_SELECT 类型
                            assign_type="internal",
                            expression=member,
                        )
                        self.graph.add_trace_edge(member_edge)

    def _create_hierarchical_bit_nodes(self):
        """方案C: 为位选择节点创建父子关系
        - 识别 data[3] 形式的节点
        - 创建/找到父节点 data
        - 设置 child.parent = data
        - 创建聚合边 data[3] → data (BIT_SELECT)
        - 重命名边: 所有引用 data[3] 的边保持不变
        """
        import re

        child_ids = [nid for nid in list(self.graph.nodes()) if "[" in nid and "]" in nid]

        for child_id in child_ids:
            # 提取父节点名: top.data[3] → top.data
            parent_id = re.sub(r"\[.*?\]", "", child_id)

            if not parent_id or parent_id == child_id:
                continue

            # 确保父节点存在
            if parent_id not in self.graph.nodes():
                # 从子节点推断父节点属性
                child_node = self.graph.get_node(child_id)
                if child_node:
                    parent_name = re.sub(r"\[.*?\]", "", child_node.name)
                    parent_node = TraceNode(
                        id=parent_id,
                        name=parent_name,
                        module=child_node.module,
                        kind=child_node.kind,
                        width=child_node.width,
                    )
                    self.graph.add_trace_node(parent_node)

            # 设置子节点的 parent
            child_node = self.graph.get_node(child_id)
            if child_node:
                child_node.parent = parent_id
                # Don't change kind here - it was set during DriverExtractor based on always_ff assignment
                # Just ensure it has a kind
                if child_node.kind is None:
                    child_node.kind = NodeKind.SIGNAL

            # 创建聚合边: child → parent (BIT_SELECT)
            agg_edge = TraceEdge(
                src=child_id,
                dst=parent_id,
                kind=EdgeKind.BIT_SELECT,
            )
            self.graph.add_trace_edge(agg_edge)

    def get_extractor(self, name: str) -> object | None:
        return self._extractors.get(name)

    def _extract_all_nodes(self):
        for _name, extractor in self._extractors.items():
            result = extractor.extract()
            for node in result.nodes:
                self.graph.add_trace_node(node)

    def _extract_all_edges(self):
        for _name, extractor in self._extractors.items():
            result = extractor.extract()
            for edge in result.edges:
                self.graph.add_trace_edge(edge)
            # 收集 port_to_internal 映射
            if hasattr(result, "port_to_internal") and result.port_to_internal:
                self.graph._port_to_internal.update(result.port_to_internal)
            # [FIX 2026-07-08] 同步收集 port_to_module_type (semantic short name)
            if hasattr(result, "port_to_module_type") and getattr(result, "port_to_module_type", None):
                if not hasattr(self.graph, "_port_to_module_type"):
                    self.graph._port_to_module_type = {}
                self.graph._port_to_module_type.update(result.port_to_module_type)

        # [P0-3] 设置 interface 信号的 modport_dir
        self._set_interface_modport_dirs()

    def _set_interface_modport_dirs(self):
        """设置 interface 信号的 modport_dir 属性

        [P2] 同时为未被驱动的 interface 信号创建 placeholder 节点
        """
        # Build interface_ports map for each module
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)

            interface_ports = {}  # port_name -> (interface_name, modport_name)
            interface_signals = {}  # (port_name, signal_name) -> direction

            try:
                # [FIX] Navigate through InstanceSymbol -> body -> definition -> syntax
                # InstanceSymbol doesn't have direct 'header' attribute
                module_header = None
                if hasattr(module, "body") and module.body:
                    definition = getattr(module.body, "definition", None)
                    if definition and hasattr(definition, "syntax") and definition.syntax:
                        module_header = getattr(definition.syntax, "header", None)

                if module_header and hasattr(module_header, "ports") and hasattr(module_header.ports, "ports"):
                    for item in module_header.ports.ports:
                        if not hasattr(item, "kind") or item.kind != pyslang.SyntaxKind.ImplicitAnsiPort:
                            continue
                        try:
                            h = getattr(item, "header", None)
                            decl = getattr(item, "declarator", None)
                        except AttributeError:
                            continue
                        if h is None or decl is None:
                            continue
                        if hasattr(h, "kind") and "InterfacePortHeader" in str(h.kind):
                            port_name = decl.name.value if hasattr(decl.name, "value") else str(decl.name)
                            interface_name = None
                            if hasattr(h, "nameOrKeyword"):
                                nk = h.nameOrKeyword
                                interface_name = nk.rawText if hasattr(nk, "rawText") else str(nk)
                            modport_name = None
                            if hasattr(h, "modport") and hasattr(h.modport, "member"):
                                member_val = h.modport.member
                                modport_name = member_val.name if hasattr(member_val, "name") else str(member_val)
                            if port_name and interface_name:
                                interface_ports[port_name.strip()] = (interface_name, modport_name)

                                # 获取该 modport 的所有信号及其方向
                                modport_signals = self.adapter.get_interface_modport_signals(
                                    interface_name, modport_name
                                )
                                for sig_name, sig_dir in modport_signals.items():
                                    interface_signals[(port_name.strip(), sig_name)] = sig_dir
            except (ValueError, AttributeError, TypeError):
                pass

            # For each node in the graph that's in this module
            existing_interface_signals = set()
            for node_id, node in self.graph._node_data.items():
                if node.module != module_name:
                    continue

                # Check if node is an interface signal (e.g., "top.m.data")
                # node_id format: module.port.signal
                if "." in node_id:
                    parts = node_id.split(".")
                    # port is the second part (index 1): e.g., 'm' from 'top.m.data'
                    if len(parts) >= 2 and parts[1] in interface_ports:
                        port_name = parts[1]
                        # signal is the third part (index 2): e.g., 'data' from 'top.m.data'
                        signal_name = parts[2] if len(parts) >= 3 else parts[1]
                        interface_name, modport_name = interface_ports[port_name]

                        # Get signal direction from interface
                        signal_dir = self.adapter.get_interface_modport_signals(interface_name, modport_name).get(
                            signal_name
                        )
                        if signal_dir:
                            node.modport_dir = signal_dir
                            existing_interface_signals.add((port_name, signal_name))

            # [P2] 为未被驱动的 interface 信号创建 placeholder 节点
            for (port_name, signal_name), signal_dir in interface_signals.items():
                if (port_name, signal_name) in existing_interface_signals:
                    continue

                node_id = f"{module_name}.{port_name}.{signal_name}"
                if node_id in self.graph._node_data:
                    continue

                # 创建 placeholder 节点
                from trace.core.graph.models import NodeKind, TraceNode

                placeholder = TraceNode(
                    id=node_id, name=signal_name, module=module_name, kind=NodeKind.SIGNAL, width=(0, 0)
                )
                placeholder.modport_dir = signal_dir
                self.graph.add_trace_node(placeholder)

    def _upgrade_reg_nodes(self):
        """Upgrade node kind to REG if it's driven by a CLOCK edge.
        Only upgrade the direct target, NOT bit-select parents."""
        for (_src, dst), edges in self.graph._edge_data.items():
            # [FIX] edges 是 List[TraceEdge]，需要遍历
            for edge in edges:
                if edge.kind == EdgeKind.CLOCK:
                    # Only upgrade the direct target
                    if "[" not in dst:  # Not a bit-select
                        node = self.graph._node_data.get(dst)
                        if node and node.kind != NodeKind.REG:
                            was_port = getattr(node, "is_port", False)
                            node.kind = NodeKind.REG
                            if was_port:
                                node.is_port = True

    def _elaborate_wrapper_passthroughs(self):
        """[FIX 2026-06-11] 补充 wrapper module 内部 port mapping 边.

        问题: graph builder 只 elaboration 顶层 (top module 跟直接子 instance).
        wrapper module (e.g. axi_ram_wr_rd_if) 内部 instance 的 port (e.g. axi_ram_wr_if_inst.s_axi_awready)
        通过 .s_axi_awready(s_axi_awready) 接到 wrapper 自己的 port (axi_ram_wr_rd_if.s_axi_awready).
        这条边没建, 导致 trace 跨 wrapper 边界时找不到 leaf driver.

        修复 heuristic: 对每个 module def 的 PORT_OUT node:
        1. 找所有 instance 化它的 parent instance (pti 反向)
        2. 在每个 instance 内部 (path = parent_inst_path), 找跟 wrapper port 同名 port 的 deep instance port
        3. 加 DRIVER 边: deep_port → wrapper_def_port (在 parent_inst scope)

        实际生成: DRIVER 边 from "axi_dp_ram.b_if.axi_ram_wr_if_inst.s_axi_awready"
        to "axi_ram_wr_rd_if.s_axi_awready"

        [FIX 2026-07-08] 治本后: port_to_internal 是 self-loop, 反向查只能找到
        instance 自己. 改为查 port_to_module_type (semantic short name) —
        多个 instance 共享同一 def_port 名字, 能找齐 instance paths.
        """
        from collections import defaultdict

        pti = self.graph._port_to_internal
        ptt = getattr(self.graph, "_port_to_module_type", {})

        # 1. 对每个 module def port (短名), 找 instance 化它的所有 instance paths
        #    reverse_ptt[def_port_short] = [instance_port_1, instance_port_2, ...]
        reverse_ptt = defaultdict(list)
        for inst_port, def_port_short in ptt.items():
            reverse_ptt[def_port_short].append(inst_port)
        # 合并旧的 pti reverse (如果 def_port short 不在 ptt 中)
        for inst_port, def_port_short in pti.items():
            if inst_port not in ptt and def_port_short not in reverse_ptt:
                reverse_ptt[def_port_short].append(inst_port)

        added_edges = 0
        # 2. 对每个 module def port
        for def_port, inst_ports in reverse_ptt.items():
            # 只处理 module def port (PORT_OUT, kind.name='PORT_OUT')
            def_node = self.graph._node_data.get(def_port)
            if not def_node or def_node.kind.name != "PORT_OUT":
                continue
            logger.debug(f"_elab_wrapper: PROCESSING {def_port} (inst_ports={len(inst_ports)})")

            # 检查 def_port 是否已经有 driver (避免重复加)
            has_driver = any(
                edge.kind == EdgeKind.DRIVER
                for edges in self.graph._edge_data.values()
                for edge in edges
                if edge.dst == def_port or (isinstance(edges, list) and any(e.dst == def_port for e in edges))
            )
            # 上面的检查比较脆弱, 用 predecessors 更稳
            if def_port in self.graph._node_data:
                preds = list(self.graph.predecessors(def_port))
                if any(
                    self.graph._edge_data.get((p, def_port), [None])[0]
                    and self.graph._edge_data[(p, def_port)][0].kind == EdgeKind.DRIVER
                    for p in preds if (p, def_port) in self.graph._edge_data
                ):
                    continue

            # def_port 格式: "module_name.port_name"
            if "." not in def_port:
                continue
            def_module, port_name = def_port.rsplit(".", 1)

            # 3. 对每个 instance 化 wrapper 的 instance, 找 wrapper 内部 deep port
            for inst_port in inst_ports:
                # inst_port 格式: "parent.inst_name.port_name"
                if "." not in inst_port:
                    continue
                # instance 路径 (parent.inst_name)
                inst_path = inst_port.rsplit(".", 1)[0]
                # 在 inst_path 内部, 找跟 port_name 同名的 deep port
                # 即: f"{inst_path}.{sub_inst}.{port_name}" 或更深
                # 用 graph 节点前缀搜索
                prefix = f"{inst_path}."
                for node_id in self.graph._node_data:
                    if not node_id.startswith(prefix):
                        continue
                    if node_id == inst_port:
                        continue
                    # 检查末尾是否是 port_name
                    if not node_id.endswith(f".{port_name}"):
                        continue
                    # 是 deep port: inst_path.sub_inst.port_name
                    # 检是不是 instance port (kind=PORT_OUT/IN) — wrapper 内部 sub_inst 的 port
                    deep_node = self.graph._node_data[node_id]
                    if deep_node.kind.name not in ("PORT_OUT", "PORT_IN"):
                        continue
                    # 加 DRIVER 边: deep_port → def_port
                    # 在 graph 上加边: deep_port 是实际 driver, def_port 是 wrapper module def
                    # 但 trace 时, def_port 还需要追到 instance_port (via pti reverse)
                    # 所以 trace 看到 def_port 时追到 inst_port (实际 signal = deep_port 的 inst scope)
                    # 加边: deep_port → inst_port (在 inst 内部)
                    # 这样 trace: top → inst_port → wrapper_def_port (DRIVER 边) → deep_port (DRIVER 边) → leaf
                    # 注意: ConnectionExtractor 可能已加 CONNECTION 边 (assign_type=connection) for 同一 (src,dst).
                    # 这里加 DRIVER 边 (assign_type=wrapper_passthrough). 二者不冲突.
                    from .graph.models import TraceEdge
                    already_has_driver = any(
                        e.kind == EdgeKind.DRIVER
                        for e in self.graph._edge_data.get((deep_node.id, inst_port), [])
                    )
                    if not already_has_driver:
                        self.graph.add_trace_edge(TraceEdge(
                            src=deep_node.id,
                            dst=inst_port,
                            kind=EdgeKind.DRIVER,
                            assign_type="wrapper_passthrough",
                        ))
                        added_edges += 1

        logger.debug(f"_elaborate_wrapper_passthroughs: added {added_edges} passthrough edges")

    def _mark_special_signals(self):
        for _node_id, node in self.graph._node_data.items():
            name_lower = node.name.lower()

            if "clk" in name_lower or "clock" in name_lower:
                node.is_clock = True

            if "rst" in name_lower or "reset" in name_lower:
                node.is_reset = True

    def stats(self) -> dict:
        return {"nodes": self.graph.number_of_nodes(), "edges": self.graph.number_of_edges(), **self.graph.stats()}


# ==============================================================================
# [补丁] 修复多事件敏感信号列表的时钟提取 (2026-05-09)
# 原因: 27690eb commit 删除了 _extract_reset_from_event_ctrl,导致
#       @(posedge clk_a or negedge rst_a_n) 只能提取到 clk_a
# ==============================================================================
