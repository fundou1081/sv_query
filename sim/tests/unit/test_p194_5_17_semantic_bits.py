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


def test_absolute_range_select_keeps_parent_metadata():
    source = (
        "module top(input logic [7:4] data, output logic [1:0] y);\n"
        "  assign y = data[5:4];\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={"abs_range.sv": source}, log_level="ERROR")
    tracer.build_graph()
    graph = tracer.get_graph()
    node = graph.get_node("top.data[5:4]")
    assert node is not None
    assert node.parent == "top.data"
    assert node.bit_range == "[5:4]"
    assert any(e.kind.name == "BIT_SELECT"
               for e in graph.get_edges("top.data[5:4]", "top.data"))
