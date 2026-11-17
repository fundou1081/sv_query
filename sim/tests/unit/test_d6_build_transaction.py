"""D6 — build_graph must not expose a half-built graph after a step failure."""
from __future__ import annotations

import pytest

from sv_query.trace.unified_tracer import UnifiedTracer

SRC = "module top(input a, output y); assign y = a; endmodule\n"


def _tracer() -> UnifiedTracer:
    return UnifiedTracer(sources={"t.sv": SRC}, log_level="ERROR")


def test_success_sets_ready_phase():
    tracer = _tracer()
    assert tracer.build_phase == "empty"
    graph = tracer.build_graph()
    assert graph is not None
    assert tracer.build_phase == "ready"
    assert tracer.build_error is None


def test_failed_step_clears_graph_and_allows_retry(monkeypatch):
    tracer = _tracer()

    def boom(_ctx):
        raise RuntimeError("injected build failure")

    monkeypatch.setattr(tracer, "_step_backfill", boom)
    with pytest.raises(RuntimeError, match="injected build failure"):
        tracer.build_graph()

    assert tracer.build_phase == "failed"
    assert tracer.get_graph() is None
    assert isinstance(tracer.build_error, RuntimeError)
    # no half-built tracers/MIG/path resolver are queryable
    assert tracer._signal_tracer is None
    assert tracer._module_graph is None
    assert tracer._path_resolver is None

    monkeypatch.undo()
    graph = tracer.build_graph()
    assert graph is not None
    assert tracer.build_phase == "ready"
    assert tracer.build_error is None


def test_keyboard_interrupt_clears_half_build(monkeypatch):
    tracer = _tracer()

    def interrupt(_ctx):
        raise KeyboardInterrupt()

    monkeypatch.setattr(tracer, "_step_backfill", interrupt)
    with pytest.raises(KeyboardInterrupt):
        tracer.build_graph()
    assert tracer.build_phase == "failed"
    assert tracer.get_graph() is None

    monkeypatch.undo()
    assert tracer.build_graph() is not None
    assert tracer.build_phase == "ready"


def test_cache_write_failure_does_not_destroy_successful_build(monkeypatch):
    import sv_query.trace.core.cache as cache_module

    class FailingCache:
        def compute_sources_hash(self, sources):
            return "fake-hash"

        def compute_project_key(self, **kwargs):
            return "fake-project"

        def get_by_key(self, *args, **kwargs):
            return None

        def put_by_key(self, *args, **kwargs):
            raise RuntimeError("cache write failed")

    monkeypatch.setattr(cache_module, "get_cache", lambda: FailingCache())
    tracer = _tracer()
    graph = tracer.build_graph(use_cache=True)
    assert graph is not None
    assert tracer.build_phase == "ready"
    assert tracer.get_graph() is not None
