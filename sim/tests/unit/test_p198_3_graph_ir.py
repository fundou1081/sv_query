"""P198.3 — expression/assignment IR is attached to graph and round-trips."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.core.graph.models import SignalGraph
from sv_query.trace.unified_tracer import UnifiedTracer


def _graph(tmp_path: Path) -> SignalGraph:
    sv = tmp_path / "ir.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [9:0] y);\n"
        "  assign y = a << 4'd2;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    return tracer.build_graph()


def test_graph_attaches_assignment_and_edge_refs(tmp_path):
    graph = _graph(tmp_path)
    assert len(graph.assignments) == 1
    aid, assignment = next(iter(graph.assignments.items()))
    assert assignment.assign_type == "continuous"
    assert assignment.rhs.op == "ShiftLeft"
    edge = graph._edge_data_for_dst("top.y")[0]
    assert edge.assignment_id == aid
    assert edge.expr_id == assignment.rhs.expr_id
    assert graph.get_expression(edge.expr_id).op == "ShiftLeft"


def test_graph_ir_round_trip_and_legacy_defaults(tmp_path):
    graph = _graph(tmp_path)
    data = graph.to_dict()
    restored = SignalGraph.from_dict(data)
    assert restored.assignments.keys() == graph.assignments.keys()
    assert len(restored.expression_store) == len(graph.expression_store)
    assert restored._edge_data_for_dst("top.y")[0].expr_id == \
        graph._edge_data_for_dst("top.y")[0].expr_id

    legacy = dict(data)
    legacy.pop("expression_store", None)
    legacy.pop("assignments", None)
    legacy["edges"] = [dict(e) for e in data["edges"]]
    for edge in legacy["edges"]:
        edge.pop("expr_id", None)
        edge.pop("assignment_id", None)
    old = SignalGraph.from_dict(legacy)
    assert old.assignments == {}
    assert len(old.expression_store) == 0


def test_multi_instance_ir_uses_instance_paths(tmp_path):
    sv = tmp_path / "multi.sv"
    sv.write_text(
        "module sub(input logic [7:0] a, output logic [9:0] y);\n"
        "  assign y = a << 4'd2;\n"
        "endmodule\n"
        "module top(input logic [7:0] a0, a1, output logic [9:0] y0, y1);\n"
        "  sub u0(.a(a0), .y(y0));\n"
        "  sub u1(.a(a1), .y(y1));\n"
        "endmodule\n")
    graph = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()
    assert len(graph.assignments) == 2
    ids = set()
    for dst in ("top.u0.y", "top.u1.y"):
        edge = graph._edge_data_for_dst(dst)[0]
        assert edge.expr_id and edge.assignment_id
        assert edge.assignment_id in graph.assignments
        ids.add(edge.assignment_id)
    assert len(ids) == 2


def test_snapshot_dangling_ir_ref_is_rejected(tmp_path):
    import pytest
    graph = _graph(tmp_path)
    data = graph.to_dict()
    for edge in data["edges"]:
        if edge["kind"] == "DRIVER":
            edge["expr_id"] = "expr:missing"
            break
    with pytest.raises(ValueError, match="dangling expr_id"):
        SignalGraph.from_dict(data)
