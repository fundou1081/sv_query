"""P186.1 — shadow-node measurement (no cleanup)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import measure_shadow_nodes as tool  # noqa: E402


def test_default_fixtures_are_real_and_measured():
    data = tool.collect()
    assert len(data["rows"]) == 5
    assert all("error" not in row for row in data["rows"])


def test_current_fixtures_have_zero_shadow_nodes():
    data = tool.collect()
    assert all(row["shadow_nodes"] == 0 for row in data["rows"])
    assert all(row["shadow_ratio"] == 0.0 for row in data["rows"])


def test_instance_prefixes_cover_top_and_children():
    ticker = tool.UnifiedTracer(
        filelist="sim/tests/fixtures/minimal_3module/filelist.f",
        log_level="ERROR",
    )
    graph = ticker.build_graph()
    prefixes = tool.instance_prefixes(ticker)
    assert "top_minimal" in prefixes
    shadow, constants = tool.classify_shadow(ticker, graph)
    assert shadow == []
    assert isinstance(constants, list)


def test_synthetic_definition_node_is_classified_shadow():
    from sv_query.trace.core.graph.models import NodeKind, SignalGraph, TraceNode

    class FakeTracer:
        def list_top_modules(self):
            return ["top"]

        def get_instances(self):
            return []

    graph = SignalGraph()
    graph.add_trace_node(TraceNode(
        id="top.a", name="a", module="top", kind=NodeKind.PORT_IN, width=(0, 0),
    ))
    graph.add_trace_node(TraceNode(
        id="definition.a", name="a", module="definition",
        kind=NodeKind.PORT_IN, width=(0, 0),
    ))
    shadow, constants = tool.classify_shadow(FakeTracer(), graph)
    assert shadow == ["definition.a"]
    assert constants == []


def test_json_shape_is_stable():
    data = tool.collect(("sim/tests/fixtures/scheduler_minimal/filelist.f",))
    assert data["rows"][0]["shadow_nodes"] == 0
    assert data["rows"][0]["shadow_by_module"] == {}
    assert data["rows"][0]["shadow_zero"] is True
