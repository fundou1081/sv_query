"""
fixed_point_annotator.py — 定点数模式识别标注器 (V6.9 datapath)

在 VizData 渲染前做语义标注:
- 截断 (truncation): dst 位宽 < src → "⤓ TRUNC" 标签
- 饱和 (saturation): ternary clamp → "↥ SAT" / "↧ SAT"
- 舍入 (rounding): +0.5 后移位 → "⊕ round half-up" / "⊕ RNE"
- 符号扩展 (sign-extend): {N{sig[MSB]}, sig} → "↕ SEXT"
- 乘法/MAC 截断: 乘积位宽 > 输出位宽 → "×→⤓"
- Clamp: 范围限定 ternary → "↕ CLAMP [lo,hi]"

原则: 不改 VizData/VizEdge 数据结构，只设置 edge.extra 字段供 renderer 使用。

用法:
    from .fixed_point_annotator import annotate_fixed_point
    annotate_fixed_point(viz)
"""

from __future__ import annotations

import re

from ..viz.viz_data_models import VizData, VizEdge, VizNode


def annotate_fixed_point(viz: VizData) -> None:
    """一站式定点数标注，就地修改 VizData 的 edge.extra + 节点颜色"""

    # Build fast lookup
    node_map: dict[str, VizNode] = {n.id: n for n in viz.nodes}

    # Edge index: dst → list of incoming edges
    incoming: dict[str, list[VizEdge]] = {}
    for e in viz.edges:
        incoming.setdefault(e.dst, []).append(e)

    # Annotate each edge
    for edge in viz.edges:
        _annotate_truncation(edge, node_map)
        _annotate_saturation(edge, node_map, incoming)
        _annotate_rounding(edge, incoming)
        _annotate_sign_extend(edge, node_map)
        _annotate_clamp(edge)


# ═══════════════════════════════════════════════════════
# Truncation detection
# ═══════════════════════════════════════════════════════

def _annotate_truncation(edge: VizEdge, node_map: dict[str, VizNode]) -> None:
    """检测截断: src→dst 有 bit_slice 标注，或 dst 位宽 < src 位宽"""
    src_node = node_map.get(edge.src)
    dst_node = node_map.get(edge.dst)
    if not src_node or not dst_node:
        return

    _width_bits(src_node.width)
    _width_bits(dst_node.width)

    # Case 1: 显式 bit_slice
    if edge.bit_slice and ":" in edge.bit_slice:
        edge.extra["trunc_tag"] = "⤓"
        edge.extra["trunc_note"] = f"trunc {edge.bit_slice}"
        return

    # Case 2: 显式 source_bit range
    if edge.source_bit_start is not None and edge.source_bit_end is not None:
        edge.extra["trunc_tag"] = "⤓"
        edge.extra["trunc_note"] = f"trunc [{edge.source_bit_start}:{edge.source_bit_end}]"
        return

    # Case 3: 隐式截断 (dst 位宽 < src 位宽, 且不是 bit_select)
    # DISABLED: comb wires often get wrong width from elaboration
    # if src_width > 0 and dst_width > 0 and dst_width < src_width:
    #     if edge.kind == "DRIVER" and not edge.condition:
    #         edge.extra["trunc_tag"] = "⤓"
    #         return


# ═══════════════════════════════════════════════════════
# Saturation detection
# ═══════════════════════════════════════════════════════

_SAT_PATTERNS = [
    # (condition regex, tag, note template)
    (re.compile(r"(\w+)\s*>\s*\d+'d?(\d+)"), "↥ SAT", "to MAX({2})"),    # val > MAX
    (re.compile(r"(\w+)\s*<\s*\d+'d?(\d+)"), "↧ SAT", "to MIN({2})"),    # val < MIN
    (re.compile(r"(\w+)\s*<\s*(\w+)"), "↧ SAT", "to min({2})"),          # val < other
]


def _annotate_saturation(
    edge: VizEdge,
    node_map: dict[str, VizNode],
    incoming: dict[str, list[VizEdge]],
) -> None:
    """检测饱和: ternary 条件包含比较 > MAX / < MIN

    识别: cond 中含 '>' 且 operand side 是常量 → 上饱和
         cond 中含 '<' 且 operand side 是常量 → 下饱和
    要求 dst 有至少 2 个条件 driver (ternary pattern)。
    """
    cond = edge.condition if edge.condition else edge.effective_condition
    if not cond:
        return

    # Must be a ternary/conditional driver
    if edge.kind != "DRIVER":
        return

    # Check ternary pattern: dst must have ≥3 incoming drivers (2 conditional + 1 default)
    dst_incoming = incoming.get(edge.dst, [])
    cond_drivers = [e for e in dst_incoming if e.condition and e.kind == "DRIVER"]
    all_drivers = [e for e in dst_incoming if e.kind == "DRIVER"]
    if len(cond_drivers) < 1 or len(all_drivers) < 2:
        return

    # Check for > MAX pattern (upper saturation)
    gt_match = re.search(r"(\w+)\s*>\s*(\d+'d?\d+)", cond)
    if gt_match:
        max_val = _parse_verilog_number(gt_match.group(2))
        if max_val is not None:
            edge.extra["sat_tag"] = "↥ SAT"
            edge.extra["sat_note"] = f"max={max_val}"
            return

    # Check for < MIN pattern (lower saturation)
    lt_match = re.search(r"(\w+)\s*<\s*(\d'd?\d+)", cond)
    if lt_match:
        min_val = _parse_verilog_number(lt_match.group(2))
        if min_val is not None:
            edge.extra["sat_tag"] = "↧ SAT"
            edge.extra["sat_note"] = f"min={min_val}"
            return


# ═══════════════════════════════════════════════════════
# Rounding detection
# ═══════════════════════════════════════════════════════

def _annotate_rounding(
    edge: VizEdge,
    incoming: dict[str, list[VizEdge]],
) -> None:
    """检测舍入: (val + half) >>> N 模式 — half = 1<<(N-1)

    分析 OP→dst 边：如果 dst 是 port output 且 src OP 是 >>>，
    检查上游是否有 Add 运算 → half-up rounding。
    """
    if not edge.source_op:
        return

    # Pattern 1: ArithmeticShiftRight → dst (output)
    if edge.source_op == "ArithmeticShiftRight":
        # The edge.src is a wire/comb signal driven by an Add
        # Check all incoming edges to edge.src
        src_incoming = incoming.get(edge.src, [])
        has_add_driver = any(e.source_op == "Add" for e in src_incoming)
        if has_add_driver:
            edge.extra["round_tag"] = "⊕ round"
            edge.extra["round_note"] = "half-up"
            return

    # Pattern 2: RNE — Add operator where operands are bit slices
    # from the SAME base signal (e.g., prod[15:8] + prod[7])
    if edge.source_op == "Add":
        dst_incoming = incoming.get(edge.dst, [])
        # Collect base signals of Add operands
        op_bases = set()
        for ie in dst_incoming:
            if ie.source_op == "Add":
                for upstream_ie in incoming.get(ie.src, []):
                    base = _base_signal(upstream_ie.src)
                    if base:
                        op_bases.add(base)
        if len(op_bases) >= 1 and all(
            any(upstream_ie.source_bit_start is not None for upstream_ie in incoming.get(ie.src, []))
            for ie in dst_incoming if ie.source_op == "Add"
        ):
            edge.extra["round_tag"] = "⊕ RNE"
            edge.extra["round_note"] = "round-nearest-even"
            return


# ═══════════════════════════════════════════════════════
# Sign extension detection
# ═══════════════════════════════════════════════════════

def _annotate_sign_extend(
    edge: VizEdge,
    node_map: dict[str, VizNode],
) -> None:
    """检测符号扩展: dst 位宽 > src 位宽，且有 $signed 或复制模式

    注意: 只有 DRIVER 非 OP 边才检查 — round/trunc OP 边不可能是 SEXT。
    """
    src_node = node_map.get(edge.src)
    dst_node = node_map.get(edge.dst)
    if not src_node or not dst_node:
        return

    src_w = _width_bits(src_node.width)
    dst_w = _width_bits(dst_node.width)

    # 跳过 OP 边 — round/trunc 边由专门的检测器处理
    if edge.source_op:
        return

    # Only flag SEXT when dst is genuinely wider than src
    # and NOT a simple bit_slice passthrough
    if not dst_w > src_w:
        return

    # 符号扩展: dst 位宽 > src 位宽 且 有 $signed cast
    if edge.source_casts and "$signed" in edge.source_casts:
        edge.extra["sext_tag"] = "↕ SEXT"
        edge.extra["sext_note"] = f"sign-ext {src_w}→{dst_w}bit"
        return

    # 联合模式: 位重复 (如 {{8{...}}, ...})
    if edge.expression and "{" in edge.expression and "{" in edge.expression.split("}")[0]:
        count = edge.expression.count("{")
        if count >= 2:  # replicated concat
            edge.extra["sext_tag"] = "↕ SEXT"
            edge.extra["sext_note"] = "replicate"
            return


# ═══════════════════════════════════════════════════════
# Clamp detection
# ═══════════════════════════════════════════════════════

def _annotate_clamp(edge: VizEdge) -> None:
    """检测 clamp: 双层 ternary 限定在 [lo, hi] 范围"""
    cond = edge.condition if edge.condition else edge.effective_condition
    if not cond:
        return

    # Double condition pattern: "!A && !B" or "!(A) && !(B)"
    # Typical clamp: (val > hi) ? hi : (val < lo) ? lo : val
    gt_match = re.search(r"(\w+)\s*>\s*(\d+'d?\d+)", cond)
    lt_match = re.search(r"(\w+)\s*<\s*(\d+'d?\d+)", cond)

    if gt_match and lt_match:
        hi = _parse_verilog_number(gt_match.group(2))
        lo = _parse_verilog_number(lt_match.group(2))
        if hi is not None and lo is not None:
            edge.extra["clamp_tag"] = "↕ CLAMP"
            edge.extra["clamp_note"] = f"[{lo},{hi}]"
            return


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

def _width_bits(w: tuple[int, int] | None) -> int:
    """从 (msb, lsb) 计算位宽"""
    if w is None:
        return 0
    msb, lsb = w
    if msb < lsb:
        return 0
    return abs(msb - lsb) + 1


def _base_signal(signal_id: str) -> str:
    """剥离位选择后缀: "foo.bar[7:0]" → "foo.bar" """
    if "[" in signal_id:
        return signal_id[:signal_id.index("[")]
    return signal_id


def _parse_verilog_number(num_str: str) -> int | None:
    """解析 Verilog 数字: 16'd255 → 255"""
    m = re.search(r"\d+'[bdh]?(\d+)", num_str)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    # Plain number
    try:
        return int(num_str)
    except ValueError:
        return None
