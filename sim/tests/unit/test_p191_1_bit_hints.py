"""P191.1 — bit-select hint contract helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sv_query.cli.core.semantic._bit_hints import (  # noqa: E402
    bit_hint_payload,
    descendant_bit_nodes,
    split_bit_range,
)
from sv_query.trace.core.graph.models import SignalGraph  # noqa: E402


def _graph() -> SignalGraph:
    graph = SignalGraph()
    graph.add_node("top.bus")
    graph.add_node("top.bus[7:0]")
    graph.add_node("top.bus[0]")
    graph.add_node("top.other[1]")
    graph.add_node("top.src")
    graph.add_edge("top.src", "top.bus[0]")
    return graph


def test_split_bit_range_and_direct_descendants():
    assert split_bit_range("top.bus[7:0]", "top.bus") == {"msb": "7", "lsb": "0"}
    assert split_bit_range("top.bus[0]", "top.bus") == {"msb": "0", "lsb": "0"}
    assert split_bit_range("top.busx[0]", "top.bus") is None
    rows = descendant_bit_nodes(_graph(), "top.bus")
    assert [row["id"] for row in rows] == ["top.bus[0]", "top.bus[7:0]"]
    assert all(row["parent_bus"] == "top.bus" for row in rows)


def test_driver_hint_requires_incoming_edge():
    payload = bit_hint_payload(_graph(), "top.bus", "drivers")
    assert payload["has_bit_select_drivers"] is True
    assert len(payload["bit_nodes"]) == 2


def test_load_hint_requires_outgoing_edge():
    payload = bit_hint_payload(_graph(), "top.bus", "loads")
    assert payload["has_bit_select_loads"] is False
    assert len(payload["bit_nodes"]) == 2


def test_no_bit_children_keeps_defaults():
    payload = bit_hint_payload(_graph(), "top.busx", "drivers")
    assert payload == {"has_bit_select_drivers": False}
