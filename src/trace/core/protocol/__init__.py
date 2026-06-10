"""
trace.core.protocol - Protocol schema 框架 (Phase A)

子模块:
  - normalize:       SignalNormalizer 名字标准化 (Session 1)
  - structural:      StructuralHints 结构性提示 (Session 2)
  - pattern_learner: PatternLearner anchor 模式学习 (Session 3)
  - schema:          YAML 协议 schema 加载/校验 (Session 4)
  - detector:        协议检测评分引擎 (Session 4)
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
from .pattern_learner import (
    ChannelGroup,
    ChannelSignal,  # 别名
    PatternLearner,
)
from .schema import (
    ChannelSpec,
    ProtocolSchema,
    ProtocolSchemaRegistry,
    SignalRoleSpec,
    VariantSpec,
    load_protocols,
)
from .detector import (
    ChannelMatch,
    ProtocolDetector,
    ProtocolMatch,
    SignalMapping,
)
from .handshake_provider import (
    HandshakeInfoLite,
    HandshakeProvider,
    NameBasedHandshakeProvider,
    handshake_type_score,
)
from .handshake_provider_trace import (
    TraceBasedHandshakeProvider,
    make_trace_based_provider,
)

__all__ = [
    "NormalizeConfig",
    "NormalizeResult",
    "SignalNormalizer",
    "SignalContext",
    "StructuralHints",
    "StructuralRoleDetector",
    "WidthCategory",
    "ChannelGroup",
    "ChannelSignal",
    "PatternLearner",
    "ChannelSpec",
    "ProtocolSchema",
    "ProtocolSchemaRegistry",
    "SignalRoleSpec",
    "VariantSpec",
    "load_protocols",
    "ChannelMatch",
    "ProtocolDetector",
    "ProtocolMatch",
    "SignalMapping",
    "HandshakeInfoLite",
    "HandshakeProvider",
    "NameBasedHandshakeProvider",
    "handshake_type_score",
    "TraceBasedHandshakeProvider",
    "make_trace_based_provider",
]
