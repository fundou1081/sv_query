"""D5 — edge-created placeholder nodes must be explicit, not silent SIGNAL."""
from __future__ import annotations

from sv_query.trace.core.graph.models import (
    EdgeKind,
    NodeKind,
    SignalGraph,
    TraceEdge,
    TraceNode,
)


def test_missing_endpoint_placeholder_is_explicitly_marked():
    graph = SignalGraph()
    graph.add_trace_edge(TraceEdge("top.a", "top.b", EdgeKind.DRIVER))

    for node_id in ("top.a", "top.b"):
        node = graph.get_node(node_id)
        assert node is not None
        assert node.kind is NodeKind.SIGNAL
        assert node.extra["placeholder"] is True
        assert node.extra["kind_origin"] == "edge_placeholder"
        assert "not declared" in node.extra["placeholder_reason"]


def test_declared_endpoint_is_not_marked_placeholder():
    graph = SignalGraph()
    graph.add_trace_node(TraceNode(
        id="top.a", name="a", module="top", kind=NodeKind.REG, width=(0, 0),
    ))
    graph.add_trace_edge(TraceEdge("top.a", "top.b", EdgeKind.DRIVER))

    declared = graph.get_node("top.a")
    assert declared.kind is NodeKind.REG
    assert "placeholder" not in declared.extra
    assert graph.get_node("top.b").extra["placeholder"] is True


def test_literal_endpoint_stays_const_without_placeholder_marker():
    graph = SignalGraph()
    graph.add_trace_edge(TraceEdge("top.a", "1'b0", EdgeKind.DRIVER))

    literal = graph.get_node("1'b0")
    assert literal.kind is NodeKind.CONST
    assert "placeholder" not in literal.extra
    assert graph.get_node("top.a").extra["placeholder"] is True


def test_placeholder_marker_roundtrips_through_dict():
    graph = SignalGraph()
    graph.add_trace_edge(TraceEdge("top.a", "top.b", EdgeKind.DRIVER))

    restored = SignalGraph.from_dict(graph.to_dict())
    assert restored.get_node("top.a").extra["placeholder"] is True
    assert restored.get_node("top.b").extra["kind_origin"] == "edge_placeholder"
