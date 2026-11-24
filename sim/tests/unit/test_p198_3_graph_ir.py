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
