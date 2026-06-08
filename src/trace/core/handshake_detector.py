# ==============================================================================
# handshake_detector.py - Phase B: Handshake Semantic Confirmation
# ==============================================================================
"""
给定一对 (valid, ready) 信号，通过分析 DriverInfo.condition 字符串和
DriverInfo.assign_type，判断握手类型（AXI 标准 / FIFO 反压 / 寄存器延迟 / TL-UL）

不需要 schema 配置，复用现有 trace_fanin_detailed() API。
"""

import re
from dataclasses import dataclass
from typing import Literal

from trace.core.graph.models import DriverInfo


# ==============================================================================
# 数据结构
# ==============================================================================

HandshakeType = Literal[
    "STANDARD_AXI",      # if (valid && ready) — 标准 AXI 握手
    "COMBINATIONAL_BP",  # assign ready = !fifo_full — FIFO组合反压
    "REGISTERED_BP",     # always_ff ready <= next_ready — 寄存器延迟
    "LATCHED_BP",        # latch逻辑产生的反压
    "WIRE_PASSTHROUGH",  # assign ready = some_other_signal — 透传连线
    "PORT_PASSTHROUGH",  # port connection / multi-level connection — 端口透传
    "UNUSED",            # 信号未被使用（无驱动）
    "UNKNOWN",           #条件不明确
]

ChannelType = Literal["AW", "W", "B", "AR", "R", "A", "D", "UNKNOWN"]


@dataclass
class HandshakeInfo:
    """握手分析结果"""
    valid: str
    ready: str
    handshake_type: HandshakeType
    channel: ChannelType
    condition: str           # 原始条件字符串
    effective_condition: str # 清理后的条件
    assign_type: str # always_ff / always_comb / continuous / blocking
    clock_domain: str
    extra: dict              # 附加信息（fifo_name, register_chain_depth 等）


# ==============================================================================
# 工具函数
# ==============================================================================

def _split_condition(cond: str) -> list[str]:
    """拆分 && 或 || 连接的条件，返回信号列表"""
    if not cond:
        return []
    # 移除空格，按 && 和 || 分割
    parts = re.split(r"\s*(&&|\|\|)\s*", cond)
    # parts like ['awvalid', '&&', 'awready'] → 只保留信号
    signals = [p.strip() for p in parts if p.strip() not in ("&&", "||")]
    return signals


def _classify_by_name(signal: str) -> ChannelType:
    """根据信号名判断 AXI 通道类型（轻量 heuristics）"""
    s = signal.lower()
    # axi_crossbar_addr 内部 AW/AR 指示信号
    if "m_wc_valid" in s or "m_wc_ready" in s or "m_wc_select" in s or "m_wc_decerr" in s:
        return "AW"
    if "m_rc_valid" in s or "m_rc_ready" in s or "m_rc_decerr" in s:
        return "AR"
    if "awvalid" in s or "awready" in s or "aw_addr" in s:
        return "AW"
    if "wvalid" in s or "wready" in s or "w_data" in s:
        return "W"
    if "bvalid" in s or "bready" in s or "bresp" in s:
        return "B"
    if "arvalid" in s or "arready" in s or "ar_addr" in s:
        return "AR"
    if "rvalid" in s or "rready" in s or "r_data" in s:
        return "R"
    # TileLink / AXI-Stream A 通道
    if "a_valid" in s or "a_ready" in s or "a_opcode" in s or "a_data" in s or "a_rd_resp" in s:
        return "A"
    # TileLink D 通道 / AXI-Stream (含 tvalid/tready)
    if "d_valid" in s or "d_ready" in s or "d_opcode" in s or "d_data" in s:
        return "D"
    if "tvalid" in s or "tready" in s or "t_data" in s or "tlast" in s:
        return "D"
    return "UNKNOWN"


# ==============================================================================
# 核心检测函数
# ==============================================================================

def _classify_one_driver(signal: str, di: DriverInfo) -> HandshakeInfo | None:
    """根据单个 DriverInfo 判定握手类型，返回 None 表示无法判定"""
    cond = (di.condition or "").strip()
    assign_type = di.assign_type or ""
    expr = (di.expression or "").strip()
    clock = di.clock_domain or ""

    # ---- Case 0: continuous assign / port connection，无条件 → 透传 ----
    if not cond and not expr and assign_type in ("connection", ""):
        channel = _classify_by_name(signal)
        return HandshakeInfo(
            valid="", ready=signal,
            handshake_type="PORT_PASSTHROUGH",
            channel=channel,
            condition=cond, effective_condition=expr,
            assign_type=assign_type, clock_domain=clock,
            extra={"note": "port/multi-level connection, no local handshake logic"}
        )
    if not cond and expr and assign_type == "continuous":
        channel = _classify_by_name(signal)
        return HandshakeInfo(
            valid="", ready=signal,
            handshake_type="WIRE_PASSTHROUGH",
            channel=channel,
            condition=cond, effective_condition=expr,
            assign_type=assign_type, clock_domain=clock,
            extra={"note": f"assign {signal.split('.')[-1]} = {expr} (wire passthrough)", "source_signal": expr}
        )

    # ---- Case 1: 条件包含 valid && ready → 标准 AXI 握手 ----
    if cond:
        sigs = _split_condition(cond)
        if len(sigs) >= 2:
            if "&&" in cond and any("valid" in s.lower() for s in sigs) and any("ready" in s.lower() for s in sigs):
                valid_sig = next((s for s in sigs if "valid" in s.lower()), "")
                ready_sig = next((s for s in sigs if "ready" in s.lower()), signal)
                channel = _classify_by_name(valid_sig or ready_sig)
                return HandshakeInfo(
                    valid=valid_sig, ready=ready_sig,
                    handshake_type="STANDARD_AXI",
                    channel=channel,
                    condition=cond, effective_condition=cond,
                    assign_type=assign_type, clock_domain=clock, extra={}
                )
            if "||" in cond:
                valid_sig = next((s for s in sigs if "valid" in s.lower()), "")
                ready_sig = next((s for s in sigs if "ready" in s.lower()), signal)
                channel = _classify_by_name(valid_sig or ready_sig)
                return HandshakeInfo(
                    valid=valid_sig, ready=ready_sig,
                    handshake_type="COMPLEX_ARB",
                    channel=channel,
                    condition=cond, effective_condition=cond,
                    assign_type=assign_type, clock_domain=clock,
                    extra={"note": "OR-based condition, may be TL-UL or multi-master arbiter"}
                )

        # ---- Case 1b: 单信号条件含 !full / !empty → FIFO 组合反压 ----
        if re.search(r"!\s*(\w+_)?full", cond) or re.search(r"!\s*(\w+_)?empty", cond):
            fifo_match = re.search(r"!\s*(\w+)", cond)
            fifo_name = fifo_match.group(1) if fifo_match else "unknown"
            channel = _classify_by_name(signal)
            sigs = _split_condition(cond)
            valid_sig = next((s for s in sigs if "valid" in s.lower() and "ready" not in s.lower()), "")
            return HandshakeInfo(
                valid=valid_sig, ready=signal,
                handshake_type="COMBINATIONAL_BP",
                channel=channel,
                condition=cond, effective_condition=cond,
                assign_type=assign_type, clock_domain=clock,
                extra={"fifo_name": fifo_name}
            )

    # ---- Case 2: 表达式包含 !full / !empty → FIFO 组合反压 ----
    if expr and (re.search(r"!\s*(\w+_)?full\b", expr) or re.search(r"!\s*(\w+_)?empty\b", expr)):
        fifo_match = re.search(r"!\s*(\w+)", expr)
        fifo_name = fifo_match.group(1) if fifo_match else "unknown"
        channel = _classify_by_name(signal)
        sigs = _split_condition(expr)
        valid_sig = next((s for s in sigs if "valid" in s.lower() and "ready" not in s.lower()), "")
        return HandshakeInfo(
            valid=valid_sig, ready=signal,
            handshake_type="COMBINATIONAL_BP",
            channel=channel,
            condition=cond, effective_condition=expr,
            assign_type=assign_type, clock_domain=clock,
            extra={"fifo_name": fifo_name}
        )

    # ---- Case 3: always_ff 寄存器延迟（无 cond）----
    if assign_type == "always_ff" and not cond:
        channel = _classify_by_name(signal)
        return HandshakeInfo(
            valid="", ready=signal,
            handshake_type="REGISTERED_BP",
            channel=channel,
            condition=cond, effective_condition=expr,
            assign_type=assign_type, clock_domain=clock, extra={}
        )

    # ---- Case 4: 有 cond 但不符合上面任何模式 → 条件控制 ----
    if cond:
        channel = _classify_by_name(signal)
        sigs = _split_condition(cond)
        valid_sig = next((s for s in sigs if "valid" in s.lower() and "ready" not in s.lower()), "")
        return HandshakeInfo(
            valid=valid_sig, ready=signal,
            handshake_type="CONDITIONAL_CTRL",
            channel=channel,
            condition=cond, effective_condition=cond,
            assign_type=assign_type, clock_domain=clock, extra={}
        )

    return None


# 握手类型优先级（高分 = 更确定的判定，优先采用）
_TYPE_PRIORITY = {
    "STANDARD_AXI":       10,
    "COMPLEX_ARB":         9,
    "COMBINATIONAL_BP":    8,
    "REGISTERED_BP":       7,
    "CONDITIONAL_CTRL":    6,
    "WIRE_PASSTHROUGH":    3,
    "PORT_PASSTHROUGH":    2,
    "UNUSED":              0,
    "UNKNOWN":             0,
}


def detect_handshake_type(
    signal: str,
    driver_infos: list[DriverInfo],
    counterpart_hint: str = None,
) -> HandshakeInfo:
    """分析一个 ready（或 valid）信号的握手类型

    遍历所有 driver_infos，按优先级选择最佳判定结果：
    STANDARD_AXI > COMPLEX_ARB > COMBINATIONAL_BP > REGISTERED_BP >
    CONDITIONAL_CTRL > WIRE_PASSTHROUGH > PORT_PASSTHROUGH > UNKNOWN

    Args:
        signal: 要分析的信号名（通常指 ready 信号）
        driver_infos: trace_fanin_detailed(signal) 返回的 DriverInfo 列表
        counterpart_hint: 可选，候选对应信号（如已知 valid 信号名）

    Returns:
        HandshakeInfo
    """
    return detect_handshake_type_with_node(signal, driver_infos, node_kind=None, counterpart_hint=counterpart_hint)


def detect_handshake_type_with_node(
    signal: str,
    driver_infos: list[DriverInfo],
    node_kind: str | None = None,
    counterpart_hint: str = None,
) -> HandshakeInfo:
    """带节点类型信息的握手分析

    额外参数 node_kind 用于区分：
    - PORT_IN  (输入端口) + 无驱动 → PORT_PASSTHROUGH (从外部连接进入)
    - SIGNAL   (内部信号) + 无驱动 → UNUSED (真正未使用)

    Args:
        signal: 要分析的信号名
        driver_infos: trace_fanin_detailed(signal) 返回的 DriverInfo 列表
        node_kind: 节点类型 (e.g. "PORT_IN", "PORT_OUT", "SIGNAL")
        counterpart_hint: 可选，候选对应信号
    """
    if not driver_infos:
        # 无驱动 — 区分端口 vs 内部信号
        # NodeKind.PORT_IN 的 str() 是 "NodeKind.PORT_IN" 或者是它的 name
        is_port_in = (
            node_kind is not None and (
                "PORT_IN" in str(node_kind) or
                "InputPort" in str(node_kind) or
                str(node_kind).lower() == "input"
            )
        )
        if is_port_in:
            return HandshakeInfo(
                valid="", ready=signal,
                handshake_type="PORT_PASSTHROUGH",
                channel=_classify_by_name(signal),
                condition="", effective_condition="",
                assign_type="port", clock_domain="", extra={"note": "input port, driven externally"}
            )
        return HandshakeInfo(
            valid="", ready=signal,
            handshake_type="UNUSED",
            channel=_classify_by_name(signal),
            condition="", effective_condition="",
            assign_type="", clock_domain="", extra={}
        )

    candidates: list[HandshakeInfo] = []
    for di in driver_infos:
        hi = _classify_one_driver(signal, di)
        if hi is not None:
            candidates.append(hi)

    if not candidates:
        di0 = driver_infos[0]
        return HandshakeInfo(
            valid="", ready=signal,
            handshake_type="UNKNOWN",
            channel=_classify_by_name(signal),
            condition=di0.condition or "", effective_condition=di0.expression or "",
            assign_type=di0.assign_type or "", clock_domain=di0.clock_domain or "", extra={}
        )

    # 按优先级排序，同优先级选 cond 最长（信息量最丰富）的
    def _rank(hi: HandshakeInfo):
        return (
            _TYPE_PRIORITY.get(hi.handshake_type, 0),
            len(hi.condition or "") + len(hi.effective_condition or ""),
        )
    candidates.sort(key=_rank, reverse=True)
    return candidates[0]


def find_counterpart_in_condition(condition: str, target: str) -> str | None:
    """在条件中找 target 的对应信号"""
    if not condition:
        return None
    sigs = _split_condition(condition)
    if target in sigs:
        idx = sigs.index(target)
        other_idx = idx ^ 1 if len(sigs) == 2 else -1
        if other_idx >= 0 and other_idx < len(sigs):
            return sigs[other_idx]
    return None


def detect_from_signal_pair(
    tracer,
    valid: str,
    ready: str,
) -> HandshakeInfo:
    """分析一对 (valid, ready) 信号的握手类型

    Args:
        tracer: SignalTracer 实例
        valid: valid 信号名
        ready: ready 信号名

    Returns:
        HandshakeInfo
    """
    # 分析 ready 的驱动
    driver_infos = tracer.trace_fanin_detailed(ready)
    # 获取 ready 的 node_kind 以区分 PORT_IN
    node_kind = None
    if hasattr(tracer, 'graph') and tracer.graph is not None:
        node = tracer.graph.get_node(ready)
        if node is not None:
            node_kind = str(node.kind)
    hi = detect_handshake_type_with_node(ready, driver_infos, node_kind=node_kind, counterpart_hint=valid)
    # 如果没找到 counterpart，尝试从 condition 中提取
    if not hi.valid and hi.condition:
        counterpart = find_counterpart_in_condition(hi.condition, ready)
        if counterpart:
            hi.valid = counterpart
    # 如果找到了 valid，保持
    if not hi.valid and hi.handshake_type == "STANDARD_AXI":
        hi.valid = valid
    return hi


# ==============================================================================
# AXI 通道快速分类（给 backpressure 用）
# ==============================================================================

def classify_signal_channel(signal: str) -> ChannelType:
    """根据信号名分类 AXI 通道（轻量 heuristics，无 schema依赖）"""
    return _classify_by_name(signal)


def classify_handshake_channels(valid: str, ready: str) -> tuple[ChannelType, ChannelType]:
    """分别分类 valid 和 ready 的通道，要求一致"""
    ch_v = _classify_by_name(valid)
    ch_r = _classify_by_name(ready)
    return ch_v, ch_r