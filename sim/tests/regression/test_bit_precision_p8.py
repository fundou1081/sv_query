"""[iter_296 / PLAN P8] 常量位：常量源切片 + 拼接字面量段。

覆盖：
  - P8.1 拼接里的字面量段：`{a, 4'b10}` → 逐位常量
  - P8.2 常量源切片：`y = 4'hA` → y[k] 是 1'b0/1'b1（不再返回 4'b1010 总线）
  - 位运算常量：`a & 4'hF` → 该位常量 + 信号位；高位零扩展 → 恒 0（无信号依赖）
  - 无宽度字面量：`y = 0` → 32 位零扩展
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _build(src: str) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


def _ids(tr, sig, kind="fanin", depth=None) -> set[str]:
    return {r.id for r in getattr(tr, f"trace_{kind}")(sig, depth=depth)}


class TestConstSource:
    def test_const_zero_bits(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = 4'h0;
endmodule''')
        assert _ids(tr, "top.y[1]") == {"1'b0"}

    def test_const_hex_bits(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = 4'hA;   // 1010
endmodule''')
        assert _ids(tr, "top.y[0]") == {"1'b0"}
        assert _ids(tr, "top.y[1]") == {"1'b1"}
        assert _ids(tr, "top.y[3]") == {"1'b1"}

    def test_const_zero_extension_high_bit(self):
        """4 位常量赋给 8 位：高 4 位是无符号零扩展 → 1'b0。"""
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = 4'hF;
endmodule''')
        assert _ids(tr, "top.y[5]") == {"1'b0"}

    def test_unsized_zero(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = 0;
endmodule''')
        assert _ids(tr, "top.y[3]") == {"1'b0"}

    def test_slice_const_bits(self):
        """y[3:0] = 4'hA：切片内位也分解（y[1]/y[3] = 1'b1）。"""
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y[3:0] = 4'hA;
endmodule''')
        assert _ids(tr, "top.y[1]") == {"1'b1"}
        assert _ids(tr, "top.y[3]") == {"1'b1"}


class TestBitwiseConst:
    def test_and_const_bit(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] s, output t, u);
  assign s = a & 4'hF;
  assign t = a[1];
  assign u = s[1];
endmodule''')
        assert _ids(tr, "top.s[1]") == {"1'b1", "top.a[1]"}

    def test_and_zero_extension_no_signal_dep(self):
        """a & 4'hF 的 bit5：常量零扩展 → 恒 0，a 不是依赖（不得高估）。"""
        tr = _build('''
module top(input [7:0] a, output [7:0] s);
  assign s = a & 4'hF;
endmodule''')
        assert _ids(tr, "top.s[5]") == {"1'b0"}


class TestConcatLiteral:
    def test_literal_segment_bits(self):
        tr = _build('''
module top(input [3:0] a, output [7:0] s, output t);
  assign s = {a, 4'b10};
  assign t = a[1];
endmodule''')
        assert _ids(tr, "top.s[0]") == {"1'b0"}
        assert _ids(tr, "top.s[1]") == {"1'b1"}
        assert _ids(tr, "top.s[5]") == {"top.a[1]"}
