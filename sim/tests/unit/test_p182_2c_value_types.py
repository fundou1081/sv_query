"""P182.2c — high-value result value types."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_envelope_schema as schema_tool  # noqa: E402


def test_type_schema_covers_expected_commands():
    assert {
        "stats", "drivers", "loads", "graph nodes", "graph edges",
        "controlflow analyze", "dataflow analyze", "verify claim",
        "trace covergroup",
    } <= set(schema_tool.TYPE_SCHEMAS)
    assert len(schema_tool.TYPE_VARIANTS) == 2


def test_stats_and_dataflow_types_are_declared():
    stats = schema_tool.value_type_schema("stats")
    assert stats["properties"]["total_nodes"] == {"type": "integer"}
    dataflow = schema_tool.value_type_schema("dataflow analyze")
    assert dataflow["properties"]["elapsed_s"] == {"type": "number"}
    assert dataflow["properties"]["is_reachable"] == {
        "type": ["boolean", "null"]
    }


def test_wrong_value_type_is_rejected():
    problems = schema_tool.validate_value_payload(
        "stats",
        {"total_nodes": "many", "total_edges": 1, "nodes": {}, "edges": {},
         "modules": [], "elaboration_errors": []},
    )
    assert any("total_nodes" in p or "not of type" in p for p in problems)


def test_schema_types_runs_eleven_cases():
    problems, total = schema_tool.run_schema_types()
    assert total >= 11
    assert problems == []


def test_gate_catches_mutated_type(monkeypatch):
    monkeypatch.setitem(
        schema_tool.JSON_CONTRACT["stats_result"],
        "total_nodes",
        {"type": "string"},
    )
    problems, _ = schema_tool.run_schema_types()
    assert any("total_nodes" in p for p in problems)
