"""[iter_290 / PLAN P5.3] 位级 drive/load 精度回归（F1 + F2 + 既有契约）。

锁定三类行为：
  A. **精确**：显式位赋值 / 寄存器位 / struct 成员位 / 位链 / 子模块内有位逻辑
  B. **不得污染**（F1）：切片 LHS、多驱动时，缺位回退只取覆盖该位的切片
  C. **不得断链**（F2）：位节点无 incoming 驱动时，父总线有驱动则补追（总线粒度）

同时保留两类**已文档化的粗粒度**（不承诺位精度，测试只锁"不崩且有答案"）：
  - 拼接：任意位都返回两个操作数（总线粒度）
  - load 方向：表达式驱动只有总线级边，`fanout(a[i])` 返回总线负载
    （但切片/寄存器产生的位节点在 load 方向是**精确**的，见 C3）
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _ids(tr, sig, kind="fanin", depth=None) -> set[str]:
    return {r.id for r in getattr(tr, f"trace_{kind}")(sig, depth=depth)}


def _build(src: str) -> UnifiedTracer:
    t = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    t.build_graph()
    return t


# ---------------------------------------------------------------------------
# A. 精确场景（回归守卫）
# ---------------------------------------------------------------------------
class TestPrecise:
    def test_bit_to_bit(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y[3] = a[7];
endmodule''')
        assert _ids(tr, "top.y[3]") == {"top.a[7]"}

    def test_register_bit(self):
        tr = _build('''
module top(input clk, input [7:0] d, output reg [7:0] q);
  always_ff @(posedge clk) q[3] <= d[1];
endmodule''')
        assert "top.d[1]" in _ids(tr, "top.q[3]")

    def test_struct_member_bit(self):
        tr = _build('''
module top(input [7:0] a, output y);
  typedef struct packed { logic [7:0] addr; logic [7:0] data; } pkt_t;
  pkt_t p;
  assign p.addr = a;
  assign y = p.addr[3];
endmodule''')
        ids = _ids(tr, "top.y")
        assert "top.p.addr[3]" in ids
        assert "top.a" in ids  # F2: 补到 p.addr 的（总线级）驱动

    def test_bit_chain(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  wire [7:0] w;
  assign w[3] = a[3];
  assign y[3] = w[3];
endmodule''')
        ids = _ids(tr, "top.y[3]")
        assert {"top.w[3]", "top.a[3]"} <= ids

    def test_cross_module_per_bit_child(self):
        """子模块内部有位逻辑时，跨模块位对位贯通。"""
        tr = _build('''
module sub(input [7:0] a, output [7:0] y);
  assign y[3] = a[3];
  assign y[2:0] = a[2:0];
endmodule
module top(input [7:0] a, output [7:0] y);
  sub u_sub(.a(a), .y(y));
endmodule''')
        ids = _ids(tr, "top.y[3]")
        assert {"top.u_sub.a[3]", "top.a[3]"} <= ids

    def test_generate_entry_isolation(self):
        tr = _build('''
module leaf(input a, output y);
  assign y = a;
endmodule
module top(input [3:0] a, output [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    leaf u(.a(a[i]), .y(y[i]));
  end endgenerate
endmodule''')
        for i in range(4):
            ids = _ids(tr, f"top.y[{i}]")
            assert f"top.G[{i}].u.y" in ids, ids
            for j in (i + 1) % 4, (i + 2) % 4, (i + 3) % 4:
                assert f"top.G[{j}].u.y" not in ids, f"y[{i}] 串到 entry {j}: {ids}"


# ---------------------------------------------------------------------------
# B. F1：缺位回退不得跨位污染
# ---------------------------------------------------------------------------
class TestNoCrossBitContamination:
    SLICE = '''
module top(input [3:0] a, output [7:0] y);
  assign y[7:4] = a;
  assign y[3:0] = 4'h0;
endmodule'''

    def test_slice_outside_bit_has_no_slice_driver(self):
        """F3: y[7:4]=a (a 4-bit) → y[5] 精确到 a[1]（低位对齐），不含 4'b0。"""
        tr = _build(self.SLICE)
        ids = _ids(tr, "top.y[5]")
        assert "4'b0" not in ids, f"y[5] 不应含 bit[3:0] 的驱动: {ids}"
        assert ids == {"top.a[1]"}, ids

    def test_slice_inside_bit_has_no_other_slice_driver(self):
        tr = _build(self.SLICE)
        ids = _ids(tr, "top.y[2]")
        assert "top.a" not in ids, f"y[2] 不应含 bit[7:4] 的驱动: {ids}"
        assert ids == {"4'b0"}, ids

    def test_multi_driver_no_cross_bit(self):
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y = a;
  assign y[3] = 1'b1;
endmodule''')
        ids = _ids(tr, "top.y[4]")
        assert "1'b1" not in ids, f"y[4] 不应含 bit3 的驱动: {ids}"
        assert ids == {"top.a"}, ids
        assert _ids(tr, "top.y[3]") == {"1'b1"}

    def test_overlapping_slices_only_covering_ones(self):
        tr = _build('''
module top(input [7:0] a, b, output [7:0] y);
  assign y[7:0] = a;
  assign y[3:0] = b;
endmodule''')
        assert _ids(tr, "top.y[5]") == {"top.a[5]"}
        # bit2 被两个切片同时覆盖 → 两个位源都合法（真多驱动）
        assert _ids(tr, "top.y[2]") == {"top.a[2]", "top.b[2]"}

    def test_dangling_bit_has_no_driver(self):
        """切片不覆盖的位：无驱动（而不是回退到别位的切片源）。"""
        tr = _build('''
module sub(input [3:0] a, output [3:0] y);
  assign y[0] = a[0]; assign y[1] = a[1];
  assign y[2] = a[2]; assign y[3] = a[3];
endmodule
module top(input [3:0] a, output [7:0] y);
  sub u_sub(.a(a), .y(y[7:4]));
endmodule''')
        assert _ids(tr, "top.y[3]") == set()


# ---------------------------------------------------------------------------
# C. F2：位节点断链修复
# ---------------------------------------------------------------------------
class TestDeadEndBitLifts:
    def test_expression_bit(self):
        tr = _build('''
module top(input [7:0] a, b, output y);
  wire [7:0] s;
  assign s = a & b;
  assign y = s[3];
endmodule''')
        ids = _ids(tr, "top.y")
        assert "top.s[3]" in ids
        assert {"top.a", "top.b"} <= ids, f"应补到父总线驱动: {ids}"

    def test_ternary_bit(self):
        tr = _build('''
module top(input sel, input [7:0] a, b, output y);
  wire [7:0] m;
  assign m = sel ? a : b;
  assign y = m[3];
endmodule''')
        ids = _ids(tr, "top.y")
        assert {"top.m[3]", "top.a", "top.b"} <= ids, ids

    def test_wire_from_submodule_bit(self):
        tr = _build('''
module sub(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
module top(input [7:0] a, output z);
  wire [7:0] w;
  sub u(.a(a), .y(w));
  assign z = w[3];
endmodule''')
        ids = _ids(tr, "top.z")
        assert "top.w[3]" in ids
        assert "top.u.y" in ids, f"应补到父总线（子模块输出端口）: {ids}"

    def test_top_input_bit_no_lift(self):
        """顶层输入位没有父总线驱动 → 不提升，答案保持精确。"""
        tr = _build('''
module top(input [7:0] data, output y);
  assign y = data[7];
endmodule''')
        assert _ids(tr, "top.y") == {"top.data[7]"}


# ---------------------------------------------------------------------------
# C2. F3：切片按位展开（LHS / RHS / slice→slice）
# ---------------------------------------------------------------------------
class TestSliceBitExpansion:
    def test_lhs_slice_offset(self):
        """y[7:4] = a[3:0] → y[5] 精确到 a[1]（低位对齐）。"""
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y[7:4] = a[3:0];
endmodule''')
        for k, exp in ((0, "top.a[0]"), (1, "top.a[1]"), (2, "top.a[2]"), (3, "top.a[3]")):
            assert _ids(tr, f"top.y[{4 + k}]") == {exp}, f"y[{4+k}] 应映射到 {exp}"

    def test_lhs_slice_from_bus(self):
        """y[7:4] = a（a 4-bit）→ y[5] 精确到 a[1]。"""
        tr = _build('''
module top(input [3:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule''')
        assert _ids(tr, "top.y[5]") == {"top.a[1]"}

    def test_rhs_slice_offset(self):
        """y = a[7:4]（y 4-bit）→ y[2] 精确到 a[6]。"""
        tr = _build('''
module top(input [7:0] a, output [3:0] y);
  assign y = a[7:4];
endmodule''')
        for k, exp in ((0, "top.a[4]"), (2, "top.a[6]"), (3, "top.a[7]")):
            assert _ids(tr, f"top.y[{k}]") == {exp}, f"y[{k}] 应映射到 {exp}"

    def test_slice_to_slice(self):
        """y[7:4] = a[7:4] → 同偏移位对位。"""
        tr = _build('''
module top(input [7:0] a, output [7:0] y);
  assign y[7:4] = a[7:4];
endmodule''')
        assert _ids(tr, "top.y[6]") == {"top.a[6]"}

    def test_no_bit_select_edges_for_synthesized_bits(self):
        """逐位节点不建 BIT_SELECT 聚合边（防父总线提升污染）。"""
        tr = _build('''
module top(input [3:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule''')
        g = tr.get_graph()
        for k in range(4, 8):
            assert g.get_edge(f"top.y[{k}]", "top.y") is None, f"y[{k}] 不应有聚合边"

    def test_short_source_does_not_create_fake_bits(self):
        """源比切片窄：只映射真实存在的位（SV 零扩展，不造不存在的 bit）。"""
        tr = _build('''
module top(input [1:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule''')
        g = tr.get_graph()
        assert "top.a[1]" in g
        assert "top.a[2]" not in g and "top.a[3]" not in g


# ---------------------------------------------------------------------------
# C3. F5：load 方向按位（fanout）
# ---------------------------------------------------------------------------
class TestLoadSideBitPrecision:
    def test_lhs_slice_fanout_bit(self):
        """y[7:4]=a → fanout(a[1]) 精确到 y[5]（不是切片/总线）。"""
        tr = _build('''
module top(input [3:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule''')
        assert _ids(tr, "top.a[1]", kind="fanout") == {"top.y[5]"}

    def test_rhs_slice_fanout_bit(self):
        """y=a[7:4] → fanout(a[6]) 精确到 y[2]。"""
        tr = _build('''
module top(input [7:0] a, output [3:0] y);
  assign y = a[7:4];
endmodule''')
        assert _ids(tr, "top.a[6]", kind="fanout") == {"top.y[2]"}

    def test_register_bit_fanout(self):
        """q[3]<=d[1] → fanout(d[1]) 精确到 q[3]。"""
        tr = _build('''
module top(input clk, input [7:0] d, output reg [7:0] q);
  always_ff @(posedge clk) q[3] <= d[1];
endmodule''')
        assert _ids(tr, "top.d[1]", kind="fanout") == {"top.q[3]"}

    def test_adjacent_bits_not_cross(self):
        """位负载不串位：a[1] 只到 y[5]。"""
        tr = _build('''
module top(input [3:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule''')
        ids = _ids(tr, "top.a[1]", kind="fanout")
        for other in ("top.y[4]", "top.y[6]", "top.y[7]"):
            assert other not in ids, f"a[1] 串到 {other}: {ids}"

    def test_unused_bit_falls_back_to_bus_loads(self):
        """位节点存在但无 load 边 → 回退父总线负载（与 fanin F2 对称）。"""
        tr = _build('''
module top(input [3:0] a, output [7:0] w, output [7:0] z);
  assign w[7:4] = a;
  assign z = w;
endmodule''')
        # w[4] 由 F3 展开建出，但没有位级负载；w 有总线负载 z
        assert _ids(tr, "top.w[4]", kind="fanout") == {"top.z"}

    def test_expression_load_stays_coarse(self):
        """表达式驱动只有总线边 → fanout(a[3]) 返回 s（已知粗粒度，非位精度承诺）。"""
        tr = _build('''
module top(input [7:0] a, b, output y);
  wire [7:0] s;
  assign s = a & b;
  assign y = s[3];
endmodule''')
        assert _ids(tr, "top.a[3]", kind="fanout") == {"top.s"}


# ---------------------------------------------------------------------------
# D. 已文档化的粗粒度（只锁"有答案/不崩"，不承诺位精度）
# ---------------------------------------------------------------------------
class TestDocumentedCoarse:
    def test_concat_is_coarse(self):
        """拼接：任一位都返回两个操作数（总线粒度，KNOWN_LIMITATIONS §3.6）。"""
        tr = _build('''
module top(input [3:0] a, b, output [7:0] y);
  assign y = {a, b};
endmodule''')
        ids = _ids(tr, "top.y[2]")
        assert ids, "拼接位查询不应空答（粗粒度）"
        assert "top.a" in ids and "top.b" in ids

    def test_pure_bus_connection_is_coarse(self):
        tr = _build('''
module sub(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
module top(input [7:0] a, output [7:0] y);
  sub u_sub(.a(a), .y(y));
endmodule''')
        assert _ids(tr, "top.y[3]") == {"top.u_sub.y"}

    def test_fanout_load_side_is_bus_coarse(self):
        """load 方向：表达式驱动只有总线级边 → fanout(bit) 返回总线负载。"""
        tr = _build('''
module top(input [7:0] a, b, output y);
  wire [7:0] s;
  assign s = a & b;
  assign y = s[3];
endmodule''')
        assert _ids(tr, "top.a[3]", kind="fanout") == {"top.s"}


def test_bus_query_still_aggregates_all_slices():
    """总线级查询保持聚合（切片过滤只作用于位查询）。"""
    tr = _build('''
module top(input [3:0] a, output [7:0] y);
  assign y[7:4] = a;
  assign y[3:0] = 4'h0;
endmodule''')
    ids = _ids(tr, "top.y")
    assert {"top.a", "4'b0"} <= ids
