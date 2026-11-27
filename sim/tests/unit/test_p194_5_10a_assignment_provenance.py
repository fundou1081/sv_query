"""P194.5.10a — carry semantic assignment source locations on DRIVER edges."""
from __future__ import annotations

from sv_query.trace.core.graph.models import EdgeKind
from sv_query.trace.unified_tracer import UnifiedTracer


def _edges(tracer, dst_suffix: str):
    graph = tracer.get_graph()
    out = []
    for edges in graph._edge_data.values():
        for edge in edges:
            if edge.kind == EdgeKind.DRIVER and edge.dst.endswith(dst_suffix):
                out.append(edge)
    return out


def test_continuous_and_always_assignments_carry_source_location():
    source = (
        "module top(input logic a, d, clk, output logic y, output logic q);\n"
        "  assign y = a;\n"
        "  always_ff @(posedge clk) begin\n"
        "    q <= d;\n"
        "  end\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={"prov.sv": source}, log_level="ERROR")
    tracer.build_graph()
    for edge in _edges(tracer, "top.y"):
        assert edge.source_location is not None
        assert edge.source_location.line_start == 2
    for edge in _edges(tracer, "top.q"):
        assert edge.source_location is not None
        assert edge.source_location.line_start == 4


def test_inactive_preprocessor_branch_is_not_selected():
    source = (
        "module top(input logic clk, d, output logic q);\n"
        "`ifdef TESTBUG\n"
        "  always_ff @(posedge clk) q <= ~d;\n"
        "`else\n"
        "  always_ff @(posedge clk) q <= d;\n"
        "`endif\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={"prov_ifdef.sv": source}, log_level="ERROR")
    tracer.build_graph()
    edges = _edges(tracer, "top.q")
    assert edges
    for edge in edges:
        assert edge.source_location is not None
        lines = source.splitlines()
        assert "q <= d" in lines[edge.source_location.line_start - 1]
        assert "~d" not in lines[edge.source_location.line_start - 1]


def test_existing_timescale_line_is_not_shifted():
    source = (
        "`timescale 1ns/1ps\n"
        "module top(input logic a, output logic y);\n"
        "  assign y = a;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={"explicit_ts.sv": source}, log_level="ERROR")
    tracer.build_graph()
    edges = _edges(tracer, "top.y")
    assert edges and edges[0].source_location.line_start == 3


def test_filelist_bare_basename_with_timescale(tmp_path):

    sv = tmp_path / "filelist_ts.sv"
    sv.write_text(
        "`timescale 1ns/1ps\n"
        "module top(input logic a, output logic y);\n"
        "  assign y = a;\n"
        "endmodule\n")
    (tmp_path / "filelist_ts.f").write_text("filelist_ts.sv\n")
    tracer = UnifiedTracer(filelist=str(tmp_path / "filelist_ts.f"),
                           log_level="ERROR")
    tracer.build_graph()
    edges = _edges(tracer, "top.y")
    assert edges and edges[0].source_location.line_start == 3
