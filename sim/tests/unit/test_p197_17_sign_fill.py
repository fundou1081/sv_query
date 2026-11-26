"""P197.17 — arithmetic shift sign fill mapping."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _edge(tmp_path: Path, decl: str, rhs: str):
    sv = tmp_path / "sign.sv"
    sv.write_text(
        f"module top(input logic {decl} a, output logic signed [10:0] y);\n"
        f"  assign y = {rhs};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    graph = tracer.get_graph()
    edge = next(e for s in graph.predecessors("top.y")
                for e in graph.get_edges(s, "top.y") if s == "top.a")
    return tracer._signal_tracer, edge


def test_signed_arithmetic_right_fills_with_sign_bit(tmp_path):
    st, edge = _edge(tmp_path, "signed [7:0]", "a >>> 4'd2")
    assert st._expr_source_bits(edge, "top.y", 5) == ["top.a[7]"]
    assert st._expr_source_bits(edge, "top.y", 9) == ["top.a[7]"]
    assert st._expr_source_bits(edge, "top.y", 10) == ["top.a[7]"]
    assert st._expr_source_bits(edge, "top.y", 0) == ["top.a[2]"]


def test_logical_and_unsigned_right_shift_zero_fill(tmp_path):
    st, edge = _edge(tmp_path, "signed [7:0]", "a >> 4'd2")
    assert st._expr_source_bits(edge, "top.y", 9) == []
    st, edge = _edge(tmp_path, "[7:0]", "a >>> 4'd2")
    assert st._expr_source_bits(edge, "top.y", 9) == []


def test_sign_bit_fanout_covers_fill_bits(tmp_path):
    st, edge = _edge(tmp_path, "signed [7:0]", "a >>> 4'd2")
    assert st._expr_dst_bits(edge, 7) == [f"top.y[{b}]" for b in range(5, 11)]
    st, edge = _edge(tmp_path, "signed [7:0]", "a >> 4'd2")
    assert st._expr_dst_bits(edge, 7) == [f"top.y[{b}]" for b in range(5, 9)]


def test_arithmetic_left_is_zero_fill(tmp_path):
    st, edge = _edge(tmp_path, "signed [7:0]", "a <<< 4'd2")
    assert st._expr_source_bits(edge, "top.y", 0) == []
    assert st._expr_source_bits(edge, "top.y", 2) == ["top.a[0]"]
