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


if __name__ == '__main__':
    unittest.main()
