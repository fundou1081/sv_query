"""P197.9 — semantic bit-index and child classification."""
from __future__ import annotations

from sv_query.trace.core.graph.models import NodeKind, SignalGraph, TraceNode
from sv_query.trace.core.query.signal import SignalTracer


def _node(nid, *, parent=None, bit_start=None, bit_end=None, bit_range=None):
    return TraceNode(
        id=nid, name=nid.split(".", 1)[-1], module=nid.split(".", 1)[0],
        kind=NodeKind.SIGNAL, width=(1, 0), parent=parent,
        parent_bit_start=bit_start, parent_bit_end=bit_end, bit_range=bit_range)


def test_bit_index_prefers_metadata_over_misleading_id():
    graph = SignalGraph()
    graph.add_trace_node(_node("top.a[3]", parent="top.a", bit_start=0, bit_end=7))
    tracer = SignalTracer(graph)
    assert tracer._bit_index_of("top.a[3]") is None
    graph.add_trace_node(_node("top.b[9]"))
    assert tracer._bit_index_of("top.b[9]") == 9


def test_expand_bit_children_uses_parent_metadata(monkeypatch):
    graph = SignalGraph()
    graph.add_trace_node(_node("top.bus"))
    graph.add_trace_node(_node("top.bus[3]", parent="top.bus", bit_start=3, bit_end=3))
    graph.add_trace_node(_node("top.bus[4]", parent="top.other", bit_start=4, bit_end=4))
    graph.add_trace_node(_node("top.bus[WIDTH-1:0]"))
    tracer = SignalTracer(graph)
    called = []
    monkeypatch.setattr(tracer, "_trace_drivers_recursive",
                        lambda nid, *args, **kwargs: called.append(nid))
    tracer._expand_bit_children("top.bus", [], set(), 0, None, True)
    assert set(called) == {"top.bus[3]", "top.bus[WIDTH-1:0]"}
