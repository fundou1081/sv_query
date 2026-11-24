"""P198.5 — fanin/fanout bit mapping consumes expression IR."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _shift_graph(tmp_path: Path):
    sv = tmp_path / "shift.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [9:0] y);\n"
        "  assign y = a << 4'd2;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer, tracer.get_graph().get_edge("top.a", "top.y")


def test_fanin_uses_ir_when_legacy_text_is_removed(tmp_path):
    tracer, edge = _shift_graph(tmp_path)
    assert edge.expr_id
    edge.expression = "not-a-shift"
    edge.source = None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 2) == ["top.a[0]"]


def test_fanout_uses_ir_when_legacy_text_is_removed(tmp_path):
    tracer, edge = _shift_graph(tmp_path)
    edge.expression = "not-a-shift"
    edge.source = None
    assert tracer._signal_tracer._expr_dst_bits(edge, 0) == ["top.y[2]"]
    assert tracer._signal_tracer._expr_dst_bits(edge, 2) == ["top.y[4]"]


def test_ir_unknown_does_not_fall_back_to_legacy(tmp_path):
    sv = tmp_path / "call.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [10:0] y);\n"
        "  function automatic logic [7:0] f(input logic [7:0] x);\n"
        "    return x + 1;\n"
        "  endfunction\n"
        "  assign y = f(a) << 4'd2;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    edge = tracer.get_graph().get_edge("top.a", "top.y")
    assert edge.expr_id
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 2) is None
    assert tracer._signal_tracer._expr_dst_bits(edge, 0) is None
