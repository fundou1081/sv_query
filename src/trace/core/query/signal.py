import logging

# ==============================================================================
# query_signal.py - Simplified Signal Query
# ==============================================================================
from dataclasses import dataclass

from ..graph.models import DriverInfo, EdgeKind, NodeKind, SignalGraph, TraceNode

logger = logging.getLogger(__name__)
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
    def __init__(self, graph: SignalGraph, mig: object | None = None):
        """[PR3 2026-06-15] Init SignalTracer.

        Args:
            graph: SignalGraph
            mig: ModuleInstanceGraph (optional) - 跨模块 port 映射.
                 设 None 时走纯 graph 路径 (兼容旧调用).
                 设非 None 时, _collect_all_* 会在 0 results 时 fallback 走 MIG.
            [iter_272] MIG fallback 已删除: 图恒为实例级, 跨模块边就在图里。
        """
        self.graph = graph
        # [PR3 2026-06-15] ModuleInstanceGraph 是跨模块 port 映射.
        self.mig = mig

    def trace(self, signal: str, module: str = None) -> SignalChain:
        """Trace signal drivers and loads"""
        signal_id = self.make_id(signal, module)

        # [铁律3] 不可信则不输出 - 节点不存在时返回 uncertain
        if signal_id not in self.graph.nodes():
            return SignalChain(root=signal_id, drivers=[], loads=[], confidence="uncertain")

        # [iter_240] 作用域: 指定 module = 限定查询 → 不跨模块
        allow_cross = module is None
        drivers = self._collect_all_drivers(signal_id, allow_cross_module=allow_cross)
        loads = self._find_loads(signal_id, allow_cross_module=allow_cross)

        # [铁律3] 无驱动时返回 uncertain
        confidence = "high" if drivers else "uncertain"

        return SignalChain(root=signal_id, drivers=drivers, loads=loads, confidence=confidence)

    def make_id(self, signal: str, module: str = None) -> str:
        """把 (signal, module) 解析成图里的节点 id; module=None 时把 signal 当完整 id.

        [iter_241] 从 _make_id 转正: `LoadTracer` 等需要同一个解析规则的调用方
        必须复用它 —— 自己拼 `f"{module}.{signal}"` 会产生 `"None.sig"` 这种
        永不存在的 id (静默空结果).
        """
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

    def _collect_all_drivers(self, signal_id: str, max_depth: int | None = None,
                             allow_cross_module: bool = True,
                             scope_prefix: str | None = None) -> list[TraceNode]:
        """[P2] 递归收集所有驱动,包括实例端口追溯

        Args:
            signal_id: signal ID
            max_depth: None=无限递归, N=最多递归 N 层
        """
        drivers = []
        seen_ids = set()
        # [iter_240] 跨模块跳转已是遍历的一步 (见 _trace_drivers_recursive 的对端注入),
        # 不再需要"零结果时补一条 MIG"的兜底。
        self._trace_drivers_recursive(signal_id, drivers, seen_ids, current_depth=0, max_depth=max_depth,
                                      allow_cross_module=allow_cross_module, scope_prefix=scope_prefix)
        return drivers

    def _trace_drivers_recursive(
        self,
        signal_id: str,
        drivers: list[TraceNode],
        seen_ids: set,
        current_depth: int = 0,
        max_depth: int | None = None,
        allow_cross_module: bool = True,
        scope_prefix: str | None = None,
        bit_filter: int | None = None,
    ):
        """递归追溯驱动 —— **编排层**（规则实现见下方 `_rule_*` / `_handle_*`）。

        [iter_281 / PLAN P0.2] 原 343 行巨型函数按 6 类规则拆开：
          ① 节点缺失/位查询回退   → `_trace_missing_node`
          ② BIT_SELECT 位提升     → `_expand_incoming_bit_select` + `_maybe_lift_to_parent_bus`
          ③ 自环分类              → `_handle_self_loop`
          ④ 边类型过滤            → `_is_control_edge`
          ⑤ 连接边源分类          → `_handle_connection_source`
          ⑥ 驱动边追加/递归       → `_append_source` + `_recurse_if_unseen`

        行为与原实现逐项一致（由 `sim/tests/golden/graph_baseline` 与全量门禁证明）。
        """
        # ① depth / 命名空间 / 节点存在性（含位查询回退）
        if max_depth is not None and current_depth >= max_depth:
            return
        if scope_prefix and not self._in_scope(signal_id, scope_prefix):
            return
        if signal_id not in self.graph.nodes():
            self._trace_missing_node(signal_id, drivers, seen_ids,
                                     current_depth, max_depth, allow_cross_module)
            return

        seen_ids.add(signal_id)

        # [iter_294 / PLAN P6.1] 位节点自动带位上下文：表达式驱动按位映射
        # （`s[3]` 或回退到总线 s 且 bit_filter=3 时，s[i]←操作数位）
        _own_bit = self._bit_index_of(signal_id)
        if _own_bit is not None and bit_filter is None:
            bit_filter = _own_bit

        # 类型级 class 属性 = 结构宿主非数据端点（iter_154 C4-A / D3）
        _node = self.graph.get_node(signal_id)
        if _node is not None and _node.kind.name == "CLASS_PROPERTY":
            return

        # ② 位级：先看"位 → 本节点"的子节点，再看"本节点 → 父总线"的提升
        has_driver_edge = self._has_incoming_driver(signal_id)
        if not has_driver_edge:
            self._expand_incoming_bit_select(signal_id, drivers, seen_ids,
                                             current_depth, max_depth, allow_cross_module,
                                             bit_filter)
        self._maybe_lift_to_parent_bus(signal_id, has_driver_edge, drivers, seen_ids,
                                       current_depth, max_depth, allow_cross_module,
                                       bit_filter)

        # ③~⑥ 遍历所有指向本信号的边
        for src, dst in list(self.graph.edges()):
            if dst != signal_id:
                continue

            # ③ 自环（state = state）
            if src == signal_id:
                self._handle_self_loop(src, drivers)
                continue

            edge = self._pick_driver_edge(src, dst)

            # [iter_290 / P5.1 F1] 位级回退时, 父总线的 BIT_SELECT 子节点只取
            # 覆盖该位的那个切片 —— 否则 y[5] 会把 y[3:0] 的驱动也带回来。
            if (bit_filter is not None and edge is not None
                    and edge.kind == EdgeKind.BIT_SELECT
                    and not self._bit_in_range(src, bit_filter)):
                continue

            # 边不存在：按"其他边类型"继续向上追溯（原实现行为）
            if edge is None:
                self._recurse_if_unseen(src, drivers, seen_ids,
                                        current_depth + 1, max_depth, allow_cross_module)
                continue

            if edge.kind != EdgeKind.DRIVER:
                # ④ 控制类边（时钟/复位/分支/case）：不 append、不递归
                if self._is_control_edge(edge.kind):
                    continue
                # ⑤ 连接边：按源节点类别分流
                if edge.kind == EdgeKind.CONNECTION:
                    self._handle_connection_source(
                        src, drivers, seen_ids, current_depth, max_depth, allow_cross_module)
                    continue
                self._recurse_if_unseen(src, drivers, seen_ids,
                                        current_depth + 1, max_depth, allow_cross_module)
                continue

            # ⑥ 驱动边：先试表达式按位映射（s[i] ← 操作数位），再回退总线
            if bit_filter is not None:
                mapped = self._expr_source_bits(edge, signal_id, bit_filter)
                if mapped is not None:
                    handled = False
                    missing = False
                    for sid in mapped:
                        if sid in seen_ids:
                            handled = True
                            continue
                        if sid not in self.graph.nodes():
                            missing = True  # 位节点不存在 → 该操作数回落总线
                            continue
                        node = self.graph.get_node(sid)
                        if node is not None:
                            drivers.append(node)
                            seen_ids.add(sid)
                        self._trace_drivers_recursive(
                            sid, drivers, seen_ids, current_depth + 1, max_depth,
                            allow_cross_module, bit_filter=self._bit_index_of(sid))
                        handled = True
                    if missing:
                        # 部分位节点不存在：补该操作数的总线（保持完整，粒度退化为总线）
                        self._append_source(src, drivers, seen_ids,
                                            current_depth, max_depth, allow_cross_module)
                        handled = True
                    if handled or not mapped:
                        continue

            # 追加源节点（字面量是叶子），并继续向上追溯
            self._append_source(src, drivers, seen_ids,
                                current_depth, max_depth, allow_cross_module)

        # [iter_295 / PLAN P7.1] 位节点已有自己的位驱动（多驱动/位覆盖）时，
        # F2 的父总线提升不会触发；这里补父总线的表达式/拷贝驱动（按位映射），
        # 保证多驱动场景两个源都在（如 assign y=a; assign y[3]=1'b1）。
        if bit_filter is not None and has_driver_edge:
            self._trace_parent_bit_drivers(
                signal_id, drivers, seen_ids, current_depth, max_depth, allow_cross_module)

    # ------------------------------------------------------------------
    # 6 类规则的具体实现
    # ------------------------------------------------------------------

    def _trace_missing_node(self, signal_id, drivers, seen_ids,
                            current_depth, max_depth, allow_cross_module):
        """节点不在图里：part-select 范围保持空答；位查询回退到父总线。

        [iter_290 / P5.1] 回退时把**位索引**传下去：父总线的 BIT_SELECT 子节点
        只取覆盖该位的切片，避免跨位污染。
        """
        if ":" in signal_id:
            return  # [iter_126] part-select 范围 [a:b] 保持空答 (locked truth)
        bit = self._bit_index_of(signal_id)
        if bit is None:
            return
        base = signal_id.rsplit("[", 1)[0]
        if base in self.graph.nodes() and base not in seen_ids:
            self._trace_drivers_recursive(base, drivers, seen_ids, current_depth,
                                          max_depth, allow_cross_module, bit_filter=bit)

    def _has_incoming_driver(self, signal_id: str) -> bool:
        """是否存在指向本节点的 DRIVER 边（BIT_SELECT 不算）。"""
        for src, dst in self.graph.edges():
            if dst == signal_id and self.graph.get_edge(src, dst).kind == EdgeKind.DRIVER:
                return True
        return False

    def _expand_incoming_bit_select(self, signal_id, drivers, seen_ids,
                                    current_depth, max_depth, allow_cross_module,
                                    bit_filter=None):
        """无 DRIVER 时，先追"位 → 本节点"的 BIT_SELECT 子节点（如 modport 实例）。

        [iter_290 / P5.1] `bit_filter` 给定时只追覆盖该位的切片。
        """
        for src, dst in list(self.graph.edges()):
            if dst != signal_id:
                continue
            edge = self.graph.get_edge(src, dst)
            if not (edge and edge.kind == EdgeKind.BIT_SELECT and src not in seen_ids):
                continue
            if bit_filter is not None and not self._bit_in_range(src, bit_filter):
                continue
            self._trace_drivers_recursive(src, drivers, seen_ids, current_depth,
                                          max_depth, allow_cross_module)

    def _maybe_lift_to_parent_bus(self, signal_id, has_driver_edge, drivers, seen_ids,
                                  current_depth, max_depth, allow_cross_module,
                                  bit_filter=None):
        """位级查询提升：叶子位（无任何真实来源）沿 BIT_SELECT 出边提到父总线。

        三个否定条件缺一不可（iter_126/128/132 的教训，详见 git 历史）：
          - 无 incoming DRIVER：有直接驱动就不该绕到父 struct/总线（会带回兄弟字段）
          - 无 incoming CONNECTION：generate per-entry 位有真实来源，提升会把各 entry 串起来
          - drivers 为空：递归中间节点不提升（否则 seen 污染兄弟位）
        提升目标限 data 类节点，避免把 interface 实例（INSTANTIATED_MODULE）当总线。
        """
        if has_driver_edge or ":" in signal_id:
            return
        if self._has_incoming_connection(signal_id):
            return

        # [iter_290 / P5.2 F2] 位节点死胡同：递归到这里时 drivers 已含该位节点
        # （它只是"别人驱动列表里的一项"），但位节点本身没有 incoming 驱动
        # （典型: assign s = a & b; assign y = s[3]; 的 s[3]）。
        # 旧规则 "drivers 非空就不提升" 会停在死胡同, 丢掉 s 的真实驱动。
        # 现在: 位节点 + 父总线**本身有 incoming** 时才补追父总线（总线粒度）;
        # 父总线没有 incoming（顶层输入位）不提升, 保持原行为。
        own_bit = self._bit_index_of(signal_id)
        if drivers:
            if own_bit is None:
                return
            parent = self._bit_select_parent(signal_id)
            if parent is None or not self._has_any_incoming(parent):
                return
        _liftable = {"SIGNAL", "PORT_OUT", "PORT_IN", "REG"}
        for src, dst in list(self.graph.edges()):
            if src != signal_id or dst == signal_id or dst in seen_ids:
                continue
            edge = self.graph.get_edge(src, dst)
            if not edge or edge.kind != EdgeKind.BIT_SELECT:
                continue
            dst_node = self.graph.get_node(dst)
            if dst_node and dst_node.kind.name in _liftable:
                # 位节点提升时把自己的位索引带下去（父总线按位过滤切片）
                own_bit = self._bit_index_of(signal_id)
                self._trace_drivers_recursive(dst, drivers, seen_ids, current_depth + 1,
                                              max_depth, allow_cross_module,
                                              bit_filter=own_bit)
                if drivers:
                    break

    # [iter_294 / PLAN P6.1] 表达式运算符 → 位依赖规则
    _EXPR_SAME_INDEX = frozenset({
        "BinaryAnd", "BinaryOr", "BinaryXor", "BinaryXnor",
        "And", "Or", "Xor", "Xnor",
        "Not", "BitwiseNot", "LogicalNot", "UnaryBitwiseNot",
        # [iter_295 / PLAN P7.1] 直接拷贝 assign y = a（无 op 元数据）
        "DirectCopy",
    })
    _EXPR_PREFIX = frozenset({
        "Add", "Subtract", "Multiply", "Power", "UnaryMinus", "UnaryPlus",
    })
    _EXPR_SHIFT = frozenset({
        "LogicalShiftLeft", "LogicalShiftRight",
        "ArithmeticShiftLeft", "ArithmeticShiftRight",
    })

    @staticmethod
    def _bit_base(node_id: str) -> str:
        """`top.a[7:4]` / `top.a[3]` → `top.a`；普通总线原样返回。"""
        import re as _re

        m = _re.match(r"^(.*)\[\d+(?::\d+)?\]$", node_id)
        return m.group(1) if m else node_id

    @staticmethod
    def _node_width(node) -> int | None:
        w = getattr(node, "width", None)
        if isinstance(w, (tuple, list)) and len(w) >= 2:
            try:
                return abs(int(w[0]) - int(w[1])) + 1
            except (TypeError, ValueError):
                return None
        return None

    def _rel_bit(self, node_id: str, bit: int) -> int:
        """[iter_294] 把"信号内的绝对位索引"换算成**该节点内的相对位**。

        位节点（宽 1）的绝对索引是它在父总线里的位置，映射到自身时相对位 = 0；
        切片节点 `a[7:4]` 的相对位 = bit - 4；普通总线原样返回。
        """
        node = self.graph.get_node(node_id)
        if node is None:
            return bit
        if self._node_width(node) == 1 and node.parent_bit_start is not None:
            return 0
        import re as _re

        m = _re.match(r"^(.*)\[(\d+):(\d+)\]$", node_id)
        if m:
            return bit - min(int(m.group(2)), int(m.group(3)))
        # 单 bit 节点（ElementSelect 未设 parent_bit_start）→ 相对位 0
        if _re.match(r"^.*\[\d+\]$", node_id):
            return 0
        return bit

    def _parent_driver_sources(self, node_id: str):
        """[iter_294 / PLAN P6.1] 位节点的**父总线** incoming DRIVER 边。

        表达式驱动挂在总线上（`s = a & b` 的边是 `a → s`），不在 `s[3]` 上；
        depth=1 的位查询也要按运算符映射这些父总线边。
        """
        node = self.graph.get_node(node_id)
        parent = getattr(node, "parent", None) if node is not None else None
        if not parent or parent == node_id or parent not in self.graph.nodes():
            return []
        out = []
        for src in self.graph.predecessors(parent):
            if src in (node_id, parent):
                continue
            edge = self.graph.get_edge(src, parent)
            if edge is not None and edge.kind == EdgeKind.DRIVER:
                out.append((src, edge))
        return out

    def _parent_driver_loads(self, node_id: str):
        """[iter_294 / PLAN P6.2] 位节点的**父总线** outgoing DRIVER 边。

        表达式负载挂在总线上（`a & b` 的边是 `a → s`），不在 `a[3]` 上；
        位查询 fanout 时必须把父总线的表达式边按位映射过来。
        返回 [(succ, edge), ...]，排除自环与节点自身。
        """
        node = self.graph.get_node(node_id)
        parent = getattr(node, "parent", None) if node is not None else None
        if not parent or parent == node_id or parent not in self.graph.nodes():
            return []
        out = []
        for succ in self.graph.successors(parent):
            if succ in (node_id, parent):
                continue
            edge = self.graph.get_edge(parent, succ)
            if edge is not None and edge.kind == EdgeKind.DRIVER and edge.source is not None:
                out.append((succ, edge))
        return out

    def _concat_items(self, edge, dst_id: str):
        """[iter_295 / PLAN P7.2] 解析 `{a, b[3:0], ...}` 的位段布局。

        返回 [{name, base, lo, width, start}]（start = 在 dst 中的起始位，
        LSB 对齐：最右操作数占 start=0）；无法解析（字面量/嵌套/未知宽度）→ None。
        """
        import re as _re

        expr = (getattr(edge, "expression", "") or "").strip()
        if not (expr.startswith("{") and expr.endswith("}")):
            return None
        body = expr[1:-1]
        if "{" in body or "}" in body:
            return None  # 嵌套拼接：v1 不处理
        parts = [p.strip() for p in body.split(",")]
        module = dst_id.rsplit(".", 1)[0] if "." in dst_id else ""

        items = []
        for part in parts:
            m = _re.match(r"^([A-Za-z_]\w*)(?:\[(\d+)(?::(\d+))?\])?$", part)
            if not m:
                return None  # 字面量/表达式：v1 不处理（避免猜宽度）
            name, hi_s, lo_s = m.group(1), m.group(2), m.group(3)
            full = f"{module}.{name}" if module else name
            if full not in self.graph.nodes():
                full = edge.src if edge.src.rsplit(".", 1)[-1] == name else None
            if full is None or full not in self.graph.nodes():
                return None
            if hi_s is None:
                lo, width = 0, self._node_width(self.graph.get_node(full))
            elif lo_s is None:
                lo, width = int(hi_s), 1
            else:
                hi, lo = int(hi_s), int(lo_s)
                lo, width = min(hi, lo), abs(hi - lo) + 1
            if not width:
                return None
            items.append({"name": name, "base": full, "lo": lo, "width": width})

        start = 0
        for item in reversed(items):  # 最右操作数在低位
            item["start"] = start
            start += item["width"]
        return items

    @staticmethod
    def _direct_copy_op(edge) -> str | None:
        """[iter_295 / PLAN P7.1] 无运算符但表达式就是源信号本身 → 直接拷贝。

        `assign y = a;` 的 DRIVER 边没有 `source.op`，但 `expression == "a"`
        （源短名）。这种边可以安全地按同索引做位映射。
        """
        expr = (getattr(edge, "expression", "") or "").strip()
        if not expr:
            return None
        short = edge.src.rsplit(".", 1)[-1]
        return "DirectCopy" if expr == short else None

    def _expr_source_bits(self, edge, dst_id: str, want_bit: int) -> list[str] | None:
        """[iter_294 / PLAN P6.1] `s[i]` 依赖的**操作数位节点 id** 列表。

        `want_bit` 是**父总线内的绝对位索引**（位节点 s[3] → 3）。
        来源是总线时用绝对位；来源本身是位/切片节点时用节点内相对位。

        返回:
          - `None`  = 该运算符不做逐位映射（调用方回落总线）
          - `[]`    = 已知该位不依赖此操作数（如移位越界，直接跳过）
          - `[id…]` = 候选操作数位（可能不在图里，调用方过滤）
        """
        src_info = getattr(edge, "source", None)
        if src_info is None:
            return None
        op = (getattr(src_info, "op", "") or "").strip()
        if not op:
            op = self._direct_copy_op(edge)
            if op is None:
                return None

        src_node = self.graph.get_node(edge.src)
        dst_node = self.graph.get_node(dst_id)
        if dst_node is None:
            return None
        dst_w = self._node_width(dst_node) or 1
        src_w = self._node_width(src_node) or dst_w

        abs_pos = want_bit
        rel_pos = self._rel_bit(dst_id, want_bit)
        src_is_bus = "[" not in edge.src
        pos = abs_pos if src_is_bus else rel_pos
        base = self._bit_base(edge.src)

        if src_info.bit_start is not None and src_info.bit_end is not None:
            lo = min(int(src_info.bit_start), int(src_info.bit_end))
            hi = max(int(src_info.bit_start), int(src_info.bit_end))
        else:
            lo, hi = 0, max(0, (src_w or 1) - 1)

        # 拼接表达式优先（操作数边可能是 op=Slice/Concat，expr 以 '{' 开头）
        items = self._concat_items(edge, dst_id)
        if items is not None:
            src_name = getattr(src_info, "signal", "") or ""
            dst_is_slice = "[" in dst_id and dst_w > 1
            pos = self._rel_bit(dst_id, abs_pos) if dst_is_slice else abs_pos
            for item in items:
                if item["name"] != src_name:
                    continue
                if not (item["start"] <= pos < item["start"] + item["width"]):
                    return []
                if item["width"] == 1:
                    return [f"{item['base']}[{item['lo']}]"]
                r = pos - item["start"]
                return [f"{item['base']}[{item['lo'] + r}]"]
            return None

        if op in self._EXPR_SAME_INDEX:
            if src_w == 1:
                return [f"{base}[{lo}]"]
            bit = lo + pos
            if bit > hi:
                return []
            return [f"{base}[{bit}]"]

        if op in self._EXPR_PREFIX:
            if src_w == 1:
                return [f"{base}[{lo}]"]
            top = min(hi, lo + pos)
            return [f"{base}[{b}]" for b in range(lo, top + 1)]

        if op in self._EXPR_SHIFT:
            import re as _re

            m = _re.search(r"(<<<|>>>|<<|>>)\s*(\d+)", getattr(edge, "expression", "") or "")
            if not m:
                return None
            k = int(m.group(2))
            left = "<<" in m.group(1)
            bit = pos - k if left else pos + k
            if bit < lo or bit > hi:
                return []
            return [f"{base}[{bit}]"]

        if op == "Slice":
            bit = lo + rel_pos
            if bit > hi:
                return []
            return [f"{base}[{bit}]"]

        if op == "Concat":
            items = self._concat_items(edge, dst_id)
            if items is None:
                return None
            src_name = getattr(src_info, "signal", "") or ""
            for item in items:
                if item["name"] != src_name:
                    continue
                if not (item["start"] <= abs_pos < item["start"] + item["width"]):
                    return []  # 该位属于别的操作数（无依赖）
                r = abs_pos - item["start"]
                return [f"{item['base']}[{item['lo'] + r}]"]
            return None

        return None

    def _expr_dst_bits(self, edge, src_bit: int) -> list[str] | None:
        """[iter_294 / PLAN P6.2] `a[j]` 影响的**结果位节点 id** 列表（fanout 方向）。

        `src_bit` 是源信号在父总线内的绝对位索引；源本身是位/切片时用相对位。

        None = 该运算符不做逐位映射；[] = 已知不影响任何位（移位越界）；
        [id…] = 候选结果位（可能不在图里）。
        """
        src_info = getattr(edge, "source", None)
        if src_info is None:
            return None
        op = (getattr(src_info, "op", "") or "").strip()
        if not op:
            op = self._direct_copy_op(edge)
            if op is None:
                return None
        dst_id = edge.dst
        if "[" in dst_id:
            return None
        dst_node = self.graph.get_node(dst_id)
        if dst_node is None:
            return None
        dst_w = self._node_width(dst_node) or 0
        src_node = self.graph.get_node(edge.src)
        src_w = self._node_width(src_node) or dst_w

        abs_pos = src_bit
        rel_pos = self._rel_bit(edge.src, src_bit)
        src_is_bus = "[" not in edge.src
        pos = abs_pos if src_is_bus else rel_pos

        items = self._concat_items(edge, dst_id)
        if items is not None:
            src_name = getattr(src_info, "signal", "") or ""
            for item in items:
                if item["name"] != src_name:
                    continue
                if item["width"] == 1:
                    bit = item["start"]
                else:
                    r = pos
                    if not (0 <= r < item["width"]):
                        return []
                    bit = item["start"] + r
                if bit < 0 or bit >= dst_w:
                    return []
                return [f"{dst_id}[{bit}]"]
            return None

        if op in self._EXPR_SAME_INDEX:
            bit = 0 if src_w == 1 else pos
            if bit < 0 or bit >= dst_w:
                return []
            return [f"{dst_id}[{bit}]"]

        if op in self._EXPR_PREFIX:
            start = max(0, pos)
            return [f"{dst_id}[{b}]" for b in range(start, dst_w)]

        if op in self._EXPR_SHIFT:
            import re as _re

            m = _re.search(r"(<<<|>>>|<<|>>)\s*(\d+)", getattr(edge, "expression", "") or "")
            if not m:
                return None
            k = int(m.group(2))
            left = "<<" in m.group(1)
            bit = pos + k if left else pos - k
            if bit < 0 or bit >= dst_w:
                return []
            return [f"{dst_id}[{bit}]"]

        if op == "Slice":
            bit = rel_pos
            if bit < 0 or bit >= dst_w:
                return []
            return [f"{dst_id}[{bit}]"]

        if op == "Concat":
            items = self._concat_items(edge, dst_id)
            if items is None:
                return None
            src_name = getattr(src_info, "signal", "") or ""
            for item in items:
                if item["name"] != src_name:
                    continue
                r = src_bit - item["lo"]
                if not (0 <= r < item["width"]):
                    return []
                bit = item["start"] + r
                if bit < 0 or bit >= dst_w:
                    return []
                return [f"{dst_id}[{bit}]"]
            return None

        return None

    @staticmethod
    def _bit_index_of(node_id: str) -> int | None:
        """从节点 id 取单 bit 索引（`top.y[3]` → 3）；slice/总线返回 None。"""
        import re

        m = re.search(r"\[(\d+)\]$", node_id)
        return int(m.group(1)) if m else None

    def _bit_in_range(self, child_id: str, bit: int) -> bool:
        """`child_id` 这个切片是否覆盖父信号的 `bit` 位（无法判定时保守返回 True）。"""
        node = self.graph.get_node(child_id)
        if node is not None and node.parent_bit_start is not None:
            end = node.parent_bit_end if node.parent_bit_end is not None else node.parent_bit_start
            return node.parent_bit_start <= bit <= end
        import re

        m = re.search(r"\[(\d+)(?::(\d+))?\]$", child_id)
        if not m:
            return True
        hi = int(m.group(1))
        lo = int(m.group(2)) if m.group(2) is not None else hi
        return min(lo, hi) <= bit <= max(lo, hi)

    def _bit_select_parent(self, node_id: str) -> str | None:
        """位节点 → BIT_SELECT 出边指向的父总线（不存在返回 None）。"""
        for nxt in self.graph.successors(node_id):
            if nxt == node_id:
                continue
            edge = self.graph.get_edge(node_id, nxt)
            if edge is not None and edge.kind == EdgeKind.BIT_SELECT:
                return nxt
        return None

    def _has_any_incoming(self, node_id: str) -> bool:
        """节点是否有任何 incoming 边（DRIVER / CONNECTION 等）。"""
        return any(True for _ in self.graph.predecessors(node_id))

    def _has_incoming_connection(self, signal_id: str) -> bool:
        for src, dst in self.graph.edges():
            if dst == signal_id and self.graph.get_edge(src, dst).kind == EdgeKind.CONNECTION:
                return True
        return False

    def _trace_parent_bit_drivers(self, signal_id, drivers, seen_ids,
                                  current_depth, max_depth, allow_cross_module):
        """[iter_295 / PLAN P7.1] 位节点：父总线上的驱动按位映射后并入。

        用于多驱动/位覆盖（`assign y = a; assign y[3] = 1'b1;`）：
        位节点 y[3] 已有自己的驱动，F2 不会提升到父总线，但 y 的总线拷贝
        仍然是 y[3] 的一个（同索引）驱动。
        """
        bit = self._bit_index_of(signal_id)
        if bit is None:
            return
        for psrc, pedge in self._parent_driver_sources(signal_id):
            # 父总线边的 dst 是总线本身；位位置用绝对索引（y[1] → 1）
            mapped = self._expr_source_bits(pedge, pedge.dst, bit)
            if mapped is None:
                continue
            handled = False
            missing = False
            for sid in mapped:
                if sid in seen_ids:
                    handled = True   # 依赖已由别的边满足，不再回退总线
                    continue
                if sid not in self.graph.nodes():
                    missing = True
                    continue
                node = self.graph.get_node(sid)
                if node is not None:
                    drivers.append(node)
                    seen_ids.add(sid)
                self._trace_drivers_recursive(
                    sid, drivers, seen_ids, current_depth + 1, max_depth,
                    allow_cross_module, bit_filter=self._bit_index_of(sid))
                handled = True
            if missing or not handled:
                if psrc in self.graph.nodes() and psrc not in seen_ids:
                    node = self.graph.get_node(psrc)
                    if node is not None:
                        drivers.append(node)
                        seen_ids.add(psrc)
                    self._trace_drivers_recursive(
                        psrc, drivers, seen_ids, current_depth + 1, max_depth,
                        allow_cross_module)

    def _handle_self_loop(self, src, drivers):
        """自环分两类：internal 标记 = 实例端口占位（跳过）；其他 = 真自依赖（保留）。"""
        loop_edges = self.graph.get_edges(src, src)
        if any(getattr(e, "assign_type", "") == "internal" and e.kind == EdgeKind.DRIVER
               for e in loop_edges):
            return
        node = self.graph.get_node(src)
        if node:
            drivers.append(node)

    @staticmethod
    def _is_control_edge(kind) -> bool:
        """控制类边不是数据驱动源（时钟/复位/三目分支/case）。"""
        return kind in (
            EdgeKind.CLOCK,
            EdgeKind.RESET,
            EdgeKind.BRANCH_CONDITION,
            EdgeKind.BRANCH_TRUE,
            EdgeKind.BRANCH_FALSE,
            EdgeKind.BRANCH_RESULT,
            EdgeKind.CASE_SELECT,
            EdgeKind.CASE_ITEM,
            EdgeKind.CASE_RESULT,
        )

    def _pick_driver_edge(self, src, dst):
        """同一 (src,dst) 有多条边时优先取 DRIVER（wrapper_passthrough 与 CONNECTION 并存）。"""
        edge = self.graph.get_edge(src, dst)
        if edge is not None and edge.kind != EdgeKind.DRIVER:
            driver_edge = next((e for e in self.graph.get_edges(src, dst)
                                if e.kind == EdgeKind.DRIVER), None)
            if driver_edge is not None:
                return driver_edge
        return edge

    def _append_source(self, src, drivers, seen_ids, current_depth, max_depth, allow_cross_module):
        """DRIVER 边的源：字面量是叶子（只追加），其他追加后继续向上追溯。"""
        node = self.graph.get_node(src)
        if node is not None and node.kind == NodeKind.CONST:
            if node.id not in seen_ids:
                drivers.append(node)
                seen_ids.add(node.id)
            return
        if node is not None and node.id not in seen_ids:
            drivers.append(node)
        self._recurse_if_unseen(src, drivers, seen_ids, current_depth + 1,
                                max_depth, allow_cross_module)

    def _recurse_if_unseen(self, src, drivers, seen_ids, next_depth, max_depth, allow_cross_module):
        if src in self.graph.nodes() and src not in seen_ids:
            self._trace_drivers_recursive(src, drivers, seen_ids, next_depth,
                                          max_depth, allow_cross_module)

    def _handle_connection_source(self, src, drivers, seen_ids,
                                  current_depth, max_depth, allow_cross_module):
        """CONNECTION 边的源节点分流：实例输出端口 / 外部输入 / 中间线网 / 其他。"""
        node = self.graph.get_node(src)
        kind = node.kind.name if node is not None else None
        args = (src, drivers, seen_ids, current_depth, max_depth, allow_cross_module)
        if kind == "PORT_OUT" and src.count(".") >= 2:
            self._handle_port_out_source(*args)
        elif kind == "PORT_IN":
            self._handle_port_in_source(*args)
        elif kind == "SIGNAL":
            self._handle_wire_source(*args)
        else:
            # 其他类别（REG 等）按"其他边类型"继续向上追（原实现 fallthrough 行为）
            self._recurse_if_unseen(src, drivers, seen_ids, current_depth + 1,
                                    max_depth, allow_cross_module)

    def _handle_port_out_source(self, src, drivers, seen_ids,
                                current_depth, max_depth, allow_cross_module):
        """实例输出端口 = 透明映射点（可能跨 wrapper 兄弟实例）。"""
        node = self.graph.get_node(src)
        if node.id not in seen_ids:
            drivers.append(node)
            seen_ids.add(node.id)
        inst_path, port_name = src.rsplit(".", 1)

        # 触发器 q/d 互补端口
        mate = {"q": "d", "d": "q"}.get(port_name)
        if mate:
            mate_id = f"{inst_path}.{mate}"
            if mate_id in self.graph.nodes() and mate_id not in seen_ids:
                self._trace_drivers_recursive(mate_id, drivers, seen_ids,
                                              current_depth + 1, max_depth, allow_cross_module)

        if self._has_internal_driver(src):
            # 实例内部有驱动：只沿 wrapper_passthrough 源继续
            # （continuous/nonblocking = 真模块内部 assign，粒度停在此端口）
            for ps in self._wrapper_passthrough_sources(src):
                self._recurse_if_unseen(ps, drivers, seen_ids, current_depth + 1,
                                        max_depth, allow_cross_module)
        else:
            # 真 wrapper 端口（无内部驱动）：跨到同模块类型的兄弟实例同名端口
            for sib in self._sibling_ports(inst_path, port_name):
                self._recurse_if_unseen(sib, drivers, seen_ids, current_depth + 1,
                                        max_depth, allow_cross_module)

    def _handle_port_in_source(self, src, drivers, seen_ids,
                               current_depth, max_depth, allow_cross_module):
        """外部输入端口（无前驱）才是有效驱动源；有前驱则不追加也不递归。

        （与旧实现一致：PORT_IN 分支自带 `continue`，不再落到"其他边类型"追溯。）
        """
        node = self.graph.get_node(src)
        if list(self.graph.predecessors(node.id)):
            return
        if node.id not in seen_ids:
            drivers.append(node)
            seen_ids.add(node.id)

    def _handle_wire_source(self, src, drivers, seen_ids,
                            current_depth, max_depth, allow_cross_module):
        """中间线网：位桥中间节点继续追内部；普通线网作为驱动停靠。"""
        node = self.graph.get_node(src)
        bus_parent = src.rsplit("[", 1)[0] if "[" in src else None
        bus_node = self.graph.get_node(bus_parent) if bus_parent else None
        if (bus_node is not None and bus_node.kind.name == "PORT_OUT"
                and src in self.graph.nodes() and src not in seen_ids):
            self._trace_drivers_recursive(src, drivers, seen_ids, current_depth + 1,
                                          max_depth, allow_cross_module)
            return
        if node.id not in seen_ids:
            drivers.append(node)
            seen_ids.add(node.id)

    def _has_internal_driver(self, src: str) -> bool:
        """该实例端口是否有真实内部驱动（任意非 internal 的 DRIVER 边指向它）。"""
        for p, d in self.graph.edges():
            if d != src:
                continue
            for e in self.graph.get_edges(p, src):
                if e.kind == EdgeKind.DRIVER and e.assign_type != "internal":
                    return True
        return False

    def _wrapper_passthrough_sources(self, src: str) -> list[str]:
        """指向 src 的 wrapper_passthrough DRIVER 源（graph_builder 后处理加的直通边）。"""
        out = []
        for ps, pd in self.graph.edges():
            if pd != src:
                continue
            for pe in self.graph.get_edges(ps, pd):
                if (pe.kind == EdgeKind.DRIVER and pe.assign_type == "wrapper_passthrough"
                        and ps in self.graph.nodes()):
                    out.append(ps)
                    break
        return out

    def _find_drivers(self, signal_id: str, allow_cross_module: bool = True,
                      scope_prefix: str | None = None) -> list[TraceNode]:
        """[兼容] 直接驱动"""
        if signal_id not in self.graph.nodes():
            return []
        # [iter_154 C4-A] 类型级 class 属性非数据端点 (D3) — depth=1 同守卫
        _kn = self.graph.get_node(signal_id)
        if _kn is not None and _kn.kind.name == "CLASS_PROPERTY":
            return []

        drivers = []
        # [iter_272] 不再注入 MIG 虚拟对端 (实例级图跨模块是普通图边)。
        for src, dst in list(self.graph.edges()):
            if dst == signal_id:
                # [iter_127 A3] 与 _trace_drivers_recursive 同规则: 跳过
                # 实例输出端口 "模块内部驱动" internal 自环标记 (非真实源).
                if src == dst:
                    _loop_edges = self.graph.get_edges(src, dst)
                    if any(
                        getattr(e, "assign_type", "") == "internal"
                        and e.kind == EdgeKind.DRIVER
                        for e in _loop_edges
                    ):
                        continue
                # [iter_294 / PLAN P6.1] 位查询的直接驱动也按运算符映射到操作数位
                want_bit = self._bit_index_of(signal_id)
                if want_bit is not None:
                    edge = self.graph.get_edge(src, dst)
                    if edge is not None and edge.kind == EdgeKind.DRIVER:
                        mapped = self._expr_source_bits(edge, signal_id, want_bit)
                        if mapped is not None:
                            existing = [self.graph.get_node(m) for m in mapped
                                        if m in self.graph.nodes()]
                            existing = [n for n in existing if n is not None]
                            if existing:
                                for n in existing:
                                    if n.id not in {d.id for d in drivers}:
                                        drivers.append(n)
                            else:
                                node = self.graph.get_node(src)
                                if node and self._in_scope(node.id, scope_prefix):
                                    drivers.append(node)
                            continue
                node = self.graph.get_node(src)
                if node and self._in_scope(node.id, scope_prefix):
                    drivers.append(node)

        # [iter_294 / PLAN P6.1] 位节点：父总线上的表达式驱动按位映射
        want_bit = self._bit_index_of(signal_id)
        if want_bit is not None:
            for psrc, pedge in self._parent_driver_sources(signal_id):
                mapped = self._expr_source_bits(pedge, pedge.dst, want_bit)
                if mapped is None:
                    continue
                existing = [self.graph.get_node(m) for m in mapped
                            if m in self.graph.nodes()]
                existing = [n for n in existing if n is not None]
                if existing:
                    for n in existing:
                        if n.id not in {d.id for d in drivers}:
                            drivers.append(n)
                else:
                    node = self.graph.get_node(psrc)
                    if (node and self._in_scope(node.id, scope_prefix)
                            and node.id not in {d.id for d in drivers}):
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

    @staticmethod
    def _scope_prefix_for(signal_id: str, allow_cross: bool) -> str | None:
        """限定查询的命名空间前缀 (允许跨模块时为 None)。"""
        if allow_cross or "." not in signal_id:
            return None
        return signal_id.rsplit(".", 1)[0]

    def _sibling_ports(self, inst_path: str, port_name: str) -> list[str]:
        """[iter_276] 同模块类型的**兄弟实例**同名端口 (wrapper 直通跨实例)。

        旧实现比较"模块定义 short name" (`port_to_module_type`), 属双命名空间产物;
        现在用 MIG 的 module_type 判定, 只看图里存在的节点。
        """
        mig = self.mig
        if mig is None:
            return []
        instances = getattr(mig, "instances", {}) or {}
        cur = instances.get(inst_path)
        if cur is None:
            return []
        module_type = getattr(cur, "module_type", None)
        if not module_type:
            return []
        out: list[str] = []
        for iid, inode in instances.items():
            if iid == inst_path or getattr(inode, "module_type", None) != module_type:
                continue
            cand = f"{iid}.{port_name}"
            if cand in self.graph.nodes():
                out.append(cand)
        return out

    def _lift_missing_bit(self, signal_id: str) -> str | None:
        """[iter_285 / PLAN P2.1] 位查询落到**不存在的位节点** → 提升到父总线。

        与 fanin 的 `_trace_missing_node` 对称：纯总线直连（子模块 `.y(y)`）
        没有 per-bit 节点时，`fanout(top.din[3])` 应回答 `top.din` 的总线级负载，
        而不是空集。带 `:` 的 part-select 保持空答（与 fanin 契约一致）。
        """
        if signal_id in self.graph.nodes():
            return signal_id
        if ":" in signal_id:
            return None
        import re
        m = re.match(r"^(.*)\[\d+\]$", signal_id)
        if not m:
            return None
        base = m.group(1)
        return base if base in self.graph.nodes() else None

    def _load_bus_fallback(self, signal_id: str) -> str:
        """[iter_292 / PLAN P5.6] 位节点无 load 边 → 用父总线的负载（与 fanin F2 对称）。

        背景：F3 会把切片两侧展开成逐位节点，但负载可能仍挂在**总线**上
        （如 `assign z = w` 读整条总线）。此时 `fanout(w[4])` 若只看位节点会空答。
        规则：位节点存在、但没有任何 DRIVER/CONNECTION 出边（不含自环）→
        若存在 BIT_SELECT 父总线且有负载，则改用父总线。
        """
        node = self.graph.get_node(signal_id)
        if node is None or node.parent is None:
            return signal_id
        has_load = any(
            src == signal_id and dst != signal_id
            and any(e.kind in (EdgeKind.DRIVER, EdgeKind.CONNECTION)
                    for e in self.graph.get_edges(src, dst))
            for src, dst in self.graph.edges()
        )
        if has_load:
            return signal_id
        parent = node.parent
        if parent in self.graph.nodes() and any(True for _ in self.graph.successors(parent)):
            return parent
        return signal_id

    @staticmethod
    def _in_scope(node_id: str, scope_prefix: str | None) -> bool:
        """[iter_271] 限定查询的作用域判定 (实例级图下的 "只看这个实例内部")。

        实例级图里跨模块是普通图边, 单靠 `allow_cross_module=False` 已经挡不住
        (那只关掉 MIG 虚拟跳)。这里按**命名空间前缀**过滤。
        """
        if not scope_prefix:
            return True
        return node_id == scope_prefix or node_id.startswith(scope_prefix + ".")

    def _find_loads(self, signal_id: str, allowed_kinds: set | None = None,
                    allow_cross_module: bool = True,
                    scope_prefix: str | None = None,
                    bit_index: int | None = None) -> list[TraceNode]:
        if signal_id not in self.graph.nodes():
            return []

        if bit_index is None:
            bit_index = self._bit_index_of(signal_id)

        loads = []
        seen_ids = set()

        # [ADD 2026-06-11 Req-12] 默认 None 走 DRIVER+CONNECTION; 指定 allowed_kinds 则照走
        if allowed_kinds is None:
            allowed_kinds = {EdgeKind.DRIVER, EdgeKind.CONNECTION}

        for succ in self.graph.successors(signal_id):
            if succ == signal_id:
                # [iter_271] 图里存在自环 (端口直通/位桥产生的 x→x)。
                # 自环不是"loads": 返回自己会让 depth=1 与 depth=2 不单调
                # (实测: depth=1 含 self, depth=2 不含)。
                continue
            edge = self.graph.get_edge(signal_id, succ)
            if edge and edge.kind not in allowed_kinds:
                continue

            # [iter_294 / PLAN P6.2] depth=1 也做表达式按位映射
            if (bit_index is not None and edge is not None
                    and edge.kind == EdgeKind.DRIVER and edge.source is not None):
                mapped = self._expr_dst_bits(edge, bit_index)
                if mapped is not None:
                    existing = [self.graph.get_node(m) for m in mapped
                                if m in self.graph.nodes()]
                    existing = [n for n in existing if n is not None]
                    if existing:
                        for n in existing:
                            if n.id not in seen_ids and self._in_scope(n.id, scope_prefix):
                                loads.append(n)
                                seen_ids.add(n.id)
                    else:
                        node = self.graph.get_node(succ)
                        if (node and node.id not in seen_ids
                                and self._in_scope(node.id, scope_prefix)):
                            loads.append(node)
                            seen_ids.add(node.id)
                    continue

            node = self.graph.get_node(succ)
            if node and node.id not in seen_ids and self._in_scope(node.id, scope_prefix):
                loads.append(node)
                seen_ids.add(node.id)

        # [iter_294 / PLAN P6.2] depth=1 也把父总线上的表达式负载按位映射过来
        if bit_index is not None:
            for _succ, pedge in self._parent_driver_loads(signal_id):
                mapped = self._expr_dst_bits(pedge, bit_index)
                if not mapped:
                    continue
                for did in mapped:
                    if did in seen_ids or did not in self.graph.nodes():
                        continue
                    node = self.graph.get_node(did)
                    if node and self._in_scope(node.id, scope_prefix):
                        loads.append(node)
                        seen_ids.add(node.id)

        # [iter_272] 不再注入 MIG 虚拟对端: 图恒为实例级, 跨模块边本来就在图里。

        return loads

    def _collect_all_loads(self, signal_id: str, max_depth: int | None = None, allowed_kinds: set | None = None,
                           allow_cross_module: bool = True,
                           scope_prefix: str | None = None,
                           bit_index: int | None = None) -> list[TraceNode]:
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
        # [iter_240] 不再需要"零结果时补一条 MIG"的兜底 —— 跨模块跳转已是遍历的一步
        # (跨模块边已在图里)。
        self._trace_loads_recursive(signal_id, loads, seen_ids, current_depth=0, max_depth=max_depth,
                                    allowed_kinds=allowed_kinds, allow_cross_module=allow_cross_module,
                                    scope_prefix=scope_prefix, bit_index=bit_index)
        return loads

    def _trace_loads_recursive(
        self,
        signal_id: str,
        loads: list[TraceNode],
        seen_ids: set,
        current_depth: int = 0,
        max_depth: int | None = None,
        allowed_kinds: set | None = None,
        allow_cross_module: bool = True,
        scope_prefix: str | None = None,
        bit_index: int | None = None,
    ):
        """递归追溯负载(被 signal_id 驱动的节点)

        [iter_294 / PLAN P6.2] `bit_index` 给定时，按运算符把 a[j] 映射到结果位
        （`s = a & b` → `a[j]` 只影响 `s[j]`；加法影响 `s[j..W-1]`）。

        Args:
            signal_id: 当前信号 ID
            loads: 结果列表(inout)
            seen_ids: 已访问节点集合(inout)
            current_depth: 当前递归深度
            max_depth: None=无限递归, N=最多递归 N 层
            allowed_kinds: [Req-12] 允许的边类型集合, None=默认 DRIVER+CONNECTION
        """
        if bit_index is None:
            bit_index = self._bit_index_of(signal_id)

        if max_depth is not None and current_depth >= max_depth:
            return
        if signal_id in seen_ids:
            return
        # [iter_271] 限定查询的命名空间守卫 (见 _trace_drivers_recursive 同款注释)
        if scope_prefix and not self._in_scope(signal_id, scope_prefix):
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
                if not self._in_scope(dst, scope_prefix):
                    continue

                # [iter_294 / PLAN P6.2] 表达式按位映射（fanout 方向）
                if (bit_index is not None and edge is not None
                        and edge.kind == EdgeKind.DRIVER and edge.source is not None):
                    mapped = self._expr_dst_bits(edge, bit_index)
                    if mapped is not None:
                        handled = False
                        missing = False
                        for did in mapped:
                            if did in seen_ids:
                                handled = True
                                continue
                            if did not in self.graph.nodes():
                                missing = True
                                continue
                            dnode = self.graph.get_node(did)
                            if dnode is not None:
                                loads.append(dnode)
                            self._trace_loads_recursive(
                                did, loads, seen_ids, current_depth + 1, max_depth,
                                allowed_kinds, allow_cross_module, scope_prefix,
                                bit_index=self._bit_index_of(did))
                            handled = True
                        if missing:
                            node = self.graph.get_node(dst)
                            if node and node.id not in seen_ids:
                                loads.append(node)
                            if dst in self.graph.nodes():
                                self._trace_loads_recursive(
                                    dst, loads, seen_ids, current_depth + 1, max_depth,
                                    allowed_kinds, allow_cross_module, scope_prefix)
                            handled = True
                        if handled or not mapped:
                            continue

                node = self.graph.get_node(dst)
                if node and node.id not in seen_ids:
                    loads.append(node)
                if dst in self.graph.nodes():
                    self._trace_loads_recursive(dst, loads, seen_ids, current_depth + 1, max_depth,
                                                allowed_kinds, allow_cross_module, scope_prefix)

        # [iter_294 / PLAN P6.2] 位节点：父总线上的表达式负载按位映射
        if bit_index is not None:
            for succ, pedge in self._parent_driver_loads(signal_id):
                if not self._in_scope(succ, scope_prefix):
                    continue
                mapped = self._expr_dst_bits(pedge, bit_index)
                if mapped is None:
                    continue
                handled = False
                for did in mapped:
                    if did in seen_ids:
                        handled = True
                        continue
                    if did not in self.graph.nodes():
                        continue
                    dnode = self.graph.get_node(did)
                    if dnode is not None:
                        loads.append(dnode)
                    self._trace_loads_recursive(
                        did, loads, seen_ids, current_depth + 1, max_depth,
                        allowed_kinds, allow_cross_module, scope_prefix,
                        bit_index=self._bit_index_of(did))
                    handled = True
                if not handled and not mapped:
                    continue
                if not handled:
                    node = self.graph.get_node(succ)
                    if node and node.id not in seen_ids:
                        loads.append(node)
                        self._trace_loads_recursive(
                            succ, loads, seen_ids, current_depth + 1, max_depth,
                            allowed_kinds, allow_cross_module, scope_prefix)

    def trace_fanout(
        self,
        signal: str,
        module: str = None,
        depth: int | None = None,
        allow_cross_module: bool | None = None,
        include_clock: bool = False,
        include_reset: bool = False,
        include_control: bool = False,
        include_conditional: bool = False,
    ) -> list[TraceNode]:
        """Trace signal fanout (loads driven by this signal)

        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct loads only, N=recursive N levels, None=recursive all
            include_clock: [Req-12 Issue 19] True 时包含 CLOCK 边 (sensitivity list)
            include_reset: [Req-12 Issue 19] True 时包含 RESET 边
            include_control: [Req-12 Issue 19] True 时包含 CONTROL 边 (always 块引用)
            include_conditional: [FIX 2026-08-21 Plan B Step 2] True 时包含 BRANCH_* / CASE_*
                边 (conditional/case 表达式分支), 让 trace 能看到 ?:/case 的两个分支.

        默认只走 DRIVER + CONNECTION 边. 要看全部边, 用 visualize graph.
        """
        signal_id = self.make_id(signal, module)
        # [iter_294 / PLAN P6.2] 记录原始位索引：lift/回退到总线后仍按位映射表达式负载
        _orig_bit = self._bit_index_of(signal_id)
        signal_id = self._lift_missing_bit(signal_id)
        if signal_id is None:
            return []
        # [iter_292 / PLAN P5.6 F5] 位节点存在但**没有任何 load 边**时，回退父总线：
        # 与 fanin 的 F2 对称（位节点可能只是切片展开产物，真实负载挂在总线上）。
        signal_id = self._load_bus_fallback(signal_id)
        # [ADD 2026-06-11 Req-12] 计算要包含的边类型
        allowed_kinds = {EdgeKind.DRIVER, EdgeKind.CONNECTION}
        if include_clock:
            allowed_kinds.add(EdgeKind.CLOCK)
        if include_reset:
            allowed_kinds.add(EdgeKind.RESET)
        if include_control:
            allowed_kinds.add(EdgeKind.CONTROL)
        # [FIX 2026-08-21 Plan B Step 2] 包含 conditional branches (?: / case)
        if include_conditional:
            allowed_kinds.update({
                EdgeKind.BRANCH_CONDITION,
                EdgeKind.BRANCH_TRUE,
                EdgeKind.BRANCH_FALSE,
                EdgeKind.BRANCH_RESULT,
                EdgeKind.CASE_SELECT,
                EdgeKind.CASE_ITEM,
                EdgeKind.CASE_RESULT,
            })
        # [iter_240] 作用域: 指定了 module (限定查询) → 不跨模块边界, 只答该模块内
        allow_cross = (module is None) if allow_cross_module is None else allow_cross_module
        scope_prefix = self._scope_prefix_for(signal_id, allow_cross)
        # depth=1 用 _find_loads 过滤
        if depth == 1:
            return self._find_loads(signal_id, allowed_kinds=allowed_kinds,
                                    allow_cross_module=allow_cross, scope_prefix=scope_prefix,
                                    bit_index=_orig_bit)
        return self._collect_all_loads(signal_id, max_depth=depth, allowed_kinds=allowed_kinds,
                                       allow_cross_module=allow_cross, scope_prefix=scope_prefix,
                                       bit_index=_orig_bit)

    def trace_fanin(self, signal: str, module: str = None, depth: int | None = None,
                    allow_cross_module: bool | None = None) -> list[TraceNode]:
        """Trace signal fanin (drivers of this signal)

        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all
        """
        signal_id = self.make_id(signal, module)
        # [iter_240] 作用域同上 (显式覆盖优先: 内部调用已传完整 id, 不能再按 module 推导)
        allow_cross = (module is None) if allow_cross_module is None else allow_cross_module
        scope_prefix = self._scope_prefix_for(signal_id, allow_cross)
        if depth == 1:
            return self._find_drivers(signal_id, allow_cross_module=allow_cross,
                                      scope_prefix=scope_prefix)
        return self._collect_all_drivers(signal_id, max_depth=depth,
                                        allow_cross_module=allow_cross,
                                        scope_prefix=scope_prefix)

    def trace_fanin_detailed(self, signal: str, module: str = None, depth: int | None = None,
                             allow_cross_module: bool | None = None) -> list[DriverInfo]:
        """[方案C] Trace signal fanin with detailed driver information

        返回 DriverInfo 列表,包含 condition, clock_domain 等详细信息

        Args:
            signal: signal name
            module: module name (optional, for relative paths)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all

        Returns:
            List[DriverInfo] - 驱动信息列表
        """
        signal_id = self.make_id(signal, module)

        # 获取所有驱动节点 (作用域透传: None = 按 module 推导)
        driver_nodes = self.trace_fanin(signal_id, depth=depth,
                                        allow_cross_module=allow_cross_module)

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
                source=edge.source if edge else None,
                condition=condition,
                clock_domain=clock_domain,
                assign_type=assign_type,
                distance=1,  # TODO: 计算实际距离
                # expression 仍通过 _resolve_full_expression 获得，优先 source
                _expression_override=expression if not (edge and edge.source) else "",
                target_signal=signal_id,  # [P3-6] 目标信号用于组装完整语句
            )
            # [Plan F2.4.2 2026-08-13] 从 graph._expr_trees 注入结构化 driver 表达式
            # tree_key 格式 = {module_name}.{lhs_name}, 跟 signal_id 完全一致
            # (driver_extractor._store_expr_tree 验证). 如果 graph 没有 _expr_trees 或
            # 该 signal 不在表里, 保持 None (向后兼容).
            expr_trees = getattr(self.graph, '_expr_trees', None)
            if expr_trees is not None:
                tree_dict = expr_trees.get(signal_id)
                if tree_dict is not None:
                    driver_info.expression_tree = tree_dict
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
        signal_id = self.make_id(signal, module)

        if signal_id not in self.graph.nodes():
            return DriverChain(root=signal_id, drivers=[], loads=[], confidence="uncertain")

        # [iter_240] 作用域透传 (trace_detailed 也接受 module)
        allow_cross = module is None
        driver_infos = self.trace_fanin_detailed(signal_id, allow_cross_module=allow_cross)
        loads = self._find_loads(signal_id, allow_cross_module=allow_cross)

        confidence = "high" if driver_infos else "uncertain"

        return DriverChain(root=signal_id, drivers=driver_infos, loads=loads, confidence=confidence)
