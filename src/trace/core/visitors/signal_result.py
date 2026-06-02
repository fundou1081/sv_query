# signal_result.py - SignalResult 数据类
"""
SignalResult: 统一信号提取结果的数据类

替代原来的双接口 (visit + get_all_signals)，统一返回 SignalResult。

[铁律X] SignalResult 模式
使用 SignalResult 统一表达单信号和多信号提取结果。

Usage:
    result = visitor.extract(node)
    result.primary      # 单信号名 (用于赋值 LHS)
    result.all_signals  # 所有信号列表 (用于赋值 RHS)
    result.kind_name    # 表达式类型名
    result.op_name      # 操作符名 (如有)
    result.signal_info  # 信号详细信息
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignalResult:
    """信号提取结果（增强版）

    包含丰富信息，支持未来的任务需求。

    Attributes:
        primary: 单个信号名（用于需要主信号的场景，如赋值 LHS）
        all_signals: 所有信号列表（去重，用于需要所有信号的场景）
        signal_info: 信号详细信息字典 {信号名: {属性}}
        kind_name: ExpressionKind 名称 (如 'BinaryOp', 'NamedValue')
        op_name: 操作符名 (如 'Add', 'Subtract', 'And')
        source_range: 源码位置 ((line, col), (line, col))
    """

    # 核心结果
    primary: str | None = None
    all_signals: list[str] = field(default_factory=list)

    # 表达式元信息
    kind_name: str | None = None
    op_name: str | None = None

    # 信号详细信息（未来扩展用）
    signal_info: dict[str, Any] = field(default_factory=dict)

    # 位置信息
    source_range: tuple | None = None

    def __post_init__(self):
        """去重 all_signals"""
        if self.all_signals:
            seen = set()
            self.all_signals = [x for x in self.all_signals if not (x in seen or seen.add(x))]

    @property
    def is_multisignal(self) -> bool:
        """是否多信号表达式"""
        return len(self.all_signals) > 1

    @property
    def signal_count(self) -> int:
        """信号数量"""
        return len(self.all_signals)

    @classmethod
    def single(cls, name: str, **kwargs) -> "SignalResult":
        """创建单信号结果"""
        return cls(primary=name, all_signals=[name] if name else [], **kwargs)

    @classmethod
    def multi(cls, signals: list[str], **kwargs) -> "SignalResult":
        """创建多信号结果"""
        signals = [s for s in signals if s]
        return cls(primary=signals[0] if signals else None, all_signals=signals, **kwargs)

    @classmethod
    def empty(cls) -> "SignalResult":
        """创建空结果"""
        return cls()

    def merge(self, other: "SignalResult | None") -> "SignalResult":
        """合并另一个 SignalResult 到当前实例 (in-place)

        Args:
            other: 另一个 SignalResult, None 则不处理

        Returns:
            self (便于链式调用)
        """
        if other is None:
            return self
        # 合并 all_signals (去重)
        for sig in (other.all_signals or []):
            if sig and sig not in self.all_signals:
                self.all_signals.append(sig)
        # 保留非空 primary
        if not self.primary and other.primary:
            self.primary = other.primary
        # 保留 kind/op 元信息 (取较详细的)
        if other.kind_name and not self.kind_name:
            self.kind_name = other.kind_name
        if other.op_name and not self.op_name:
            self.op_name = other.op_name
        return self
