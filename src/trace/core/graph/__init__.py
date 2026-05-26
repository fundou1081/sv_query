#==============================================================================
# trace.core.graph - Graph 数据模型 + 图操作
#==============================================================================

from .models import (
    SignalGraph,
    TraceNode,
    TraceEdge,
    NodeKind,
    EdgeKind,
)

from .diff import (
    GraphDiff,
    diff_graph,
    diff_reachability,
    forward_reachability,
)

from .dataflow import (
    DataFlowGraph,
    DataFlowSegment,
    DataFlowPath,
    DataFlowResult,
)

# ControlFlow
from .controlflow_models import (
    ControlFlowNodeKind,
    ControlFlowEdgeKind,
    BranchKind,
    Location,
    Branch,
    ControlBlock,
    ControlFlowNode,
    ControlFlowEdge,
    BranchResult,
    Contradiction,
    LintWarning,
    StateTransition,
    StateMachineAnalysis,
    Z3Result,
    ControlFlowResult,
)

from .controlflow import ControlFlowGraph

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