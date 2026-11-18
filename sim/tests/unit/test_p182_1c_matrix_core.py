"""P182.1c — core standard success matrix (26) envelope gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_contract as envelope_tool  # noqa: E402
from check_envelope_contract import CaseRun  # noqa: E402

# Current-tree blockers: both run with rc=0 but do not emit the standard
# envelope. They are asserted explicitly so the gap cannot be silently
# whitewashed; when P182.1d/P182.1e rules on them, update this set.

def _valid_envelope(command: str) -> CaseRun:
    payload = {
        "ok": True,
        "command": command,
        "params": {},
        "result": {},
        "errors": [],
    }
    return CaseRun(0, json.dumps(payload), "")


def _fake_runner(argv: tuple[str, ...],
                 _env: dict[str, str] | None = None) -> CaseRun:
    return _valid_envelope(argv[0])


def _run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
    )


def test_manifest_is_26_and_matches_registry():
    assert len(envelope_tool.CORE_SUCCESS_MANIFEST) == 26
    assert envelope_tool.matrix_manifest_problems() == []
    names = [case.command for case in envelope_tool.CORE_SUCCESS_MANIFEST]
    assert names == envelope_tool.core_standard_commands()


def test_manifest_uses_existing_fixtures_and_references_them():
    for case in envelope_tool.CORE_SUCCESS_MANIFEST:
        assert case.uncovered_reason is None
        assert (ROOT / case.fixture).is_file(), case.fixture
        assert case.fixture in case.argv, case.command
        for support in case.support_fixtures:
            assert (ROOT / support).is_file(), support


def test_matrix_core_passes_all_26_with_valid_envelopes(capsys):
    outcomes = envelope_tool.run_matrix_core(_fake_runner, env={})
    assert all(outcome.kind == "success" and outcome.passed
               for outcome in outcomes)
    assert envelope_tool.render_matrix_core(outcomes, []) is True
    out = capsys.readouterr().out
    assert "matrix-core: PASS (26/26)" in out
    assert "FAIL" not in out


def test_matrix_core_injected_bad_case_fails(capsys):
    def broken_runner(argv: tuple[str, ...],
                      env: dict[str, str] | None = None) -> CaseRun:
        run = _fake_runner(argv, env)
        if argv[:2] == ("graph", "edges"):
            payload = json.loads(run.stdout)
            del payload["errors"]
            return CaseRun(run.rc, json.dumps(payload), "")
        return run

    outcomes = envelope_tool.run_matrix_core(broken_runner, env={})
    bad = next(o for o in outcomes if o.label == "graph edges")
    assert bad.passed is False
    assert any(p.startswith("errors=") for p in bad.problems)
    assert envelope_tool.render_matrix_core(outcomes, []) is False
    out = capsys.readouterr().out
    assert "FAIL\tgraph edges\trc=0" in out
    assert "matrix-core: FAIL (25/26, 1 blocked)" in out


def test_matrix_core_current_tree_passes():
    proc = _run_tool("--matrix-core")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert not any(line.startswith("FAIL\t") for line in lines)
    assert sum(1 for line in lines if line.startswith("PASS\t")) == 26
    assert "matrix-core: PASS (26/26)" in lines[-1]
