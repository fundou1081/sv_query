"""P194.5.17 — top-anchored duplicate bit nodes must not fail verification."""
from __future__ import annotations

from sv_query.cli.core.semantic.verify import _check_bit_mapping
from sv_query.trace.core.graph.models import NodeKind, SignalGraph, TraceNode


def test_nested_peer_suppresses_top_shadow_violation():
    graph = SignalGraph()
    graph.add_trace_node(TraceNode(id="top.rdata0", name="rdata0",
                                   module="top", kind=NodeKind.SIGNAL, width=(0, 0)))
    graph.add_trace_node(TraceNode(
        id="top.rdata0[1:1]", name="rdata0[1:1]", module="top",
        kind=NodeKind.SIGNAL, width=(1, 1), parent="top.rdata0",
        parent_bit_start=1, parent_bit_end=1, bit_range="[1:1]"))
    graph.add_trace_node(TraceNode(id="top.u.rdata0", name="rdata0",
                                   module="top.u", kind=NodeKind.REG, width=(1, 0)))
    graph.add_trace_node(TraceNode(id="top.u.rdata0[1:1]", name="rdata0[1:1]",
                                   module="top.u", kind=NodeKind.SIGNAL,
                                   width=(1, 0)))
    result = _check_bit_mapping(graph, None)
    assert result["violations"] == []
