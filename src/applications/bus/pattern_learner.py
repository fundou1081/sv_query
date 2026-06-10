"""
applications.bus.pattern_learner - Anchor-based 模式学习

Phase A Session 3: PatternLearner

设计要点
========

1. **Anchor 驱动**: 已知 (valid, ready) 握手对作为"种子", 学习通道名
2. **公共前缀 = 通道名**: 从 anchor 两个信号找最长公共前缀
3. **同前缀分组**: 通道名作为 prefix, 匹配所有同前缀信号
4. **角色推断**: 简单 name-based (valid/ready/data/addr/resp/ctrl/strb/last)
5. **置信度**: 通道 base 越长 → 置信度越高

为什么这样设计
==============

**问题**: 协议有 5 通道 (AXI) / 2 通道 (TL-UL) / 1 通道 (APB), 但模块里
所有信号混在一起, 怎么知道哪些信号属于同一通道?

**核心洞察**: 一个 valid 一定有一个对应的 ready (handshake 对), 它们
共享通道前缀. 找到 valid 就找到了 ready, 找到 (valid, ready) 就找到了
通道名, 找到通道名就能分所有信号.

**算法**:
    1. 标准化所有信号名 (Session 1)
    2. 对每个 anchor (valid_raw, ready_raw):
       a. 标准化两者 → valid_norm, ready_norm
       b. 找公共前缀 → channel_base (e.g., "aw", "w", "a")
       c. 用 channel_base prefix-match 所有信号
    3. 输出: List[ChannelGroup]

**置信度**:
    - channel_base 长度 ≥ 2: 0.8 (具体, 不会误匹配)
    - channel_base 长度 1:  0.4 (模糊, 可能误匹配)
    - 0 长度:                0.0 (无 anchor)

使用
====

    from applications.bus.pattern_learner import PatternLearner
    from applications.bus.normalize import SignalNormalizer, NormalizeConfig

    norm = SignalNormalizer(NormalizeConfig.default())
    learner = PatternLearner(norm)

    groups = learner.learn(
        anchors=[("awvalid", "awready"), ("wvalid", "wready")],
        all_signals=[
            "awvalid", "awready", "awaddr", "awlen",  # AW 通道
            "wvalid", "wready", "wdata", "wstrb",     # W 通道
        ],
    )
    for g in groups:
        print(f"{g.name}: {g.signals} (conf={g.confidence:.2f})")
    # AW: ['awvalid', 'awready', 'awaddr', 'awlen'] (conf=0.80)
    # W:  ['wvalid', 'wready', 'wdata', 'wstrb']     (conf=0.80)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .normalize import NormalizeConfig, SignalNormalizer


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ChannelGroup:
    """一个信号通道 (e.g., AXI AW / TL-UL A).

    Attributes:
        name: 通道名 (uppercase, e.g., "AW", "W", "A", "D")
        anchor_valid: anchor 的 valid 信号原始名
        anchor_ready: anchor 的 ready 信号原始名
        signals: 通道内所有信号 (原始名, 包括 anchor)
        confidence: 0.0-1.0, 反映分组可信度
    """

    name: str
    anchor_valid: str
    anchor_ready: str
    signals: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def signal_count(self) -> int:
        return len(self.signals)

    def get_role(self, signal_name: str) -> str:
        """推断信号在通道内的角色.

        优先 anchor 匹配, 然后基于 name 后缀 (简单 name-based).
        Session 4 融合会用 structural + handshake 进一步校准.
        """
        if signal_name == self.anchor_valid:
            return "valid"
        if signal_name == self.anchor_ready:
            return "ready"
        # Fallback: name pattern
        return _infer_role_from_name(signal_name)

    def __repr__(self) -> str:
        return (
            f"ChannelGroup(name={self.name!r}, signals={self.signals}, "
            f"conf={self.confidence:.2f})"
        )


# 兼容旧 API: ChannelSignal 作为 ChannelGroup 的别名 (旧测试可能引用)
ChannelSignal = ChannelGroup


# ---------------------------------------------------------------------------
# 角色推断 (name-based, 简单版)
# ---------------------------------------------------------------------------

def _infer_role_from_name(name: str) -> str:
    """基于 name 后缀推断角色. 简单版, Session 4 融合会进一步校准."""
    n = name.lower()
    # 标准角色后缀
    if n.endswith("valid") or n.endswith("vld") or n.endswith("req"):
        return "valid"
    if n.endswith("ready") or n.endswith("rdy") or n.endswith("ack"):
        return "ready"
    if n.endswith("stall") or n.endswith("wait"):
        return "ready"
    if n.endswith("data") or n.endswith("payload"):
        return "data"
    if n.endswith("addr") or n.endswith("address"):
        return "addr"
    if n.endswith("resp") or n.endswith("response"):
        return "resp"
    if n.endswith("strb") or n.endswith("strobe") or n.endswith("be"):
        return "strb"
    if n.endswith("last") or n.endswith("eop"):
        return "last"
    # AXI 控制信号
    if n.endswith(("len", "size", "burst", "id", "cache", "prot", "qos", "region", "lock", "user")):
        return "ctrl"
    return "unknown"


# ---------------------------------------------------------------------------
# PatternLearner
# ---------------------------------------------------------------------------

class PatternLearner:
    """Anchor-based 模式学习器.

    输入: (valid, ready) 锚点 + 所有信号名
    输出: List[ChannelGroup] (按通道分组)
    """

    def __init__(self, normalizer: Optional[SignalNormalizer] = None):
        self._norm = normalizer or SignalNormalizer(NormalizeConfig.default())

    def learn(
        self,
        anchors: List[Tuple[str, str]],
        all_signals: List[str],
    ) -> List[ChannelGroup]:
        """从 anchors 学习所有通道.

        Args:
            anchors: List of (valid_raw, ready_raw) tuples
            all_signals: 全部信号原始名 (用于分组)

        Returns:
            List[ChannelGroup] — 一个 anchor 对应一个 group
        """
        groups: List[ChannelGroup] = []
        seen_bases: Dict[str, ChannelGroup] = {}

        for valid_raw, ready_raw in anchors:
            # 1. 标准化 anchor 双方
            valid_norm = self._norm.normalize(valid_raw).normalized
            ready_norm = self._norm.normalize(ready_raw).normalized

            # 2. 找公共前缀
            channel_base = self._common_prefix(valid_norm, ready_norm)
            if not channel_base:
                continue

            # 3. 用 base 找所有匹配信号
            matched = self._match_signals(channel_base, all_signals)

            # 4. 确保 anchor 本身在 matched 里 (即使 all_signals 没给)
            if valid_raw not in matched:
                matched.insert(0, valid_raw)
            if ready_raw not in matched:
                matched.insert(1 if valid_raw in matched else 0, ready_raw)

            # 5. 推断置信度
            confidence = self._compute_confidence(channel_base, len(matched))

            # 6. 创建 / 复用 group (按 base 去重)
            base_key = channel_base
            if base_key in seen_bases:
                # 复用已有 group, 合并 signals
                existing = seen_bases[base_key]
                for sig in matched:
                    if sig not in existing.signals:
                        existing.signals.append(sig)
                continue

            group = ChannelGroup(
                name=channel_base.upper(),
                anchor_valid=valid_raw,
                anchor_ready=ready_raw,
                signals=matched,
                confidence=confidence,
            )
            seen_bases[base_key] = group
            groups.append(group)

        return groups

    # ----- 内部 -----

    @staticmethod
    def _common_prefix(s1: str, s2: str) -> str:
        """最长公共前缀."""
        if not s1 or not s2:
            return ""
        i = 0
        while i < len(s1) and i < len(s2) and s1[i] == s2[i]:
            i += 1
        return s1[:i]

    def _match_signals(self, channel_base: str, all_signals: List[str]) -> List[str]:
        """用 channel_base prefix-match 所有信号 (标准化后)."""
        matched: List[str] = []
        for sig in all_signals:
            sig_norm = self._norm.normalize(sig).normalized
            # 标准化后名字以 channel_base 开头
            if sig_norm.startswith(channel_base):
                matched.append(sig)
        return matched

    @staticmethod
    def _compute_confidence(channel_base: str, signal_count: int) -> float:
        """置信度: base 长度 + 信号数."""
        # 基础分: base 长度
        if len(channel_base) >= 3:
            base_score = 0.9
        elif len(channel_base) == 2:
            base_score = 0.8
        elif len(channel_base) == 1:
            base_score = 0.4
        else:
            return 0.0

        # 信号数加分 (≥3 信号置信度提升)
        if signal_count >= 5:
            count_bonus = 0.1
        elif signal_count >= 3:
            count_bonus = 0.05
        else:
            count_bonus = 0.0

        return min(1.0, base_score + count_bonus)
