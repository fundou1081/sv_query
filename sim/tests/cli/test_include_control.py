"""[iter_331 / PLAN P35.1] include_control 不再崩溃：显式 unsupported。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "struct.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def test_include_control_is_explicit_error():
    r = _run("trace", "fanout", "top.u.a", "-f", str(FIXTURE),
             "--include-control", "--json")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert d["errors"][0]["error_code"] == "E_INVALID_INPUT"
    assert "unsupported" in d["errors"][0]["error"].lower()
    assert d["result"]["signals"][0]["resolution"] == "exact"


def test_help_marks_unsupported():
    r = _run("trace", "fanout", "--help")
    assert r.returncode == 0
    assert "--include-control" in r.stdout
    assert "UNSUPPORTED" in r.stdout
