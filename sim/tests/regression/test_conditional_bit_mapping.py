"""[iter_306 / PLAN P13.5] 三元/case 分支按位映射（查询层）。

`m = sel ? a : b; y = m[3]`：
  - 分支源位节点存在时：fanin(y) = {m[3], a[3], b[3]}（不再 a/b 总线）
  - 分支源位节点缺失时：回落总线（P13.2 的 coarse_fallback 会标记）
case 语句同理（条件分支边 + direct copy）。

条件信号本身不并入 fanin（沿用现有语义：条件是控制，不是数据源）。
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


def _ids(tr, sig, kind="fanin") -> set[str]:
    return {r.id for r in getattr(tr, f"trace_{kind}")(sig)}


class TestTernaryBitMapping:
    SRC = """
module top(input sel, input [7:0] a, b, output [7:0] m, output y, ta, tb);
  assign m = sel ? a : b;
  assign y = m[3];
  assign ta = a[3];
  assign tb = b[3];
endmodule
"""

    def test_fanin_branch_bits(self):
        tr = _build(self.SRC)
        assert _ids(tr, "top.y") == {"top.m[3]", "top.a[3]", "top.b[3]"}

    def test_fanout_branch_bit(self):
        tr = _build(self.SRC)
        ids = _ids(tr, "top.a[3]", kind="fanout")
        assert {"top.ta", "top.m[3]", "top.y"} <= ids, ids

    def test_fallback_without_branch_bits(self):
        tr = _build("""
module top(input sel, input [7:0] a, b, output [7:0] m, output y);
  assign m = sel ? a : b;
  assign y = m[3];
endmodule""")
        assert _ids(tr, "top.y") == {"top.m[3]", "top.a", "top.b"}

    def test_width_mismatch_stays_coarse(self):
        """分支宽度不等时不做同索引映射（避免错位）。"""
        tr = _build("""
module top(input sel, input [3:0] a, input [7:0] b, output [7:0] m, output y);
  assign m = sel ? a : b;
  assign y = m[3];
endmodule""")
        ids = _ids(tr, "top.y")
        assert "top.a" in ids and "top.b" in ids, ids
        assert "top.a[3]" not in ids


class TestCaseBitMapping:
    SRC = """
module top(input [1:0] sel, input [7:0] a, b, output reg [7:0] s,
           output y, ta, tb);
  always_comb case (sel)
    2'd0: s = a;
    default: s = b;
  endcase
  assign y = s[3];
  assign ta = a[3];
  assign tb = b[3];
endmodule
"""

    def test_case_fanin_branch_bits(self):
        tr = _build(self.SRC)
        assert _ids(tr, "top.y") == {"top.s[3]", "top.a[3]", "top.b[3]"}

    def test_case_fanout_branch_bit(self):
        tr = _build(self.SRC)
        ids = _ids(tr, "top.b[3]", kind="fanout")
        assert {"top.tb", "top.s[3]", "top.y"} <= ids, ids

    def test_condition_not_a_data_source(self):
        tr = _build(self.SRC)
        assert "top.sel" not in _ids(tr, "top.y")
