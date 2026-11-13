# ==============================================================================
# sv_query.trace.core.graph - Graph 数据模型 + 图操作
# ==============================================================================

from .controlflow import ControlFlowGraph

# Edge 分类契约 (P158.1) —— 唯一实现
from .contracts import (
    CLASS_EDGE_KINDS,
    CONTROL_EDGE_KINDS,
    DATA_EDGE_KINDS,
    SIGNAL_EDGE_KINDS,
    STRUCTURAL_EDGE_KINDS,
    data_edge_view,
    filter_edges,
    has_data_edge,
    is_control_edge,
    is_data_edge,
    is_structural_edge,
)

# ControlFlow
from .controlflow_models import (
    Branch,
    BranchKind,
    BranchResult,
    Contradiction,
    ControlBlock,
    ControlFlowEdge,
    ControlFlowEdgeKind,
    ControlFlowNode,
    ControlFlowNodeKind,
    ControlFlowResult,
    LintWarning,
    Location,
    StateMachineAnalysis,
    StateTransition,
    Z3Result,
)
from .dataflow import (
    DataFlowGraph,
    DataFlowPath,
    DataFlowResult,
    DataFlowSegment,
)
from .diff import (
    GraphDiff,
    diff_graph,
    diff_reachability,
    forward_reachability,
)
from .models import (
    EdgeKind,
    NodeKind,
    SignalGraph,
    TraceEdge,
    TraceNode,
)

__all__ = [
    # Models
    "SignalGraph",
    "TraceNode",
    "TraceEdge",
    "NodeKind",
    "EdgeKind",
    # Edge 分类契约 (P158.1)
    "DATA_EDGE_KINDS",
    "CONTROL_EDGE_KINDS",
    "STRUCTURAL_EDGE_KINDS",
    "CLASS_EDGE_KINDS",
    "SIGNAL_EDGE_KINDS",
    "is_data_edge",
    "is_control_edge",
    "is_structural_edge",
    "has_data_edge",
    "filter_edges",
    "data_edge_view",
    # Diff
    "GraphDiff",
    "diff_graph",
    "diff_reachability",
    "forward_reachability",
    # DataFlow
    "DataFlowGraph",
    "DataFlowSegment",
    "DataFlowPath",
    "DataFlowResult",
    # ControlFlow
    "ControlFlowNodeKind",
    "ControlFlowEdgeKind",
    "BranchKind",
    "Location",
    "Branch",
    "ControlBlock",
    "ControlFlowNode",
    "ControlFlowEdge",
    "BranchResult",
    "Contradiction",
    "LintWarning",
    "StateTransition",
    "StateMachineAnalysis",
    "Z3Result",
    "ControlFlowResult",
    "ControlFlowGraph",
]
