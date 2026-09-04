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
        # depth=None 递归: 真实源 top.a; 自身 top.u_sub.y 不应出现
        ids = {r.id for r in tr.trace_fanin('top.u_sub.y')}
        self.assertEqual(ids, {'top.a'},
                        f"fanin 不应含 internal 自环自身 (A3), 实际 {ids}")

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


if __name__ == '__main__':
    unittest.main()
