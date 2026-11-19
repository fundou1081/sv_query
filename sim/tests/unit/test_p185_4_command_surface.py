"""P185.4 — command-surface ratchet."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_command_surface as tool  # noqa: E402


def test_current_baseline_matches_surface():
    actual = tool.collect()
    expected = tool.json.loads(tool.BASELINE.read_text(encoding="utf-8"))
    assert tool.compare(expected, actual) == []


def test_new_canonical_command_is_rejected():
    actual = tool.collect()
    expected = tool.json.loads(tool.BASELINE.read_text(encoding="utf-8"))
    actual["canonical"] = actual["canonical"] + ["new command"]
    actual["counts"]["canonical"] += 1
    problems = tool.compare(expected, actual)
    assert any("canonical added" in p for p in problems)


def test_command_metadata_or_hidden_drift_is_rejected():
    actual = tool.collect()
    expected = tool.json.loads(tool.BASELINE.read_text(encoding="utf-8"))
    actual["by_command"]["drivers"]["envelope"] = "direct"
    actual["hidden"] = actual["hidden"] + ["new-hidden"]
    problems = tool.compare(expected, actual)
    assert any("command metadata changed for drivers" in p for p in problems)
    assert any("hidden added" in p for p in problems)


def test_alias_or_visibility_drift_is_rejected():
    actual = tool.collect()
    expected = tool.json.loads(tool.BASELINE.read_text(encoding="utf-8"))
    actual["aliases"] = dict(actual["aliases"])
    actual["aliases"]["new-alias"] = "drivers"
    actual["default_visible"] = actual["default_visible"][:-1]
    problems = tool.compare(expected, actual)
    assert any("aliases changed" in p for p in problems)
    assert any("default_visible removed" in p for p in problems)


def test_gate_passes_and_missing_baseline_fails(tmp_path, monkeypatch):
    assert tool.main(["--check"]) == 0
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(tool, "BASELINE", missing)
    assert tool.main(["--check"]) == 1
