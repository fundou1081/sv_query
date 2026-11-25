"""P195.2 — graph-only cache must not satisfy MIG-dependent queries."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sv_query.trace.core.cache import ast_cache as ac  # noqa: E402
from sv_query.trace.unified_tracer import UnifiedTracer  # noqa: E402

FL = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _fresh_cache(tmp_path, monkeypatch):
    cache = ac.ASTCache(cache_dir=str(tmp_path))
    monkeypatch.setattr(ac, "_global_cache", cache)
    return cache


def test_graph_entry_carries_mig_and_satisfies_mig_required(tmp_path, monkeypatch):
    _fresh_cache(tmp_path, monkeypatch)
    first = UnifiedTracer(filelist=FL, log_level="ERROR")
    first.build_graph(use_cache=True, required_capabilities={"graph"})
    assert first.get_module_graph() is not None
    assert first.cache_info()["capabilities"] == ["graph", "mig"]

    # A later caller needing cross-module query capability can hydrate MIG.
    ac._global_cache = ac.ASTCache(cache_dir=str(tmp_path))
    needs_mig = UnifiedTracer(filelist=FL, log_level="ERROR")
    needs_mig.build_graph(
        use_cache=True, required_capabilities={"graph", "mig"})
    assert needs_mig.cache_info()["status"] == "hit"
    assert needs_mig.get_module_graph() is not None
    assert "mig" in needs_mig.cache_info()["capabilities"]


def test_graph_only_entry_still_hits_for_graph_only(tmp_path, monkeypatch):
    _fresh_cache(tmp_path, monkeypatch)
    first = UnifiedTracer(filelist=FL, log_level="ERROR")
    first.build_graph(use_cache=True, required_capabilities={"graph"})
    ac._global_cache = ac.ASTCache(cache_dir=str(tmp_path))
    second = UnifiedTracer(filelist=FL, log_level="ERROR")
    second.build_graph(use_cache=True, required_capabilities={"graph"})
    assert second.cache_info()["status"] == "hit"
    assert second.cache_info()["capabilities"] == ["graph", "mig"]
    # MIG is restored, so the graph+mig request is satisfied in place.
    second.build_graph(required_capabilities={"graph", "mig"})
    assert second.get_module_graph() is not None
    assert "mig" in second.cache_info()["capabilities"]


def test_graph_session_requires_mig_after_graph_cache(tmp_path, monkeypatch):
    _fresh_cache(tmp_path, monkeypatch)
    graph_only = UnifiedTracer(filelist=FL, log_level="ERROR")
    graph_only.build_graph(use_cache=True, required_capabilities={"graph"})
    ac._global_cache = ac.ASTCache(cache_dir=str(tmp_path))

    from sv_query.graph_session import GraphSession
    gs = GraphSession(filelist=FL)
    assert gs.tracer.get_module_graph() is not None
    assert gs.drivers("Scheduler_minimal.s0_reg", depth=1)["count"] > 0
