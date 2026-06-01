# ==============================================================================
# trace.core.graph - Graph 数据模型 + 图操作
# ==============================================================================

from .controlflow import ControlFlowGraph

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
