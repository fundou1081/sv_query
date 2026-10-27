"""[iter_307 / PLAN P13.6] 静态 indexed memory 的位精度。

`logic [7:0] mem [0:3]; assign mem[1]=d; assign y=mem[1]; assign z=y[3];`
  - mem / mem[1] 宽度 = 元素宽度 8（之前是 (1,0)）
  - mem[1][3] / y[3] 位节点由 F4 位桥合成
  - fanin(z) = {y[3], mem[1][3], d[3]}
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC = """
module top(input [7:0] d, output [7:0] y, output z);
  logic [7:0] mem [0:3];
  assign mem[1] = d;
  assign y = mem[1];
  assign z = y[3];
endmodule
"""


def _build(src: str = SRC) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


def _ids(tr, sig, kind="fanin") -> set[str]:
    return {r.id for r in getattr(tr, f"trace_{kind}")(sig)}


class TestStaticMemoryBits:
    def test_element_widths(self):
        g = _build().get_graph()
        assert g.get_node("top.mem").width == (7, 0)
        assert g.get_node("top.mem[1]").width == (7, 0)

    def test_element_bit_nodes_synthesized(self):
        g = _build().get_graph()
        assert "top.mem[1][3]" in g
        assert "top.y[3]" in g

    def test_fanin_bit_precise(self):
        assert _ids(_build(), "top.z") == {
            "top.y[3]", "top.mem[1][3]", "top.d[3]"}

    def test_fanout_bit_precise(self):
        assert _ids(_build(), "top.d[3]", kind="fanout") == {
            "top.mem[1][3]", "top.y[3]", "top.z"}

    def test_other_index_not_crossed(self):
        tr = _build("""
module top(input [7:0] d, output [7:0] y, output z);
  logic [7:0] mem [0:3];
  assign mem[1] = d;
  assign y = mem[2];
  assign z = y[3];
endmodule""")
        ids = _ids(tr, "top.z")
        assert "top.mem[1][3]" not in ids
