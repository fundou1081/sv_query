"""D4 regression — `SignalGraph.from_dict` must not guess unknown `NodeKind`."""
from __future__ import annotations

import pytest

from sv_query.trace.core.graph.models import (
    EdgeKind,
    NodeKind,
    SignalGraph,
    TraceEdge,
    TraceNode,
)

NODE_ID = "top.a"


def _node(kind: object = NodeKind.SIGNAL, *, include_kind: bool = True) -> dict:
    node = {"id": NODE_ID, "name": "a", "module": "top"}
    if include_kind:
        node["kind"] = kind
    return node


def _one(node: dict) -> dict:
    return {"nodes": [node], "edges": []}


@pytest.mark.parametrize(
    "bad_kind",
    ["NOPE", "signal", "", "PORT-IN", "Signal "],
)
def test_unknown_node_kind_raises(bad_kind: str):
    with pytest.raises(ValueError, match="unknown NodeKind"):
        SignalGraph.from_dict(_one(_node(bad_kind)))


def test_non_string_node_kind_raises():
    with pytest.raises(ValueError, match="unknown NodeKind"):
        SignalGraph.from_dict(_one(_node([1, 2])))


def test_missing_node_kind_raises_instead_of_signal_fallback():
    with pytest.raises(ValueError, match="missing 'kind'"):
        SignalGraph.from_dict(_one(_node(include_kind=False)))


@pytest.mark.parametrize("kind", list(NodeKind), ids=[k.name for k in NodeKind])
def test_all_node_kinds_load_unchanged(kind: NodeKind):
    graph = SignalGraph.from_dict(_one(_node(kind.name)))
    assert graph.get_node(NODE_ID).kind is kind


def test_node_kind_roundtrip_preserves_kinds():
    graph = SignalGraph()
    for i, kind in enumerate(NodeKind):
        graph.add_trace_node(TraceNode(
            id=f"top.n{i}", name=f"n{i}", module="top", kind=kind, width=(0, 0),
        ))
    graph.add_trace_edge(TraceEdge("top.n0", "top.n1", EdgeKind.DRIVER))

    restored = SignalGraph.from_dict(graph.to_dict())
    for i, kind in enumerate(NodeKind):
        assert restored.get_node(f"top.n{i}").kind is kind
