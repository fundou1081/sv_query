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
    control_blocks: list[Any] = field(default_factory=list)  # list[ControlBlock]
    depth_reached: int = 0
    signal_count: int = 0
    truncated: bool = False
    error: str | None = None

    def __str__(self) -> str:
        if self.error:
            return f"Error: {self.error}"
        return (
            f"Decompose({self.original_signal}) -> "
            f"{self.signal_count} atomic signals (depth={self.depth_reached})"
        )
