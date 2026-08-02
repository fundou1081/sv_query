"""
pattern_matcher.py — 定点数计算模式匹配框架 (V6.9)

可扩展的插件式架构:
  - PatternMatch: 统一的匹配结果占位符
  - PatternMatcher: 抽象基类，定义 match() 接口
  - PatternRegistry: 管理所有 Matcher，串联运行
  - 每个 Matcher 通过 VizData/VizEdge 的结构化字段做判断，不靠正则

设计原则:
  1. 不靠正则 — 靠 source_op / source_casts / width / bit_slice 等结构化字段
  2. 占位符模式 — PatternMatch 是纯数据描述，renderer 解释为视觉样式
  3. 可扩展 — 新增识别器只需要子类化 PatternMatcher + 注册
  4. 零改动上游 — 不改 DriverExtractor / VizData 模型

用法:
    registry = PatternRegistry()
    registry.register(TruncationMatcher())
    registry.register(SaturationMatcher())
    ...
    matches = registry.match_all(viz)  # → list[PatternMatch]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..viz.viz_data_models import VizData, VizEdge, VizNode

# ═══════════════════════════════════════════════════════
# PatternMatch — 统一的匹配结果占位符
# ═══════════════════════════════════════════════════════


@dataclass
class PatternMatch:
    """单次模式匹配的结果 (renderer 解释为视觉样式)

    字段都是可选 — 只设置匹配到的部分:
    - edge_id: 匹配到哪条边
    - category: 模式类别 (truncation | saturation | rounding | sext | clamp | ...)
    - label: 边上显示的标签 (如 "⤓ TRUNC")
    - note: tooltip/详细信息
    - edge_color: 边颜色覆盖
    - edge_style: 边样式覆盖 (dashed | solid | bold)
    - node_color: 节点颜色覆盖
    - priority: 优先级 (数字越小越先渲染, 同 edge 多个 match 时用)
    """

    edge_id: str = ""
    category: str = ""
    label: str = ""
    note: str = ""
    edge_color: str = ""
    edge_style: str = ""
    node_color: str = ""
    priority: int = 50
    extra: dict[str, Any] = field(default_factory=dict)

    # ── 便捷工厂 ──

    @classmethod
    def truncation(cls, edge_id: str, bit_range: str = "") -> PatternMatch:
        label = f"⤓ {bit_range}" if bit_range else "⤓"
        return cls(edge_id=edge_id, category="truncation", label=label,
                   note=f"truncate {bit_range}" if bit_range else "truncation",
                   edge_color="#cc6600", priority=10)

    @classmethod
    def saturation_upper(cls, edge_id: str, max_val: int) -> PatternMatch:
        return cls(edge_id=edge_id, category="saturation",
                   label=f"↥ SAT({max_val})", note=f"saturate to MAX={max_val}",
                   edge_color="#cc44cc", edge_style="dashed", priority=20)

    @classmethod
    def saturation_lower(cls, edge_id: str, min_val: int) -> PatternMatch:
        return cls(edge_id=edge_id, category="saturation",
                   label=f"↧ SAT({min_val})", note=f"saturate to MIN={min_val}",
                   edge_color="#cc44cc", edge_style="dashed", priority=20)

    @classmethod
    def round_half_up(cls, edge_id: str, shift: int = 0) -> PatternMatch:
        note = f"round half-up (>> {shift})" if shift > 0 else "round half-up"
        return cls(edge_id=edge_id, category="rounding",
                   label="⊕ round", note=note,
                   edge_color="#44cc44", priority=25)

    @classmethod
    def round_rne(cls, edge_id: str) -> PatternMatch:
        return cls(edge_id=edge_id, category="rounding",
                   label="⊕ RNE", note="round-to-nearest-even",
                   edge_color="#44cc44", priority=25)

    @classmethod
    def sign_extend(cls, edge_id: str, src_w: int, dst_w: int) -> PatternMatch:
        return cls(edge_id=edge_id, category="sext",
                   label="↕ SEXT", note=f"sign-ext {src_w}→{dst_w}bit",
                   edge_color="#4488cc", priority=30)

    @classmethod
    def clamp(cls, edge_id: str, lo: int, hi: int) -> PatternMatch:
        return cls(edge_id=edge_id, category="clamp",
                   label=f"↕ CLAMP[{lo},{hi}]", note=f"clamp to [{lo},{hi}]",
                   edge_color="#cc44cc", edge_style="dashed", priority=15)


# ═══════════════════════════════════════════════════════
# PatternMatcher — 抽象基类
# ═══════════════════════════════════════════════════════


class PatternMatcher(ABC):
    """定点数模式识别器基类

    子类实现:
      - match(edge, node_map, incoming) → PatternMatch | None
        通过结构化字段 (source_op, source_casts, width, etc.) 做判断
      - category: 模式类别名 (用于去重/排序)
    """

    category: str = ""

    @abstractmethod
    def match(
        self,
        edge: VizEdge,
        node_map: dict[str, VizNode],
        incoming: dict[str, list[VizEdge]],
    ) -> PatternMatch | None:
        """对一条边做模式匹配

        Args:
            edge: 待检测的边
            node_map: {node_id → VizNode}
            incoming: {dst_id → [incoming edges]}

        Returns:
            PatternMatch 或 None (不匹配)
        """
        ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} category={self.category}>"


# ═══════════════════════════════════════════════════════
# 具体 Matcher 实现
# ═══════════════════════════════════════════════════════


class TruncationMatcher(PatternMatcher):
    """截断检测: src→dst 存在 bit_slice 或 source_bit_range

    判断逻辑 (纯结构化, 无正则):
      - edge.bit_slice 非空 且 含 ":" → 显式截断
      - edge.source_bit_start / source_bit_end 非 None → 位范围截断
      - 跳过 CLOCK/RESET/CONNECTION 边
    """

    category = "truncation"

    def match(self, edge, node_map, incoming) -> PatternMatch | None:
        if edge.kind in ("CLOCK", "RESET", "CONNECTION"):
            return None

        # Case 1: 显式 bit_slice (如 "[7:0]")
        if edge.bit_slice and ":" in edge.bit_slice:
            return PatternMatch.truncation(edge.id, edge.bit_slice)

        # Case 2: source_bit 范围 (如 source_bit_start=7, source_bit_end=0)
        if edge.source_bit_start is not None and edge.source_bit_end is not None:
            rng = f"[{edge.source_bit_start}:{edge.source_bit_end}]"
            return PatternMatch.truncation(edge.id, rng)

        return None


class SaturationMatcher(PatternMatcher):
    """饱和检测: OP 节点 → dst 的输出边，同时 dst 有其他条件 driver

    判断逻辑 (结构化):
      - edge.kind == "DRIVER" 且 edge.condition 非空
      - dst 有至少 2 个条件 driver → 三元模式
      - 条件中含 compare 关系的 OP 节点 (GreaterThan/LessThan/...) 连到该 dst

    注: 不直接解析 condition 字符串，而是通过 source_op 链判断。
    如果条件边来自一个比较 OP (如 GreaterThan → 条件信号)，则识别为饱和。
    """

    category = "saturation"

    _COMPARE_OPS = {
        "GreaterThan", "GreaterThanEqual", "LessThan", "LessThanEqual",
        "Equality", "Inequality",
    }

    def match(self, edge, node_map, incoming) -> PatternMatch | None:
        if edge.kind != "DRIVER" or not (edge.condition or edge.effective_condition):
            return None

        dst_id = edge.dst
        dst_incoming = incoming.get(dst_id, [])

        # Need at least 2 conditional drivers + 1 unconditional → ternary pattern
        cond_edges = [e for e in dst_incoming if e.condition and e.kind == "DRIVER"]
        uncond_edges = [e for e in dst_incoming if not e.condition and e.kind == "DRIVER"]
        if len(cond_edges) < 2 or not uncond_edges:
            return None

        # Check if the condition signal comes from a compare OP
        # The condition signal itself (edge's src in condition chain) might have
        # an incoming edge with source_op in _COMPARE_OPS
        for cond_edge in cond_edges:
            upstream = incoming.get(cond_edge.src, [])
            for up_e in upstream:
                if up_e.source_op in self._COMPARE_OPS:
                    # Found: saturation via compare OP
                    # Distinguish upper vs lower by operator name
                    if "Greater" in up_e.source_op:
                        return PatternMatch.saturation_upper(edge.id, 0)
                    return PatternMatch.saturation_lower(edge.id, 0)

        return None


class RoundingMatcher(PatternMatcher):
    """舍入检测: (val + half) >>> N 或 RNE 模式

    判断逻辑 (结构化):
      Pattern 1 (half-up):
        - edge.source_op == "ArithmeticShiftRight" (>>>)
        - edge.src 有上游 Add driver
        → ⊕ round half-up

      Pattern 2 (RNE):
        - edge.source_op == "Add"
        - operands 是同一信号的不同 bit slices
        → ⊕ RNE
    """

    category = "rounding"

    def match(self, edge, node_map, incoming) -> PatternMatch | None:
        if not edge.source_op:
            return None

        # Pattern 1: ArithmeticShiftRight → dst, with Add upstream
        if edge.source_op == "ArithmeticShiftRight":
            src_incoming = incoming.get(edge.src, [])
            if any(e.source_op == "Add" for e in src_incoming):
                return PatternMatch.round_half_up(edge.id)

        # Pattern 2: RNE — Add operator, operands are bit slices of same signal
        if edge.source_op == "Add":
            dst_incoming = incoming.get(edge.dst, [])
            # Collect all bit-slice operands feeding into the Add OP
            slice_bases: set[str] = set()
            has_slices = False
            for ie in dst_incoming:
                if ie.source_op == "Add":
                    for up_ie in incoming.get(ie.src, []):
                        if up_ie.source_bit_start is not None:
                            has_slices = True
                            base = _base_signal_name(up_ie.src)
                            slice_bases.add(base)
            if has_slices and len(slice_bases) <= 2:
                return PatternMatch.round_rne(edge.id)

        return None


class SignExtendMatcher(PatternMatcher):
    """符号扩展检测: dst 位宽 > src 位宽 且有 $signed cast

    判断逻辑 (结构化):
      - 非 OP 边 (OP 边由 round/trunc 处理)
      - dst_node.width > src_node.width
      - edge.source_casts 含 "$signed"
    """

    category = "sext"

    def match(self, edge, node_map, incoming) -> PatternMatch | None:
        # Skip OP edges — round/trunc matchers handle those
        if edge.source_op:
            return None

        src_node = node_map.get(edge.src)
        dst_node = node_map.get(edge.dst)
        if not src_node or not dst_node:
            return None

        src_w = _node_width_bits(src_node)
        dst_w = _node_width_bits(dst_node)
        if not (dst_w > src_w > 0):
            return None

        if edge.source_casts and "$signed" in edge.source_casts:
            return PatternMatch.sign_extend(edge.id, src_w, dst_w)

        return None


class ClampMatcher(PatternMatcher):
    """范围限定检测: 双层 ternary 限定在 [lo, hi]

    判断逻辑 (结构化):
      - edge.kind == "DRIVER" 且 edge.condition 非空
      - dst 有 ≥2 条件 driver + 1 无条件 driver (三元)
      - 条件来自比较 OP 链 (GreaterThan + LessThan → AND → condition signal)
      → CLAMP
    """

    category = "clamp"

    _COMPARE_OPS = {
        "GreaterThan", "GreaterThanEqual", "LessThan", "LessThanEqual",
    }

    def match(self, edge, node_map, incoming) -> PatternMatch | None:
        if edge.kind != "DRIVER" or not (edge.condition or edge.effective_condition):
            return None

        dst_id = edge.dst
        dst_incoming = incoming.get(dst_id, [])
        cond_edges = [e for e in dst_incoming if e.condition and e.kind == "DRIVER"]
        uncond_edges = [e for e in dst_incoming if not e.condition and e.kind == "DRIVER"]
        if len(cond_edges) < 2 or not uncond_edges:
            return None

        # Check if the condition chain involves 2+ different compare OPs
        # (GreaterThan and LessThan → clamp pattern)
        compare_types: set[str] = set()
        for cond_edge in cond_edges:
            upstream = incoming.get(cond_edge.src, [])
            for up_e in upstream:
                if up_e.source_op in self._COMPARE_OPS:
                    compare_types.add(up_e.source_op)

        if len(compare_types) >= 2:
            return PatternMatch.clamp(edge.id, 0, 0)

        return None


# ═══════════════════════════════════════════════════════
# PatternRegistry — 管理所有 Matcher
# ═══════════════════════════════════════════════════════


class PatternRegistry:
    """模式匹配注册中心

    串联所有注册的 Matcher，对每条边依次尝试匹配。
    同一条边被多个 Matcher 命中时，按 priority 取最优。
    """

    def __init__(self) -> None:
        self._matchers: list[PatternMatcher] = []

    def register(self, matcher: PatternMatcher) -> None:
        """注册一个模式识别器 (调用顺序 = 优先级顺序)"""
        self._matchers.append(matcher)

    def match_all(self, viz: VizData) -> list[PatternMatch]:
        """对 VizData 中所有边依次匹配，返回所有命中结果

        Args:
            viz: VizData 包

        Returns:
            PatternMatch 列表 (已按 priority 排序)
        """
        node_map: dict[str, VizNode] = {n.id: n for n in viz.nodes}
        incoming: dict[str, list[VizEdge]] = {}
        for e in viz.edges:
            incoming.setdefault(e.dst, []).append(e)

        results: list[PatternMatch] = []

        for edge in viz.edges:
            edge_matches: list[PatternMatch] = []
            for matcher in self._matchers:
                m = matcher.match(edge, node_map, incoming)
                if m is not None:
                    m.edge_id = edge.id  # ensure edge_id is set
                    edge_matches.append(m)

            if edge_matches:
                # Take the highest-priority match (lowest priority number)
                best = min(edge_matches, key=lambda x: x.priority)
                results.append(best)

        return sorted(results, key=lambda x: x.priority)

    def annotated(self, viz: VizData) -> VizData:
        """一站式: 匹配 + 就地标注 VizData 的 edge.extra

        供 renderer 在渲染前调用。
        """
        matches = self.match_all(viz)

        # Build edge lookup
        edge_map: dict[str, VizEdge] = {e.id: e for e in viz.edges}

        for m in matches:
            edge = edge_map.get(m.edge_id)
            if edge is None:
                continue
            edge.extra["fp_category"] = m.category
            edge.extra["fp_label"] = m.label
            edge.extra["fp_note"] = m.note
            if m.edge_color:
                edge.extra["fp_color"] = m.edge_color
            if m.edge_style:
                edge.extra["fp_style"] = m.edge_style
            if m.node_color:
                edge.extra["fp_node_color"] = m.node_color

        return viz


# ═══════════════════════════════════════════════════════
# 预配置的默认 Registry
# ═══════════════════════════════════════════════════════


def create_default_registry() -> PatternRegistry:
    """创建包含所有标准 Matcher 的默认注册中心。

    顺序即优先级 (先注册的先匹配，同 edge 取最优 priority):
      1. Truncation  (priority 10) — 最基础
      2. Clamp       (priority 15)
      3. Saturation  (priority 20)
      4. Rounding    (priority 25)
      5. SignExtend  (priority 30)
    """
    reg = PatternRegistry()
    reg.register(TruncationMatcher())
    reg.register(ClampMatcher())
    reg.register(SaturationMatcher())
    reg.register(RoundingMatcher())
    reg.register(SignExtendMatcher())
    return reg


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════


def _node_width_bits(node: VizNode) -> int:
    """从 VizNode.width 计算实际位宽"""
    w = node.width
    if w is None:
        return 0
    msb, lsb = w
    if msb < lsb:
        return 0
    return abs(msb - lsb) + 1


def _base_signal_name(signal_id: str) -> str:
    """剥离位选择后缀: 'foo.bar[7:0]' → 'foo.bar'"""
    idx = signal_id.find("[")
    return signal_id[:idx] if idx >= 0 else signal_id
