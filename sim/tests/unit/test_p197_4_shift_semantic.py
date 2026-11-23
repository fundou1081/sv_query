"""P197.4 — shift amount comes from the semantic operand, not expression text."""
from __future__ import annotations

from pathlib import Path

import pytest


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


def _a_edge(tracer):
    graph = tracer.get_graph()
    for src, dst in graph.edges():
        if dst == "top.y" and "top.a" in src:
            return graph.get_edge(src, dst)
    raise AssertionError("no top.a -> top.y edge")


def test_sized_shift_literal_uses_value_not_width(tmp_path):
    tracer = _tracer(tmp_path, "a << 4'd2")
    edge = _a_edge(tracer)
    assert edge.source.shift_amount == 2
    signal = tracer._signal_tracer
    assert signal._expr_source_bits(edge, "top.y", 2) == ["top.a[0]"]
    assert signal._expr_source_bits(edge, "top.y", 4) == ["top.a[2]"]
    assert signal._expr_source_bits(edge, "top.y", 6) == ["top.a[4]"]
    assert signal._expr_dst_bits(edge, 0) == ["top.y[2]"]
    assert signal._expr_dst_bits(edge, 2) == ["top.y[4]"]


@pytest.mark.parametrize("rhs,expected", [
    ("a << 4'd2", 2), ("a >> 8'd3", 3), ("a <<< 2", 2),
    ("a >>> 4'h2", 2), ("a[7:0] << 4'd2", 2)])
def test_shift_operator_and_literal_matrix(tmp_path, rhs, expected):
    edge = _a_edge(_tracer(tmp_path, rhs))
    assert edge.source.shift_amount == expected


@pytest.mark.parametrize("rhs", ["a << 4'dx", "a >> 4'dz"])
def test_unknown_shift_literal_is_not_coerced_to_zero(tmp_path, rhs):
    tracer = _tracer(tmp_path, rhs)
    edge = _a_edge(tracer)
    assert edge.source.shift_amount is None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 2) is None


def test_conversion_wrapped_shift_keeps_semantic_amount(tmp_path):
    edge = _a_edge(_tracer(tmp_path, "$signed(a) >>> 4'd2"))
    assert edge.source.shift_amount == 2


def test_dynamic_shift_has_no_fixed_bit_mapping(tmp_path):
    tracer = _tracer(tmp_path, "a << b")
    edge = _a_edge(tracer)
    assert edge.source.shift_amount is None
    assert tracer._signal_tracer._expr_source_bits(edge, "top.y", 2) is None
