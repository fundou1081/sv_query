"""P182.2d — remaining 17 core standard result value types."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_schema as schema_tool  # noqa: E402


def test_all_26_core_standard_commands_have_type_schemas():
    expected = {
        case.command for case in schema_tool.envelope.CORE_SUCCESS_MANIFEST
    }
    assert expected == set(schema_tool.TYPE_SCHEMAS)
    assert len(expected) == 26


def test_verify_claim_enum_is_preserved():
    schema = schema_tool.value_type_schema("verify claim")
    assert schema["properties"]["status"] == {
        "type": "string",
        "enum": ["verified", "contradicted", "unknown"],
    }


def test_remaining_types_are_declared():
    assert schema_tool.value_type_schema("trace tb-join")["properties"][
        "join_status"] == {"type": "string"}
    assert schema_tool.value_type_schema("verify structural")["properties"][
        "coverage"] == {"type": "object"}
    assert schema_tool.value_type_schema("scope")["properties"][
        "parent"] == {"type": ["string", "null"]}
    assert "output" not in schema_tool.value_type_schema("filelist prune")[
        "required"]


def test_schema_types_covers_26_manifest_plus_two_variants():
    problems, total = schema_tool.run_schema_types()
    assert total == 28
    assert problems == []
