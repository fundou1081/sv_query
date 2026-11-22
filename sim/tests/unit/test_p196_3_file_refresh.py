"""P196.3 — file-mode GraphSession.refresh re-reads disk content."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sv_query.graph_session import GraphSession  # noqa: E402


def _session(tmp_path, monkeypatch) -> tuple[GraphSession, Path]:
    src = tmp_path / "m.sv"
    src.write_text("module m; logic a; endmodule\n")
    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "cache"))
    return GraphSession(file=str(src)), src


def test_file_refresh_detects_disk_change(tmp_path, monkeypatch):
    gs, src = _session(tmp_path, monkeypatch)
    assert [n["id"] for n in gs.graph_nodes()["nodes"]] == ["m.a"]
    src.write_text("module m; logic a; logic b; assign b = a; endmodule\n")
    assert gs.refresh() is True
    assert gs.generation == 1
    assert {n["id"] for n in gs.graph_nodes()["nodes"]} >= {"m.a", "m.b"}
    assert gs.refresh() is False
    gs.close()


def test_file_refresh_surfaces_missing_file(tmp_path, monkeypatch):
    gs, src = _session(tmp_path, monkeypatch)
    src.unlink()
    with pytest.raises(FileNotFoundError):
        gs.refresh()
    gs.close()
