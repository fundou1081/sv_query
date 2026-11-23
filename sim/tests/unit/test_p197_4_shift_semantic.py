"""P197.4 — shift amount comes from the semantic operand, not expression text."""
from __future__ import annotations

from pathlib import Path


def _tracer(tmp_path: Path, rhs: str):
    from sv_query.trace.unified_tracer import UnifiedTracer

    sv = tmp_path / "shift.sv"
    sv.write_text(
        "module top(input logic [7:0] a, input logic [2:0] b, output logic [9:0] y);\n"
        f"  assign y = {rhs};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer


def test_sized_shift_literal_uses_value_not_width(tmp_path):
    tracer = _tracer(tmp_path, "a << 4'd2")
    edge = tracer.get_graph().get_edge("top.a", "top.y")
    assert edge.source.shift_amount == 2
    signal = tracer._signal_tracer
    assert signal._expr_source_bits(edge, "top.y", 2) == ["top.a[0]"]
    assert signal._expr_source_bits(edge, "top.y", 4) == ["top.a[2]"]
    assert signal._expr_source_bits(edge, "top.y", 6) == ["top.a[4]"]
    assert signal._expr_dst_bits(edge, 0) == ["top.y[2]"]
    assert signal._expr_dst_bits(edge, 2) == ["top.y[4]"]


def test_dynamic_shift_has_no_fixed_bit_mapping(tmp_path):
    tracer = _tracer(tmp_path, "a << b")
    edge = tracer.get_graph().get_edge("top.a", "top.y")
    assert edge.source.shift_amount is None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 2) is None
