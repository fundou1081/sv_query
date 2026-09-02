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
    def __init__(self, adapter: PyslangAdapter, target_module: str | None = None):
        """[Phase 3 2026-07-11] GraphBuilder + target_module filter.

        Args:
            adapter: PyslangAdapter (semantic AST)
            target_module: [NEW] If set, extractors use this as root_module_name
                           instead of auto-detected first top instance. This ensures
                           instance paths in SignalGraph use user-specified target.
        """
        self.adapter = adapter
        self.target_module = target_module  # [Phase 3]
        self.graph = SignalGraph()
        self._extractors = {
            "driver": DriverExtractor(adapter),
            "load": LoadExtractor(adapter),
            "connection": ConnectionExtractor(adapter, root_module_name=target_module),
            "clock": ClockDomainExtractor(adapter),
        }
        # Propagate target_module to other extractors that might need it
        for ext in self._extractors.values():
            if hasattr(ext, 'set_target_module'):
                ext.set_target_module(target_module)
        # SubroutineExpander for function/task call expansion
        self._subroutine_expander = SubroutineExpander(adapter)
        # [FIX] Track struct members for expansion
        # Key: struct variable id (e.g., "module.pkt2")
        # Value: set of member names (e.g., {"addr", "data", "valid"})
        self._struct_members: dict[str, set[str]] = {}

    def build(self) -> SignalGraph:
        # [Phase 4 2026-07-11] If target_module set, walk target's instance tree
        # to find (instance_path, instance_symbol) pairs. Pass to DriverExtractor
        # so it emits signal IDs with full instance paths (e.g.,
        # 'darksocv.bridge0.core0.REGS' instead of 'darkriscv.REGS').
        if self.target_module:
            self._configure_instance_paths()

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

        # [Phase 3 2026-07-11] If target_module set, drop type-level nodes
        # that don't belong to target's hierarchy. Without this filter,
        # DriverExtractor emits nodes like "darkriscv.XRES" (module type +
        # signal name) which confuse pipeline/timing rendering.
        if self.target_module:
            self._filter_by_target()

        # [V16.11 2026-08-18] 抓 pyslang GenerateBlock{Array} → assign LHS base signal 映射
        # 替代 V16.10.3 的启发式: 直接从源码读 generate block 真实 label
        self._capture_generate_block_map()

        return self.graph

    def _capture_generate_block_map(self):
        """[V16.11.1 2026-08-18] Capture pyslang GenerateBlockArray/GenerateBlock.name → LHS base signal mapping.

        V16.10.3 用启发式 (信号名 bufN → gen_stageN):
          - 仅凑巧对 case29 有效 (3 个 generate block 恰好叫 gen_stage1/2/3)
          - 对 case27 (gen_accum 块, acc[] 信号) 完全失败: 0 个 genblk 分组

        V16.11 用 pyslang native API 真读 GenerateBlockArray.name (for-loop 型):
          - 遍历 target_top.body 找 GenerateBlockArray.name (e.g. 'gen_accum', 'gen_stage1')
          - 遍历 entries → ContinuousAssign → assignment.left (ElementSelect) → .value.symbol.name
          - 存入 graph._gen_block_map: {signal_short_name → gen_block_real_label}

        V16.11.1 扩展 (case30/case31):
          - 新增 GenerateBlock (if/case 型) 处理 — case30/31 的 generate 不是 Array, 直接 iterate item
          - 新增 NamedValue LHS 支持 — case30/31 的 LHS 是简单信号 (e.g. result) 而非 ElementSelect (e.g. buf[i])

        用法: viz_data_builder 把 graph._gen_block_map 复制到 viz.meta.datapath.gen_block_map,
             elk_bridge 用真值替代启发式归位.
        """
        def _extract_lhs_base_signal(left_expr):
            """从 LHS 表达式提取 base signal 短名.

            支持三种 pyslang LHS 形态:
            - ElementSelect (arr[i]): case27/29 for-loop generate 内的 buf[i+1]
              → left.value.symbol (NamedValue→NetSymbol)
            - NamedValue (x): case30/31 if/case generate 内的 result = ...
              → left.symbol (NetSymbol) 或 left.expression.symbol
            - 其他 (e.g. HierarchicalReference 链): 防御性 fallback 拿名字
            """
            if left_expr is None:
                return ''
            kind_str = str(getattr(left_expr, 'kind', ''))
            sym = None
            if 'ElementSelect' in kind_str:
                base = getattr(left_expr, 'value', None) or getattr(left_expr, 'base', None)
                if base is not None:
                    sym = getattr(base, 'symbol', None)
            elif 'NamedValue' in kind_str:
                sym = getattr(left_expr, 'symbol', None)
                if sym is None:
                    expr = getattr(left_expr, 'expression', None)
                    if expr is not None:
                        sym = getattr(expr, 'symbol', None)
            if sym is None:
                return ''
            sig_name = getattr(sym, 'name', '') or ''
            if not sig_name:
                sig_name = str(sym).strip().strip()
            return sig_name

        def _extract_lhs_constant_index(left_expr):
            """[V16.14 F-N3 2026-08-19] 从 ElementSelect.selector 提取 élaboré constant index.

            pyslang 11.x 在 semantic AST 中会 fold genvar 表达式到 constant. 例如:
              case27 src: assign acc[i+1] = acc[i] + prod; (genvar i loop)
              entry[0].selector.constant = 1   (i=0 → 0+1=1)
              entry[1].selector.constant = 2
              ...
            通过 left.selector.constant 拿 constant, 转 int 返. 失败返 None.
            """
            if left_expr is None:
                return None
            if 'ElementSelect' not in str(getattr(left_expr, 'kind', '')):
                return None
            sel = getattr(left_expr, 'selector', None)
            if sel is None:
                return None
            cv = getattr(sel, 'constant', None)
            if cv is None:
                return None
            try:
                if hasattr(cv, 'integer'):
                    return int(cv.integer)
                if hasattr(cv, 'value'):
                    return int(cv.value)
                return int(str(cv))
            except (TypeError, ValueError):
                return None

        try:
            target_top = self._find_target_top(self.target_module or '')
            if target_top is None:
                return
            target_module = self.target_module or ''

            # [V16.11 2026-08-18] 1st pass: GenerateBlockArray (for-loop 型)
            # entries[i].sub 里的 ContinuousAssign, case27/29 都走这条路
            for item in target_top.body:
                kind = str(getattr(item, 'kind', ''))
                if 'GenerateBlockArray' not in kind:
                    continue
                gb_name = getattr(item, 'name', '')
                if not gb_name:
                    continue
                entries = getattr(item, 'entries', None)
                if not entries:
                    continue
                for entry_idx, entry in enumerate(entries):
                    for sub in entry:
                        sk = str(getattr(sub, 'kind', ''))
                        if 'ContinuousAssign' not in sk and 'Assign' not in sk:
                            continue
                        asg = getattr(sub, 'assignment', None)
                        if asg is None:
                            continue
                        left = getattr(asg, 'left', None)
                        sig_name = _extract_lhs_base_signal(left)
                        if not sig_name:
                            continue
                        # [V16.14 F-N3 2026-08-19] 提取 LHS element constant index (pyslang selector.constant)
                        # 并存 _gen_iter_map. key 策略:
                        #  - 有 constant (case27): 用 per-element key 'acc[1]', 'acc[2]'.
                        #    elk_bridge 顶层按 dst_short='acc[1]' 查 → entry_idx=0,
                        #    'acc[2]' → entry_idx=1 → 4 个独立 cluster (gen_accum i=0/1/2/3)
                        #  - 无 constant (case30 NamedValue 'result' / case29 退化): 仍存 base 名,
                        #    case29 里所有 sub-iter (chain_out dst) 都查到 base 'buf3' → entry_idx=0,
                        #    累加语义由 viz_data_builder regex 提供 (gen_stage1 i=0/1/2)
                        const_idx = _extract_lhs_constant_index(left)
                        self.graph._gen_block_map[sig_name] = gb_name
                        if const_idx is not None:
                            # per-element key (case27 主路径)
                            full_pattern = f'{sig_name}[{const_idx}]'
                            self.graph._gen_iter_map[full_pattern] = entry_idx
                            # 总是也存 base (兼容 case30 NamedValue 退化路径)
                            self.graph._gen_iter_map.setdefault(sig_name, entry_idx)
                        else:
                            # NamedValue / 其他 (case30/31 result, case29 buffer buf3 退化)
                            self.graph._gen_iter_map.setdefault(sig_name, entry_idx)

            # [V16.11.2 2026-08-18] 2nd pass: GenerateBlock (if/case 型, case30/case31)
            # 不是 GenerateBlockArray, 直接 iterate item 拿 sub
            # 优雅修复: 用 pyslang 原生 isUninstantiated 过滤 inactive branch
            # (case30 MODE=1 时 gen_subtractor.isUninstantiated=True → skip)
            # (case31 SEL=2 时 gen_adder/gen_default isUninstantiated=True → skip)
            for item in target_top.body:
                kind = str(getattr(item, 'kind', ''))
                if 'GenerateBlockArray' in kind:
                    continue  # 已在 1st pass 处理
                if 'GenerateBlock' not in kind:
                    continue
                # [V16.11.2] pyslang 提供 isUninstantiated 属性优雅区分 active vs inactive branch
                if getattr(item, 'isUninstantiated', False):
                    continue  # inactive branch: pyslang 已经决定排除, 不 capture
                gb_name = getattr(item, 'name', '')
                if not gb_name:
                    continue
                try:
                    for sub in item:
                        sk = str(getattr(sub, 'kind', ''))
                        if 'ContinuousAssign' not in sk and 'Assign' not in sk:
                            continue
                        asg = getattr(sub, 'assignment', None)
                        if asg is None:
                            continue
                        sig_name = _extract_lhs_base_signal(getattr(asg, 'left', None))
                        if not sig_name:
                            continue
                        self.graph._gen_block_map[sig_name] = gb_name
                except Exception as e:
                    logger.warning("gen_block 映射写入失败: %s", e)

            import sys
            if self.graph._gen_block_map:
                print(
                    f"[V16.11.1] captured {len(self.graph._gen_block_map)} generate block labels: "
                    f"{dict(list(self.graph._gen_block_map.items())[:5])}{'...' if len(self.graph._gen_block_map) > 5 else ''}",
                    file=sys.stderr,
                )
        except Exception as e:
            # [P0 核实 2026-08-29] 失败显式记录 (原 print 调试残留)
            logger.warning("_capture_generate_block_map failed: %s", e)

    def _configure_instance_paths(self):
        """[Phase 4 2026-07-11] Walk target instance tree, configure extractors.

        Builds a list of (instance_path, instance_symbol) pairs for all instances
        within the user-specified target. Passes to DriverExtractor so signal
        IDs include full instance paths.

        [iter_113 修复] generate 分支必须真正下钻到 entry 内的实例:
        旧实现 GenerateBlockArray → walk(entry=GenerateBlock, path), 而 walk 只认
        inst.body — GenerateBlockSymbol 是 scope 无 .body → 永不下钻 → generate 内
        实例 (cordic.genblk1[i].U / toplevel.u_cla.generators[i].u_cell4) 从未进
        driver paths → 实例内部逻辑 (always/assign) 零提取 (CLA 摸底缺口:
        toplevel.cout 无驱动; inst==type 时 connection 侧再叠递归假节点)。
        iter_109 的 get_modules collect_instances 只覆盖无-target 旧路径。

        修复: generate 块内实例用 child.hierarchicalPath 作为完整路径 (pyslang
        自动带 target 前缀 + generate 块名/索引, 如 'cordic.genblk1[0].U' /
        'toplevel.u_cla.generators[2].u_cell4') — 与 connection extractor
        (get_module_instances hp 路径) 命名一致, 两边节点才对得上。
        """
        try:
            target_top = self._find_target_top(self.target_module)
            if target_top is None:
                return

            paths = []

            def walk(inst, path):
                paths.append((path, inst))
                body = getattr(inst, 'body', None)
                if body is None:
                    return
                try:
                    for child in body:
                        kind = str(getattr(child, 'kind', ''))
                        # [iter_112] 门级原语是叶子, 不进 driver paths
                        if 'PrimitiveInstance' in kind:
                            continue
                        # [GAP-2] InstanceArray 含 'Instance' 子串, 须先于普通实例
                        if 'GenerateBlockArray' in kind:
                            entries = getattr(child, 'entries', None) or list(child)
                            for entry in entries:
                                if 'GenerateBlock' in str(getattr(entry, 'kind', '')):
                                    _walk_gen_block(entry)
                        elif 'GenerateBlock' in kind:
                            _walk_gen_block(child)
                        elif 'InstanceArray' in kind:
                            # 数组实例元素各有独立 hp (含 [k]) — 逐个下钻
                            elements = getattr(child, 'elements', None) or list(child)
                            for elem in elements:
                                if 'Instance' in str(getattr(elem, 'kind', '')) \
                                        and 'PrimitiveInstance' not in str(getattr(elem, 'kind', '')):
                                    _walk_inst(elem)
                        elif 'Instance' in kind:
                            try:
                                name = str(child.name)
                            except Exception:
                                name = '_anon'
                            walk(child, f"{path}.{name}")
                except Exception as e:
                    logger.warning("gen_block 映射写入失败: %s", e)

            def _hp(child):
                """generate 块内实例的完整路径 (hp, 含 generate 块名+索引)."""
                try:
                    hp = getattr(child, 'hierarchicalPath', None)
                    if hp:
                        return str(hp)
                except (UnicodeDecodeError, TypeError):
                    pass
                try:
                    return f"{getattr(child, 'name', '_anon')}"
                except Exception:
                    return '_anon'

            def _walk_inst(inst_sym):
                """用 hp 路径下钻实例 (generate entry 内 / 数组元素)."""
                walk(inst_sym, _hp(inst_sym))

            def _walk_gen_block(block):
                """下钻 GenerateBlock(Array entry) 的实例 children (含嵌套 generate).

                GenerateBlockSymbol 是 semantic scope, 直接 __iter__ 得成员;
                实例用其 hierarchicalPath (如 'cordic.genblk1[0].U') 全路径,
                不再拼 path.name (会丢 generate 块名/索引段)。
                """
                try:
                    for sub in block:
                        sk = str(getattr(sub, 'kind', ''))
                        if 'PrimitiveInstance' in sk:
                            continue
                        if 'InstanceArray' in sk:
                            elements = getattr(sub, 'elements', None) or list(sub)
                            for elem in elements:
                                if 'Instance' in str(getattr(elem, 'kind', '')) \
                                        and 'PrimitiveInstance' not in str(getattr(elem, 'kind', '')):
                                    _walk_inst(elem)
                        elif 'GenerateBlockArray' in sk:
                            for entry in (getattr(sub, 'entries', None) or list(sub)):
                                if 'GenerateBlock' in str(getattr(entry, 'kind', '')):
                                    _walk_gen_block(entry)
                        elif 'GenerateBlock' in sk:
                            _walk_gen_block(sub)
                        elif 'Instance' in sk:
                            _walk_inst(sub)
                except Exception as e:
                    logger.warning("generate 块下钻失败: %s", e)

            walk(target_top, self.target_module)

            # Pass to DriverExtractor
            driver = self._extractors.get('driver')
            if driver is not None and hasattr(driver, 'set_instance_paths'):
                driver.set_instance_paths(paths)

            import sys
            print(
                f"[Phase 4] target={self.target_module!r}: "
                f"configured {len(paths)} instance paths for DriverExtractor",
                file=sys.stderr,
            )
        except Exception as e:
            # [P0 核实 2026-08-29] 失败显式记录 (原 print 调试残留)
            logger.warning("_configure_instance_paths failed: %s", e)

    def _find_target_top(self, target_module: str):
        """[Phase 4 2026-07-11] Find target in topInstances."""
        try:
            # [D5] v11 always has topInstances on RootSymbol
            root = self.adapter.root
            if not root or not root.topInstances:
                return None
            for top in root.topInstances:
                try:
                    if str(top.name) == target_module:
                        return top
                except Exception:
                    continue
        except Exception as e:
            logger.warning("generate 遍历失败: %s", e)
        return None

    def _drop_literal_nodes(self):
        """[REVERTED 2026-07-11 Phase 4] Don't drop CONST nodes.

        Original fix tried to drop CONST (literal) nodes from graph, but this
        broke 14 regression tests that depend on edges like '8'd0 -> ifc.data'.

        Instead, fix should be at viz layer: skip CONST nodes when rendering DOT.
        See pipeline_viz.py / timing_analyzer.py / dataflow_viz.py.

        Kept as no-op for backward compat.
        """

    def _filter_by_target(self):
        """[Phase 3 2026-07-11] Drop nodes whose path doesn't start with target.

        Strategy:
        - KEEP: nodes where node_id starts with '{target}.'
        - KEEP: nodes where node_id == '{target}' (top-level)
        - KEEP: literal/constant nodes (no '.', or starts with digit)
        - DROP: type-level nodes like 'darkriscv.XRES' (when 'darkriscv' != target
                and 'darkriscv' isn't a sub-instance of target)

        We use a simple heuristic: if node_id contains '.' and first segment
        is NOT target and NOT a known sub-instance path within target, drop it.
        """
        target = self.target_module
        # Collect all instance paths within target via pyslang
        target_sub_paths = set()
        target_sub_paths.add(target)
        try:
            from .semantic_adapter import SemanticAdapter
            sa = SemanticAdapter(self.adapter.root, target_module=target)
            for inst in sa.get_module_instances():
                sym = getattr(inst, '_symbol', None)
                if sym:
                    try:
                        hp = str(sym.hierarchicalPath)
                        if hp:
                            target_sub_paths.add(hp)
                    except Exception as e:
                        logger.warning("hierarchicalPath 提取失败: %s", e)
        except Exception as e:
            logger.warning("子路径遍历失败: %s", e)

        # Filter nodes
        nodes_to_drop = []
        for node_id in list(self.graph.nodes()):
            if not isinstance(node_id, str) or not node_id:
                continue
            # [FIX 2026-07-11] Drop CONST (literal) nodes — they're noise.
            # add_trace_edge creates CONST nodes for literals like '4'b1011',
            # '32'd3735928559', '0', '1' which clutter dataflow/timing/chain DOTs.
            # These should stay as edge attributes, not graph nodes.
            # [Phase 8 / Fix F 2026-7-14] KEEP CONST (literal) nodes in graph
            # Reason: trace_fanin queries need literal drivers (e.g., picorv32.trap
            # drivers = [0, 1] from RHS literals). Dropping them causes fanin=0.
            # Viz layer (pipeline_viz.py / dataflow_viz.py) already filters CONST
            # nodes from DOT rendering to avoid clutter, so graph can keep them.
            # (Removed the unconditional CONST drop here.)
            # [Phase 8 / Fix F 2026-7-14] KEEP literal/constant nodes per docstring intent
            # Strategy: nodes without "." or starting with digit are literal-like.
            # These are needed as driver endpoints for trace_fanin (e.g., picorv32.trap
            # drivers = [0, 1] from RHS literals).
            if "." not in node_id or (node_id and node_id[0].isdigit()):
                continue  # Keep literal-like nodes
            # Skip target itself and its sub-instances
            if node_id in target_sub_paths:
                continue
            # Check if starts with any target sub-path
            is_within_target = any(
                node_id == p or node_id.startswith(p + ".")
                for p in target_sub_paths
            )
            if not is_within_target:
                nodes_to_drop.append(node_id)

        # Drop from graph
        for node_id in nodes_to_drop:
            try:
                self.graph.remove_node(node_id)
            except Exception as e:
                logger.warning("节点删除失败: %s", e)

        if nodes_to_drop:
            import sys
            print(
                f"[Phase 3] target={target!r}: filtered {len(nodes_to_drop)} "
                f"out-of-target nodes (kept {len(list(self.graph.nodes()))} "
                f"within target)",
                file=sys.stderr,
            )

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
                        # [V6.2 2026-07-20] Inherit file/line from parent struct node
                        self.graph.add_trace_node(
                            TraceNode(
                                id=src_member_id,
                                name=member,
                                module=src_node.module,
                                kind=NodeKind.SIGNAL,
                                width=src_node.width,
                                file=getattr(src_node, 'file', ''),
                                line=getattr(src_node, 'line', 0),
                            )
                        )

                if dst_member_id not in self.graph.nodes():
                    dst_node = self.graph.get_node(dst_struct)
                    if dst_node:
                        # [V6.2 2026-07-20] Inherit file/line from parent struct node
                        self.graph.add_trace_node(
                            TraceNode(
                                id=dst_member_id,
                                name=member,
                                module=dst_node.module,
                                kind=NodeKind.SIGNAL,
                                width=dst_node.width,
                                file=getattr(dst_node, 'file', ''),
                                line=getattr(dst_node, 'line', 0),
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
        - 识别 data[3] / data[3:0] 形式的节点
        - 创建/找到父节点 data
        - 设置 child.parent = data
        - 创建聚合边 child → data (BIT_SELECT)
        - 重命名边: 所有引用 child 的边保持不变

        [ARCHITECTURE_TODOLIST #2 G3 Option 3 (通用方案 a) 2026-08-28 07:23]
        集成 pyslang native API (`_common.iter_bit_selects` + BitSelectHit).
        - helper 返回 BitSelectHit (full_id + base_chain + msb/lsb via pyslang eval)
        - 走 base_chain 创建多条 BIT_SELECT 边 (处理 struct.field.[] 嵌套场景):
          * chain=['top.data', 'top.data[3:0]'] -> 1 边 (top.data[3:0] -> top.data)
          * chain=['top.pkt', 'top.pkt.addr', 'top.pkt.addr[3:0]'] -> 2 边:
            (top.pkt.addr -> top.pkt) + (top.pkt.addr[3:0] -> top.pkt.addr)
        - 设 RangeSelect 4 属性 (bit_range / parent_bit_start / parent_bit_end / width)
        - ElementSelect 只创 BIT_SELECT 边, 不设 4 属性 (跟路径 A 一致)
        """
        from trace.core.extractors._common import iter_bit_selects, BitSelectHit

        # [G3 Option 3 2026-08-28] target_module 为空时 (trace_signal 内部 build_graph 无 target),
        # 用首个 top instance 的实际名字当前缀, 跟 DriverExtractor 的 top.out[0] 前缀一致.
        # 否则产生 bare 'out[0]' duplicate 节点族, 破坏 driver trace 聚合 (for-loop 回归).
        instance_path = ''
        pyslang_root = None
        adapter_root = getattr(self.adapter, '_root', None)
        if adapter_root is not None:
            if hasattr(adapter_root, 'get_root'):
                pyslang_root = adapter_root.get_root()
            elif hasattr(adapter_root, 'topInstances'):
                pyslang_root = adapter_root

        if pyslang_root is None:
            # [2026-08-28 纪律修正] 原为 `return` (静默跳过全部位选处理)。
            # SemanticAdapter.__init__ 恒设 self._root, 故 None 只可能是调用方传错
            # adapter 类型 —— 静默 return 会让整张图的 BIT_SELECT 边凭空消失,
            # 且与"该设计本来就没有位选"无法区分。依 AGENTS.md 纪律 #2 改为显式报错。
            raise ValueError(
                f"GraphBuilder._create_hierarchical_bit_nodes: 无法从 adapter "
                f"({type(self.adapter).__name__}) 取得 pyslang root。"
                "位选处理需要 semantic root; 静默跳过会导致 BIT_SELECT 边全部缺失。"
            )

        if self.target_module:
            instance_path = self.target_module
        else:
            # 无 target: 用第一个 top instance 名当前缀 (匹配 DriverExtractor 行为)
            toplevel = pyslang_root.topInstances
            if len(toplevel) > 0:
                tname = toplevel[0].name
                instance_path = tname if tname else ''

        # [G3 Option 3] Step 2: 遍历所有 top instance 拿 BitSelectHit
        top = pyslang_root.topInstances
        for i in range(len(top)):
            mod = top[i]

            for hit in iter_bit_selects(mod, instance_path=instance_path):
                # [G3 Option 3 2026-08-28] 符号下标 (e.g. for-loop 里 q[i] / generate out[i]):
                # index=None (变量 i 非字面量), 但仍要走 base_chain 创 BIT_SELECT 边 + 设 parent
                # (pre-G3 regex helper 无条件为 graph 已有节点反推 parent, 保持对齐).
                if hit.select_kind == 'RangeSelect' and (hit.msb is None or hit.lsb is None):
                    # 参数位选边界不 evaluate (节点 ID 用 raw text), 仍走 BIT_SELECT 边
                    pass

                # base_chain 最后一位是 immediate parent 含 sel 后缀
                # 前面是 ancestor chain
                # 走链上每个相邻对创 BIT_SELECT 边
                chain = hit.base_chain
                if len(chain) < 2:
                    # 只有 immediate 没 ancestor (e.g. simple RangeSelect 都在 chain[0])
                    continue

                # 创各 chain entry 对应的 TraceNode (如果不存在)
                # 从 ancestor 到 immediate 逐一创节点 + 创 BIT_SELECT 边
                for j in range(1, len(chain)):
                    parent_id = chain[j - 1]
                    child_id = chain[j]

                    # [G3 Option 3 2026-08-28] 符号下标 (e.g. for-loop q[i], i 是变量):
                    # _extract_base_chain 把 sel 转成 [?] placeholder 但 graph 实际节点是 q[i] (raw text).
                    # 用 hit.full_id (保留原始 [i]) 覆盖末位 child_id, 才能匹配 DriverExtractor 建的节点.
                    # [FIX iter_071 2026-08-29] 只在 chain 末位含 '?' placeholder 时覆盖 —
                    # 多级 ElementSelect (data_o[i][j]) 的 chain 末位已完整 ('top.data_o[2][1]'),
                    # 无条件下用 full_id 首个 '[' 起的整个 select 文本追加, 会错拼成
                    # data_o[0][0][0] (多一个维度), 导致 data_o[i][j] → data_o[i] 聚合边缺失
                    # (test_sub_bytes_genvar_iteration 失败根因).
                    if j == len(chain) - 1 and hit.full_id and '?' in child_id:
                        # full_id 是 'q[i]' (无 instance_path 前缀), child_id 是 'top.q[?]' (有前缀)
                        # 用 full_id 的 select 文本替换 chain 末位的 placeholder
                        bracket = hit.full_id.find('[')
                        if bracket > 0:
                            sel_text = hit.full_id[bracket:]  # '[i]' or '[3:0]'
                            base_no_sel = child_id.rsplit('[', 1)[0] if '[' in child_id else child_id
                            child_id = f"{base_no_sel}{sel_text}"

                    # 确保 parent 节点存在
                    if parent_id not in self.graph.nodes():
                        parent_node = TraceNode(
                            id=parent_id,
                            name=parent_id.rsplit('.', 1)[-1],
                            module=instance_path or '',
                            kind=NodeKind.SIGNAL,
                            width=None,
                            file='',
                            line=0,
                        )
                        self.graph.add_trace_node(parent_node)

                    # 确保 child 节点存在
                    child_node = self.graph.get_node(child_id)
                    if child_node is None:
                        child_node = TraceNode(
                            id=child_id,
                            name=child_id.rsplit('.', 1)[-1],
                            module=instance_path or '',
                            kind=NodeKind.SIGNAL,
                            width=None,
                            file='',
                            line=hit.line,
                        )
                        self.graph.add_trace_node(child_node)

                    # 设 child.parent
                    child_node.parent = parent_id

                    # [G3 Option 3] RangeSelect 4 属性 (只在最末位 child, 即 hit.full_id 对应节点)
                    if j == len(chain) - 1 and hit.select_kind == 'RangeSelect' and hit.msb is not None and hit.lsb is not None:
                        msb, lsb = hit.msb, hit.lsb
                        child_node.bit_range = f"[{msb}:{lsb}]"
                        child_node.parent_bit_start = min(msb, lsb)
                        child_node.parent_bit_end = max(msb, lsb)
                        child_node.width = (max(msb, lsb), min(msb, lsb))

                    if child_node.kind is None:
                        child_node.kind = NodeKind.SIGNAL

                    # 创 BIT_SELECT 边
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
            # [REFACTOR 2026-08-07 A计划] 收集 expr_trees/const_map/func_info (从 semantic AST, 消灭 viz 源码重读)
            if getattr(result, 'expr_trees', None):
                self.graph._expr_trees.update(result.expr_trees)
            if getattr(result, 'const_map', None):
                self.graph._const_map.update(result.const_map)
            if getattr(result, 'func_info', None):
                self.graph._func_info.update(result.func_info)

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
            except (ValueError, AttributeError, TypeError) as _e:
                logger.debug("提取失败 ((ValueError, AttributeError, TypeError)): %s", _e)
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
            # [FIX 2026-07-16] 同时处理 PORT_OUT 和 PORT_IN.
            # 之前只处理 PORT_OUT, 导致 wrapper input ports (PORT_IN) 的 wrapper passthrough
            # edge (top.valid_i → wrapper inner.valid_i) 没建, chain/trace 跨 wrapper
            # input 边界找不到 path.
            # Edge 方向:
            # - PORT_OUT: deep → inst_port (deep driver drives wrapper output)
            # - PORT_IN:  inst_port → deep  (wrapper input drives inner deep port)
            def_node = self.graph._node_data.get(def_port)
            if not def_node or def_node.kind.name not in ("PORT_OUT", "PORT_IN"):
                continue
            is_input = def_node.kind.name == "PORT_IN"
            logger.debug(f"_elab_wrapper: PROCESSING {def_port} (is_input={is_input}, inst_ports={len(inst_ports)})")

            # 检查 def_port 是否已经有 driver (避免重复加). 用 predecessors 更稳.
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
                    # Edge 方向根据 input/output:
                    # - PORT_OUT: deep → inst_port (deep driver drives wrapper output)
                    # - PORT_IN:  inst_port → deep  (wrapper input drives inner deep port)
                    edge_src = inst_port if is_input else deep_node.id
                    edge_dst = deep_node.id if is_input else inst_port
                    # 加 DRIVER 边 wrapper_passthrough.
                    # 注意: ConnectionExtractor 可能已加 CONNECTION 边 for 同一 (src,dst). 这里加 DRIVER 边. 二者不冲突.
                    from .graph.models import TraceEdge
                    already_has_driver = any(
                        e.kind == EdgeKind.DRIVER
                        for e in self.graph._edge_data.get((edge_src, edge_dst), [])
                    )
                    if not already_has_driver:
                        self.graph.add_trace_edge(TraceEdge(
                            src=edge_src,
                            dst=edge_dst,
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
