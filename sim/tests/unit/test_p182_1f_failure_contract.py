"""P182.1f — strict failure contract matrix + 4-command hybrid allowlist."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_contract as envelope_tool  # noqa: E402
from check_envelope_contract import CaseRun, FailureCase  # noqa: E402

HYBRID_ALLOWLIST = ("drivers", "loads", "trace evidence", "trace profile")
_SUBCOMMAND_ROOTS = ("trace", "graph", "controlflow", "dataflow", "verify", "filelist")


def _run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
    )


def _json_run(rc: int, payload: dict) -> CaseRun:
    return CaseRun(rc, json.dumps(payload), "")


def _case_label(argv: tuple[str, ...]) -> str:
    if argv[:1] and argv[0] in _SUBCOMMAND_ROOTS:
        return " ".join(argv[:2])
    return argv[0]


def _hybrid_run() -> CaseRun:
    return _json_run(0, {
        "ok": False,
        "errors": [{"signal": "NoSuchSignal", "error_code": "E_SIGNAL_NOT_FOUND"}],
    })


def _strict_run() -> CaseRun:
    # No error_code on purpose: the strict rule asserts only rc and ok.
    return _json_run(1, {"ok": False, "error": "operational failure"})


def _contract_runner(argv: tuple[str, ...],
                     _env: dict[str, str] | None = None) -> CaseRun:
    if _case_label(argv) in HYBRID_ALLOWLIST:
        return _hybrid_run()
    return _strict_run()


def _mutating_runner(mutate):
    def runner(argv: tuple[str, ...],
               _env: dict[str, str] | None = None) -> CaseRun:
        run = _contract_runner(argv)
        label = _case_label(argv)
        replacement = mutate(label, run)
        return run if replacement is None else replacement
    return runner


def _outcome(outcomes: list, label: str):
    return next(outcome for outcome in outcomes if outcome.label == label)


def test_failure_manifest_is_one_entry_per_core_standard_command():
    assert len(envelope_tool.CORE_FAILURE_MANIFEST) == 26
    assert envelope_tool.failure_contract_manifest_problems() == []
    names = [case.command for case in envelope_tool.CORE_FAILURE_MANIFEST]
    success_names = [case.command for case in envelope_tool.CORE_SUCCESS_MANIFEST]
    assert names == success_names
    assert names == envelope_tool.core_standard_commands()
    assert len(set(names)) == 26


def test_hybrid_allowlist_is_exactly_the_four_known_commands():
    assert envelope_tool.HYBRID_ALLOWLIST == HYBRID_ALLOWLIST
    manifest_names = {case.command for case in envelope_tool.CORE_FAILURE_MANIFEST}
    assert set(HYBRID_ALLOWLIST) <= manifest_names
    assert len(envelope_tool.HYBRID_ALLOWLIST) == 4


def test_matrix_failure_passes_all_26_with_contract_conforming_runner(capsys):
    outcomes = envelope_tool.run_matrix_failure(_contract_runner, env={})
    assert all(outcome.passed for outcome in outcomes)
    assert envelope_tool.render_matrix_failure(outcomes, []) is True
    out = capsys.readouterr().out
    assert "matrix-failure: PASS (26/26)" in out
    assert not any(line.startswith("FAIL\t") for line in out.splitlines())


def test_injected_operational_rc0_fails(capsys):
    def mutate(label: str, _run: CaseRun) -> CaseRun | None:
        if label == "stats":
            return _json_run(0, {"ok": False, "error": "operational failure"})
        return None

    outcomes = envelope_tool.run_matrix_failure(_mutating_runner(mutate), env={})
    stats = _outcome(outcomes, "stats")
    assert stats.passed is False
    assert "rc=0, expected 1" in stats.problems
    assert envelope_tool.render_matrix_failure(outcomes, []) is False
    out = capsys.readouterr().out
    assert "FAIL\tstats\tstrict\trc=0" in out
    assert "matrix-failure: FAIL (25/26)" in out


def test_injected_hybrid_rc1_fails(capsys):
    def mutate(label: str, _run: CaseRun) -> CaseRun | None:
        if label == "drivers":
            return _json_run(1, {
                "ok": False,
                "errors": [{"error_code": "E_SIGNAL_NOT_FOUND"}],
            })
        return None

    outcomes = envelope_tool.run_matrix_failure(_mutating_runner(mutate), env={})
    drivers = _outcome(outcomes, "drivers")
    assert drivers.passed is False
    assert "rc=1, expected 0" in drivers.problems
    assert envelope_tool.render_matrix_failure(outcomes, []) is False
    out = capsys.readouterr().out
    assert "FAIL\tdrivers\thybrid\trc=1" in out


def test_injected_hybrid_missing_error_code_fails(capsys):
    def mutate(label: str, _run: CaseRun) -> CaseRun | None:
        if label == "loads":
            return _json_run(0, {"ok": False, "errors": [{"error": "not found"}]})
        return None

    outcomes = envelope_tool.run_matrix_failure(_mutating_runner(mutate), env={})
    loads = _outcome(outcomes, "loads")
    assert loads.passed is False
    assert any("errors[0].error_code" in problem for problem in loads.problems)
    assert envelope_tool.render_matrix_failure(outcomes, []) is False


def test_hybrid_requires_non_empty_errors_and_exact_code():
    empty = CaseRun(0, json.dumps({"ok": False, "errors": []}), "")
    assert any("non-empty" in problem
               for problem in envelope_tool.hybrid_failure_violations(empty))

    wrong = CaseRun(0, json.dumps({
        "ok": False, "errors": [{"error_code": "E_OTHER"}],
    }), "")
    assert any("E_SIGNAL_NOT_FOUND" in problem
               for problem in envelope_tool.hybrid_failure_violations(wrong))

    missing_ok = CaseRun(0, json.dumps({
        "errors": [{"error_code": "E_SIGNAL_NOT_FOUND"}],
    }), "")
    assert any("ok=None" in problem
               for problem in envelope_tool.hybrid_failure_violations(missing_ok))


def test_no_failure_input_is_a_visible_failure_not_a_skip(capsys):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("NO_FAILURE_INPUT must not execute a command")

    outcome = envelope_tool._run_failure_contract_case(
        FailureCase("synthetic", (), None, "no legitimate failure input"),
        forbidden, {},
    )
    assert outcome.kind == "no_failure_input"
    assert outcome.passed is False
    assert any("no legitimate failure input" in problem
               for problem in outcome.problems)

    assert envelope_tool.render_matrix_failure([outcome], []) is False
    out = capsys.readouterr().out
    assert "NO_FAILURE_INPUT\tsynthetic" in out
    assert "matrix-failure: FAIL" in out


def test_current_tree_failure_contract_passes_26_of_26():
    proc = _run_tool("--matrix-failure")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert not any(line.startswith("FAIL\t") for line in lines)
    assert sum(1 for line in lines if line.startswith("PASS\t")) == 26
    assert lines[-1] == "matrix-failure: PASS (26/26)"
