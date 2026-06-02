# ==============================================================================
# coverage_models.py - Control Coverage Generator 数据模型
#
# 数据结构:
# - SourceLocation: 源码位置
# - SourceSnippet: 源码片段（懒加载）
# - EvidenceStep: 推导链单步
# - AtomicSignal: 原子信号（含位选）
# - DecompositionResult: 分解结果
# ==============================================================================

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SourceLocation:
    """源码位置

    Attributes:
        file: 文件路径
        line_start: 起始行 (1-indexed)
        line_end: 结束行 (1-indexed)
        column: 列号 (0-indexed)
    """

    file: str = ""
    line_start: int = 0
    line_end: int = 0
    column: int = 0

    def is_empty(self) -> bool:
        """是否没有位置信息"""
        return not self.file or self.line_start == 0

    def to_dict(self) -> dict:
        """序列化为 dict (V2.C 周期 12)

        Returns:
            包含所有字段的普通 dict
        """
        return {
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column": self.column,
        }

    def __str__(self) -> str:
        if self.is_empty():
            return "(no location)"
        if self.line_start == self.line_end:
            return f"{self.file}:{self.line_start}"
        return f"{self.file}:{self.line_start}-{self.line_end}"


@dataclass
class SourceSnippet:
    """源码片段（懒加载）

    当 text 为空时，调用 text_provider(file) 加载内容。
    加载结果会缓存，避免重复 IO。
    """

    location: SourceLocation
    text: str = ""
    text_provider: Callable[[str], str] | None = field(default=None, repr=False)
    _loaded: bool = field(default=False, init=False, repr=False)

    def load_text(self) -> str:
        """懒加载源码

        Returns:
            源码内容。如果 text 已设置，直接返回。
            否则调用 text_provider(file) 获取并缓存。
        """
        if self.text:
            return self.text
        if self._loaded:
            return self.text
        if self.text_provider and self.location.file:
            self.text = self.text_provider(self.location.file)
            self._loaded = True
        return self.text


@dataclass
class EvidenceStep:
    """推导链单步 - signal/位选分开

    Attributes:
        step_type: 类型 (driver_chain|bit_select|expression_parse|
                    control_block|port_stop|cross_module)
        description: 人类可读描述
        from_signal: 推导起点
        to_signals: 推导终点列表
        source: 所在源码
    """

    step_type: str = ""
    description: str = ""
    from_signal: str = ""
    to_signals: list[str] = field(default_factory=list)
    source: SourceSnippet | None = None

    def to_dict(self) -> dict:
        """序列化为 dict (V2.C 周期 12)

        注意: 不调用 SourceSnippet.load_text() 以避免在 JSON 输出时
        意外触发文件 IO。SourceSnippet 对象的 text 为空时序列化为 ""。
        """
        return {
            "step_type": self.step_type,
            "description": self.description,
            "from_signal": self.from_signal,
            "to_signals": list(self.to_signals),
            "source": (self.source.text if self.source else None),
        }

    def __str__(self) -> str:
        if self.description:
            return self.description
        return f"{self.step_type}: {self.from_signal} -> {self.to_signals}"


@dataclass
class AtomicSignal:
    """原子信号（含位选）

    Attributes:
        name: 完整名称 "a" 或 "a[3:0]"
        base_name: 不含位选的名称 "a"
        bit_range: 位选范围 (3, 0) 或 None
        source: 出现位置
        evidence: 推导链步骤列表
    """

    name: str = ""
    base_name: str = ""
    bit_range: tuple[int, int] | None = None
    source: SourceLocation = field(default_factory=SourceLocation)
    evidence: list[EvidenceStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化为 dict (V2.C 周期 12)

        bit_range 序列化为 list (JSON spec 不支持 tuple).
        """
        return {
            "name": self.name,
            "base_name": self.base_name,
            "bit_range": list(self.bit_range) if self.bit_range is not None else None,
            "source": self.source.to_dict() if self.source is not None else None,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    def __str__(self) -> str:
        return self.name


@dataclass
class DecompositionResult:
    """信号分解结果

    Attributes:
        original_signal: 用户输入的原始信号
        atomic_signals: 分解后的原子信号列表
        control_blocks: 涉及的 if/case blocks
        depth_reached: 实际分解深度
        signal_count: 原子信号数量
        truncated: 是否因为限制被截断
        error: 错误信息 (如有)
    """

    original_signal: str = ""
    atomic_signals: list[AtomicSignal] = field(default_factory=list)
    control_blocks: list[Any] = field(default_factory=list)  # list[ControlBlock|TraceEdge]
    depth_reached: int = 0
    signal_count: int = 0
    truncated: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        """序列化为 dict (V2.C 周期 12)

        Returns:
            包含所有字段的普通 dict, 所有嵌套 dataclass 递归展开.
            control_blocks 异构: TraceEdge / ControlBlock (带 to_dict) / 其他
            三种情况都兼容。
        """
        return {
            "original_signal": self.original_signal,
            "atomic_signals": [a.to_dict() for a in self.atomic_signals],
            "control_blocks": [self._control_block_to_dict(b) for b in self.control_blocks],
            "depth_reached": self.depth_reached,
            "signal_count": self.signal_count,
            "truncated": self.truncated,
            "error": self.error,
        }

    def to_json(self, indent: int | None = 2) -> str:
        """序列化为 JSON 字符串 (V2.C 周期 12)

        Args:
            indent: JSON 缩进, 默认 2. 传 None 紧凑模式 (单行).

        Returns:
            有效的 JSON 字符串 (ensure_ascii=False 支持中文)
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def _control_block_to_dict(block: Any) -> dict:
        """控制块可能是 TraceEdge 或 ControlBlock, 兼容两种类型

        优先级:
        1. 带 effective_condition 属性的对象 (TraceEdge) -> 详细字段
        2. 带 to_dict() 方法的对象 (未来 ControlBlock) -> 调用 to_dict()
        3. 其他 (int, str, None) -> 降级为 repr 字符串
        """
        if hasattr(block, "effective_condition"):
            return {
                "type": "TraceEdge",
                "src": getattr(block, "src", ""),
                "dst": getattr(block, "dst", ""),
                "condition": (
                    getattr(block, "effective_condition", "")
                    or getattr(block, "condition", "")
                ),
                "expression": getattr(block, "expression", ""),
            }
        if hasattr(block, "to_dict") and callable(block.to_dict):
            try:
                return block.to_dict()
            except Exception:
                pass
        # Fallback: repr 字符串
        return {"repr": str(block)}

    def __str__(self) -> str:
        if self.error:
            return f"Error: {self.error}"
        return (
            f"Decompose({self.original_signal}) -> "
            f"{self.signal_count} atomic signals (depth={self.depth_reached})"
        )
