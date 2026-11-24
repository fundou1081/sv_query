"""P198.7 — generate-scope continuous assigns carry expression IR."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _graph(tmp_path: Path, body: str):
    sv = tmp_path / "gen.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [7:0] y);\n"
        "  genvar i;\n"
        "  generate\n"
        f"{body}\n"
        "  endgenerate\n"
        "endmodule\n")
    return UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()


def test_generate_for_bit_select_assign_has_ir(tmp_path):
    graph = _graph(tmp_path, "    for (i=0;i<2;i=i+1) begin : G\n"
                            "      assign y[i] = a[i];\n"
                            "    end")
    assert len(graph.assignments) == 2
    for bit in (0, 1):
        edge = graph._edge_data_for_dst(f"top.y[{bit}]")[0]
        assert edge.expr_id and edge.assignment_id
        assert edge.assignment_id in graph.assignments
        assert graph.get_expression(edge.expr_id).op in ("SignalRef", "Cast", "Slice")


def test_generate_for_assign_ids_are_distinct_and_referenced(tmp_path):
    graph = _graph(tmp_path, "    for (i=0;i<2;i=i+1) begin : G\n"
                            "      assign y[i] = a[i];\n"
                            "    end")
    referenced = {e.assignment_id for (_, _), edges in graph._edge_data.items()
                  for e in edges if e.assignment_id}
    assert referenced == set(graph.assignments)
