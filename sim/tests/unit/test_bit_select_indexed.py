"""[iter_352 / PLAN P51] indexed part-select / multi-top namespace。"""
from __future__ import annotations

from pathlib import Path

from trace.unified_tracer import UnifiedTracer


def test_indexed_part_select_normalized():
    src = """
module top(input [63:0] bus, output [31:0] out);
  assign out = bus[32 +: 32];
endmodule
"""
    tr = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    g = tr.build_graph(use_cache=False, target_module="top")
    assert "top.bus[63:32]" in g.nodes()
    assert "top.bus[32:32]" not in g.nodes()
    node = g.get_node("top.bus[63:32]")
    assert node.parent == "top.bus"
    assert node.bit_range == "[63:32]"


def test_multi_top_bit_prefix(tmp_path: Path):
    a = tmp_path / "a.sv"
    b = tmp_path / "b.sv"
    fl = tmp_path / "files.f"
    body = """
module {name}(input [63:0] bus, output [31:0] out);
  assign out = bus[32 +: 32];
endmodule
"""
    a.write_text(body.format(name="top_a"))
    b.write_text(body.format(name="top_b"))
    fl.write_text(f"{a}\n{b}\n")
    tr = UnifiedTracer(filelist=str(fl), log_level="ERROR")
    g = tr.build_graph(use_cache=False)
    assert "top_a.bus[63:32]" in g.nodes()
    assert "top_b.bus[63:32]" in g.nodes()
    assert g.get_node("top_a.bus[63:32]").parent == "top_a.bus"
    assert g.get_node("top_b.bus[63:32]").parent == "top_b.bus"


def test_internal_reg_parent_width_propagates():
    src = """
module top(output [7:0] out);
  reg [7:0] bus;
  assign bus = 8'hA5;
  assign out = bus[4 +: 4];
endmodule
"""
    tr = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    g = tr.build_graph(use_cache=False, target_module="top")
    parent = g.get_node("top.bus")
    assert parent is not None and parent.width == (7, 0)
    child = g.get_node("top.bus[7:4]")
    assert child is not None and child.parent == "top.bus"
