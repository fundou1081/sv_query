#==============================================================================
# trace.core - 统一查询入口
#==============================================================================

from .graph_models import (
    SignalGraph,
    TraceNode,
    TraceEdge,
    NodeKind,
    EdgeKind,
)

from .graph_builder import (
    GraphBuilder,
    DriverExtractor,
    LoadExtractor,
    ConnectionExtractor,
    ClockDomainExtractor,
)

from .query_signal import (
    SignalTracer,
    SignalChain,
)

from .query_module import (
    ModuleTracer,
    ModuleConnections,
)

from .query_clock_domain import (
    ClockDomainTracer,
    ClockDomainTrace,
    CrossingRisk,
)

# 也导出 base 模块
from .base import PyslangAdapter, ASTWalker

__all__ = [
    # Graph Models
    "SignalGraph",
    "TraceNode", 
    "TraceEdge",
    "NodeKind",
    "EdgeKind",
    # Builder
    "GraphBuilder",
    "DriverExtractor",
    "LoadExtractor",
    "ConnectionExtractor",
    "ClockDomainExtractor",
    # Signal Query
    "SignalTracer",
    "SignalChain",
    # Module Query
    "ModuleTracer",
    "ModuleConnections",
    # Clock Domain Query
    "ClockDomainTracer",
    "ClockDomainTrace", 
    "CrossingRisk",
    # Syntax Layer
    "PyslangAdapter",
    "ASTWalker",
]
