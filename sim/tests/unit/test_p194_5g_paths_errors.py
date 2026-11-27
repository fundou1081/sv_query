"""P194.5g — unknown paths endpoints are structured errors."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _fixture(tmp_path: Path) -> Path:
    sv = tmp_path / "paths.sv"
    sv.write_text(
        "module top(input logic a, output logic y);\n"
        "  assign y = a;\n"
        "endmodule\n")
    return sv


def test_session_paths_unknown_endpoint_is_structured(tmp_path):
    from sv_query.graph_session import GraphSession, SignalNotFoundError
    from sv_query.session import Session
    sv = _fixture(tmp_path)
    gs = GraphSession(file=str(sv), use_cache=False)
    try:
        try:
            gs.paths("top.missing", "top.y")
        except SignalNotFoundError as exc:
            assert exc.error_code == "E_SIGNAL_NOT_FOUND"
        else:
            raise AssertionError("expected SignalNotFoundError")
    finally:
        gs.close()
    response = Session(GraphSession(file=str(sv), use_cache=False).handlers()).execute(
        {"op": "paths", "src": "top.missing", "dst": "top.y"})
    assert response["ok"] is False
    assert response["error_code"] == "E_SIGNAL_NOT_FOUND"


def test_cli_paths_unknown_endpoint_code_matches(tmp_path):
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "paths", "top.missing", "top.y",
         "--file", str(_fixture(tmp_path)), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_SIGNAL_NOT_FOUND"


def test_out_of_vocabulary_handler_code_falls_back():
    from sv_query.session import E_HANDLER_FAILED, Session

    class Weird(Exception):
        error_code = "E_FROM_THE_FUTURE"

    def boom(request):
        raise Weird("boom")

    response = Session(handlers={"paths": boom}).execute({"op": "paths"})
    assert response["ok"] is False
    assert response["error_code"] == E_HANDLER_FAILED

