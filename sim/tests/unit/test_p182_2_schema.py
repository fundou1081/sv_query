"""P182.2 — executable top-level schema for the 26 core standard successes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_schema as schema_tool  # noqa: E402


def test_schema_requires_standard_keys_and_true_ok():
    schema = schema_tool.standard_success_schema()
    assert set(schema["required"]) == {"ok", "command", "params", "result", "errors"}
    assert schema["properties"]["ok"] == {"const": True}
    assert schema["properties"]["errors"]["maxItems"] == 0


def test_valid_payload_passes_and_missing_error_fails():
    assert schema_tool.validate_success_payload({
        "ok": True, "command": "stats", "params": {}, "result": {}, "errors": [],
    }) == []
    problems = schema_tool.validate_success_payload({
        "ok": True, "command": "stats", "params": {}, "result": {},
    })
    assert any("errors" in p for p in problems)
    assert schema_tool.validate_success_payload({
        "ok": True, "command": "stats", "params": {}, "result": {},
        "errors": ["bad"],
    }) != []


def test_schema_core_runs_all_26_cases():
    problems, total = schema_tool.run_schema_core()
    assert total == len(schema_tool.envelope.CORE_SUCCESS_MANIFEST)
    assert problems == []
