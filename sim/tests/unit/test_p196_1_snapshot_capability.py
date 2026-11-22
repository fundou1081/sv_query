"""P196.1 — a legacy snapshot without MIG must fail explicitly, not empty the graph."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sv_query.graph_session import GraphSession  # noqa: E402
from sv_query.trace.core.snapshot_manager import SnapshotManager  # noqa: E402
from sv_query.trace.unified_tracer import SnapshotCapabilityError, UnifiedTracer  # noqa: E402

FL = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _legacy_snapshot(tmp_path, monkeypatch) -> GraphSession:
    snaps = tmp_path / "snaps"
    monkeypatch.setenv("SVQ_SNAPSHOT_DIR", str(snaps))
    source = GraphSession(filelist=FL)
    SnapshotManager(base_dir=str(snaps)).save("legacy", source.graph.to_dict())
    return GraphSession(from_snapshot="legacy")


def test_legacy_snapshot_reports_graph_only_and_keeps_graph(tmp_path, monkeypatch):
    legacy = _legacy_snapshot(tmp_path, monkeypatch)
    assert legacy.cache_info()["capabilities"] == ["graph"]
    before = legacy.graph_nodes()["total"]
    with pytest.raises(SnapshotCapabilityError, match="mig"):
        legacy.loads("Scheduler_minimal.s0_reg", depth=1)
    assert legacy.graph_nodes()["total"] == before
    with pytest.raises(SnapshotCapabilityError, match="mig"):
        legacy.drivers("Scheduler_minimal.s0_reg", depth=1)
    assert legacy.graph_nodes()["total"] == before


@pytest.mark.parametrize("op", ["drivers", "loads", "paths", "dataflow"])
def test_all_mig_ops_reject_legacy_snapshot(op, tmp_path, monkeypatch):
    legacy = _legacy_snapshot(tmp_path, monkeypatch)
    before = legacy.graph_nodes()["total"]
    def call():
        if op in ("drivers", "loads"):
            return getattr(legacy, op)("Scheduler_minimal.s0_reg", depth=1)
        return getattr(legacy, op)(
            "Scheduler_minimal.clk", "Scheduler_minimal.s0_reg")

    with pytest.raises(SnapshotCapabilityError, match="mig"):
        call()
    assert legacy.graph_nodes()["total"] == before


def test_unified_tracer_guard_does_not_empty_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("SVQ_SNAPSHOT_DIR", str(tmp_path / "snaps"))
    source = GraphSession(filelist=FL)
    snap = source.graph.to_dict()
    tracer = UnifiedTracer(sources={}, log_level="ERROR")
    tracer.load_snapshot(snap)
    before = tracer.get_graph().nodes()
    with pytest.raises(SnapshotCapabilityError, match="mig"):
        tracer.build_graph(required_capabilities={"graph", "mig"})
    assert tracer.get_graph().nodes() == before


def test_mig_capability_is_not_lost_on_a_normal_build(tmp_path, monkeypatch):
    from sv_query.trace.unified_tracer import UnifiedTracer

    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "cache"))
    tracer = UnifiedTracer(filelist=FL, log_level="ERROR")
    tracer.build_graph(use_cache=True, required_capabilities={"graph", "mig"})
    assert tracer.get_built_capabilities() >= {"graph", "mig"}
    assert tracer.get_module_graph() is not None


def test_snapshot_with_mig_allows_mig_queries(tmp_path, monkeypatch):
    snaps = tmp_path / "snaps"
    monkeypatch.setenv("SVQ_SNAPSHOT_DIR", str(snaps))
    source = GraphSession(filelist=FL)
    data = source.graph.to_dict()
    mig = source.tracer.get_module_graph()
    assert mig is not None
    data["module_graph"] = mig.to_dict()
    SnapshotManager(base_dir=str(snaps)).save("full", data)

    hydrated = GraphSession(from_snapshot="full")
    assert "mig" in hydrated.cache_info()["capabilities"]
    assert hydrated.drivers("Scheduler_minimal.s0_reg", depth=1)["count"] > 0
