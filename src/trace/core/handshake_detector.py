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
    if "awvalid" in s or "awready" in s or "aw_addr" in s:
        return "AW"
    if "wvalid" in s or "wready" in s or "_w_" in s:
        return "W"
    if "bvalid" in s or "bready" in s or "_b_" in s:
        return "B"
    if "arvalid" in s or "arready" in s or "ar_addr" in s:
        return "AR"
    if "rvalid" in s or "rready" in s or "_r_" in s:
        return "R"
    if "a_valid" in s or "a_ready" in s or "_a_" in s:
        return "A"
    if "d_valid" in s or "d_ready" in s or "_d_" in s:
        return "D"
    return "UNKNOWN"


# ==============================================================================
# 核心检测函数
# ==============================================================================

def detect_handshake_type(
    signal: str,
    driver_infos: list[DriverInfo],
    counterpart_hint: str = None,
) -> HandshakeInfo:
    """分析一个 ready（或 valid）信号的握手类型

    Args:
        signal: 要分析的信号名（通常指 ready 信号）
        driver_infos: trace_fanin_detailed(signal) 返回的 DriverInfo 列表
        counterpart_hint: 可选，候选对应信号（如已知 valid 信号名）

    Returns:
        HandshakeInfo
    """
    if not driver_infos:
        return HandshakeInfo(
            valid="", ready=signal,
            handshake_type="UNUSED",
            channel=_classify_by_name(signal),
            condition="", effective_condition="",
            assign_type="", clock_domain="", extra={}
        )

    extra = {}

    for di in driver_infos:
        cond = (di.condition or "").strip()
        assign_type = di.assign_type or ""
        expr = (di.expression or "").strip()
        clock = di.clock_domain or ""

        # ---- Case 1: 条件包含 valid && ready → 标准 AXI 握手 ----
        if cond:
            sigs = _split_condition(cond)
            if len(sigs) >= 2:
                # valid && ready 同时出现在条件中 → 标准握手
                if "&&" in cond and any("valid" in s.lower() for s in sigs) and any("ready" in s.lower() for s in sigs):
                    valid_sig = next((s for s in sigs if "valid" in s.lower()), "")
                    ready_sig = next((s for s in sigs if "ready" in s.lower()), signal)
                    channel = _classify_by_name(valid_sig or ready_sig)
                    return HandshakeInfo(
                        valid=valid_sig, ready=ready_sig,
                        handshake_type="STANDARD_AXI",
                        channel=channel,
                        condition=cond,
                        effective_condition=cond,
                        assign_type=assign_type,
                        clock_domain=clock,
                        extra=extra
                    )

                # ||分离的条件 →可能是 TL-UL 或复杂仲裁
                if "||" in cond:
                    valid_sig = next((s for s in sigs if "valid" in s.lower()), "")
                    ready_sig = next((s for s in sigs if "ready" in s.lower()), signal)
                    channel = _classify_by_name(valid_sig or ready_sig)
                    return HandshakeInfo(
                        valid=valid_sig, ready=ready_sig,
                        handshake_type="COMPLEX_ARB",
                        channel=channel,
                        condition=cond,
                        effective_condition=cond,
                        assign_type=assign_type,
                        clock_domain=clock,
                        extra={"note": "OR-based condition, may be TL-UL or multi-master arbiter"}
                    )

            # 单信号条件，无 && / ||
            # 检查表达式是否有 !full / !empty模式
            if re.search(r"!\s*(\w+_)?full", cond) or re.search(r"!\s*(\w+_)?empty", cond):
                fifo_match = re.search(r"!\s*(\w+)", cond)
                fifo_name = fifo_match.group(1) if fifo_match else "unknown"
                channel = _classify_by_name(signal)
                return HandshakeInfo(
                    valid="", ready=signal,
                    handshake_type="COMBINATIONAL_BP",
                    channel=channel,
                    condition=cond,
                    effective_condition=cond,
                    assign_type=assign_type,
                    clock_domain=clock,
                    extra={"fifo_name": fifo_name}
                )

        # ---- Case 2:表达式包含 !full / !empty → FIFO 组合反压 ----
        if re.search(r"!\s*(\w+_)?full\b", expr) or re.search(r"!\s*(\w+_)?empty\b", expr):
            fifo_match = re.search(r"!\s*(\w+)", expr)
            fifo_name = fifo_match.group(1) if fifo_match else "unknown"
            channel = _classify_by_name(signal)
            return HandshakeInfo(
                valid="", ready=signal,
                handshake_type="COMBINATIONAL_BP",
                channel=channel,
                condition=cond,
                effective_condition=expr,
                assign_type=assign_type,
                clock_domain=clock,
                extra={"fifo_name": fifo_name}
            )

        # ---- Case 3: always_ff 寄存器延迟 ----
        if assign_type == "always_ff" and not cond:
            channel = _classify_by_name(signal)
            return HandshakeInfo(
                valid="", ready=signal,
                handshake_type="REGISTERED_BP",
                channel=channel,
                condition=cond,
                effective_condition=expr,
                assign_type=assign_type,
                clock_domain=clock,
                extra={}
            )

        # ---- Case 4: 有条件但无 valid/ready 关键字 → 其他控制 ----
        if cond:
            channel = _classify_by_name(signal)
            return HandshakeInfo(
                valid="", ready=signal,
                handshake_type="CONDITIONAL_CTRL",
                channel=channel,
                condition=cond,
                effective_condition=cond,
                assign_type=assign_type,
                clock_domain=clock,
                extra={}
            )

    # Fallback
    channel = _classify_by_name(signal)
    return HandshakeInfo(
        valid="", ready=signal,
        handshake_type="UNKNOWN",
        channel=channel,
        condition=driver_infos[0].condition or "",
        effective_condition=driver_infos[0].expression or "",
        assign_type=driver_infos[0].assign_type or "",
        clock_domain=driver_infos[0].clock_domain or "",
        extra={}
    )


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
    hi = detect_handshake_type(ready, driver_infos, counterpart_hint=valid)
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