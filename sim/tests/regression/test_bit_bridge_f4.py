"""[iter_293 / PLAN P5.5 F4] bus↔bus 位桥模式测试（one 默认 / full 可选）。

`GraphBuilder._synthesize_missing_bit_bridges` 的两种模式：
  - `one`（默认）：只给"一侧已有位节点"的连接补位节点（不改 iter_126 契约）
  - `full`：纯总线连接也两侧合成（位查询全贯通，图更大）

DRIVER 只对**直接拷贝**（`assign y = a`）展开；算术/逻辑表达式（`s = a + b`）
的位映射不是同索引，两种模式都必须跳过。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402

PASS_SRC = """
module sub(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
module top(input [7:0] a, output [7:0] y);
  sub u(.a(a), .y(y));
endmodule
"""


def _build(src: str) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


def _ids(tr, sig, kind="fanin") -> set[str]:
    return {r.id for r in getattr(tr, f"trace_{kind}")(sig)}


class TestDefaultOneMode:
    def test_synthesizes_missing_side_when_other_has_bits(self):
        """子模块有位逻辑 → 顶层线网缺位节点 → one 模式补齐并贯通。"""
        tr = _build('''
module sub(input [7:0] a, output [7:0] y);
  assign y[3] = a[3];
  assign y[2:0] = a[2:0];
endmodule
module top(input [7:0] a, output [7:0] w);
  sub u(.a(a), .y(w));
endmodule''')
        ids = _ids(tr, "top.w[3]")
        assert "top.u.a[3]" in ids and "top.a[3]" in ids, ids

    def test_pure_bus_stays_coarse(self):
        """两侧都没有位节点 → 保持总线粒度（iter_126 契约不变）。"""
        tr = _build(PASS_SRC)
        assert _ids(tr, "top.y[3]") == {"top.u.y"}


class TestFullMode:
    def test_pure_bus_is_bit_precise(self, monkeypatch):
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        tr = _build(PASS_SRC)
        assert _ids(tr, "top.y[3]") == {"top.u.a[3]", "top.a[3]"}
        assert _ids(tr, "top.a[3]", kind="fanout") == {
            "top.u.a[3]", "top.u.y[3]", "top.y[3]"}

    def test_direct_copy_is_bit_precise(self, monkeypatch):
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule''')
        assert _ids(tr, "top.y[3]") == {"top.a[3]"}
        assert _ids(tr, "top.a[3]", kind="fanout") == {"top.y[3]"}

    def test_expression_never_expanded(self, monkeypatch):
        """`s = a + b` 的位映射不是同索引（进位）→ full 也必须跳过。"""
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        tr = _build('''
module top(input [7:0] a, b, output y);
  wire [7:0] s;
  assign s = a + b;
  assign y = s[3];
endmodule''')
        assert _ids(tr, "top.a[3]", kind="fanout") == {"top.s"}

    def test_synthesized_bits_have_no_aggregation_edge(self, monkeypatch):
        """合成位节点不加 BIT_SELECT 聚合边（防父总线提升污染）。"""
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        tr = _build(PASS_SRC)
        g = tr.get_graph()
        assert g.get_edge("top.y[3]", "top.y") is None
        assert g.get_edge("top.a[3]", "top.a") is None


class TestModeHandling:
    def test_invalid_mode_falls_back_to_one(self, monkeypatch):
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "bogus")
        tr = _build(PASS_SRC)
        assert _ids(tr, "top.y[3]") == {"top.u.y"}

    def test_mode_can_be_switched_off_with_one(self, monkeypatch):
        """显式 one：纯总线仍粗粒度（默认行为可复现）。"""
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "one")
        tr = _build(PASS_SRC)
        assert _ids(tr, "top.y[3]") == {"top.u.y"}
