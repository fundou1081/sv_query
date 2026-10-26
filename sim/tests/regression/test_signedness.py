"""[iter_297 / PLAN P9] signedness 建模与符号扩展。

P9.1 图元数据：TraceNode.is_signed（端口/网表/变量声明，来自 pyslang type.isSigned）；
      JSON 序列化往返保留。
P9.2 查询层：
      - 有符号字面量 4'shF → 高位符号扩展 = 1；4'sh2 → 扩展位 = 0
      - 有符号信号加宽：y[5] ← a[3]（符号位）；无符号 → 1'b0
      - 拼接内字面量自决定宽度（不符号扩展）
      - a & 4'shF：高位依赖信号位（符号扩展常量不是恒 0）
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.graph.models import SignalGraph  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

SIGNED_DECLS = """
module top(input logic signed [3:0] a, input logic [3:0] b, output logic [7:0] y);
  logic signed [3:0] s;
  logic [3:0] u;
  wire signed [3:0] w;
  integer i;
  assign y = a;
endmodule
"""


def _build(src: str) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


def _ids(tr, sig, kind="fanin") -> set[str]:
    return {r.id for r in getattr(tr, f"trace_{kind}")(sig)}


class TestGraphSignedness:
    def test_ports(self):
        g = _build(SIGNED_DECLS).get_graph()
        assert g.get_node("top.a").is_signed is True
        assert g.get_node("top.b").is_signed is False
        assert g.get_node("top.y").is_signed is False

    def test_variables_and_nets(self):
        g = _build(SIGNED_DECLS).get_graph()
        assert g.get_node("top.s").is_signed is True        # logic signed
        assert g.get_node("top.u").is_signed is False       # logic
        assert g.get_node("top.w").is_signed is True        # wire signed
        assert g.get_node("top.i").is_signed is True        # integer 默认 signed

    def test_json_roundtrip(self):
        g = _build(SIGNED_DECLS).get_graph()
        g2 = SignalGraph.from_dict(g.to_dict())
        assert g2.get_node("top.a").is_signed is True
        assert g2.get_node("top.b").is_signed is False
        assert g2.get_node("top.s").is_signed is True


class TestSignedLiteralExtension:
    SRC = """
module top(input [7:0] a, output [7:0] y);
  assign y = 4'shF;
endmodule
"""

    def test_negative_literal_sign_extends(self):
        tr = _build(self.SRC)
        for bit in (0, 2, 5, 7):
            assert _ids(tr, f"top.y[{bit}]") == {"1'b1"}, bit

    def test_positive_signed_literal_zero_extends(self):
        tr = _build("""
module top(input [7:0] a, output [7:0] y);
  assign y = 4'sh2;
endmodule""")
        assert _ids(tr, "top.y[5]") == {"1'b0"}
        assert _ids(tr, "top.y[1]") == {"1'b1"}

    def test_unsigned_literal_still_zero_extends(self):
        tr = _build("""
module top(input [7:0] a, output [7:0] y);
  assign y = 4'hF;
endmodule""")
        assert _ids(tr, "top.y[5]") == {"1'b0"}


class TestSignedSignalExtension:
    SRC = """
module top(input logic signed [3:0] a, output [7:0] y, output [4:0] t, output u);
  assign y = a;
  assign u = a[3];
  assign t = {y[7], y[6], y[5], y[4], y[3]};
endmodule
"""

    def test_high_bit_maps_to_sign_bit(self):
        tr = _build(self.SRC)
        assert _ids(tr, "top.y[5]") == {"top.a[3]"}

    def test_fanout_sign_bit_drives_all_high_bits(self):
        tr = _build(self.SRC)
        assert _ids(tr, "top.a[3]", kind="fanout") == {
            "top.u", "top.y[3]", "top.y[4]", "top.y[5]",
            "top.y[6]", "top.y[7]", "top.t"}

    def test_unsigned_signal_extends_zero(self):
        tr = _build("""
module top(input logic [3:0] a, output [7:0] y);
  assign y = a;
endmodule""")
        assert _ids(tr, "top.y[5]") == {"1'b0"}

    def test_non_sign_bit_stays_same_index(self):
        tr = _build("""
module top(input logic signed [3:0] a, output [7:0] y, output [1:0] t);
  assign y = a;
  assign t = {a[2], a[3]};
endmodule""")
        assert _ids(tr, "top.y[2]") == {"top.a[2]"}


class TestSignedInConcatAndBitwise:
    def test_concat_literal_is_self_determined(self):
        """拼接内 4'shF 只贡献 4 位（不符号扩展），低位全 1。"""
        tr = _build("""
module top(input [3:0] a, output [7:0] s);
  assign s = {a, 4'shF};
endmodule""")
        for bit in range(4):
            assert _ids(tr, f"top.s[{bit}]") == {"1'b1"}, bit

    def test_signed_const_in_and_keeps_signal_dep(self):
        """a & 4'shF：bit5 的常量操作数符号扩展为 1，信号位仍是依赖（不判恒 0）。"""
        tr = _build("""
module top(input logic [7:0] a, output [7:0] s, output t);
  assign s = a & 4'shF;
  assign t = a[5];
endmodule""")
        assert _ids(tr, "top.s[5]") == {"1'b1", "top.a[5]"}

    def test_unsigned_const_in_and_is_constant_zero(self):
        tr = _build("""
module top(input logic [7:0] a, output [7:0] s);
  assign s = a & 4'hF;
endmodule""")
        assert _ids(tr, "top.s[5]") == {"1'b0"}
