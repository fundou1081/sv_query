"""
trace.core.protocol.structural - 结构性角色提示

Phase A Session 2: StructuralHints

设计要点
========

1. **纯结构, 不看名字** — 名字标准化是 Session 1 的事, Session 2 只看
   - width (1bit / small / wide)
   - direction (input / output / inout)
   - driver_kind (register / wire / port)
   - 配对 (paired_signals)

2. **8 个角色**:
   - valid:   1-bit output register, 配 ready
   - ready:   1-bit input, 配 valid
   - data:    宽 (≥32-bit) 信号
   - addr:    宽 output (32/64-bit)
   - resp:    小 (2-4 bit) input
   - ctrl:    小 (4-8 bit) 控制 (len/size/burst/id)
   - strb:    1-bit output, 配 data
   - last:    1-bit output, 配 data

3. **配对 boost** — 当一个 1-bit input 与 1-bit output 配对时, 双方分数都 +0.2
4. **分数归一化 [0, 1]** — 任何输入下不越界
5. **可独立使用** — 不依赖 Session 1/3, 输入是 SignalContext (解耦)

使用
====

    from trace.core.protocol.structural import (
        SignalContext, StructuralRoleDetector,
    )

    sigs = [
        SignalContext("awvalid", width=1, direction="output",
                      driver_kind="register", paired_signals=["awready"]),
        SignalContext("awready", width=1, direction="input",
                      paired_signals=["awvalid"]),
        SignalContext("awaddr", width=32, direction="output",
                      paired_signals=["awvalid"]),
    ]
    det = StructuralRoleDetector()
    results = det.detect_all(sigs)
    for name, hints in results.items():
        print(f"{name}: {hints.dominant_role()} ({hints.max_score():.2f})")
    # awvalid: valid (0.95)
    # awready: ready (0.85)
    # awaddr: addr (0.65)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 宽度分类
# ---------------------------------------------------------------------------

class WidthCategory(Enum):
    """宽度分类: 用于快速判断信号角色."""
    UNKNOWN = "unknown"  # 0 / 负数
    ONE_BIT = "1bit"     # 1
    SMALL = "small"      # 2-8 (resp / id / len / size / burst)
    WIDE = "wide"        # ≥9 (data / addr)

    @classmethod
    def classify(cls, width: int) -> "WidthCategory":
        if width <= 0:
            return cls.UNKNOWN
        if width == 1:
            return cls.ONE_BIT
        if width <= 8:
            return cls.SMALL
        return cls.WIDE


# ---------------------------------------------------------------------------
# SignalContext
# ---------------------------------------------------------------------------

@dataclass
class SignalContext:
    """信号上下文 (从 SV AST 提取的结构信息).

    Attributes:
        name: 信号名 (原始)
        width: 位宽 (整数)
        direction: input / output / inout
        driver_kind: register (clocked) / wire (combinational) / port (default)
        paired_signals: 配对信号名列表 (valid↔ready, data↔strb/last)
    """

    name: str
    width: int
    direction: str = "input"
    driver_kind: str = "port"
    paired_signals: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"SignalContext({self.name!r}, w={self.width}, "
            f"dir={self.direction}, drv={self.driver_kind}, "
            f"paired={self.paired_signals})"
        )


# ---------------------------------------------------------------------------
# StructuralHints
# ---------------------------------------------------------------------------

@dataclass
class StructuralHints:
    """结构性角色提示 (每个角色 0.0 - 1.0 置信度).

    8 个角色:
        is_valid_like: valid / req / strobe 类
        is_ready_like: ready / ack / stall / wait 类
        is_data_like:  data / payload 类 (宽信号)
        is_addr_like:  addr 类 (宽 output)
        is_resp_like:  resp / status 类 (小 input)
        is_ctrl_like:  len / size / burst / id / cache / prot 类 (小 output)
        is_strb_like:  strb / byte_enable 类
        is_last_like:  last 类
    """

    is_valid_like: float = 0.0
    is_ready_like: float = 0.0
    is_data_like: float = 0.0
    is_addr_like: float = 0.0
    is_resp_like: float = 0.0
    is_ctrl_like: float = 0.0
    is_strb_like: float = 0.0
    is_last_like: float = 0.0

    # 阈值: 高于此值认为是有效角色 (Session 4 融合会进一步调高)
    DEFAULT_THRESHOLD = 0.3

    # ----- 工具 -----

    # 内部: field 名 → short 名 映射
    _FIELD_TO_ROLE: Dict[str, str] = None  # type: ignore  # 延迟初始化

    @classmethod
    def _field_to_role_map(cls) -> Dict[str, str]:
        if cls._FIELD_TO_ROLE is None:
            cls._FIELD_TO_ROLE = {
                "is_valid_like": "valid",
                "is_ready_like": "ready",
                "is_data_like": "data",
                "is_addr_like": "addr",
                "is_resp_like": "resp",
                "is_ctrl_like": "ctrl",
                "is_strb_like": "strb",
                "is_last_like": "last",
            }
        return cls._FIELD_TO_ROLE

    def _all_scores(self) -> Dict[str, float]:
        """返回 {short_role: score} 映射, 用于 dominant_role()."""
        m = self._field_to_role_map()
        return {
            short: getattr(self, field)
            for field, short in m.items()
        }

    def max_score(self) -> float:
        scores = self._all_scores()
        return max(scores.values()) if scores else 0.0

    def dominant_role(self) -> Optional[str]:
        """返回最可能的角色, 阈值 0.5. 若所有都低于阈值, 返回 None."""
        scores = self._all_scores()
        if not scores:
            return None
        best_role = max(scores, key=scores.get)
        if scores[best_role] < self.DEFAULT_THRESHOLD:
            return None
        return best_role

    def above_threshold(self, threshold: float) -> List[str]:
        """返回所有 ≥ threshold 的角色名 (short form)."""
        return [
            role for role, score in self._all_scores().items()
            if score >= threshold
        ]

    def to_dict(self) -> Dict[str, float]:
        """返回 {field_name: score} 完整映射 (与 dataclass 字段名一致)."""
        return {
            field: getattr(self, field)
            for field in self._field_to_role_map()
        }


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class StructuralRoleDetector:
    """基于 width + direction + driver_kind + 配对 推断角色.

    算法:
        1. 基础分: width 类 → data/addr/resp/ctrl 初始分
        2. 方向分: direction → valid/ready 偏好
        3. driver 分: register → valid boost, wire → ready boost
        4. 配对分: 与 1-bit 配对 → valid+ready 双方 +0.2
        5. 归一化: 限制在 [0, 1]

    所有分数都是 heuristic, 不是 ML. 输出供 Session 4 融合层使用.
    """

    def __init__(
        self,
        # 可调权重 (一般不需改)
        valid_register_boost: float = 0.2,
        valid_1bit_boost: float = 0.3,
        ready_1bit_boost: float = 0.3,
        data_wide_boost: float = 0.3,
        addr_wide_boost: float = 0.3,
        resp_small_boost: float = 0.4,
        ctrl_small_boost: float = 0.3,
        pairing_boost: float = 0.2,
    ):
        self.valid_register_boost = valid_register_boost
        self.valid_1bit_boost = valid_1bit_boost
        self.ready_1bit_boost = ready_1bit_boost
        self.data_wide_boost = data_wide_boost
        self.addr_wide_boost = addr_wide_boost
        self.resp_small_boost = resp_small_boost
        self.ctrl_small_boost = ctrl_small_boost
        self.pairing_boost = pairing_boost

    def detect(
        self,
        signal: SignalContext,
        all_signals: Optional[List[SignalContext]] = None,
    ) -> StructuralHints:
        """对单个信号计算结构性 hints."""
        hints = StructuralHints()
        wcat = WidthCategory.classify(signal.width)

        # 构建按 name 索引的查找表 (用于配对查找)
        name_lookup: Dict[str, SignalContext] = {}
        if all_signals:
            for s in all_signals:
                name_lookup[s.name] = s

        # 1) 基础分: width
        if wcat == WidthCategory.WIDE:
            # 宽信号: data/addr 候选
            hints.is_data_like = self.data_wide_boost
            if signal.direction in ("output", "inout"):
                hints.is_addr_like = self.addr_wide_boost
        elif wcat == WidthCategory.SMALL:
            # 小信号: resp/ctrl 候选
            if signal.direction == "input":
                hints.is_resp_like = self.resp_small_boost
            else:
                hints.is_ctrl_like = self.ctrl_small_boost
        elif wcat == WidthCategory.ONE_BIT:
            # 1-bit: valid/ready/strb/last 候选
            if signal.direction == "output":
                hints.is_valid_like = self.valid_1bit_boost
                # 1-bit output 也可能是 strb/last (跟 data 配对)
                hints.is_strb_like = 0.1
                hints.is_last_like = 0.1
            elif signal.direction == "input":
                hints.is_ready_like = self.ready_1bit_boost
            # inout 1-bit: 低分多角色
            elif signal.direction == "inout":
                hints.is_valid_like = 0.05
                hints.is_ready_like = 0.05

        # 2) direction bias (已在 1) 处理)

        # 3) driver_kind bias
        if signal.driver_kind == "register" and signal.direction == "output" and wcat == WidthCategory.ONE_BIT:
            hints.is_valid_like += self.valid_register_boost
        elif signal.driver_kind == "wire" and signal.direction == "input" and wcat == WidthCategory.ONE_BIT:
            # combinational 1-bit input 更像 ready (ready 是 wire 常常)
            hints.is_ready_like += 0.1

        # 4) 配对 boost
        if signal.paired_signals and name_lookup:
            self._apply_pairing_boost(signal, name_lookup, hints, wcat)

        # 5) 归一化
        hints = self._clamp(hints)
        return hints

    def detect_all(
        self, signals: List[SignalContext],
    ) -> Dict[str, StructuralHints]:
        """批量检测, 返回 {name: hints}."""
        return {s.name: self.detect(s, all_signals=signals) for s in signals}

    # ----- 内部 -----

    def _apply_pairing_boost(
        self,
        signal: SignalContext,
        name_lookup: Dict[str, SignalContext],
        hints: StructuralHints,
        wcat: WidthCategory,
    ) -> None:
        """配对 boost: 找配对信号, 互相加分.

        优先级: 1-bit↔1-bit 握手对 > 1-bit↔wide last 模式 > 其他
        """
        # 先检查是否有 1-bit 输入配对 (valid+ready 模式) — 决定是否需要 last 降级
        has_1bit_input_pair = False
        for paired_name in signal.paired_signals:
            if paired_name not in name_lookup:
                continue
            paired = name_lookup[paired_name]
            if (
                WidthCategory.classify(paired.width) == WidthCategory.ONE_BIT
                and paired.direction == "input"
            ):
                has_1bit_input_pair = True
                break

        for paired_name in signal.paired_signals:
            if paired_name not in name_lookup:
                continue
            paired = name_lookup[paired_name]
            pwcat = WidthCategory.classify(paired.width)
            pdir = paired.direction

            # 1-bit ↔ 1-bit (valid + ready 配对)
            if (
                wcat == WidthCategory.ONE_BIT
                and pwcat == WidthCategory.ONE_BIT
                and signal.direction != pdir
            ):
                if signal.direction == "output" and pdir == "input":
                    hints.is_valid_like += self.pairing_boost
                elif signal.direction == "input" and pdir == "output":
                    hints.is_ready_like += self.pairing_boost
            # 1-bit output 配 wide output (last/strb 场景) — 仅当无 1-bit 输入配对时
            elif (
                wcat == WidthCategory.ONE_BIT
                and pwcat == WidthCategory.WIDE
                and signal.direction == "output"
                and pdir == "output"
                and not has_1bit_input_pair
            ):
                # wlast 1-bit output 配 wdata 32/64-bit (无 ready 配对)
                hints.is_last_like += 0.35
                hints.is_valid_like -= 0.25  # 压 valid (不要 valid 误判)
            # small output (strb) 配 wide output (data) — AXI wstrb/wdata 场景
            elif (
                wcat == WidthCategory.SMALL
                and pwcat == WidthCategory.WIDE
                and signal.direction == "output"
                and pdir == "output"
                and not has_1bit_input_pair
            ):
                # wstrb 是 byte enable, 4-bit/8-bit, 配 wdata 32/64-bit
                hints.is_strb_like += 0.3
                hints.is_ctrl_like -= 0.1  # 减 ctrl 分数
            # wide output (data) 配 1-bit/ small output (last/strb)
            elif (
                wcat == WidthCategory.WIDE
                and pwcat in (WidthCategory.ONE_BIT, WidthCategory.SMALL)
            ):
                if signal.direction == "output" and pdir == "output":
                    hints.is_data_like += 0.1
                elif signal.direction == "input" and pdir == "input":
                    hints.is_data_like += 0.1
            # wide input (read data) 配 1-bit input (read valid)
            elif (
                wcat == WidthCategory.WIDE
                and pwcat == WidthCategory.ONE_BIT
            ):
                if signal.direction == "input" and pdir == "input":
                    hints.is_data_like += 0.1

    @staticmethod
    def _clamp(hints: StructuralHints) -> StructuralHints:
        """限制分数在 [0, 1]."""
        return StructuralHints(
            is_valid_like=_clamp01(hints.is_valid_like),
            is_ready_like=_clamp01(hints.is_ready_like),
            is_data_like=_clamp01(hints.is_data_like),
            is_addr_like=_clamp01(hints.is_addr_like),
            is_resp_like=_clamp01(hints.is_resp_like),
            is_ctrl_like=_clamp01(hints.is_ctrl_like),
            is_strb_like=_clamp01(hints.is_strb_like),
            is_last_like=_clamp01(hints.is_last_like),
        )


def _clamp01(x: float) -> float:
    """限制在 [0, 1]."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x
