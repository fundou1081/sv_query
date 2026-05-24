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
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class SignalResult:
    """信号提取结果
    
    统一 visit() 和 get_all_signals() 的返回值。
    
    Attributes:
        primary: 单个信号名（用于需要主信号的场景）
        all_signals: 所有信号列表（去重）
    """
    primary: Optional[str] = None
    all_signals: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """去重 all_signals"""
        if self.all_signals:
            seen = set()
            self.all_signals = [x for x in self.all_signals if not (x in seen or seen.add(x))]
    
    @classmethod
    def single(cls, name: str) -> 'SignalResult':
        """创建单信号结果"""
        return cls(primary=name, all_signals=[name] if name else [])
    
    @classmethod
    def multi(cls, signals: List[str]) -> 'SignalResult':
        """创建多信号结果"""
        signals = [s for s in signals if s]
        return cls(primary=signals[0] if signals else None, all_signals=signals)
    
    @classmethod
    def empty(cls) -> 'SignalResult':
        """创建空结果"""
        return cls(primary=None, all_signals=[])
