"""P182.1b — canary envelope gate (6 success + 1 failure on scheduler_minimal)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_contract as envelope_tool  # noqa: E402
from check_envelope_contract import CaseRun  # noqa: E402


def _valid_envelope(command: str) -> CaseRun:
    payload = {
        "ok": True,
        "command": command,
        "params": {},
        "result": {},
        "errors": [],
    }
    return CaseRun(0, json.dumps(payload), "")


def _fake_runner(argv: tuple[str, ...]) -> CaseRun:
    if "--file" in argv:
        payload = {"ok": False, "command": "stats", "error_code": "E_FILE_NOT_FOUND"}
        return CaseRun(1, json.dumps(payload), "")
    return _valid_envelope(argv[0])


def _run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )


def test_canary_passes_on_current_tree():
    proc = _run_tool("--canary")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert sum(1 for line in lines if line.startswith("PASS\t")) == 7
    assert not any(line.startswith("FAIL") for line in lines)
    assert "canary: PASS (7/7)" in lines[-1]


def test_canary_fails_when_injected_success_envelope_missing_errors(capsys):
    def broken_runner(argv: tuple[str, ...]) -> CaseRun:
        run = _fake_runner(argv)
        if argv[:2] == ("graph", "edges"):
            payload = json.loads(run.stdout)
            del payload["errors"]
            return CaseRun(run.rc, json.dumps(payload), "")
        return run

    outcomes = envelope_tool.run_canary(broken_runner)
    bad = next(o for o in outcomes if o.label == "graph edges")
    assert bad.passed is False
    assert "missing keys: errors" in bad.problems
    assert envelope_tool.render_canary(outcomes) is False
    out = capsys.readouterr().out
    assert "FAIL\tgraph edges\trc=0" in out
    assert "canary: FAIL (6/7)" in out


def test_canary_fails_when_failure_case_returns_success():
    def broken_runner(argv: tuple[str, ...]) -> CaseRun:
        if "--file" in argv:
            return _valid_envelope("stats")
        return _fake_runner(argv)

    outcomes = envelope_tool.run_canary(broken_runner)
    bad = next(o for o in outcomes if o.label == "stats missing file")
    assert bad.passed is False
    assert bad.rc == 0
    assert "rc=0, expected 1" in bad.problems
    assert "ok=True, expected false" in bad.problems


def test_inventory_never_executes_a_command(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("--inventory must not spawn a command")

    monkeypatch.setattr(envelope_tool.subprocess, "run", forbidden)
    assert envelope_tool.main(["--inventory", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mode"] == "read-only-static"
