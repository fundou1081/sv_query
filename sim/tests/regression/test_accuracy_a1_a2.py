# test_accuracy_a1_a2.py - 准确性审计 A1/A2 回归 (iter_126)
#
# A1: target_module=None 且单 top 时自动以该 top 为 target —
#     generate 实例内部逻辑不再整块缺失 (graph_builder.py:68 gate +
#     driver_extractor.py:1287 type-level 旧路径的默认盲区)
# A2: 纯总线直连的位查询 (top.y[3]) 不再空答 —
#     query/signal.py 位节点不存在时提升到父总线 (总线粒度)
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


def _graph(source, target=None):
    tr = UnifiedTracer(sources={'test.sv': source}, log_level='ERROR')
    return tr, tr.build_graph(use_cache=False, target_module=target)


GENFIX = '''module leaf (input a, output y);
  assign y = a;
endmodule
module top (input [3:0] a, output [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    leaf u_leaf (.a(a[i]), .y(y[i]));
  end endgenerate
endmodule
'''

BUSFIX = '''module sub (input [3:0] a, output [3:0] y);
  assign y = a;
endmodule
module top (input [3:0] a, output [3:0] y);
  sub u_sub (.a(a), .y(y));
endmodule
'''


class TestA1AutoTarget(unittest.TestCase):
    """A1: 单 top 无 target → generate 嵌套实例内部逻辑提取 (不再 type-level 盲区).

    [iter_126 收窄 2026-09-04] A1 flag (auto_target_single_top) 语义:
    - 默认 False: 库 API 保持无 target 类型级多模块契约 (cross_module 等
      测试锁定), generate 实例内部只有输出端口 self-loop DRIVER 标记,
      没有真实 assign 驱动 (a → y 非自环)。
    - True (CLI visualize 入口 build_viz_tracer 在无 --module 时启用):
      generate 实例内部真实驱动恢复 (top.G[i].u_leaf.a → .y)。
    """

    def _real_drivers(self, g, dst):
        """dst 的非自环 DRIVER 源 (真实 assign/驱动, 排除输出端口 self-loop 标记)."""
        srcs = []
        for s, d in g.edges():
            if d != dst:
                continue
            for e in g._edge_data.get((s, d), []):
                if e.kind.name == 'DRIVER' and s != d:
                    srcs.append(s)
        return srcs

    def test_default_library_keeps_type_level_contract(self):
        # 默认 (auto_target_single_top=False): 库 API 旧契约 — generate 实例
        # 内部无真实 assign 驱动 (只有 self-loop 标记), 类型级驱动 leaf.a→leaf.y 在
        tr, g = _graph(GENFIX)
        self.assertIn('leaf.a', self._real_drivers(g, 'leaf.y'),
                      "类型级驱动应在 (leaf.a → leaf.y)")
        self.assertEqual(self._real_drivers(g, 'top.G[3].u_leaf.y'), [],
                         "默认库契约: 实例内部无真实驱动 (A1 flag 未开)")

    def test_generate_internal_present_with_flag(self):
        # CLI 可视化入口等价调用 (auto_target_single_top=True): 实例内部真实
        # assign 驱动恢复 (非自环) — 这是 iter_126 A1 的用户可见收益
        tr = UnifiedTracer(sources={'test.sv': GENFIX}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, auto_target_single_top=True)
        self.assertEqual(self._real_drivers(g, 'top.G[3].u_leaf.y'),
                         ['top.G[3].u_leaf.a'],
                         "flag 开启时实例内部应有真实 a→y DRIVER (A1)")

    def test_top_name_used_as_namespace_with_flag(self):
        tr = UnifiedTracer(sources={'test.sv': GENFIX}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, auto_target_single_top=True)
        # 节点带 'top.' 前缀 (target 命名空间生效, 而非 type-level 'leaf.')
        self.assertTrue(any(n.startswith('top.G[0].u_leaf.') for n in g.nodes()),
                        "节点应落在 top.G[i].u_leaf 命名空间")


class TestA2BusBitFanin(unittest.TestCase):
    """A2: 纯总线直连的位查询不空答 (提升到父总线)."""

    def test_bus_passthrough_bit_fanin(self):
        tr, g = _graph(BUSFIX, target='top')
        res = tr.trace_fanin('top.y[3]')
        ids = {r.id for r in res}
        self.assertTrue(ids, "top.y[3] fanin 不应为空 (A2 修复前空答)")
        self.assertIn('top.u_sub.y', ids,
                      "应指向子模块输出总线 (总线粒度; 位对位折算留待后续)")

    def test_bit_node_case_still_fine(self):
        # 有 per-bit 逻辑 (xor16 风格) 时位查询保持原语义
        src = '''module top (input a, b, output [1:0] y);
  assign y[0] = a ^ b;
  assign y[1] = a & b;
endmodule
'''
        tr, g = _graph(src, target='top')
        res = tr.trace_fanin('top.y[0]')
        ids = {r.id for r in res}
        self.assertTrue({'top.a', 'top.b'} <= ids,
                        f"位查询应含 a,b 实际 {ids}")


BITSUB = '''module sub (input [3:0] a, b, output [3:0] y);
  assign y[0] = a[0] & b[0];
  assign y[1] = a[1] & b[1];
  assign y[2] = a[2] & b[2];
  assign y[3] = a[3] & b[3];
endmodule
module top (input [3:0] a, b, output [3:0] y);
  sub u_sub (.a(a), .b(b), .y(y));
endmodule
'''


class TestA2BitBridge(unittest.TestCase):
    """[iter_137] A2 位对位折算 — 跨实例 bus 桥的位索引贯通.

    iter_126 后 bus 粒度: 子模块输出总线直连顶层位时 fanin(top.y[3]) 停在
    u_sub.y (总线粒度)。iter_137 补同宽同构 bus CONNECTION 的位桥边
    (graph_builder._expand_bus_conn_bit_bridges, 仅两侧位节点都存在时) +
    查询层位桥出口递归 → 顶层位查询贯通到 sub 内部位逻辑。
    纯 bus 直通 (BUSFIX, 无位节点) 保持总线粒度 (不造假节点)。
    """

    def _fanin(self, src, q):
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        return {r.id for r in tr.trace_fanin(q)}

    def test_bit_level_sub_consistent_with_internal(self):
        """顶层位查询 == sub 内位查询 (位对位贯通): 均含 sub 输入端口位 + 顶层输入位."""
        top_q = self._fanin(BITSUB, 'top.y[3]')
        inner_q = self._fanin(BITSUB, 'top.u_sub.y[3]')
        self.assertEqual(top_q, inner_q,
                         "fanin(top.y[3]) 应跨桥后与 fanin(u_sub.y[3]) 一致")
        self.assertTrue({'top.a[3]', 'top.b[3]',
                         'top.u_sub.a[3]', 'top.u_sub.b[3]'} <= top_q,
                        f"应贯通到 a[3]/b[3] (输入跨桥到顶层), 实际 {top_q}")
        self.assertNotIn('top.u_sub.y', top_q,
                         "位粒度答案不应含 bus 粒度 u_sub.y")
        self.assertNotIn('top.u_sub.y[3]', top_q,
                         "位桥中间节点不应作为源 (递归其内部驱动)")

    def test_other_bits_per_entry(self):
        """每位的答案按各自索引 (y[0]/y[2] 不串)."""
        for i, exp in ((0, 'top.a[0]'), (2, 'top.b[2]')):
            ids = self._fanin(BITSUB, f'top.y[{i}]')
            self.assertIn(exp, ids, f"y[{i}] 应含 {exp}, 实际 {ids}")
            self.assertNotIn(f'top.a[{3 - i}]', ids, "不应串其他位")

    def test_bus_passthrough_stays_bus_granularity(self):
        """纯 bus 直通 (BUSFIX, sub assign y=a 无位节点): 保持总线粒度 (iter_126)."""
        ids = self._fanin(BUSFIX, 'top.y[3]')
        self.assertEqual(ids, {'top.u_sub.y'},
                         f"无位节点不建位桥 (不造假节点), 实际 {ids}")


SLICE_OUT = '''module sub (input [3:0] a, output [3:0] y);
  assign y[0] = ~a[0]; assign y[1] = ~a[1]; assign y[2] = ~a[2]; assign y[3] = ~a[3];
endmodule
module top (input [3:0] a, output [7:0] y);
  sub u_sub (.a(a), .y(y[7:4]));
endmodule
'''

SLICE_IN = '''module sub (input [3:0] a, output [3:0] y);
  assign y[0] = a[0]; assign y[1] = a[1]; assign y[2] = a[2]; assign y[3] = a[3];
endmodule
module top (input [7:0] a, output [3:0] y);
  sub u_sub (.a(a[7:4]), .y(y));
endmodule
'''


class TestA2SliceBridge(unittest.TestCase):
    """[iter_143] A2 位对位: 切片/偏移连接 (.y(y[7:4])) 的位级贯通.

    iter_137 同构直连 (bit i ↔ bit i) 后残留: bus↔切片 CONNECTION
    (u_sub.y → top.y[7:4]) 无位桥 — 顶层位 top.y[7] 查询停 bus 粒度。
    修: 位桥第二段处理一端 bus 一端切片 — 声明序低位对齐
    (bus[blo+off] ↔ slice[slo+off]); bus 侧位节点存在时, 切片侧单 bit
    节点缺失则创建 (真实位, 由切片连接驱动); **不建 BIT_SELECT 聚合边**
    (避免 bus 提升查询收位驱动污染, 悬空位 top.y[3] 保持干净)。
    """

    def _fanin(self, src, q):
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        return {r.id for r in tr.trace_fanin(q)}

    def test_output_slice_offset_maps_bits(self):
        """输出切片 y[7:4]: top.y[4+k] fanin == sub y[k] 源 (偏移映射)."""
        for k, exp_a in ((0, 'top.a[0]'), (1, 'top.a[1]'),
                         (2, 'top.a[2]'), (3, 'top.a[3]')):
            ids = self._fanin(SLICE_OUT, f'top.y[{4 + k}]')
            self.assertIn(exp_a, ids,
                          f"y[{4+k}] 应跨切片偏移到 a[{k}], 实际 {ids}")
            self.assertNotIn(f'top.a[{(k + 1) % 4}]', ids,
                             "不应串相邻位")

    def test_output_slice_dangling_bit_clean(self):
        """非切片区悬空位 top.y[3]: bus 粒度且不串切片位驱动 (无污染)."""
        ids = self._fanin(SLICE_OUT, 'top.y[3]')
        self.assertEqual(ids, {'top.u_sub.y'},
                         f"悬空位应保持 bus 粒度且不串位, 实际 {ids}")

    def test_input_slice_offset_maps_bits(self):
        """输入切片 a[7:4]: sub 内 y[k] fanin 跨切片到 top.a[4+k]."""
        for k, exp_a in ((0, 'top.a[4]'), (1, 'top.a[5]'),
                         (2, 'top.a[6]'), (3, 'top.a[7]')):
            ids = self._fanin(SLICE_IN, f'top.u_sub.a[{k}]')
            self.assertEqual(ids, {exp_a},
                             f"u_sub.a[{k}] 应跨输入切片到 {exp_a}, 实际 {ids}")


class TestA3SelfLoopNotDriverSource(unittest.TestCase):
    """A3: 实例输出端口 internal 自环标记不计为驱动源 (iter_127).

    区分两类自环:
    - assign_type="internal" 自环 = connection_extractor output 边1
      (child_signal_id==inst_port_id 恒成立, "模块内部驱动"标记) — 非真实源
    - nonblocking 自环 (state<=state+1) = 真操作数自环 — 保留
    """

    BUSFIX = '''module sub (input a, output y);
  assign y = a;
endmodule
module top (input a, output y);
  sub u_sub (.a(a), .y(y));
endmodule
'''

    SELFFIX = '''module top(input clk, output reg [1:0] state);
    always_ff @(posedge clk) state <= state + 1;
endmodule
'''

    def test_port_selfloop_excluded_from_fanin(self):
        tr = UnifiedTracer(sources={'test.sv': self.BUSFIX}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        # depth=None 递归: 直接驱动 u_sub.a (模块内部 assign) + 递归源 top.a;
        # 自身 top.u_sub.y 不应出现 (A3 核心: internal 自环标记不计源)
        ids = {r.id for r in tr.trace_fanin('top.u_sub.y')}
        self.assertNotIn('top.u_sub.y', ids,
                        f"fanin 不应含 internal 自环自身 (A3), 实际 {ids}")
        self.assertIn('top.u_sub.a', ids, "直接驱动 u_sub.a 应在")
        self.assertIn('top.a', ids, "递归源 top.a 应在")

    def test_port_selfloop_excluded_depth1(self):
        tr = UnifiedTracer(sources={'test.sv': self.BUSFIX}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.u_sub.y', depth=1)}
        self.assertEqual(ids, {'top.u_sub.a'},
                        f"depth=1 直接驱动不应含自身, 实际 {ids}")

    def test_state_self_update_kept(self):
        # nonblocking 自环 (真操作数 state<=state+1) 保留为驱动源
        tr = UnifiedTracer(sources={'test.sv': self.SELFFIX}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.state')}
        self.assertIn('top.state', ids,
                      "时序自更新 state 自环应保留 (A3 只排除 internal 标记)")

    def test_graph_edge_kept_for_other_tools(self):
        # 图结构不改: internal 自环边仍在图中 (out_edges/可视化使用)
        tr = UnifiedTracer(sources={'test.sv': self.BUSFIX}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        loops = [1 for s, d in g.edges()
                 if s == d == 'top.u_sub.y'
                 and any(getattr(e, 'assign_type', '') == 'internal'
                         for e in g._edge_data.get((s, d), []))]
        self.assertTrue(loops, "internal 自环边应保留在图 (A3 只改查询层)")


class TestAuditCandidates(unittest.TestCase):
    """iter_128 待验证候选实测修复锁定:
    - 候选2: struct 字段 fanin 不泄漏兄弟字段 (A2 提升条件 has_driver_edge)
    - 候选4: CLOCK/RESET 边不当作数据驱动源 (跨模块时钟链假驱动)
    - 候选5: 顶层输入 fanin 空答属预期 (外部驱动图内无源)
    """

    STRUCT = '''typedef struct packed {
  logic [7:0] addr;
  logic [7:0] data;
} pkt_t;
module top (input logic [7:0] a, d, output pkt_t p);
  assign p.addr = a;
  assign p.data = d;
endmodule
'''

    CLKDIV = '''module clkdiv (input clk, output reg div2);
  always @(posedge clk) div2 <= ~div2;
endmodule
module top (input clk, output reg [3:0] cnt_b);
  wire div2;
  clkdiv u_div (.clk(clk), .div2(div2));
  always_ff @(posedge div2)
    cnt_b <= cnt_b + 1;
endmodule
'''

    def test_struct_field_fanin_no_sibling_leak(self):
        # 候选2: p.addr ← a (直接 DRIVER), 不应沿 BIT_SELECT 提升到 p 带回 p.data
        tr = UnifiedTracer(sources={'test.sv': self.STRUCT}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertEqual({r.id for r in tr.trace_fanin('top.p.addr')},
                         {'top.a'},
                         "struct 字段 fanin 不应含兄弟字段 (A2 提升误判)")
        self.assertEqual({r.id for r in tr.trace_fanin('top.p')},
                         {'top.a', 'top.d'},
                         "父 struct fanin 应含全部字段驱动")

    def test_clock_edge_not_data_driver(self):
        # 候选4: cnt_b<=cnt_b+1 的数据驱动只有自身; clk/div2 是时序采样边,
        # 不应经跨模块链 (div2←u_div.clk←top.clk) 混入 fanin
        tr = UnifiedTracer(sources={'test.sv': self.CLKDIV}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.cnt_b')}
        self.assertEqual(ids, {'top.cnt_b'},
                        f"fanin(cnt_b) 不应含时钟链 (假驱动), 实际 {ids}")

    def test_clock_as_data_kept(self):
        # assign out = clk: clk 作为数据 (DRIVER continuous) 仍应是驱动源
        src = 'module top (input clk, output out);\n  assign out = clk;\nendmodule\n'
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertIn('top.clk', {r.id for r in tr.trace_fanin('top.out')},
                      "数据用 clk (assign out=clk) 驱动应保留")

    def test_top_input_fanin_empty_is_expected(self):
        # 候选5: 顶层输入端口 = 外部驱动, 图内无源 → fanin 空是预期语义
        src = 'module top (input a, output y);\n  assign y = a;\nendmodule\n'
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertEqual(list(tr.trace_fanin('top.a')), [],
                         "顶层输入 fanin 空 = 外部驱动 (预期, 文档化)")
        # 但它的负载 y 应可追踪 (a 作为源在 fanin(y) 中)
        self.assertIn('top.a', {r.id for r in tr.trace_fanin('top.y')})


class TestInoutCrossModule(unittest.TestCase):
    """iter_129 候选1: inout 跨模块连接 (父线 ↔ 实例端口同线)."""

    SRC = '''module bidir_io (inout wire sda, input wire en, input wire data);
  assign sda = en ? data : 1'bz;
endmodule
module top (inout wire sda, input wire en, input wire data);
  bidir_io u_io (.sda(sda), .en(en), .data(data));
endmodule
'''

    def test_inout_connection_edge(self):
        # 实例 inout 端口 → 父线 CONNECTION (同线, output 式)
        tr = UnifiedTracer(sources={'test.sv': self.SRC}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        conns = [1 for s, d in g.edges()
                 if s == 'top.u_io.sda' and d == 'top.sda'
                 and any(e.kind.name == 'CONNECTION'
                         for e in g._edge_data.get((s, d), []))]
        self.assertTrue(conns, "inout 实例端口→父线应有 CONNECTION (iter_129)")

    def test_inout_fanin_reaches_instance_driver(self):
        # fanin(顶层 inout) 穿透到实例内部三态驱动链 (修复前空答)
        tr = UnifiedTracer(sources={'test.sv': self.SRC}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.sda')}
        self.assertTrue(ids, "顶层 inout fanin 不应空 (iter_129 修复前空答)")
        self.assertIn('top.u_io.data', ids,
                      "应含实例内部驱动源 u_io.data (三态 assign)")

    def test_inout_port_node_kind(self):
        # 回归: PORT_INOUT kind 保持 (不破坏 iter_064 断言)
        tr = UnifiedTracer(sources={'test.sv': self.SRC}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        nd = g.get_node('top.u_io.sda')
        self.assertIsNotNone(nd)
        self.assertEqual(nd.kind.name, 'PORT_INOUT')


class TestInoutTriStateControlExclusion(unittest.TestCase):
    """[iter_139 方案2, 方豆拍板] 三态/条件控制信号 (en/sel) 不进数据 fanin.

    根因 (iter_138 诊断): 三态 `sda = en ? data : z` 的 en 记录在
    data→sda DRIVER.condition 字段 (铁律16) + BRANCH_CONDITION 边;
    fanin 对 BRANCH 链 fallthrough 递归会把使能当数据源 — i2c 双驱动
    场景 en_slave (经实例 PORT_IN→CONNECTION→顶层输入) 混入而
    en_master (顶层直接条件) 缺, 不对称杂音。
    修: BRANCH_*/CASE_* 与 CLOCK/RESET 同规则 — 控制边不 append 不递归。
    """

    I2C = '''module bidir_io (inout wire sda, input wire en, input wire data);
  assign sda = en ? data : 1'bz;
endmodule
module top (inout wire sda,
            input wire en_master, data_master,
            input wire en_slave, data_slave);
  assign sda = en_master ? data_master : 1'bz;
  bidir_io u_slave (.sda(sda), .en(en_slave), .data(data_slave));
endmodule
'''

    TERNARY = '''module top (input a, b, sel, output y);
  assign y = sel ? a : b;
endmodule
'''

    CASE = '''module top (input [1:0] sel, input a, b, c, output reg y);
  always @(*) begin
    case (sel)
      2'd0: y = a;
      2'd1: y = b;
      default: y = c;
    endcase
  end
endmodule
'''

    def _fanin(self, src, q):
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        return {r.id for r in tr.trace_fanin(q)}

    def test_i2c_multidriver_no_en_noise(self):
        """开漏双驱动: 数据源都在, 使能 (en_master/en_slave) 一律不混入."""
        ids = self._fanin(self.I2C, 'top.sda')
        self.assertTrue({'top.data_master', 'top.data_slave',
                         'top.u_slave.data'} <= ids,
                        f"双器件数据源应在, 实际 {ids}")
        self.assertNotIn('top.en_master', ids, "master 使能不应作数据源")
        self.assertNotIn('top.en_slave', ids,
                         f"slave 使能不应作数据源 (iter_138 杂音), 实际 {ids}")

    def test_ternary_condition_not_data_source(self):
        """纯三目: fanin 数据源 {a,b}, 条件 sel 不进."""
        ids = self._fanin(self.TERNARY, 'top.y')
        self.assertEqual(ids, {'top.a', 'top.b'},
                         f"ternary fanin 应只含数据分支, 实际 {ids}")

    def test_case_select_not_data_source(self):
        """case: 各分支数据源 {a,b,c}, 选择信号 sel 不进."""
        ids = self._fanin(self.CASE, 'top.y')
        self.assertEqual(ids, {'top.a', 'top.b', 'top.c'},
                         f"case fanin 应只含分支数据, 实际 {ids}")

    def test_detailed_keeps_condition(self):
        """条件仍可在 DRIVER.condition 查 (fanin_detailed), 不丢失."""
        tr = UnifiedTracer(sources={'test.sv': self.TERNARY}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        conds = {r.id: getattr(r, 'condition', '') for r in tr.trace_fanin_detailed('top.y')}
        self.assertEqual(conds.get('top.a'), 'sel',
                         f"a 的 DRIVER 应带 condition='sel', 实际 {conds}")
        self.assertEqual(conds.get('top.b'), '!(sel)')


class TestInterfaceMemberBridge(unittest.TestCase):
    """iter_129 候选3: interface 成员级桥 (实例端口成员 ↔ interface 实例成员)."""

    WRITER = '''interface bus_if;
  logic [7:0] addr;
endinterface
module writer (bus_if b, input logic [7:0] a);
  assign b.addr = a;
endmodule
module top (input logic [7:0] a);
  bus_if bf();
  writer u_w (.b(bf), .a(a));
endmodule
'''

    COMBINED = '''interface bus_if;
  logic [7:0] addr;
endinterface
module writer (bus_if b, input logic [7:0] a);
  assign b.addr = a;
endmodule
module slave (bus_if b, output logic [7:0] o);
  assign o = b.addr;
endmodule
module top (input logic [7:0] a, output logic [7:0] o);
  bus_if bf();
  writer u_w (.b(bf), .a(a));
  slave u_s (.b(bf), .o(o));
endmodule
'''

    def test_writer_member_bridge_edge(self):
        # 实例驱动成员 (writer assign b.addr=a) → 桥 u_w.b.addr → bf.addr
        tr = UnifiedTracer(sources={'test.sv': self.WRITER}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        conns = [1 for s, d in g.edges()
                 if s == 'top.u_w.b.addr' and d == 'top.bf.addr'
                 and any(e.kind.name == 'CONNECTION'
                         for e in g._edge_data.get((s, d), []))]
        self.assertTrue(conns, "writer 成员驱动桥应存在 (u_w.b.addr→bf.addr)")

    def test_writer_member_fanin_reaches_internal(self):
        # fanin(interface 实例成员) → 实例端口成员 → 内部驱动
        tr = UnifiedTracer(sources={'test.sv': self.WRITER}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids1 = {r.id for r in tr.trace_fanin('top.bf.addr')}
        self.assertEqual(ids1, {'top.u_w.b.addr'},
                         "bf.addr 直接驱动 = writer 端口成员 (粒度层)")
        ids2 = {r.id for r in tr.trace_fanin('top.u_w.b.addr')}
        self.assertTrue({'top.u_w.a', 'top.a'} <= ids2,
                        f"writer 端口成员 fanin 应达 a, 实际 {ids2}")

    def test_slave_read_bridge_direction(self):
        # 只读方 (slave) 桥反向: bf.addr → u_s.b.addr
        tr = UnifiedTracer(sources={'test.sv': self.COMBINED}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        conns = [1 for s, d in g.edges()
                 if s == 'top.bf.addr' and d == 'top.u_s.b.addr'
                 and any(e.kind.name == 'CONNECTION'
                         for e in g._edge_data.get((s, d), []))]
        self.assertTrue(conns, "slave 只读方桥应反向 (bf.addr→u_s.b.addr)")
        # slave 读方 fanin 跨回 interface 线
        ids = {r.id for r in tr.trace_fanin('top.u_s.b.addr')}
        self.assertEqual(ids, {'top.bf.addr'},
                         "slave 端口成员 fanin = interface 实例成员 (粒度层)")
        # 全链: o → u_s.o? (输出端口粒度) → b.addr → bf.addr → u_w.b.addr → a
        ids_o = {r.id for r in tr.trace_fanin('top.u_s.o')}
        self.assertTrue(ids_o, "slave 内部输出应有驱动")

    def test_interface_object_no_fake_clk(self):
        # iter_128 遗留: 无驱动 interface 成员不应有假驱动 (含 clk)
        src = '''interface bus_if (input logic clk);
  logic [7:0] addr;
endinterface
module top (input logic clk);
  bus_if bf (.clk(clk));
endmodule
'''
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertEqual(list(tr.trace_fanin('top.bf.addr')), [],
                         "无驱动 interface 成员 fanin 应空 (无假 clk)")


class TestDataflowBusAggregation(unittest.TestCase):
    """iter_131: dataflow bus→bus 查询聚合所有 per-entry 候选路径.

    回归: _find_paths 找到首个非空候选组合即 return — iter_118 per-entry
    (DRIVER 边 req_i[i]→gnt_o[i]) 后, bus 查询 (req_i → gnt_o) 只枚举
    req_i[0] 一条, 丢 7 位 (arbiter usage golden 40→8→1 暴露). 修复:
    收集并合并所有 (from_candidate × to_candidate) 组合的路径。
    """

    GENFOR = '''module leaf (input a, output y);
  assign y = a;
endmodule
module top (input [3:0] a, output [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    leaf u_leaf (.a(a[i]), .y(y[i]));
  end endgenerate
endmodule
'''

    def _df(self, src):
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        from trace.core.graph.dataflow import DataFlowGraph
        return DataFlowGraph(g, getattr(tr, '_module_graph', None))

    def test_genfor_bus_aggregates_all_entries(self):
        # bus a→y: 4 个 generate entry 各一条路径 (修复前只 a[0]→y[0] 1 条)
        df = self._df(self.GENFOR)
        r = df.analyze('top.a', 'top.y')
        self.assertEqual(r.paths_count, 4,
                         f"bus 查询应聚合 4 entry, got {r.paths_count}")
        tos = sorted({s.to_signal for p in r.paths for s in p.segments
                      if s.to_signal.startswith('top.y[')})
        self.assertEqual(tos, [f'top.y[{i}]' for i in range(4)],
                         f"应覆盖全部输出位, got {tos}")

    def test_bus_passthrough_still_one_path(self):
        # 纯总线直连无分叉: 1 path 不变 (非 bus 多 entry 场景)
        src = '''module sub (input [3:0] a, output [3:0] y);
  assign y = a;
endmodule
module top (input [3:0] a, output [3:0] y);
  sub u_sub (.a(a), .y(y));
endmodule
'''
        df = self._df(src)
        r = df.analyze('top.a', 'top.y')
        self.assertEqual(r.paths_count, 1,
                         f"纯直连应 1 path, got {r.paths_count}")

    def test_single_bit_query_unchanged(self):
        # per-bit 查询语义不变
        df = self._df(self.GENFOR)
        r = df.analyze('top.a[2]', 'top.y[2]')
        self.assertTrue(r.is_reachable)
        self.assertGreaterEqual(r.paths_count, 1)


class TestGeneratePerEntryFaninIsolation(unittest.TestCase):
    """iter_132: generate per-entry fanin 位隔离 (wrapper cross 守卫).

    回归: fanin(top.y[3]) 串入 G[0..2] (G[0].u_leaf.y / top.a[1] 等假源)。
    双根因: ① A2 位提升在"位节点有 incoming CONNECTION"时仍触发 → 提升到
    bus y 全 entry 串; ② PORT_OUT via CONNECTION 的 wrapper cross-instance
    展开无条件跨到 ptt 同 short-name 的所有实例端口 (leaf 4 实例全串)。
    """

    GENFOR = '''module leaf (input a, output y);
  assign y = a;
endmodule
module top (input [3:0] a, output [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    leaf u_leaf (.a(a[i]), .y(y[i]));
  end endgenerate
endmodule
'''

    def test_bit_fanin_isolated_to_own_entry(self):
        tr = UnifiedTracer(sources={'test.sv': self.GENFOR}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        for i in range(4):
            ids = {r.id for r in tr.trace_fanin(f'top.y[{i}]')}
            self.assertEqual(ids, {f'top.G[{i}].u_leaf.y'},
                             f"y[{i}] fanin 应只含本 entry G[{i}], 实际 {ids}")

    def test_bus_fanin_still_aggregates(self):
        # bus 级 fanin 仍聚合 4 entry (不受隔离影响)
        tr = UnifiedTracer(sources={'test.sv': self.GENFOR}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.y')}
        self.assertEqual(ids, {f'top.G[{i}].u_leaf.y' for i in range(4)},
                         f"bus fanin 应聚合 4 entry, 实际 {ids}")

    def test_wrapper_cross_still_works(self):
        # wrapper passthrough (0 internal driver) 跨 instance 不被守卫误伤:
        # 两个实例端口共享 short-name, 但无内部驱动 → 仍跨
        src = '''module inner (input logic a, output logic y);
  assign y = a;
endmodule
module outer (input logic a, output logic y);
  inner u_inner (.a(a), .y(y));
endmodule
module top (input logic a0, a1, output logic y0, y1);
  outer u0 (.a(a0), .y(y0));
  outer u1 (.a(a1), .y(y1));
endmodule
'''
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        # u0.y 由 outer 内部 inner.y 驱动 (非跨实例) — 有内部驱动链
        ids = {r.id for r in tr.trace_fanin('top.u0.y')}
        self.assertTrue(ids, "u0.y 应有驱动")
        self.assertNotIn('top.u1', ' '.join(ids),
                         f"u0.y fanin 不应跨到 u1, 实际 {ids}")


class TestNestedGeneratePathCleanup(unittest.TestCase):
    """iter_134: 嵌套 generate 深层重复段假节点清理.

    回归: 3+ 层 generate (top→G[i]→mid→leaf) 内层实例 (leaf) 的 hp 含祖先
    generate 段 (top.G[i].u_mid.u_leaf), _get_generate_block_name 正则误取
    祖先 G[i] 为 gen_block → get_path 拼出假节点 u_mid.G[i].u_leaf
    (aes ROUND[1].U_ROUND.ROUND[1].U_SUB ×351 / cordic U.genblk1[i] ×105)。
    修复: gen_block 只取 hp 中紧邻实例名的直接宿主 generate 段。
    """

    NESTED = '''module leaf (input a, output y);
  assign y = a;
endmodule
module mid (input a, output y);
  leaf u_leaf (.a(a), .y(y));
endmodule
module top (input [3:0] a, output [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    mid u_mid (.a(a[i]), .y(y[i]));
  end endgenerate
endmodule
'''

    def test_no_dup_generate_segment(self):
        # 内层实例路径不应重复外层 generate 段 (u_mid.G[i].u_leaf 假节点)
        tr = UnifiedTracer(sources={'test.sv': self.NESTED}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        dups = [n for n in g.nodes() if '.u_mid.G[' in n]
        self.assertEqual(dups, [],
                         f"不应有 u_mid.G[i] 重复段假节点, got {dups[:4]}")

    def test_inner_leaf_path_correct(self):
        # leaf 正确路径: top.G[i].u_mid.u_leaf (无 G[i] 段)
        tr = UnifiedTracer(sources={'test.sv': self.NESTED}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        self.assertTrue(
            any(n.startswith('top.G[2].u_mid.u_leaf.')
                for n in g.nodes()),
            "leaf 应挂在 top.G[i].u_mid.u_leaf (直接宿主链)")

    def test_mid_fanin_reaches_leaf_driver(self):
        # 链可达且无跨 entry: y[2] fanin 全在 G[2] 内 (u_mid.y + 内部 leaf
        # 链 + top.a[2]), G[0]/G[1]/G[3] 绝不应出现。
        # [iter_134] wrapper_passthrough 自递归: u_mid.y 由内部 u_leaf.y
        # passthrough 驱动 → 递归追到 leaf.a / top.a[2] (非粒度停)。
        tr = UnifiedTracer(sources={'test.sv': self.NESTED}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.y[2]')}
        self.assertIn('top.G[2].u_mid.y', ids,
                      "y[2] fanin 应含 G[2] 内 mid 输出")
        self.assertIn('top.G[2].u_mid.u_leaf.a', ids,
                      f"应递归到 G[2] 内 leaf 驱动 (u_leaf.a), 实际 {ids}")
        for i in (0, 1, 3):
            cross = {x for x in ids if f'.G[{i}].' in x}
            self.assertEqual(cross, set(), f"不应含 G[{i}] (跨 entry), got {cross}")
        # 逐层到底
        deep = {r.id for r in tr.trace_fanin('top.G[2].u_mid.u_leaf.y')}
        self.assertTrue(deep, "leaf.y fanin 应有内部驱动")
        self.assertNotIn('top.y[3]', ' '.join(deep))


if __name__ == '__main__':
    unittest.main()
