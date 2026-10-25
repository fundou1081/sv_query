"""[iter_285 / PLAN P2.1] drive-load 边缘场景回归。

覆盖主干测试较薄的 4 类形态（全部用最小 fixture，跑得快）：
  1. 位选跨模块（纯总线直连，无 per-bit 节点）→ 总线粒度回退
  2. interface 成员（modport 两侧 + 成员桥）
  3. inout 三态（`assign sda = en ? data : 1'bz`）
  4. struct 成员（成员赋值 / 聚合体查询）
  5. class 属性（类型级成员守卫）

这些用例同时充当两个 P2.1 修复的守卫：
  - interface 成员桥漏传 `TraceNode.width` → 构建直接 TypeError（已修）
  - `fanout(<bit>)` 位节点不存在时返回空集，与 fanin 的总线回退不对称（已修）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _tracer(src: str) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


def _ids(result) -> list[str]:
    return [r.id for r in result]


# ---------------------------------------------------------------------------
# 1. 位选跨模块
# ---------------------------------------------------------------------------
BIT_SRC = """
module sub(input [7:0] a, output [7:0] y);
  assign y = a + 8'd1;
endmodule
module top(input [7:0] din, output [7:0] dout);
  wire [7:0] w;
  sub u_sub(.a(din), .y(w));
  assign dout = w;
endmodule
"""


class TestCrossModuleBitSelect:
    @pytest.fixture(scope="class")
    def tr(self):
        return _tracer(BIT_SRC)

    def test_fanin_bit_lifts_to_bus(self, tr):
        """无 per-bit 节点时，fanin(bit) 回退到总线级驱动（iter_126 契约）。"""
        ids = set(_ids(tr.trace_fanin("top.dout[3]")))
        assert "top.w" in ids or "top.u_sub.y" in ids, ids
        assert not any("[" in i for i in ids), f"总线粒度不该出现位节点: {ids}"

    def test_fanout_bit_lifts_to_bus(self, tr):
        """[P2.1 修复] fanout(bit) 与 fanin 对称：回退到父总线而非空集。"""
        ids = _ids(tr.trace_fanout("top.din[3]"))
        assert ids, "fanout(top.din[3]) 不应为空（父总线有负载）"
        assert "top.u_sub.a" in ids, ids

    def test_fanout_bit_equals_bus(self, tr):
        assert _ids(tr.trace_fanout("top.din[3]")) == _ids(tr.trace_fanout("top.din"))

    def test_part_select_stays_empty(self, tr):
        """带 `:` 的 part-select 保持空答（与 fanin 一致，locked truth）。"""
        assert _ids(tr.trace_fanout("top.din[7:4]")) == []
        assert _ids(tr.trace_fanin("top.dout[7:4]")) == []


# ---------------------------------------------------------------------------
# 2. interface 成员
# ---------------------------------------------------------------------------
IFACE_SRC = """
interface bus_if(input logic clk);
  logic req, gnt;
  modport master (output req, input gnt);
  modport slave  (input req, output gnt);
endinterface
module master(input logic clk, bus_if.master m);
  assign m.req = clk;
endmodule
module slave(input logic clk, bus_if.slave s);
  assign s.gnt = s.req;
endmodule
module top(input logic clk);
  bus_if bf(.clk(clk));
  master u_m(.clk(clk), .m(bf));
  slave  u_s(.clk(clk), .s(bf));
endmodule
"""


class TestInterfaceMembers:
    @pytest.fixture(scope="class")
    def tr(self):
        # [P2.1 修复] 旧实现在这里 TypeError（成员桥 TraceNode 漏 width）
        return _tracer(IFACE_SRC)

    def test_writer_side_fanin(self, tr):
        assert "top.u_m.m.req" in _ids(tr.trace_fanin("top.bf.req"))

    def test_reader_side_fanout(self, tr):
        ids = _ids(tr.trace_fanout("top.bf.req"))
        assert "top.u_s.s.req" in ids, f"reader 侧应收到 interface 成员: {ids}"

    def test_slave_driven_member_fanin(self, tr):
        assert "top.u_s.s.gnt" in _ids(tr.trace_fanin("top.bf.gnt"))

    def test_interface_clock_not_data_source(self, tr):
        """interface 的 clk 端口不应混进数据 fanin。"""
        ids = set(_ids(tr.trace_fanin("top.bf.req")))
        assert "top.bf.clk" not in ids and "top.clk" not in ids, ids


# ---------------------------------------------------------------------------
# 3. inout 三态
# ---------------------------------------------------------------------------
TRI_SRC = """
module top(input logic en, input logic data, inout wire sda, output logic seen);
  assign sda = en ? data : 1'bz;
  assign seen = sda;
endmodule
"""


class TestTriStateInout:
    @pytest.fixture(scope="class")
    def tr(self):
        return _tracer(TRI_SRC)

    def test_fanin_is_data_not_enable(self, tr):
        ids = _ids(tr.trace_fanin("top.sda"))
        assert "top.data" in ids, ids
        assert "top.en" not in ids, f"条件使能不是数据源: {ids}"

    def test_loads_who_reads_inout(self, tr):
        assert "top.seen" in _ids(tr.trace_fanout("top.sda"))


# ---------------------------------------------------------------------------
# 4. struct 成员
# ---------------------------------------------------------------------------
STRUCT_SRC = """
module top(input logic [7:0] a, output logic [7:0] y);
  typedef struct packed { logic [7:0] addr; logic [7:0] data; } pkt_t;
  pkt_t p;
  assign p.addr = a;
  assign p.data = a + 1;
  assign y = p.addr;
endmodule
"""


class TestStructMembers:
    @pytest.fixture(scope="class")
    def tr(self):
        return _tracer(STRUCT_SRC)

    def test_member_fanin(self, tr):
        assert "top.a" in _ids(tr.trace_fanin("top.p.addr"))

    def test_member_fanout(self, tr):
        assert "top.y" in _ids(tr.trace_fanout("top.p.addr"))

    def test_aggregate_fanin_reaches_member_driver(self, tr):
        """查聚合体 p 时能追到成员驱动（不因聚合体无直接驱动而空答）。"""
        ids = _ids(tr.trace_fanin("top.p"))
        assert ids, "struct 聚合体 fanin 不应为空"
        assert "top.a" in ids, ids


# ---------------------------------------------------------------------------
# 5. class 属性（类型级守卫）
# ---------------------------------------------------------------------------
CLASS_FIXTURE = REPO / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_35_class_oop.sv"


class TestClassPropertyGuard:
    @pytest.fixture(scope="class")
    def tr(self):
        p = CLASS_FIXTURE
        t = UnifiedTracer(sources={str(p): p.read_text()}, log_level="ERROR")
        t.build_graph()
        return t

    def test_class_property_fanin_empty(self, tr):
        """类型级 CLASS_PROPERTY 不是数据端点（iter_154 C4-A / D3）。"""
        assert _ids(tr.trace_fanin("packet.addr")) == []

    def test_method_body_driver_still_visible(self, tr):
        """方法体成员赋值仍可沿 fanout 看到（结构建模不丢）。"""
        assert "packet.data" in _ids(tr.trace_fanout("packet.addr"))
