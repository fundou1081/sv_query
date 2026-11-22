"""P196.2 — every stdio error path uses the published Session failure envelope."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _serve(*, filelist=FIXTURE, stdin: str = "") -> list[dict]:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "session", "--serve", "--filelist", filelist],
        cwd=ROOT, input=stdin, capture_output=True, text=True, timeout=120,
    )
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0:
        assert lines, proc.stderr[-400:]
    return lines


def test_parse_and_non_object_errors_are_structured():
    lines = _serve(stdin="not-json\n[1,2]\n")
    assert len(lines) == 2
    for line in lines:
        assert line["ok"] is False
        assert line["error_code"] == "E_INVALID_REQUEST"
        assert isinstance(line["error"], dict)
        assert line["error"]["type"] == "InvalidRequest"
        assert "message" in line["error"]


def test_startup_failure_is_structured():
    lines = _serve(filelist="/tmp/p1962_missing_filelist.f")
    assert len(lines) == 1
    line = lines[0]
    assert line["ok"] is False
    assert line["error_code"] == "E_INVALID_REQUEST"
    assert line["error"]["type"] == "InvalidRequest"


def test_refresh_failure_preserves_op_and_request_id(monkeypatch, tmp_path, capsys):
    from sv_query.cli.core.locate import session_cmd
    from sv_query.graph_session import GraphSession

    def _boom(self):
        raise RuntimeError("source vanished")

    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(GraphSession, "refresh", _boom)
    monkeypatch.setattr(session_cmd.sys, "stdin", io.StringIO(
        '{"op":"graph_nodes","request_id":"r1"}\n'))
    session_cmd._serve(filelist=FIXTURE, from_snapshot=None, file=None)
    response = json.loads(capsys.readouterr().out.strip())
    assert response["ok"] is False
    assert response["op"] == "graph_nodes"
    assert response["request_id"] == "r1"
    assert response["error_code"] == "E_HANDLER_FAILED"
    assert response["error"]["type"] == "HandlerFailed"
