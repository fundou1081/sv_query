"""P182.3 — stats success completeness + structured elaboration failure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_stats_completeness as stats_check  # noqa: E402


def test_success_stats_has_empty_elaboration_errors():
    proc = stats_check._run_stats("--filelist", stats_check.FIXTURE)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["result"]["elaboration_errors"] == []


def test_elaboration_failure_is_structured_json():
    problems = stats_check.check_elaboration_failure()
    assert problems == []


def test_filelist_failure_uses_the_shared_error_code():
    assert stats_check.check_filelist_failure() == []


def test_stats_completeness_gate_passes():
    assert stats_check.main() == 0
