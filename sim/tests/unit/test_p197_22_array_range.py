"""P197.22 — unpacked array indices are not packed bit indices."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer


def _tracer(tmp_path: Path):
    sv = tmp_path / "array.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [7:0] mem [0:15]);\n"
        "  assign mem[0] = a;\n"
        "  assign mem[9] = a;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer


def test_unpacked_array_metadata_and_element_width(tmp_path):
    graph = _tracer(tmp_path).get_graph()
    base = graph.get_node("top.mem")
    assert (base.extra or {}).get("is_array") is True
    element = graph.get_node("top.mem[9]")
    assert element is not None
    assert (element.extra or {}).get("array_element") is True


def test_missing_array_element_is_not_packed_bit_fallback(tmp_path):
    tracer = _tracer(tmp_path)
    for sig in ("top.mem[15]", "top.mem[9]"):
        chain = tracer.trace_detailed(sig)
        if sig == "top.mem[9]":
            assert chain.drivers
        else:
            assert chain.drivers == []
            assert chain.confidence == "uncertain"


def test_driven_array_missing_element_is_not_parent_bus_bit(tmp_path):
    sv = tmp_path / "driven_array.sv"
    sv.write_text(
        "module sub(output logic [31:0] o [0:3]);\n"
        "  assign o[0] = 32'h1;\n"
        "endmodule\n"
        "module top(input logic [31:0] a, output logic [31:0] mem [0:3]);\n"
        "  sub u(.o(mem));\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    chain = tracer.trace_detailed("top.mem[9]")
    assert chain.drivers == []
    assert chain.confidence == "uncertain"


def test_instance_qualified_array_metadata(tmp_path):
    sv = tmp_path / "inst_array.sv"
    sv.write_text(
        "module sub(output logic [31:0] mem [0:3]);\n"
        "  assign mem[0] = 32'h1;\n"
        "endmodule\n"
        "module top(input logic clk);\n"
        "  sub u1(.mem());\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    graph = tracer.get_graph()
    base = graph.get_node("top.u1.mem")
    assert (base.extra or {}).get("is_array") is True
    assert base.width == (31, 0)
    element = graph.get_node("top.u1.mem[0]")
    assert (element.extra or {}).get("array_element") is True
    assert tracer.trace_detailed("top.u1.mem[9]").drivers == []


def test_connected_instance_array_keeps_drivers(tmp_path):
    sv = tmp_path / "connected_array.sv"
    sv.write_text(
        "module sub(output logic [31:0] o [0:3]);\n"
        "  assign o[0] = 32'h1;\n"
        "endmodule\n"
        "module top(output logic [31:0] mem [0:3]);\n"
        "  sub u(.o(mem));\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    chain = tracer.trace_detailed("top.mem[0]")
    assert chain.drivers, "instance-array driver was lost"
