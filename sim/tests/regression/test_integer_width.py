"""[iter_298 / PLAN P10] 整数类型位宽提取。

`integer/int/byte/shortint/longint/time` 之前一律 (1,0)（假 1 位），
导致位查询/表达式映射基于错误宽度。P10 按类型关键字映射到 SV 标准宽度：

  byte=8, shortint=16, int=32, integer=32, longint=64, time=64

signedness: integer/int/byte/shortint/longint = signed；time = unsigned。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.graph.models import SignalGraph  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC = """
module top(input clk, input [7:0] din, output reg [7:0] y);
  integer i;
  int j;
  byte b;
  shortint si;
  longint li;
  time t;
  logic [7:0] l;
  always_ff @(posedge clk) i <= i + 1;
  assign y = din;
endmodule
"""


def _build(src: str = SRC) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


class TestIntegerWidths:
    def test_integer_is_32bit_signed(self):
        g = _build().get_graph()
        assert g.get_node("top.i").width == (31, 0)
        assert g.get_node("top.i").is_signed is True

    def test_type_matrix(self):
        g = _build().get_graph()
        expected = {
            "top.j": ((31, 0), True),    # int
            "top.b": ((7, 0), True),     # byte
            "top.si": ((15, 0), True),   # shortint
            "top.li": ((63, 0), True),   # longint
            "top.t": ((63, 0), False),   # time
            "top.l": ((7, 0), False),    # logic [7:0]
        }
        for nid, (width, signed) in expected.items():
            n = g.get_node(nid)
            assert n.width == width, (nid, n.width)
            assert n.is_signed is signed, (nid, n.is_signed)

    def test_ports_unchanged(self):
        g = _build().get_graph()
        assert g.get_node("top.din").width == (7, 0)
        assert g.get_node("top.y").width == (7, 0)

    def test_lazy_node_backfilled(self):
        """integer 先被 always 引用（懒建 (1,0)），变量声明阶段回填 32 位。"""
        g = _build().get_graph()
        assert g.get_node("top.i").width == (31, 0)

    def test_json_roundtrip_keeps_width(self):
        g = _build().get_graph()
        g2 = SignalGraph.from_dict(g.to_dict())
        assert g2.get_node("top.i").width == (31, 0)

    def test_bit_query_on_integer_does_not_crash(self):
        """integer 没有 per-bit 节点时，位查询回落总线（不崩、不空答）。"""
        t = _build()
        assert {n.id for n in t.trace_fanin("top.i[3]")} == {"top.i"}

    def test_for_loop_variable_width(self):
        tr = _build("""
module top(input clk, output reg [7:0] q);
  integer k;
  always_ff @(posedge clk) begin
    for (k = 0; k < 8; k = k + 1) q[k] <= 1'b1;
  end
endmodule""")
        assert tr.get_graph().get_node("top.k").width == (31, 0)
