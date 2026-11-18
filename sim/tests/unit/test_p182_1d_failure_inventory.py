"""P182.1d — core standard failure inventory (observation only, non-gating)."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_contract as envelope_tool  # noqa: E402
from check_envelope_contract import (  # noqa: E402
    CaseRun,
    FailureCase,
    failure_manifest_problems,
    observe_failure,
)


def _run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
    )


def _json_run(rc: int, payload: dict) -> CaseRun:
    return CaseRun(rc, json.dumps(payload), "")


def _fake_runner(argv: tuple[str, ...],
                 _env: dict[str, str] | None = None) -> CaseRun:
    if argv[:1] == ("drivers",):
        return _json_run(0, {"ok": False, "errors": [{"signal": "x"}]})
    if argv[:1] == ("stats",):
        return _json_run(1, {
            "ok": False, "error": "missing", "error_code": "E_FILE_NOT_FOUND",
        })
    return _json_run(1, {"ok": False, "error": "bad", "errors": ["bad"]})


def test_failure_manifest_is_one_entry_per_core_standard_command():
    assert len(envelope_tool.CORE_FAILURE_MANIFEST) == 26
    assert failure_manifest_problems() == []
    names = [case.command for case in envelope_tool.CORE_FAILURE_MANIFEST]
    success_names = [case.command for case in envelope_tool.CORE_SUCCESS_MANIFEST]
    assert names == success_names
    assert names == envelope_tool.core_standard_commands()
    assert len(set(names)) == 26


def test_manifest_fixtures_exist_and_are_referenced():
    covered = 0
    missing_input = 0
    for case in envelope_tool.CORE_FAILURE_MANIFEST:
        if case.no_failure_reason:
            missing_input += 1
            continue
        covered += 1
        assert case.argv, case.command
        if case.fixture is not None:
            assert (ROOT / case.fixture).is_file(), case.fixture
            assert case.fixture in case.argv, case.command
    assert covered + missing_input == 26


def test_observe_failure_extracts_rc_ok_and_classifies():
    business = observe_failure(
        _json_run(0, {"ok": False, "errors": [{"signal": "x"}]})
    )
    assert business.rc == 0
    assert business.stdout_json is True
    assert business.ok is False
    assert business.error_code is None
    assert business.errors_present is True
    assert business.errors_count == 1
    assert business.result_present is False
    assert business.classification == "business_ok_false"

    operational = observe_failure(_json_run(1, {
        "ok": False, "error": "missing", "error_code": "E_FILE_NOT_FOUND",
    }))
    assert operational.rc == 1
    assert operational.ok is False
    assert operational.error_code == "E_FILE_NOT_FOUND"
    assert operational.errors_present is False
    assert operational.errors_count is None
    assert operational.classification == "operational_error"

    usage = observe_failure(CaseRun(2, "", "usage"))
    assert usage.stdout_json is False
    assert usage.ok is None
    assert usage.classification == "usage_error_no_envelope"


def test_failure_inventory_extracts_rc_ok_from_fake_runner():
    data = envelope_tool.failure_inventory(_fake_runner, env={})
    assert data["summary"]["entries"] == 26
    assert data["summary"]["observed"] == 26
    rows = {row["command"]: row for row in data["rows"]}
    assert len(rows) == 26

    drivers = rows["drivers"]["observation"]
    assert drivers["rc"] == 0
    assert drivers["ok"] is False
    assert drivers["classification"] == "business_ok_false"

    stats = rows["stats"]["observation"]
    assert stats["rc"] == 1
    assert stats["error_code"] == "E_FILE_NOT_FOUND"
    assert stats["classification"] == "operational_error"

    assert data["summary"]["business_ok_false"] == 1
    assert data["summary"]["operational_error"] == 25


def test_no_failure_input_is_marked_without_inventing_input():
    def forbidden(*_args, **_kwargs):
        raise AssertionError("NO_FAILURE_INPUT must not execute a command")

    entry = envelope_tool._run_failure_case(
        FailureCase("synthetic", (), None, "no legitimate failure input"),
        forbidden, {},
    )
    assert entry.status == "no_failure_input"
    assert entry.observation is None
    assert entry.reason == "no legitimate failure input"


def test_current_tree_failure_inventory_is_stable_and_non_gating():
    first = _run_tool("--failure-inventory", "--json")
    second = _run_tool("--failure-inventory", "--json")
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    data = json.loads(first.stdout)
    assert data["inventory"] == "P182.1d"
    assert data["manifest_problems"] == []
    assert len(data["rows"]) == 26
    assert data["summary"]["entries"] == 26
    assert data["summary"]["observed"] + data["summary"]["no_failure_input"] == 26
    assert data["rows"] == json.loads(second.stdout)["rows"]


def test_failure_inventory_does_not_mutate_cli_registry(monkeypatch, capsys):
    commands_before = copy.deepcopy([
        (c.key, c.layer, c.envelope, c.listed) for c in envelope_tool.COMMANDS
    ])
    contract_before = copy.deepcopy(envelope_tool.JSON_CONTRACT)
    monkeypatch.setattr(envelope_tool, "run_cli_case_with_env", _fake_runner)

    assert envelope_tool.main(["--failure-inventory", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["rows"]) == 26
    assert [
        (c.key, c.layer, c.envelope, c.listed) for c in envelope_tool.COMMANDS
    ] == commands_before
    assert envelope_tool.JSON_CONTRACT == contract_before
