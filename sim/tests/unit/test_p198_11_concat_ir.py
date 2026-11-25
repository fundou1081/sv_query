"""P198.11 — concat fanin/fanout consumes expression IR."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _graph(tmp_path: Path):
    sv = tmp_path / "concat_ir.sv"
    sv.write_text(
        "module top(input logic [3:0] a, input logic [3:0] b,\n"
        "           output logic [7:0] y);\n"
        "  assign y = {a, b};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer, tracer.get_graph()


def test_concat_fanin_uses_ir_without_legacy(tmp_path):
    tracer, graph = _graph(tmp_path)
    edge = next(e for e in graph._edge_data_for_dst("top.y")
                if e.expr_id and e.src == "top.a")
    assert graph.get_expression(edge.expr_id).op == "Concat"
    edge.expression = "not-a-concat"
    edge.source = None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 7) == ["top.a[3]"]
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 0) == []


def test_concat_fanout_uses_ir_without_legacy(tmp_path):
    tracer, graph = _graph(tmp_path)
    edge = next(e for e in graph._edge_data_for_dst("top.y")
                if e.expr_id and e.src == "top.a")
    edge.expression = "not-a-concat"
    edge.source = None
    assert tracer._signal_tracer._expr_dst_bits(edge, 0) == ["top.y[4]"]
    assert tracer._signal_tracer._expr_dst_bits(edge, 3) == ["top.y[7]"]
