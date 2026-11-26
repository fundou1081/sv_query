"""P197.19 — nested signed shift fanout and unsigned vacated bits."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _edge(tmp_path: Path, a_decl: str, rhs: str):
    sv = tmp_path / "nested.sv"
    sv.write_text(
        f"module top(input logic {a_decl} a, output logic signed [10:0] y);\n"
        f"  assign y = {rhs};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    graph = tracer.get_graph()
    return tracer._signal_tracer, next(
        e for s in graph.predecessors("top.y")
        for e in graph.get_edges(s, "top.y") if s == "top.a")


def test_nested_signed_shift_fanout_is_inverse(tmp_path):
    st, edge = _edge(tmp_path, "signed [7:0]", "$signed(a <<< 2)")
    assert st._expr_dst_bits(edge, 7) == []
    assert st._expr_dst_bits(edge, 5) == [f"top.y[{b}]" for b in range(7, 11)]
    assert st._expr_source_bits(edge, "top.y", 9) == ["top.a[5]"]


def test_nested_signed_logical_shift_does_not_sign_fill(tmp_path):
    st, edge = _edge(tmp_path, "signed [7:0]", "$signed(a >> 2)")
    assert st._expr_dst_bits(edge, 7) == ["top.y[5]"]
    assert st._expr_source_bits(edge, "top.y", 9) == []


def test_unsigned_arithmetic_right_vacated_bits_are_zero(tmp_path):
    st, edge = _edge(tmp_path, "[7:0]", "a >>> 2")
    for bit in range(6, 11):
        assert st._expr_source_bits(edge, "top.y", bit) == []
