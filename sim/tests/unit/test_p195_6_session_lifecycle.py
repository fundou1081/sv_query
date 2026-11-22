"""P195.6 — GraphSession/stdio lifecycle and cleanup."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def test_context_manager_closes_and_close_is_idempotent(tmp_path, monkeypatch):
    from sv_query.graph_session import GraphSession

    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path))
    with GraphSession(filelist=FIXTURE) as gs:
        assert gs.graph_nodes()["total"] > 0
    with pytest.raises(RuntimeError, match="closed"):
        _ = gs.graph
    with pytest.raises(RuntimeError, match="closed"):
        gs.graph_nodes()
    gs.close()  # idempotent


def test_refresh_increments_generation_and_old_graph_is_not_mutated(tmp_path, monkeypatch):
    from sv_query.graph_session import GraphSession

    src = tmp_path / "m.sv"
    src.write_text("module m; logic a; endmodule\n")
    fl = tmp_path / "m.f"
    fl.write_text(f"{src}\n")
    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "cache"))
    gs = GraphSession(filelist=str(fl))
    old_graph = gs.graph
    old_nodes = set(old_graph.nodes())
    src.write_text("module m; logic a; logic b; assign b = a; endmodule\n")
    assert gs.refresh() is True
    assert gs.generation == 1
    assert gs.graph is not old_graph
    assert set(old_graph.nodes()) == old_nodes  # old references are immutable, not mutated
    assert gs.refresh() is False
    assert gs.generation == 1
    gs.close()


def test_serve_survives_broken_pipe(monkeypatch, tmp_path):
    from sv_query.cli.core.locate import session_cmd

    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path))
    calls = {"n": 0}

    def _broken_print(*args, **kwargs):
        calls["n"] += 1
        raise BrokenPipeError

    # Feed exactly one request through a fake stdin, then a broken stdout writer.
    import io
    monkeypatch.setattr(session_cmd.sys, "stdin", io.StringIO('{"op":"version"}\n'))
    monkeypatch.setattr("builtins.print", _broken_print)
    session_cmd._serve(filelist=FIXTURE, from_snapshot=None, file=None)
    assert calls["n"] >= 1
