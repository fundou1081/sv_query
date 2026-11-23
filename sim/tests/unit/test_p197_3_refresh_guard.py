"""P197.3 — unreadable refresh and load_graph capability guard are explicit."""
from __future__ import annotations

import pytest

from sv_query.graph_session import GraphSession
from sv_query.trace.core.graph.models import SignalGraph
from sv_query.trace.unified_tracer import SnapshotCapabilityError, UnifiedTracer


def test_filelist_refresh_raises_when_closure_is_missing(tmp_path):
    src = tmp_path / "m.sv"
    src.write_text("module m(input logic a, output logic y); assign y = a; endmodule\n")
    fl = tmp_path / "proj.f"
    fl.write_text(str(src) + "\n")
    gs = GraphSession(filelist=str(fl))
    assert gs.generation == 0
    src.unlink()
    with pytest.raises(RuntimeError, match="cannot compute build identity"):
        gs.refresh()
    assert gs.generation == 0
    assert gs.graph is not None


def test_load_graph_requires_capabilities_instead_of_rebuilding_empty():
    tracer = UnifiedTracer(sources={}, log_level="ERROR")
    graph = SignalGraph()
    tracer.load_graph(graph)
    assert tracer.build_graph(required_capabilities={"graph"}) is graph
    with pytest.raises(SnapshotCapabilityError):
        tracer.build_graph(required_capabilities={"graph", "mig"})


def test_load_graph_with_sources_can_rebuild_mig(tmp_path):
    src = tmp_path / "m.sv"
    src.write_text("module m(input logic a, output logic y); assign y = a; endmodule\n")
    tracer = UnifiedTracer(sources={str(src): src.read_text()}, log_level="ERROR")
    loaded = SignalGraph()
    tracer.load_graph(loaded)
    rebuilt = tracer.build_graph(required_capabilities={"graph", "mig"})
    assert rebuilt is not loaded
    assert tracer.get_module_graph() is not None
