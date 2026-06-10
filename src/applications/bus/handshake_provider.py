"""
applications.bus.handshake_provider - Phase B handshake 桥接

Phase A + Phase B 集成: handshake_score 融合

设计要点
========

1. **抽象 HandshakeProvider 接口**:
   - `get_handshake(valid, ready) -> HandshakeInfoLite | None`
   - 多种实现可注入 (NameBased / TraceBased / 自定义)

2. **NameBasedHandshakeProvider 默认实现**:
   - 不需要 SV 编译, 纯 name-based 启发式
   - 用 `_classify_by_name` 判断通道 (复用 Phase B)
   - 匹配协议名 → STANDARD_AXI, 不匹配 → WIRE_PASSTHROUGH

3. **HandshakeType → 分数映射**:
   - STANDARD_AXI:        1.0 (完美握手)
   - COMBINATIONAL_BP:    0.8 (FIFO 反压, 协议正确)
   - REGISTERED_BP:       0.7 (流水线延迟, 协议正确)
   - LATCHED_BP:          0.7
   - WIRE_PASSTHROUGH:    0.4 (握手被绕过)
   - PORT_PASSTHROUGH:    0.4
   - UNUSED:             -0.3 (信号未驱动)
   - UNKNOWN:             0.0

4. **集成到 ProtocolDetector**:
   - 接受可选 `handshake_provider` 参数
   - 遍历 anchors, 调 provider, 累加分数
   - 平均 → `handshake_score` (权重 0.15)

使用
====

    from applications.bus.handshake_provider import (
        NameBasedHandshakeProvider, handshake_type_score,
    )
    from applications.bus.detector import ProtocolDetector

    # 默认 name-based (MVP)
    provider = NameBasedHandshakeProvider()
    det = ProtocolDetector(schemas=schemas, handshake_provider=provider)

    # 自定义 (注入真实 trace 结果)
    class MyProvider(HandshakeProvider):
        def get_handshake(self, valid, ready):
            # 调 Phase B detect_handshake_type(...)
            ...

    det = ProtocolDetector(schemas=schemas, handshake_provider=MyProvider())
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from .normalize import SignalNormalizer, NormalizeConfig


# ---------------------------------------------------------------------------
# HandshakeInfoLite (轻量版, 不依赖 DriverInfo)
# ---------------------------------------------------------------------------

@dataclass
class HandshakeInfoLite:
    """轻量版 HandshakeInfo — Phase A 融合用.

    Phase B 完整版需要 DriverInfo (trace 后的结果), 但 Phase A 在调用
    detector 时通常没有 trace 上下文. 这个 lite 版只保留关键字段,
    用 name-based 启发式填充.

    Attributes:
        valid: valid 信号名
        ready: ready 信号名
        handshake_type: STANDARD_AXI / COMBINATIONAL_BP / WIRE_PASSTHROUGH / ...
        channel: 通道 (AW / W / B / AR / R / A / D / UNKNOWN)
    """

    valid: str
    ready: str
    handshake_type: str = "UNKNOWN"
    channel: str = "UNKNOWN"

    def __repr__(self) -> str:
        return (
            f"HandshakeInfoLite({self.valid}/{self.ready}, "
            f"type={self.handshake_type}, ch={self.channel})"
        )


# ---------------------------------------------------------------------------
# 分数映射
# ---------------------------------------------------------------------------

# HandshakeType → 置信度分数 (0.0 - 1.0)
# 设计: 越像"标准 AXI 握手"分数越高, UNUSED 减分
_HANDSHAKE_TYPE_SCORES = {
    "STANDARD_AXI":       1.0,   # 完美 AXI 握手 → 协议强匹配
    "COMBINATIONAL_BP":   0.8,   # FIFO 反压 → 协议正确, 有 BP 链
    "REGISTERED_BP":      0.7,   # 流水线 ready → 协议正确
    "LATCHED_BP":         0.7,   # latch ready
    "WIRE_PASSTHROUGH":   0.4,   # 透传 → 协议存在但握手被绕过
    "PORT_PASSTHROUGH":   0.4,
    "UNUSED":            -0.3,   # 信号未驱动 → 反向证据
    "UNKNOWN":            0.0,   # 不知道
}


def handshake_type_score(handshake_type: str) -> float:
    """HandshakeType → 置信度分数. 未知 type 返回 0."""
    return _HANDSHAKE_TYPE_SCORES.get(handshake_type, 0.0)


# ---------------------------------------------------------------------------
# HandshakeProvider 抽象
# ---------------------------------------------------------------------------

class HandshakeProvider(ABC):
    """握手分析的抽象接口.

    Phase A detector 不知道如何 trace 驱动信息, 所以需要调用方提供
    (valid, ready) 对的握手分析结果.
    """

    @abstractmethod
    def get_handshake(self, valid: str, ready: str) -> Optional[HandshakeInfoLite]:
        """返回 (valid, ready) 对的握手信息, 或 None.

        Args:
            valid: valid 信号名
            ready: ready 信号名

        Returns:
            HandshakeInfoLite 或 None (表示不知道)
        """
        ...


# ---------------------------------------------------------------------------
# NameBasedHandshakeProvider 默认实现
# ---------------------------------------------------------------------------

class NameBasedHandshakeProvider(HandshakeProvider):
    """纯 name-based 启发式, 不需要 SV 编译. MVP 阶段用这个.

    规则:
    1. 用 Session 1 标准化后的名字, 匹配 AXI 通道 (awvalid/awready→AW, etc.)
    2. 如果 valid+ready 名字配对, 且都像协议信号 → STANDARD_AXI
    3. 如果名字完全不像协议 → WIRE_PASSTHROUGH
    4. 否则 UNKNOWN
    """

    # 通道 → canonical 名字后缀模式
    _CHANNEL_SUFFIXES = {
        "AW": {"valid": ["awvalid"], "ready": ["awready"]},
        "W":  {"valid": ["wvalid"],  "ready": ["wready"]},
        "B":  {"valid": ["bvalid"],  "ready": ["bready"]},
        "AR": {"valid": ["arvalid"], "ready": ["arready"]},
        "R":  {"valid": ["rvalid"],  "ready": ["rready"]},
        "A":  {"valid": ["avalid"],  "ready": ["aready"]},
        "D":  {"valid": ["dvalid"],  "ready": ["dready"]},
    }

    def __init__(
        self,
        normalizer: Optional[SignalNormalizer] = None,
    ):
        self._norm = normalizer or SignalNormalizer(NormalizeConfig.default())

    def get_handshake(
        self, valid: str, ready: str
    ) -> Optional[HandshakeInfoLite]:
        """name-based 启发式."""
        valid_norm = self._norm.normalize(valid).normalized
        ready_norm = self._norm.normalize(ready).normalized

        # 1. 检查是否匹配已知协议通道
        matched_channel = self._match_channel(valid_norm, ready_norm)
        if matched_channel:
            return HandshakeInfoLite(
                valid=valid, ready=ready,
                handshake_type="STANDARD_AXI",
                channel=matched_channel,
            )

        # 2. 至少一个像 valid/ready, 另一个不像 → 透传
        if self._looks_like_valid(valid_norm) or self._looks_like_ready(ready_norm):
            return HandshakeInfoLite(
                valid=valid, ready=ready,
                handshake_type="WIRE_PASSTHROUGH",
                channel="UNKNOWN",
            )

        # 3. 完全不相关 → 透传或 None
        if self._looks_like_protocol_signal(valid_norm) or self._looks_like_protocol_signal(ready_norm):
            return HandshakeInfoLite(
                valid=valid, ready=ready,
                handshake_type="WIRE_PASSTHROUGH",
                channel="UNKNOWN",
            )

        return None

    # ----- 内部 -----

    def _match_channel(self, valid_norm: str, ready_norm: str) -> Optional[str]:
        """匹配已知 AXI/TL-UL 通道."""
        for ch, patterns in self._CHANNEL_SUFFIXES.items():
            valid_pat = patterns["valid"]
            ready_pat = patterns["ready"]
            # valid 名字以 valid_pat 结尾, ready 名字以 ready_pat 结尾
            if (
                any(valid_norm.endswith(p) or p in valid_norm for p in valid_pat)
                and any(ready_norm.endswith(p) or p in ready_norm for p in ready_pat)
            ):
                # 共享通道前缀 (去掉 valid/ready 后)
                valid_base = self._strip_role_suffix(valid_norm)
                ready_base = self._strip_role_suffix(ready_norm)
                if valid_base == ready_base:
                    return ch
        return None

    @staticmethod
    def _strip_role_suffix(name: str) -> str:
        """去 valid/ready/ack 后缀, 留通道 base."""
        for suffix in ("valid", "ready", "ack", "vld", "rdy"):
            if name.endswith(suffix) and len(name) > len(suffix):
                return name[: -len(suffix)]
        return name

    @staticmethod
    def _looks_like_valid(name: str) -> bool:
        """名字看起来像 valid."""
        n = name.lower()
        return any(s in n for s in ("valid", "vld", "req", "strobe", "ack"))

    @staticmethod
    def _looks_like_ready(name: str) -> bool:
        """名字看起来像 ready."""
        n = name.lower()
        return any(s in n for s in ("ready", "rdy", "stall", "wait", "grant"))

    @staticmethod
    def _looks_like_protocol_signal(name: str) -> bool:
        """名字看起来像任何协议相关信号 (data/addr/resp/...)."""
        n = name.lower()
        return any(s in n for s in (
            "data", "addr", "resp", "strb", "last", "len", "size", "burst",
            "id", "prot", "qos", "region", "lock", "cache", "user",
        ))
