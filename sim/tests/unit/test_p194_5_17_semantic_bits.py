"""P194.5.17 — nested bit selects must not create top-level shadow nodes."""
from __future__ import annotations

from sv_query.trace.unified_tracer import UnifiedTracer


def test_nested_bit_select_uses_elaborated_instance_path():
    source = (
        "module sub(input logic a, output logic q);\n"
        "  wire [2:0] cnt;\n"
        "  assign cnt = {a, a, a};\n"
        "  assign q = cnt[1];\n"
        "endmodule\n"
        "module top(input logic a, output logic y);\n"
        "  sub u(.a(a), .q(y));\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={"nested_bits.sv": source}, log_level="ERROR")
    tracer.build_graph()
    nodes = set(tracer.get_graph().nodes())
    assert "top.u.cnt[1]" in nodes
    assert "top.cnt[1]" not in nodes
