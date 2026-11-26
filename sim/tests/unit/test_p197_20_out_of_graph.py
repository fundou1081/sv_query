"""P197.20 — out-of-graph bit queries agree across detailed paths."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _tracer(tmp_path: Path):
    sv = tmp_path / "bits.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [7:0] y);\n"
        "  assign y = 8'h00;\n"
        "  assign y[3] = a[3];\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer


def test_in_range_out_of_graph_bit_matches_fanin(tmp_path):
    tracer = _tracer(tmp_path)
    assert tracer.trace_fanin_detailed("top.y[2]")
    assert [d.node.id for d in tracer.trace_detailed("top.y[2]").drivers] == [
        d.node.id for d in tracer.trace_fanin_detailed("top.y[2]")]


def test_out_of_range_bit_has_no_false_literal_driver(tmp_path):
    tracer = _tracer(tmp_path)
    assert tracer.trace_fanin("top.y[9]") == []
    assert tracer.trace_fanin_detailed("top.y[9]") == []
    assert tracer.trace_detailed("top.y[9]").drivers == []
