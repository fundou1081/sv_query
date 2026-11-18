"""P182.1e — static direct envelope contract (no CLI execution)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_contract as tool  # noqa: E402


def _run() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", "--direct-contract"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


def test_direct_contract_has_all_13_commands():
    rows = tool.direct_contract_rows()
    assert len(rows) == 13
    assert tool.direct_contract_problems() == []
    names = {row["name"] for row in rows}
    assert "paths" in names
    assert "snapshot list" in names


def test_snapshot_list_is_explicitly_list_or_object():
    rows = {row["name"]: row for row in tool.direct_contract_rows()}
    assert rows["snapshot list"]["root"] == "list_or_object"
    assert rows["capabilities"]["root"] == "object"
    assert rows["paths"]["contract"] is True


def test_direct_contract_passes_and_reports_count():
    proc = _run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "direct-contract: PASS (13/13)" in proc.stdout
    assert "snapshot list" in proc.stdout


def test_injected_registry_drift_fails(monkeypatch):
    real = tool.COMMANDS
    monkeypatch.setattr(tool, "COMMANDS", [c for c in real if c.key != "paths"])
    problems = tool.direct_contract_problems()
    assert any("missing direct contract rows" in p for p in problems)
