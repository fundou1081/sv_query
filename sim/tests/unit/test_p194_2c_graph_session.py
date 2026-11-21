"""P194.2c — local GraphSession and stdio graph server."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def test_graph_session_reuses_one_graph(tmp_path, monkeypatch):
    from sv_query.graph_session import GraphSession
    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path))
    gs = GraphSession(filelist=FIXTURE)
    graph = gs.graph
    nodes = gs.graph_nodes(match="s0_reg")
    edges = gs.graph_edges()
    assert gs.graph is graph
    assert nodes["total"] >= 1
    assert edges["total"] > 0
    assert gs.cache_info()["status"] in ("miss", "hit")


def test_stdio_graph_server_handles_multiple_requests(tmp_path, monkeypatch):
    env = dict(os.environ, SVQ_CACHE_DIR=str(tmp_path))
    proc = subprocess.Popen(
        [sys.executable, "run_cli.py", "session", "--serve", "--filelist", FIXTURE],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=env,
    )
    stdout, stderr = proc.communicate(
        '{"op":"graph_nodes","match":"s0_reg"}\n{"op":"graph_edges"}\n',
        timeout=120,
    )
    assert proc.returncode == 0, stderr[-400:]
    lines = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    assert [line["op"] for line in lines] == ["graph_nodes", "graph_edges"]
    assert all(line["ok"] is True for line in lines)
    assert lines[0]["result"]["total"] >= 1
    assert lines[1]["result"]["total"] > 0


def test_graph_session_can_hydrate_snapshot(tmp_path, monkeypatch):
    from sv_query.graph_session import GraphSession
    from sv_query.trace.core.snapshot_manager import SnapshotManager
    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SVQ_SNAPSHOT_DIR", str(tmp_path / "snap"))
    gs = GraphSession(filelist=FIXTURE)
    SnapshotManager(base_dir=str(tmp_path / "snap")).save(
        "session", gs.graph.to_dict(), files=[FIXTURE],
    )
    hydrated = GraphSession(from_snapshot="session")
    assert hydrated.cache_info()["status"] == "snapshot"
    assert hydrated.graph_nodes()["total"] == gs.graph_nodes()["total"]
