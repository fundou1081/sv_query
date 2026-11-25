"""P198.9 — IR bit mapping for broad shapes (slice/cast/ternary)."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _graph(tmp_path: Path, body: str):
    sv = tmp_path / "shapes.sv"
    sv.write_text(
        "module top(input logic [7:0] a, input logic [7:0] b, input logic sel,\n"
        "           output logic [7:0] y);\n"
        f"  {body}\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer, tracer.get_graph()


def test_slice_route_works_without_legacy_source(tmp_path):
    tracer, graph = _graph(tmp_path, "assign y = a[3:0];")
    edge = next(e for e in graph._edge_data_for_dst("top.y") if e.expr_id)
    edge.expression = "not-a-slice"
    edge.source = None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 0) == ["top.a[0]"]
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 3) == ["top.a[3]"]


def test_ternary_route_works_without_legacy_source(tmp_path):
    tracer, graph = _graph(tmp_path, "assign y = sel ? a : b;")
    edge = next(e for e in graph._edge_data_for_dst("top.y") if e.expr_id)
    assert graph.get_expression(edge.expr_id).op == "Ternary"
    edge.expression = "not-a-ternary"
    edge.source = None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 2) == ["top.a[2]"]
