"""D13 / P183.4 — single read-only Session runner."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import typer

from sv_query.cli._session_runner import SessionRenderOptions, emit_json_result, run_session

ROOT = Path(__file__).resolve().parents[3]


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        return self.response


def test_runner_calls_session_once_and_returns_result_copy():
    result = {"nodes": [1, 2]}
    session = FakeSession({"ok": True, "result": result})
    out = run_session(session, {"op": "x"}, SessionRenderOptions())
    assert out == result
    assert out is not result
    assert session.calls == [{"op": "x"}]


@pytest.mark.parametrize(
    "response",
    [None, [], {}, {"ok": "true", "result": {}}, {"ok": True}, {"ok": True, "result": []}],
)
def test_malformed_response_is_explicit_typeerror(response):
    with pytest.raises(TypeError):
        run_session(FakeSession(response), {"op": "x"}, SessionRenderOptions())


def test_failure_delegates_to_single_fail_adapter(capsys):
    session = FakeSession({
        "ok": False,
        "op": "capabilities",
        "error_code": "E_HANDLER_FAILED",
        "error": {"type": "HandlerFailed", "message": "provider boom"},
    })
    with pytest.raises(typer.Exit) as exc:
        run_session(
            session,
            {"op": "capabilities"},
            SessionRenderOptions(json_output=True, context="capabilities 查询失败"),
        )
    assert exc.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_HANDLER_FAILED"
    assert payload["error"] == "capabilities 查询失败: provider boom"


def test_emit_json_result_honours_pretty_flag(capsys):
    emit_json_result({"a": 1}, SessionRenderOptions(json_output=True, pretty=True))
    assert capsys.readouterr().out == '{\n  "a": 1\n}\n'


def test_capabilities_still_uses_runner_path_and_keeps_json_shape():
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "capabilities", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["schema_version"] == "1"
    assert data["counts"]["total"] > 0


def test_capabilities_calls_runner_once(monkeypatch, capsys):
    import sv_query.cli.core.locate.capabilities as mod

    calls = []

    def fake_runner(session, request, options):
        calls.append((request, options))
        return {"schema_version": "1", "counts": {"total": 0}, "layers": {}}

    monkeypatch.setattr(mod, "run_session", fake_runner)
    mod.capabilities(json_output=True, pretty=False, recommended=True, include_exp=False)
    assert len(calls) == 1
    request, options = calls[0]
    assert request == {"op": "capabilities", "recommended": True, "include_exp": False}
    assert options.json_output is True
    assert options.pretty is False
    assert json.loads(capsys.readouterr().out) == {
        "schema_version": "1", "counts": {"total": 0}, "layers": {},
    }
