"""P182.5 — snapshot/cache/session surface evaluation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import eval_p1825_snapshot_surface as ev  # noqa: E402


def test_snapshot_surface_counts_and_sets():
    data = ev.collect()
    assert data["listed"] == 45
    assert data["core"] == 39
    assert data["core_from_snapshot"] == [
        "connections", "dataflow analyze", "drivers", "hierarchy", "instances",
        "loads", "paths", "ports", "trace evidence", "trace frontier",
        "trace tb-join", "verify claim", "verify consistency",
    ]
    assert data["core_no_cache"] == ["drivers", "loads", "trace evidence"]
    assert len(data["core_without_snapshot"]) == 26
    assert "stats" in data["core_without_snapshot"]
    assert data["snapshot_commands"] == [
        "snapshot compare", "snapshot delete", "snapshot list", "snapshot save",
    ]


def test_session_has_only_version_builtin():
    from sv_query.session import _BUILTIN_OPS

    assert _BUILTIN_OPS == frozenset({"version"})


def test_cache_defaults_are_explicit():
    import inspect

    from sv_query.cli._common import _build_pruned_tracer, _build_tracer
    from sv_query.trace.unified_tracer import UnifiedTracer

    assert "use_cache" not in inspect.signature(_build_tracer).parameters
    assert inspect.signature(_build_pruned_tracer).parameters["use_cache"].default is True
    assert inspect.signature(UnifiedTracer.build_graph).parameters["use_cache"].default is False
