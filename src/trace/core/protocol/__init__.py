"""
trace.core.protocol - Protocol schema 框架 (Phase A)

子模块:
  - normalize: SignalNormalizer 名字标准化
  - schema:    YAML 协议 schema 加载/校验
  - detector:  协议检测评分引擎
"""

from .normalize import (
    NormalizeConfig,
    NormalizeResult,
    SignalNormalizer,
)

__all__ = [
    "NormalizeConfig",
    "NormalizeResult",
    "SignalNormalizer",
]
