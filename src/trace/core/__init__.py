# ==============================================================================
# trace.core - 统一查询入口
# ==============================================================================

# 也导出 base 模块
from .base import ASTWalker, PyslangAdapter
from .graph import (
    EdgeKind,
    GraphDiff,
    NodeKind,
    SignalGraph,
    TraceEdge,
    TraceNode,
    diff_graph,
    diff_reachability,
    forward_reachability,
)
from .graph_builder import (
    ClockDomainExtractor,
    ConnectionExtractor,
    DriverExtractor,
    GraphBuilder,
    LoadExtractor,
)
from .query import (
    ClockDomainTrace,
    ClockDomainTracer,
    CrossingRisk,
    LoadChain,
    LoadTracer,
    ModuleConnections,
    ModuleTracer,
    SignalChain,
    SignalTracer,
)

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
