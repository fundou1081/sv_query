"""P182.2b — per-command result key schemas for 26 core standard cases."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_schema as schema_tool  # noqa: E402

from cli._registry import JSON_CONTRACT  # noqa: E402


def test_result_schema_uses_contract_required_keys():
    schema = schema_tool.result_key_schema("stats")
    assert set(schema["required"]) == set(
        JSON_CONTRACT["commands"]["stats"]["result_fields"]
    )
    assert schema["additionalProperties"] is True


def test_optional_result_fields_are_not_required():
    schema = schema_tool.result_key_schema("filelist prune")
    assert "output" not in schema["required"]
    assert "top" in schema["required"]
    covergroup = schema_tool.result_key_schema("trace covergroup")
    assert "links" not in covergroup["required"]
    assert "samples" not in covergroup["required"]


def test_result_payload_rejects_missing_and_non_object():
    problems = schema_tool.validate_result_payload("stats", {"total_nodes": 1})
    assert any("required" in p or "required property" in p for p in problems)
    assert schema_tool.validate_result_payload("stats", []) == [
        "result is list, expected object"
    ]


def test_schema_results_runs_all_manifest_cases():
    problems, total = schema_tool.run_schema_results()
    assert total == len(schema_tool.envelope.CORE_SUCCESS_MANIFEST)
    assert problems == []
