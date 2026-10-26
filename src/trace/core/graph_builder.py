# ==============================================================================
# graph_builder.py - Builder Layer
# ==============================================================================

from __future__ import annotations

import logging

from .._safe import safe_attr, safe_str, safe_str  # [iter_182]

import pyslang

from .semantic_adapter import SemanticAdapter
from .builder.graph_pipeline import GraphPipeline, Stage
from .builder.subroutine_expander import SubroutineExpander
from .connection_extractor import ConnectionExtractor  # [P1 cycle 9b] re-export 保兼容
from .driver_extractor import DriverExtractor  # [P1 cycle 8] re-export 保兼容
from .extractor_models import ExtractorResult  # [P1 cycle 9] 共享 (避免循环 import)
from .graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode

logger = logging.getLogger(__name__)

# [P1 cycle 9] ExtractorResult 移到了 extractor_models.py
# 这里 re-export 保持向后兼容 (from trace.core.graph_builder import ExtractorResult)
__all__ = [
    "ExtractorResult",
    "GraphBuilder",
    "DriverExtractor",
    "ConnectionExtractor",
]

class GraphBuilder:
    def __init__(self, adapter: SemanticAdapter, target_module: str | None = None):
        """[Phase 3 2026-07-11] GraphBuilder + target_module filter.

        Args:
            adapter: SemanticAdapter (semantic AST)
            target_module: [NEW] If set, extractors use this as root_module_name
                           instead of auto-detected first top instance. This ensures
                           instance paths in SignalGraph use user-specified target.
        """
        self.adapter = adapter
        self.target_module = target_module  # [Phase 3]
        # [iter_272] 图**只有实例级**一种模式 (模块定义级路径已删除):
        #   - target_module 给定时: 只建该子树并过滤 (单模块调试)
        #   - 否则: 建所有 top 的实例树 (全设计视图)
        self.graph = SignalGraph()
        self._extractors = {
            "driver": DriverExtractor(adapter),
            "connection": ConnectionExtractor(adapter, root_module_name=target_module),
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
        """建图：extract → 12 个声明式后处理 pass（顺序由依赖推导，见 graph_pipeline）。"""
        pipeline = GraphPipeline([
            Stage(
                "configure_instances",
                self._configure_instance_paths,
                provides={"instances"},
                note="按 target/顶层实例配置 DriverExtractor 的实例路径",
            ),
            Stage(
                "extract_nodes",
                self._extract_all_nodes,
                requires={"instances"},
                provides={"nodes"},
                note="driver/connection extractor 产出节点",
            ),
            Stage(
                "extract_edges",
                self._extract_all_edges,
                requires={"nodes"},
                provides={"edges"},
                note="driver/connection extractor 产出边",
            ),
            Stage(
                "special_signals",
                self._mark_special_signals,
                requires={"nodes", "edges"},
                provides={"special_flags"},
                note="打 clock/reset 标记",
            ),
            Stage(
                "bit_nodes",
                self._create_hierarchical_bit_nodes,
                requires={"nodes", "edges"},
                provides={"bit_nodes"},
                note="按 RTL 位选建位节点",
            ),
            Stage(
                "slice_bits",
                self._expand_slice_bit_nodes,
                requires={"bit_nodes"},
                provides={"slice_bits"},
                note="[iter_291] 切片赋值展开成逐位节点 (LHS/RHS 切片 → 位对位 DRIVER)",
            ),
            Stage(
                "struct_members",
                self._collect_struct_members,
                requires={"nodes", "edges"},
                provides={"struct_members"},
            ),
            Stage(
                "struct_assigns",
                self._expand_struct_assignments,
                requires={"struct_members"},
                provides={"struct_assigns"},
                note="struct 整体赋值展开到成员",
            ),
            Stage(
                "upgrade_regs",
                self._upgrade_reg_nodes,
                requires={"bit_nodes"},
                provides={"reg_nodes"},
                note="必须在 bit_nodes 之后",
            ),
            Stage(
                "wrapper_passthrough",
                self._elaborate_wrapper_passthroughs,
                requires={"nodes", "bit_nodes"},
                provides={"wrapper_passthrough"},
                note="wrapper 端口 ↔ 内部同名子端口直通边（纯图实现）",
            ),
            Stage(
                "filter_target",
                self._filter_by_target,
                requires={"bit_nodes"},
                provides={"filtered"},
                note="target_module 给定时裁剪子树（无 target 时内部直接返回）",
            ),
            Stage(
                "bus_bit_bridges",
                self._expand_bus_conn_bit_bridges,
                requires={"bit_nodes", "filtered"},
                provides={"bus_bit_bridges"},
                note="必须在 filter_target 之后：只给最终保留节点建位桥",
            ),
            Stage(
                "bit_bridge_synth",
                self._synthesize_missing_bit_bridges,
                requires={"bus_bit_bridges"},
                provides={"bit_bridge_synth"},
                note="[iter_293] bus↔bus 端口/赋值桥: 缺位一侧合成位节点（模式见 env）",
            ),
            Stage(
                "gen_block_map",
                self._capture_generate_block_map,
                requires={"nodes", "edges"},
                provides={"gen_block_map"},
                note="generate block 真实 label → LHS 基名映射（viz 用）",
            ),
        ])
        pipeline.run()
        # [iter_299 / PLAN P11.2] 所有 pass 完成后统一修 packed 成员宽度/位段
        # （成员节点可能由 bit_nodes/struct_assigns 等后续 pass 建出）
        self._apply_packed_member_layout()
        return self.graph

    def _expand_slice_bit_nodes(self) -> None:
        """[iter_291 / PLAN P5.4 F3] 把切片赋值展开成**逐位节点 + 位对位 DRIVER**。

        背景：`assign y[7:4] = a;` 只在图里产生 slice 节点 `y[7:4]` 和一条
        `a → y[7:4]` 的总线 DRIVER，查询 `y[5]` 只能回答 `a`（粗粒度）。
        本 pass 对**显式切片**建逐位节点，让查询能回答 `a[1]`：

          低位对齐（SV 声明序，与 iter_143 一致）:
            LHS 切片 X[hi:lo] (hi>lo)      bit k ← 源 bus/slice 的 bit k
            RHS 切片 S[hi:lo] (hi>lo)      bus[k] ← S[lo+k]

        约束（避免造假节点 / 爆炸）：
          - 只处理**显式切片节点**（id 带 `[hi:lo]`、hi>lo、宽度 = 源宽）
          - 常量源（4'h0 / 1'b1 等）不展开（值位映射不在本版）
          - 逐位节点**不加 BIT_SELECT 聚合边**（iter_143 的教训：避免父总线提升
            把兄弟位的驱动带回来）
          - 新节点总量上限 20000；超限显式 warning 并停止（不静默截断）
        """
        from .graph.models import NodeKind, TraceEdge

        MAX_NEW_NODES = 20000
        import re as _re

        SLICE_RE = _re.compile(r"^(?P<base>.+?)\[(?P<hi>\d+):(?P<lo>\d+)\]$")
        new_nodes = 0

        def _slice_range(node_id: str):
            m = SLICE_RE.match(node_id)
            if not m:
                return None
            hi, lo = int(m.group("hi")), int(m.group("lo"))
            if hi <= lo:
                return None  # 只处理升序（常见）切片
            return m.group("base"), hi, lo

        def _ensure_bit(base: str, bit: int):
            nonlocal new_nodes
            bit_id = f"{base}[{bit}]"
            if bit_id in self.graph._node_data:
                return bit_id
            base_node = self.graph.get_node(base)
            if base_node is None:
                return None
            if new_nodes >= MAX_NEW_NODES:
                logger.warning(
                    "_expand_slice_bit_nodes: 新增位节点达到上限 %d，停止展开（图可能不完整）",
                    MAX_NEW_NODES,
                )
                return None
            self.graph.add_trace_node(TraceNode(
                id=bit_id,
                name=f"{base.rsplit('.', 1)[-1]}[{bit}]",
                module=getattr(base_node, "module", ""),
                kind=NodeKind.SIGNAL,
                width=(0, 0),
                parent=base,
                parent_bit_start=bit,
                parent_bit_end=bit,
                bit_range=f"[{bit}]",
            ))
            new_nodes += 1
            return bit_id

        def _width_of(node) -> int | None:
            w = getattr(node, "width", None)
            if isinstance(w, (tuple, list)) and len(w) >= 2:
                try:
                    return abs(int(w[0]) - int(w[1])) + 1
                except (TypeError, ValueError):
                    return None
            return None

        def _add_driver(src_bit: str, dst_bit: str) -> None:
            if src_bit is None or dst_bit is None:
                return
            existing = self.graph._edge_data.get((src_bit, dst_bit), [])
            if any(e.kind == EdgeKind.DRIVER for e in existing):
                return
            self.graph.add_trace_edge(TraceEdge(
                src=src_bit, dst=dst_bit, kind=EdgeKind.DRIVER, assign_type="continuous"))

        for (src, dst), edges in list(self.graph._edge_data.items()):
            if not any(e.kind == EdgeKind.DRIVER for e in edges):
                continue
            src_node = self.graph.get_node(src)
            dst_node = self.graph.get_node(dst)
            if src_node is None or dst_node is None:
                continue

            dst_slice = _slice_range(dst)
            src_slice = _slice_range(src)

            # --- LHS 切片: X[hi:lo] = source ---
            if dst_slice is not None:
                base, hi, lo = dst_slice
                width = hi - lo + 1
                if src_slice is not None:
                    sbase, shi, slo = src_slice
                    if (shi - slo + 1) != width:
                        continue
                    for k in range(width):
                        _add_driver(_ensure_bit(sbase, slo + k), _ensure_bit(base, lo + k))
                elif src_node.kind.name in ("CONST", "OP_TERNARY", "OP_CASE"):
                    continue  # 常量/运算节点：值位映射不在本版
                else:
                    # 源比切片窄时只映射真实存在的位（SV 高位零扩展；不造不存在的 bit）
                    src_w = _width_of(src_node)
                    limit = min(width, src_w) if src_w else width
                    for k in range(limit):
                        _add_driver(_ensure_bit(src, k), _ensure_bit(base, lo + k))
                continue

            # --- RHS 切片: bus = S[hi:lo] ---
            if src_slice is not None and "[" not in dst:
                sbase, shi, slo = src_slice
                width = shi - slo + 1
                dst_width = dst_node.width if isinstance(dst_node.width, tuple) else None
                if dst_width is not None and dst_width[0] != dst_width[1]:
                    dst_w = abs(int(dst_width[0]) - int(dst_width[1])) + 1
                    if dst_w != width:
                        continue
                if dst_node.kind.name in ("CONST", "OP_TERNARY", "OP_CASE"):
                    continue
                for k in range(width):
                    _add_driver(_ensure_bit(sbase, slo + k), _ensure_bit(dst, k))

        logger.debug("_expand_slice_bit_nodes: 新增 %d 个位节点", new_nodes)

    def _expand_bus_conn_bit_bridges(self):
        """[iter_137 A2 位对位] 同宽同构 bus↔bus CONNECTION 的位级桥边.

        iter_126 A2 后: 子模块输出总线直连顶层位时 fanin(top.y[3]) 停在总线
        粒度 (top.u_sub.y) — bus CONNECTION (u_sub.y→top.y) 无位级桥, 顶层位
        top.y[3] 只有 BIT_SELECT 出边, 无 incoming 驱动链到 sub 内部位逻辑
        (u_sub.y[3] 由 driver 层按 RTL 位选建的位节点及其 DRIVER 存在, 但
        查询跨不过 bus 边界)。

        修: 对 bus↔bus CONNECTION 边 (两端无 [N]、宽度相等), 若**两侧位节点
        都存在** (driver/_create_hierarchical_bit_nodes 按 RTL 真实位选建的),
        补位级 CONNECTION 边 (u_sub.y[i]→top.y[i]; 输入侧 top.a[i]→
        u_sub.a[i] 同规则)。位节点不存在 (纯 bus 直通, BUSFIX 型) 不建 —
        保持 iter_126 总线粒度契约, 不造假节点 (AGENTS.md §2)。
        切片连接 (.y(y[7:4]) 偏移位映射) 不在本版 — audit 后续项。
        """
        added = 0
        for src, dst in list(self.graph.edges()):
            if "[" in src or "[" in dst:
                continue  # 已位/切片粒度
            snode = self.graph.get_node(src)
            dnode = self.graph.get_node(dst)
            if snode is None or dnode is None:
                continue
            if snode.width is None or dnode.width is None:
                continue
            if snode.width != dnode.width:
                continue  # 非同宽 → 位映射不可同构推断, 跳过 (防错桥)
            # width=(msb,lsb) 方向不定 → min/max 枚举
            lo, hi = min(snode.width), max(snode.width)
            if hi <= lo:
                continue  # 1 位 bus (单 bit) 无需桥
            edges = self.graph.get_edges(src, dst)
            if not any(e.kind == EdgeKind.CONNECTION for e in edges):
                continue
            for i in range(lo, hi + 1):
                src_i = f"{src}[{i}]"
                dst_i = f"{dst}[{i}]"
                if (src_i not in self.graph.nodes()
                        or dst_i not in self.graph.nodes()):
                    continue  # 任一侧无位节点 → 不建 (不造假节点)
                if self.graph.get_edge(src_i, dst_i) is not None:
                    continue  # 已有
                conn_e = next((e for e in edges
                               if e.kind == EdgeKind.CONNECTION), None)
                self.graph.add_trace_edge(TraceEdge(
                    src=src_i, dst=dst_i, kind=EdgeKind.CONNECTION,
                    assign_type=getattr(conn_e, "assign_type", "connection"),
                ))
                added += 1

        # [iter_143 A2 切片偏移桥] 一端 bus 一端切片 (.y(y[7:4]) / [k]) 的
        # CONNECTION: 切片连接隐含每 bit 真实驱动 — bus 侧位节点存在时,
        # 按声明序低位对齐建 bus[blo+off] ↔ slice[slo+off] 位桥 (偏移映射);
        # 切片侧单 bit 节点缺失则创建 (真实位: 由切片连接驱动, 非造假 —
        # iter_137 '不造假节点' 指 bus 直通无真实位逻辑, 与此不同)。
        # 位宽不匹配 (leaf 1 位接 2 位切片等, iter_136 场景) → skip。
        import re as _re
        for src, dst in list(self.graph.edges()):
            s_br = "[" in src
            d_br = "[" in dst
            if s_br == d_br:
                continue  # bus↔bus (上段) 或 bit↔bit
            bus, sl_id = (dst, src) if s_br else (src, dst)
            bnode = self.graph.get_node(bus)
            if bnode is None or bnode.width is None:
                continue
            blo, bhi = min(bnode.width), max(bnode.width)
            _m = _re.match(r"^(.*)\[(\d+):(\d+)\]$", sl_id)
            if _m:
                base, slo, shi = (_m.group(1), int(_m.group(2)),
                                  int(_m.group(3)))
                slo, shi = min(slo, shi), max(slo, shi)
            else:
                _m2 = _re.match(r"^(.*)\[(\d+)\]$", sl_id)
                if not _m2:
                    continue
                base = _m2.group(1)
                slo = shi = int(_m2.group(2))
            if (bhi - blo) != (shi - slo):
                continue  # 宽度不匹配 → 不能序对齐 (防错桥)
            edges = self.graph.get_edges(src, dst)
            conn_e = next((e for e in edges
                           if e.kind == EdgeKind.CONNECTION), None)
            if conn_e is None:
                continue
            for off in range(0, bhi - blo + 1):
                bus_i = f"{bus}[{blo + off}]"
                if bus_i not in self.graph.nodes():
                    continue  # bus 侧无位节点 → 不造 (bus 直通保持粒度)
                sl_i = f"{base}[{slo + off}]"
                if sl_i not in self.graph.nodes():
                    if base not in self.graph.nodes():
                        continue
                    # 只建位节点作查询落点, **不建 BIT_SELECT → base 聚合边**:
                    # 聚合边会让 bus 提升查询 (悬空位 top.y[3] → bus top.y →
                    # BIT_SELECT 子递归) 收到这些位驱动 → 污染 (iter_143 实测
                    # top.y[3] 悬空位 fanin 串入 a[0..3])。位查询本身经桥可达,
                    # 无需聚合边。
                    self.graph.add_trace_node(TraceNode(
                        id=sl_i,
                        name=sl_i.rsplit(".", 1)[-1],
                        module=(base.rsplit(".", 1)[0]
                                if "." in base
                                else (self.target_module or "")),
                        kind=NodeKind.SIGNAL,
                        width=None,
                    ))
                # 桥方向 = 原 CONNECTION 方向 (切片 src → bus dst, 反之亦然)
                e_src, e_dst = ((sl_i, bus_i) if s_br else (bus_i, sl_i))
                if self.graph.get_edge(e_src, e_dst) is None:
                    self.graph.add_trace_edge(TraceEdge(
                        src=e_src, dst=e_dst, kind=EdgeKind.CONNECTION,
                        assign_type=getattr(conn_e, "assign_type", "connection"),
                    ))
                    added += 1
        if added:
            logger.debug(f"_expand_bus_conn_bit_bridges: added {added} bit edges")

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

    def _all_top_instances(self) -> list[tuple[str, Any]]:
        """所有顶层实例 (name, symbol), 供全设计 walk。

        来源: SemanticAdapter 的 root.topInstances (elaborated)。取不到就返回空,
        由调用方决定是否降级 (本函数不静默造假)。
        """
        root = getattr(self.adapter, "_root", None)
        if root is None:
            logger.warning("adapter 没有 _root, 无法枚举顶层实例")
            return []
        tops = []
        for top in getattr(root, "topInstances", []) or []:
            try:
                name = str(getattr(top, "name", ""))
            except (UnicodeDecodeError, TypeError) as e:
                logger.debug("top instance 名字不可读, 跳过: %s", e)
                continue
            if name:
                tops.append((name, top))
        return tops

    def _configure_instance_paths(self):
        """[Phase 4 2026-07-11] Walk target instance tree, configure extractors.

        Builds a list of (instance_path, instance_symbol) pairs for all instances
        within the user-specified target. Passes to DriverExtractor so signal
        IDs include full instance paths.

        [iter_113 修复] generate 分支必须真正下钻到 entry 内的实例:
        旧实现 GenerateBlockArray → walk(entry=GenerateBlock, path), 而 walk 只认
        safe_attr(inst, "body", []) — GenerateBlockSymbol 是 scope 无 .body → 永不下钻 → generate 内
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
            # [iter_272] 无 target → walk **所有** top 的实例树 (全设计视图);
            # 有 target → 只 walk 该子树 (单模块调试)。
            if not self.target_module:
                roots = self._all_top_instances()
            else:
                target_top = self._find_target_top(self.target_module)
                if target_top is None:
                    return
                roots = [(self.target_module, target_top)]

            if not roots:
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
                except (UnicodeDecodeError, TypeError) as e:
                    logger.debug("%s: 忽略 (UnicodeDecodeError, TypeError): %s", __name__, e)
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

            for root_name, root_sym in roots:
                walk(root_sym, root_name)


            # Pass to DriverExtractor
            driver = self._extractors.get('driver')
            if driver is not None and hasattr(driver, 'set_instance_paths'):
                driver.set_instance_paths(paths)

            from .compiler import is_quiet
            if not is_quiet():                      # [iter_202] --quiet 必须真的安静
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
                    if str(safe_str(safe_attr(top, "name", ""))) == target_module:
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
        if not self.target_module:
            return
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
            from .compiler import is_quiet
            if not is_quiet():                      # [iter_202] --quiet 必须真的安静
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

    def _apply_packed_member_layout(self):
        """packed struct/union 成员：宽度 + signedness + 在父聚合中的位段。

        节点名模式 `module.var.member`；语义符号 `.hierarchicalPath` 与节点 id 对齐。
        """
        symbols = {}
        try:
            instances = []
            root = getattr(self.adapter, "root", None)
            if root is not None:
                instances.extend(getattr(root, "topInstances", []) or [])
            for wrapper in self.adapter.get_module_instances():
                sym = getattr(wrapper, "_symbol", None)
                if sym is not None:
                    instances.append(sym)
            for sym in instances:
                body = getattr(sym, "body", None)
                if body is None:
                    continue
                for member in body:
                    if str(getattr(member, "kind", "")) != "SymbolKind.Variable":
                        continue
                    hp = str(getattr(member, "hierarchicalPath", "") or "")
                    if hp:
                        symbols[hp] = member
        except Exception as e:
            logger.debug("%s: packed 成员符号收集失败: %s", __name__, e)
            return

        # 重新扫描当前图（成员节点可能晚建），按 "父节点存在 + 至少 2 个成员" 识别
        parent_members: dict[str, set] = {}
        for node_id in list(self.graph.nodes()):
            if "." not in node_id:
                continue
            parent_path, member_name = node_id.rsplit(".", 1)
            if parent_path in self.graph.nodes():
                parent_members.setdefault(parent_path, set()).add(member_name)

        # [iter_300 / PLAN P12] 除"已有成员节点"的父路径外，也要覆盖未被引用的
        # struct 变量（需要为其建成员节点，查询才可达）
        for parent_path in set(parent_members) | set(symbols):
            sym = symbols.get(parent_path)
            if sym is None or parent_path not in self.graph.nodes():
                continue
            layout = self.adapter.get_packed_member_layout(sym)
            if not layout:
                continue
            parent_node = self.graph.get_node(parent_path)
            for item in layout:
                node_id = f"{parent_path}.{item['name']}"
                node = self.graph.get_node(node_id)
                w = item["width"]
                if node is None:
                    # [iter_300 / PLAN P12] 未被引用的成员也建节点（查询可达）
                    from .graph.models import NodeKind, TraceNode
                    node = TraceNode(
                        id=node_id, name=item["name"],
                        module=getattr(parent_node, "module", "") if parent_node else "",
                        kind=NodeKind.SIGNAL,
                        width=(w - 1, 0) if w > 1 else (1, 0),
                        is_signed=item["signed"],
                        parent=parent_path,
                        parent_bit_start=item["offset"] + w - 1,
                        parent_bit_end=item["offset"],
                        extra={"packed_member": True},
                    )
                    self.graph.add_trace_node(node)
                    continue
                node.width = (w - 1, 0) if w > 1 else (1, 0)
                node.is_signed = item["signed"]
                node.parent = parent_path
                node.parent_bit_start = item["offset"] + w - 1
                node.parent_bit_end = item["offset"]
                # [iter_300 / PLAN P12] 标记 packed 成员（查询层位桥按 parent 链换算）
                node.extra["packed_member"] = True

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
                # [iter_184 加, iter_185 定性] safe_attr 兜住 name getter 异常 —
                # 真因 (SourceManager 生命周期, iter_185) 已修, 此处保留为廉价防御。
                tname = safe_str(safe_attr(toplevel[0], "name", ""))
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
            # [REFACTOR 2026-08-07 A计划] 收集 expr_trees/const_map/func_info (从 semantic AST, 消灭 viz 源码重读)
            if getattr(result, 'expr_trees', None):
                self.graph._expr_trees.update(result.expr_trees)
            if getattr(result, 'const_map', None):
                self.graph._const_map.update(result.const_map)
            if getattr(result, 'func_info', None):
                self.graph._func_info.update(result.func_info)
            # [iter_129] interface 成员桥需要 connection 结果里的端口连接信息
            if getattr(result, 'interface_links', None):
                if not hasattr(self.graph, "_interface_links"):
                    self.graph._interface_links = []
                self.graph._interface_links.extend(result.interface_links)

        # [P0-3] 设置 interface 信号的 modport_dir
        self._set_interface_modport_dirs()
        # [iter_129] interface 成员级桥 (实例端口成员 ↔ interface 实例成员)
        self._bridge_interface_member_signals()

    def _bridge_interface_member_signals(self):
        """[iter_129 候选3] interface 成员级连接桥.

        connection_extractor 收集 interface 端口连接 (interface_links):
        (inst_path, port_name, iface_name, members, parent_member_prefix).
        例: writer u_w(.b(bf)) → ('top.u_w', 'b', 'bus_if', ['addr','data'],
        'top.bf')。

        此 pass 在 driver 边全部就绪后执行, 对每个成员信号建**单向桥**:
        - 实例内部驱动该成员 (实例侧成员有 incoming DRIVER, e.g. writer 内
          assign b.addr=a → top.u_w.b.addr ← top.u_w.a) → 桥方向
          实例成员 → interface 实例成员 (top.u_w.b.addr → top.bf.addr),
          fanin(top.bf.addr) 能穿透到 writer 内部驱动链。
        - 实例只读该成员 (无 incoming DRIVER, e.g. slave assign l=b.addr) →
          桥方向 interface 实例成员 → 实例成员 (top.bf.addr → top.u_slv.b.addr),
          fanin(实例内部读方) 能跨回 interface 线。
        双向线本质: 两侧都建会让 fanin(端口成员) 把无驱动的 interface 线当
        假源 (实测 [a, bf.addr, u_w.a]); 按"谁驱动谁"单向建模与普通端口一致。
        """
        from trace.core.graph.models import EdgeKind, TraceEdge

        links = getattr(self.graph, "_interface_links", [])
        for (inst_path, port_name, _iface_name, members, parent_prefix) in links:
            inst_member_base = f"{inst_path}.{port_name}"
            for member in members:
                inst_member_id = f"{inst_member_base}.{member}"
                parent_member_id = f"{parent_prefix}.{member}"
                if inst_member_id not in self.graph._node_data:
                    continue
                # 实例侧成员是否被实例内部驱动 (非自环 DRIVER incoming)
                inst_driven = any(
                    (src, dst) != (inst_member_id, inst_member_id)
                    and any(e.kind == EdgeKind.DRIVER and e.assign_type != "internal"
                            for e in self.graph._edge_data.get((src, dst), []))
                    for src, dst in list(self.graph.edges())
                    if dst == inst_member_id
                )
                if parent_member_id not in self.graph._node_data:
                    # 占位: 未出现的 interface 实例成员 (顶层未引用) 也建,
                    # 让桥稳定存在 (只读方 fanin 需要目标节点)
                    from trace.core.graph.models import NodeKind, TraceNode
                    # [iter_285 / PLAN P2.1] TraceNode.width 是必填; 这里原先漏传 →
                    # 带 interface 的设计直接 TypeError 崩溃 (P2.1 边缘回归暴露)。
                    # 位宽优先沿用实例侧成员, 退化时用 (0, 0) sentinel。
                    _inst_node = self.graph.get_node(inst_member_id)
                    self.graph.add_trace_node(TraceNode(
                        id=parent_member_id,
                        name=member,
                        module=parent_prefix,
                        kind=NodeKind.SIGNAL,
                        width=_inst_node.width if _inst_node is not None else (0, 0),
                    ))
                # 单向桥: 驱动方 → 观察方
                if inst_driven:
                    # 实例内部驱动成员 (writer 型): 实例成员 → interface 成员
                    if (inst_member_id, parent_member_id) not in self.graph._edge_data:
                        self.graph.add_trace_edge(TraceEdge(
                            src=inst_member_id, dst=parent_member_id,
                            kind=EdgeKind.CONNECTION, assign_type="connection"))
                else:
                    # 实例只读 (slave 型): interface 成员 → 实例成员
                    if (parent_member_id, inst_member_id) not in self.graph._edge_data:
                        self.graph.add_trace_edge(TraceEdge(
                            src=parent_member_id, dst=inst_member_id,
                            kind=EdgeKind.CONNECTION, assign_type="connection"))

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
                if hasattr(module, "body") and safe_attr(module, "body", []):
                    definition = getattr(safe_attr(module, "body", []), "definition", None)
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
                            port_name = safe_str(safe_attr(decl, "name", "")).value if hasattr(safe_str(safe_attr(decl, "name", "")), "value") else str(safe_str(safe_attr(decl, "name", "")))
                            interface_name = None
                            if hasattr(h, "nameOrKeyword"):
                                nk = h.nameOrKeyword
                                interface_name = nk.rawText if hasattr(nk, "rawText") else str(nk)
                            modport_name = None
                            if hasattr(h, "modport") and hasattr(h.modport, "member"):
                                member_val = h.modport.member
                                # [iter_183] safe_attr (hasattr 不吞 UnicodeDecodeError)
                                modport_name = safe_str(safe_attr(member_val, "name", "")) or str(member_val)
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

    def _synthesize_missing_bit_bridges(self) -> None:
        """[iter_293 / PLAN P5.5 F4] bus↔bus 连接/赋值的位桥（缺位一侧合成位节点）。

        iter_137/143 的位桥只在**两侧位节点都已存在**时补边；纯总线连接
        （`sub .y(w)`、`assign y = a`）两侧都没有位节点 → 位查询停在总线。

        本 pass 的两种模式（环境变量 `SVQ_BIT_BRIDGE`）：
          - `one`（默认）: 只处理**一侧已有位节点**的连接 —— 给缺位一侧补位节点，
            再建位对位边。不改 iter_126 的"纯总线不造假节点"契约。
          - `full`: 纯总线连接也两侧合成位节点（`i ↔ i` 同索引），位查询可全贯通；
            图会变大（verilog-axi 实测见迭代记录），需显式开启。

        覆盖两类边：CONNECTION（端口/网络连接）与 DRIVER（`assign bus = bus`）。
        合成节点**不加 BIT_SELECT 聚合边**（防父总线提升污染），并受总量上限保护。
        """
        import os as _os
        from .graph.models import NodeKind, TraceEdge

        mode = (_os.environ.get("SVQ_BIT_BRIDGE") or "one").strip().lower()
        if mode not in ("one", "full"):
            logger.warning("SVQ_BIT_BRIDGE 取值非法 (%r)，用默认 one", mode)
            mode = "one"

        MAX_NEW_NODES = 30000
        new_nodes = 0
        new_edges = 0

        def width_of(node) -> int | None:
            w = getattr(node, "width", None)
            if isinstance(w, (tuple, list)) and len(w) >= 2:
                try:
                    return abs(int(w[0]) - int(w[1])) + 1
                except (TypeError, ValueError):
                    return None
            return None

        def has_bits(base: str, width: int) -> bool:
            return any(f"{base}[{i}]" in self.graph._node_data for i in range(width))

        def ensure_bit(base: str, bit: int) -> str | None:
            nonlocal new_nodes
            bit_id = f"{base}[{bit}]"
            if bit_id in self.graph._node_data:
                return bit_id
            base_node = self.graph.get_node(base)
            if base_node is None:
                return None
            if new_nodes >= MAX_NEW_NODES:
                logger.warning(
                    "_synthesize_missing_bit_bridges: 新节点达到上限 %d，停止（图可能不完整）",
                    MAX_NEW_NODES,
                )
                return None
            self.graph.add_trace_node(TraceNode(
                id=bit_id,
                name=f"{base.rsplit('.', 1)[-1]}[{bit}]",
                module=getattr(base_node, "module", ""),
                kind=NodeKind.SIGNAL,
                width=(0, 0),
                parent=base,
                parent_bit_start=bit,
                parent_bit_end=bit,
                bit_range=f"[{bit}]",
            ))
            new_nodes += 1
            return bit_id

        def add_edge(a: str | None, b: str | None, kind) -> None:
            nonlocal new_edges
            if a is None or b is None:
                return
            if any(e.kind == kind for e in self.graph._edge_data.get((a, b), [])):
                return
            self.graph.add_trace_edge(TraceEdge(src=a, dst=b, kind=kind, assign_type="continuous"))
            new_edges += 1

        # 最多 3 轮：合成位节点会让"另一侧有位"的 pair 变为可处理（端口/内部
        # DRIVER 的先后顺序不应影响结果）。稳定或达上限即停。
        for _round in range(3):
            before_nodes, before_edges = new_nodes, new_edges
            for (src, dst), edges in list(self.graph._edge_data.items()):
                if "[" in src or "[" in dst:
                    continue
                kinds = {e.kind for e in edges}
                is_conn = EdgeKind.CONNECTION in kinds
                is_drv = EdgeKind.DRIVER in kinds
                if not (is_conn or is_drv):
                    continue
                src_node = self.graph.get_node(src)
                dst_node = self.graph.get_node(dst)
                if src_node is None or dst_node is None:
                    continue
                if src_node.kind.name in ("CONST", "OP_TERNARY", "OP_CASE"):
                    continue
                if dst_node.kind.name in ("CONST", "OP_TERNARY", "OP_CASE"):
                    continue
                w = width_of(src_node)
                if not w or w <= 1 or w != width_of(dst_node):
                    continue

                # DRIVER 只对**直接拷贝**（assign y = a）做同索引位桥：
                # 算术/逻辑表达式（s = a + b）的位映射不是同索引（进位/移位），
                # 合成会给出错误的位依赖。CONNECTION 是网络连接，同索引恒成立。
                if is_drv and not is_conn:
                    src_short = src.rsplit(".", 1)[-1]
                    drv_edges = [e for e in edges if e.kind == EdgeKind.DRIVER]
                    if not drv_edges or any((e.expression or "") != src_short for e in drv_edges):
                        continue
                    # dst 已有位级驱动（多驱动/部分赋值）→ 不做，避免把总线拷贝
                    # 混进已有位驱动（语义是多驱动解析，不是同索引覆盖）
                    if any(f"{dst}[{i}]" in self.graph._node_data
                           and any(True for _ in self.graph.predecessors(f"{dst}[{i}]"))
                           for i in range(w)):
                        continue

                src_has = has_bits(src, w)
                dst_has = has_bits(dst, w)
                if src_has and dst_has:
                    continue  # iter_137 已处理
                if mode != "full" and not (src_has or dst_has):
                    continue  # one 模式：纯总线不合成

                edge_kind = EdgeKind.CONNECTION if is_conn else EdgeKind.DRIVER
                for i in range(w):
                    sb = ensure_bit(src, i) if (mode == "full" or src_has or dst_has) else None
                    db = ensure_bit(dst, i) if (mode == "full" or src_has or dst_has) else None
                    add_edge(sb, db, edge_kind)

            if (new_nodes, new_edges) == (before_nodes, before_edges):
                break

        if new_nodes or new_edges:
            logger.info(
                "_synthesize_missing_bit_bridges (%s): +%d 位节点 / +%d 位边",
                mode, new_nodes, new_edges,
            )

    def _elaborate_wrapper_passthroughs(self):
        """[iter_276] wrapper 直通边 —— **纯图 + 实例路径**实现。

        旧实现遍历"模块定义端口"(如 `axi_ram_wr_rd_if.s_axi_awready`), 靠
        `port_to_module_type` 的 short name 字符串把实例对上。那是双命名空间时代的
        产物: 它要求模块定义端口节点存在, 于是 Load/Clock extractor 造出的影子节点
        反过来成了它的前提 —— 这也是"阴影节点清理 pass"删不掉的根因。

        新实现只看图里的实例端口节点 (id 形如 `top.G[0].u_mid.y`):
          对每个实例端口 P = `I.p` (至少两级实例路径, 排除顶层 `top.p`),
          找同一实例子树下**同名**的端口 D = `I.<...>.p`:
            - P 是 PORT_OUT: D --DRIVER(wrapper_passthrough)--> P
            - P 是 PORT_IN : P --DRIVER(wrapper_passthrough)--> D
          仅当 (src,dst) 还没有 DRIVER 边时补。

        语义不变: "wrapper 端口由内部同名的子实例端口直通驱动"。
        """
        from .graph.models import TraceEdge

        nodes = list(self.graph._node_data)
        added = 0

        for port_id in nodes:
            parts = port_id.split(".")
            if len(parts) < 3:            # 顶层端口 (top.a) 不算 wrapper
                continue
            node = self.graph._node_data.get(port_id)
            if node is None:
                continue
            kind = node.kind.name
            if kind not in ("PORT_OUT", "PORT_IN"):
                continue

            inst_path, port_name = port_id.rsplit(".", 1)
            prefix = inst_path + "."
            suffix = "." + port_name
            for deep_id in nodes:
                if deep_id == port_id or not deep_id.startswith(prefix):
                    continue
                if not deep_id.endswith(suffix):
                    continue
                deep_node = self.graph._node_data.get(deep_id)
                if deep_node is None or deep_node.kind.name not in ("PORT_OUT", "PORT_IN"):
                    continue
                edge_src, edge_dst = (
                    (port_id, deep_id) if kind == "PORT_IN" else (deep_id, port_id)
                )
                already = any(
                    e.kind == EdgeKind.DRIVER
                    for e in self.graph._edge_data.get((edge_src, edge_dst), [])
                )
                if already:
                    continue
                self.graph.add_trace_edge(TraceEdge(
                    src=edge_src, dst=edge_dst,
                    kind=EdgeKind.DRIVER, assign_type="wrapper_passthrough",
                ))
                added += 1

        logger.debug("_elaborate_wrapper_passthroughs: added %d passthrough edges", added)

    def _mark_special_signals(self):
        for _node_id, node in self.graph._node_data.items():
            name_lower = safe_str(safe_attr(node, "name", "")).lower()

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
