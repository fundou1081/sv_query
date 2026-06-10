"""
trace.core.protocol - Protocol schema 框架 (Phase A)

子模块:
  - normalize:   SignalNormalizer 名字标准化 (Session 1)
  - structural:  StructuralHints 结构性提示 (Session 2)
  - schema:      YAML 协议 schema 加载/校验
  - detector:    协议检测评分引擎
"""

from .normalize import (
    NormalizeConfig,
    NormalizeResult,
    SignalNormalizer,
)
from .structural import (
    SignalContext,
    StructuralHints,
    StructuralRoleDetector,
    WidthCategory,
)

__all__ = [
    "NormalizeConfig",
    "NormalizeResult",
    "SignalNormalizer",
    "SignalContext",
    "StructuralHints",
    "StructuralRoleDetector",
    "WidthCategory",
]
