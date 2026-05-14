#==============================================================================
# trace.core - 统一查询入口
#==============================================================================

from .graph import (
    SignalGraph,
    TraceNode,
    TraceEdge,
    NodeKind,
    EdgeKind,
    GraphDiff,
    diff_graph,
    diff_reachability,
    forward_reachability,
)

from .graph_builder import (
    GraphBuilder,
    DriverExtractor,
    LoadExtractor,
    ConnectionExtractor,
    ClockDomainExtractor,
)

from .query import (
    SignalTracer,
    SignalChain,
    LoadTracer,
    LoadChain,
    ModuleTracer,
    ModuleConnections,
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
    # Graph Diff
    "GraphDiff",
    "diff_graph",
    "diff_reachability",
    "forward_reachability",
    # Builder
    "GraphBuilder",
    "DriverExtractor",
    "LoadExtractor",
    "ConnectionExtractor",
    "ClockDomainExtractor",
    # Signal Query
    "SignalTracer",
    "SignalChain",
    # Load Query
    "LoadTracer",
    "LoadChain",
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