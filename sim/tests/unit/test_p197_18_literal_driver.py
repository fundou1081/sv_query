"""P197.18 — synthetic literal drivers must not crash detailed fanin."""
from __future__ import annotations

from sv_query.trace.unified_tracer import UnifiedTracer


def test_detailed_fanin_with_synthetic_literal_does_not_raise(tmp_path):
    sv = tmp_path / "literal.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [7:0] y);\n"
        "  assign y = 8'h00;\n"
        "  assign y[3] = a[3];\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    chain = tracer.trace_detailed("top.y[3]")
    ids = {d.node.id for d in chain.drivers}
    assert "top.a[3]" in ids
    assert chain.confidence in ("high", "low")
