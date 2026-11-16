"""D1 regression — `SignalGraph.from_dict` must not guess unknown `EdgeKind`.

Root PLAN: P183.1 (failure-as-state quick fixes).

Defect (baseline `0a277491`): `from_dict` did

    kind_str = edge_dict.get("kind", "DRIVER")
    try:
        kind = EdgeKind[kind_str]
    except (KeyError, TypeError):
        kind = EdgeKind.DRIVER

so any unknown string, `None`, non-string, or a snapshot with a missing
`kind` key silently became `DRIVER`.  A control edge written by a newer
schema would then be read as a data edge, violating
SEMANTIC_CONTRACTS §2 (data edges are exactly DRIVER + CONNECTION).

Contract under test:
  * unknown / missing edge kind -> ValueError (message names src/dst/kind);
  * every known `EdgeKind` member still loads unchanged (oracle = the enum).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from sv_query.trace.core.graph.models import (  # noqa: E402
    EdgeKind,
    NodeKind,
    SignalGraph,
    TraceEdge,
    TraceNode,
)

SRC_ID = "top.a"
DST_ID = "top.b"


def _snapshot(edge_extra: dict, *, include_kind: bool = True) -> dict:
    edge = {"src": SRC_ID, "dst": DST_ID}
    if include_kind:
        edge["kind"] = edge_extra["kind"]
    return {
        "nodes": [{"id": SRC_ID, "kind": "SIGNAL"}, {"id": DST_ID, "kind": "SIGNAL"}],
        "edges": [edge],
    }


@pytest.mark.parametrize(
    "bad_kind",
    ["CONTROL", "UNKNOWN", "port_connection", "", "DRIVER "],
    ids=["control", "unknown", "snake_case", "empty", "trailing_space"],
)
def test_unknown_edge_kind_raises_value_error(bad_kind: str):
    with pytest.raises(ValueError) as excinfo:
        SignalGraph.from_dict(_snapshot({"kind": bad_kind}))

    message = str(excinfo.value)
    assert "unknown EdgeKind" in message
    assert repr(bad_kind) in message
    assert SRC_ID in message and DST_ID in message


def test_non_string_edge_kind_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        SignalGraph.from_dict(_snapshot({"kind": [1, 2]}))

    message = str(excinfo.value)
    assert "unknown EdgeKind" in message
    assert SRC_ID in message and DST_ID in message


def test_missing_edge_kind_raises_instead_of_defaulting_driver():
    with pytest.raises(ValueError) as excinfo:
        SignalGraph.from_dict(_snapshot({}, include_kind=False))

    message = str(excinfo.value)
    assert "missing 'kind'" in message
    assert SRC_ID in message and DST_ID in message


@pytest.mark.parametrize("kind", list(EdgeKind), ids=[k.name for k in EdgeKind])
def test_known_edge_kinds_load_unchanged(kind: EdgeKind):
    graph = SignalGraph.from_dict(_snapshot({"kind": kind.name}))

    edges = graph.get_edges(SRC_ID, DST_ID)
    assert [edge.kind for edge in edges] == [kind]


def test_roundtrip_with_all_edge_kinds_preserves_kinds():
    """True-negative against the old fallback: mixed kinds survive a round trip."""
    graph = SignalGraph()
    for i, kind in enumerate(EdgeKind):
        src, dst = f"top.src{i}", f"top.dst{i}"
        for node_id in (src, dst):
            graph.add_trace_node(
                TraceNode(
                    id=node_id,
                    name=node_id.split(".", 1)[1],
                    module="top",
                    kind=NodeKind.SIGNAL,
                    width=(0, 0),
                )
            )
        graph.add_trace_edge(TraceEdge(src=src, dst=dst, kind=kind))

    restored = SignalGraph.from_dict(graph.to_dict())

    for i, kind in enumerate(EdgeKind):
        edges = restored.get_edges(f"top.src{i}", f"top.dst{i}")
        assert [edge.kind for edge in edges] == [kind]
