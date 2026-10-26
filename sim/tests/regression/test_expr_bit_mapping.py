"""[iter_294 / PLAN P6] 表达式驱动的逐位映射（查询层）。

`TraceEdge.source`（SignalSource）带 op / operand_side / bit_start,end，
按运算符把 `s[i]` 映射到操作数位（fanin），反向映射到结果位（fanout）：

  - 位运算（& | ^ ~）：同索引
  - 加/减/乘：fanin 前缀（进位，sound 保守）；fanout 后缀
  - 常量移位：`s[i] ← a[i∓k]`
  - 切片（Slice）：低位对齐
  - 比较/逻辑/变量移位：不做逐位（总线粒度）

位节点不存在时回落总线（保持完整，粒度退化），不合成节点（图结构不变）。
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


AND_BITS = """
module top(input [7:0] a, b, output y, t, u);
  wire [7:0] s;
  assign s = a & b;
  assign y = s[3];
  assign t = a[3];
  assign u = b[3];
endmodule
"""

ADD_BITS = """
module top(input [7:0] a, b, output y, output [2:0] ta, tb);
  wire [8:0] s;
  assign s = a + b;
  assign y = s[2];
  assign ta = {a[2], a[1], a[0]};
  assign tb = {b[2], b[1], b[0]};
endmodule
"""


class TestFaninExprBits:
    def test_bitwise_same_index(self):
        tr = _build(AND_BITS)
        assert _ids(tr, "top.y") == {"top.s[3]", "top.a[3]", "top.b[3]"}

    def test_bitwise_depth1_consistent(self):
        tr = _build(AND_BITS)
        assert _ids(tr, "top.s[3]", depth=1) == {"top.a[3]", "top.b[3]"}

    def test_add_prefix_bits(self):
        tr = _build(ADD_BITS)
        ids = _ids(tr, "top.y")
        for i in range(3):
            assert f"top.a[{i}]" in ids and f"top.b[{i}]" in ids, ids
        assert "top.a[3]" not in ids, f"进位只来自低位，不该含 a[3]: {ids}"

    def test_shift_constant(self):
        tr = _build('''
module top(input [7:0] a, output y, output [3:0] t);
  wire [7:0] s;
  assign s = a << 2;
  assign y = s[3];
  assign t = a[1];
endmodule''')
        assert "top.a[1]" in _ids(tr, "top.y")

    def test_partial_bits_fall_back_to_bus(self):
        """只有一侧位节点存在时：已有位精确，缺位侧回落总线（完整、不丢源）。"""
        tr = _build('''
module top(input [7:0] a, b, output y, output [2:0] ta);
  wire [8:0] s;
  assign s = a + b;
  assign y = s[2];
  assign ta = {a[2], a[1], a[0]};
endmodule''')
        ids = _ids(tr, "top.y")
        assert {"top.a[0]", "top.a[1]", "top.a[2]", "top.b"} <= ids, ids

    def test_missing_bits_keep_bus_fallback(self):
        """没有任何位节点 → 回落总线（与 P6 之前一致）。"""
        tr = _build('''
module top(input [7:0] a, b, output y);
  wire [7:0] s;
  assign s = a & b;
  assign y = s[3];
endmodule''')
        ids = _ids(tr, "top.y")
        assert {"top.a", "top.b"} <= ids, ids

    def test_compare_has_no_bit_mapping(self):
        """比较结果 1 bit，所有位都可能影响 → 总线粒度（不做逐位）。"""
        tr = _build('''
module top(input [7:0] a, b, output y);
  wire eq;
  assign eq = (a == b);
  assign y = eq;
endmodule''')
        ids = _ids(tr, "top.y")
        assert "top.a[0]" not in ids, ids


class TestFanoutExprBits:
    def test_bitwise_same_index(self):
        tr = _build(AND_BITS)
        assert _ids(tr, "top.a[3]", kind="fanout") >= {"top.s[3]", "top.y"}

    def test_no_cross_bit_load(self):
        tr = _build(AND_BITS)
        ids = _ids(tr, "top.a[3]", kind="fanout")
        assert "top.s[2]" not in ids and "top.s[4]" not in ids, ids

    def test_add_suffix_bits(self):
        tr = _build(ADD_BITS)
        ids = _ids(tr, "top.a[1]", kind="fanout")
        assert "top.s[2]" in ids and "top.y" in ids, ids

    def test_shift_constant(self):
        tr = _build('''
module top(input [7:0] a, output y, output [3:0] t);
  wire [7:0] s;
  assign s = a << 2;
  assign y = s[3];
  assign t = a[1];
endmodule''')
        assert "top.s[3]" in _ids(tr, "top.a[1]", kind="fanout")

    def test_depth1_consistent(self):
        tr = _build(AND_BITS)
        assert "top.s[3]" in _ids(tr, "top.a[3]", kind="fanout", depth=1)

    def test_bus_query_stays_bus(self):
        """总线查询不做逐位映射（避免把位答案混进总线答案）。"""
        tr = _build(AND_BITS)
        assert _ids(tr, "top.a", kind="fanout") == {"top.s"}


class TestNoWrongBits:
    def test_add_prefix_no_high_bit(self):
        tr = _build(ADD_BITS)
        ids = _ids(tr, "top.y")
        assert "top.a[3]" not in ids and "top.b[3]" not in ids

    def test_shift_out_of_range_bit_empty(self):
        """左移 2：s[0]/s[1] 不依赖 a[0] 之外的位（越界位返回空，不瞎连）。"""
        tr = _build('''
module top(input [7:0] a, output y, output [3:0] t);
  wire [7:0] s;
  assign s = a << 2;
  assign y = s[3];
  assign t = a[1];
endmodule''')
        assert "top.a[0]" not in _ids(tr, "top.y")
