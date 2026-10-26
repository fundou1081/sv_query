"""[iter_299 / PLAN P11] packed struct/union 的聚合宽度与 signedness。

之前 typedef 用户类型（packed struct/union）的宽度是 (1,0)（syntax 层无宽度），
signedness 也丢失。P11.1 用语义符号 `.type.bitWidth` / `.type.isSigned`：
  - struct packed：所有成员宽度之和（first member 在 MSB）
  - struct packed signed：signed=True
  - union packed：最大成员宽度
  - 端口/net/变量声明一致
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.graph.models import SignalGraph  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC = """
typedef struct packed { logic [3:0] a; logic [3:0] b; } pkt_t;
typedef struct packed signed { logic [3:0] sa; } spkt_t;
typedef union packed { logic [7:0] u8; logic [1:0][3:0] u2; } pun_t;
typedef struct packed { pkt_t inner; logic [3:0] c; } outer_t;
module top(input clk, input pkt_t pin, input spkt_t spin,
           output pkt_t pout, output spkt_t spout, output [3:0] y);
  pkt_t p;
  spkt_t sp;
  pun_t pu;
  outer_t o;
  wire pkt_t w;
  assign y = o.c;
endmodule
"""


def _build(src: str = SRC) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


class TestPackedAggregateWidth:
    def test_struct_width_unsigned(self):
        g = _build().get_graph()
        n = g.get_node("top.p")
        assert n.width == (7, 0)
        assert n.is_signed is False

    def test_struct_signed(self):
        g = _build().get_graph()
        n = g.get_node("top.sp")
        assert n.width == (3, 0)
        assert n.is_signed is True

    def test_union_width(self):
        g = _build().get_graph()
        n = g.get_node("top.pu")
        assert n.width == (7, 0)
        assert n.is_signed is False

    def test_nested_struct_width(self):
        g = _build().get_graph()
        assert g.get_node("top.o").width == (11, 0)

    def test_net_declaration_width(self):
        g = _build().get_graph()
        assert g.get_node("top.w").width == (7, 0)

    def test_ports_width_and_signedness(self):
        g = _build().get_graph()
        assert g.get_node("top.pin").width == (7, 0)
        assert g.get_node("top.pout").width == (7, 0)
        assert g.get_node("top.spin").is_signed is True
        assert g.get_node("top.spout").is_signed is True


class TestPackedMemberLayout:
    SRC = """
typedef struct packed { logic [3:0] a; logic [3:0] b; } pkt_t;
typedef union packed { logic [7:0] u8; logic [1:0][3:0] u2; } pun_t;
typedef struct packed { pkt_t inner; logic [3:0] c; } outer_t;
module top(input clk, output [7:0] y, output [4:0] z);
  pkt_t p;
  pun_t pu;
  outer_t o;
  assign y = {p.a, pu.u8};
  assign z = {o.inner, o.c};
endmodule
"""

    def test_struct_member_width_and_range(self):
        g = _build(self.SRC).get_graph()
        a = g.get_node("top.p.a")
        assert a.width == (3, 0) and a.parent == "top.p"
        assert (a.parent_bit_start, a.parent_bit_end) == (7, 4)   # a 在 MSB

    def test_union_member_overlaps(self):
        g = _build(self.SRC).get_graph()
        u8 = g.get_node("top.pu.u8")
        assert u8.width == (7, 0)
        assert (u8.parent_bit_start, u8.parent_bit_end) == (7, 0)

    def test_nested_struct_member(self):
        g = _build(self.SRC).get_graph()
        inner = g.get_node("top.o.inner")
        assert inner.width == (7, 0)
        assert (inner.parent_bit_start, inner.parent_bit_end) == (11, 4)
        c = g.get_node("top.o.c")
        assert (c.parent_bit_start, c.parent_bit_end) == (3, 0)

    def test_member_signedness(self):
        g = _build("""
typedef struct packed signed { logic [3:0] sa; } spkt_t;
module top(input clk, output [3:0] y);
  spkt_t sp;
  assign y = sp.sa;
endmodule""").get_graph()
        assert g.get_node("top.sp.sa").width == (3, 0)
        # 成员自身是 logic（unsigned）；struct 整体的 signed 见上面聚合测试
        assert g.get_node("top.sp.sa").is_signed is False


class TestPackedStructSerialization:
    def test_json_roundtrip(self):
        g = _build().get_graph()
        g2 = SignalGraph.from_dict(g.to_dict())
        assert g2.get_node("top.p").width == (7, 0)
        assert g2.get_node("top.sp").is_signed is True
        assert g2.get_node("top.o").width == (11, 0)
