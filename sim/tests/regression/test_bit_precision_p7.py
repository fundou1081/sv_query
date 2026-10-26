"""[iter_295 / PLAN P7] 位精确性扩展：直接拷贝 + 纯拼接。

覆盖：
  - P7.1 `assign y = a`（无 op 元数据）的查询层同索引映射
    （one 模式也能位精确，无需 F4 full 扩图；源位节点存在时）
  - 多驱动 `assign y=a; assign y[3]=1'b1` 的完整性（两个驱动都算，不跨位）
  - P7.2 纯拼接 `{a, b}` 按表达式顺序切段（支持 `{a[3:0], b}`）

边界：位节点不存在 → 回落总线；拼接里的字面量段暂不分解（文档化粗粒度）。
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


class TestDirectCopy:
    def test_copy_bit_precise_when_source_bit_exists(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y, output t);
  assign y = a;
  assign t = a[3];
endmodule''')
        assert _ids(tr, "top.y[3]") == {"top.a[3]"}

    def test_copy_load_bit_precise(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y, output t);
  assign y = a;
  assign t = a[3];
endmodule''')
        ids = _ids(tr, "top.a[3]", kind="fanout")
        assert {"top.y[3]", "top.t"} <= ids, ids

    def test_copy_without_bits_is_coarse(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule''')
        assert _ids(tr, "top.y[3]") == {"top.a"}

    def test_multi_driver_includes_both(self):
        """y=a + y[3]=1'b1 → y[3] 两个驱动都返回；y[4] 不含 bit3 的驱动。"""
        tr = _build('''
module top(input [7:0] a, output [7:0] y, output t);
  assign y = a;
  assign y[3] = 1'b1;
  assign t = a[3];
endmodule''')
        assert _ids(tr, "top.y[3]") == {"1'b1", "top.a[3]"}
        assert "1'b1" not in _ids(tr, "top.y[4]")

    def test_multi_driver_falls_back_to_bus(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = a;
  assign y[3] = 1'b1;
endmodule''')
        assert _ids(tr, "top.y[3]") == {"1'b1", "top.a"}


class TestConcat:
    SRC = '''
module top(input [3:0] a, b, output y, u, output [3:0] t);
  wire [7:0] s;
  assign s = {a, b};
  assign y = s[5];
  assign u = s[1];
  assign t = b[1];
  assign v = a[1];
endmodule
'''

    def test_fanin_high_segment(self):
        tr = _build(self.SRC)
        assert _ids(tr, "top.y") == {"top.s[5]", "top.a[1]"}

    def test_fanin_low_segment(self):
        tr = _build(self.SRC)
        assert _ids(tr, "top.u") == {"top.s[1]", "top.b[1]"}

    def test_fanout_segment_offset(self):
        tr = _build(self.SRC)
        ids = _ids(tr, "top.a[1]", kind="fanout")
        assert {"top.s[5]", "top.y", "top.v"} <= ids, ids

    def test_slice_operand_concat(self):
        """`{a[3:0], b}`：操作数边 op=Slice，也要按拼接段映射。"""
        tr = _build('''
module top(input [7:0] a, output [3:0] b, output y, output t);
  wire [7:0] s;
  assign s = {a[3:0], b};
  assign y = s[5];
  assign t = a[1];
endmodule''')
        assert _ids(tr, "top.y") == {"top.s[5]", "top.a[1]"}

    def test_no_cross_operand(self):
        """低段位查询不应把高段操作数拉进来（无位节点时回落到本段总线）。"""
        tr = _build('''
module top(input [3:0] a, b, output [7:0] y);
  assign y = {a, b};
endmodule''')
        ids = _ids(tr, "top.y[2]")
        assert "top.b" in ids and "top.a" not in ids, ids

    def test_literal_segment_stays_coarse(self):
        """`{a, 4'h0}` 的字面量段暂不分解：不崩、有答案（粗粒度，已文档）。"""
        tr = _build('''
module top(input [3:0] a, output [7:0] y);
  assign y = {a, 4'h0};
endmodule''')
        ids = _ids(tr, "top.y[1]")
        assert ids, "不应空答"
