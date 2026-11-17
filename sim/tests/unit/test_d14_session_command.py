"""D14 / P183.4 — hidden generic `session --request` transport adapter."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


def test_session_version_json():
    proc = _run("session", "--request", '{"op": "version"}', "--json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {
        "schema_version": "1.0", "package_version": "0.3.0",
    }
    assert proc.stderr == ""


def test_session_capabilities_json_matches_direct_command():
    session = _run("session", "--request", '{"op": "capabilities"}', "--json")
    direct = _run("capabilities", "--json")
    assert session.returncode == direct.returncode == 0
    assert session.stdout == direct.stdout
    assert session.stderr == direct.stderr == ""


def test_session_invalid_json_is_structured():
    proc = _run("session", "--request", "{not-json", "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_INVALID_INPUT"
    assert "invalid --request JSON" in payload["error"]


def test_session_non_object_json_is_structured():
    proc = _run("session", "--request", "[]", "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_INVALID_REQUEST"


def test_session_unknown_op_uses_session_failure_mapping():
    proc = _run("session", "--request", '{"op": "does_not_exist"}', "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_UNSUPPORTED_OP"
    assert "does_not_exist" in payload["error"]


def test_session_is_hidden_but_callable():
    proc = _run("session", "--help")
    assert proc.returncode == 0
    assert "--request" in proc.stdout


def test_session_is_registered_but_not_in_capabilities():
    proc = _run("capabilities", "--json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    names = {c["name"] for c in data["commands"]}
    assert "session" not in names
    assert data["counts"]["total"] == 45


def test_session_non_object_error_message_is_explicit():
    proc = _run("session", "--request", "[]", "--json")
    payload = json.loads(proc.stdout)
    assert "root must be an object" in payload["error"]


def test_session_not_listed_in_root_help():
    proc = _run("--help")
    assert proc.returncode == 0
    assert "session" not in proc.stdout


def test_session_not_listed_even_with_include_exp():
    proc = _run("capabilities", "--json", "--include-exp")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "session" not in {c["name"] for c in data["commands"]}
    assert data["counts"]["total"] == 45


def test_session_capabilities_options_pass_through():
    session = _run(
        "session", "--request",
        '{"op":"capabilities","recommended":true}', "--json",
    )
    direct = _run("capabilities", "--json", "--recommended")
    assert session.returncode == direct.returncode == 0
    assert session.stdout == direct.stdout
