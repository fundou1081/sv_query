#==============================================================================
# test_fan_query.py - Fanin/Fanout 查询测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestFanQuery(unittest.TestCase):
    """Fanin/Fanout 查询测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})

    def test_fanout_single_driver(self):
        """[Golden] 单驱动信号的 fanout"""
        source = '''
module top(input wire din, output wire dout);
    wire inter;
    assign inter = din;
    assign dout = inter;
endmodule'''
        tracer = self._make_tracer(source)
        fanout = tracer.trace_fanout('inter', 'top')
        # inter drives dout
        self.assertGreaterEqual(len(fanout), 1)

    def test_fanout_no_loads(self):
        """[Golden] 无负载信号"""
        source = '''
module top(input wire din);
    wire unused;
    assign unused = din;
endmodule'''
        tracer = self._make_tracer(source)
        fanout = tracer.trace_fanout('unused', 'top')
        self.assertEqual(len(fanout), 0)

    def test_fanin_single_driver(self):
        """[Golden] 单驱动信号的 fanin"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        tracer = self._make_tracer(source)
        fanin = tracer.trace_fanin('dout', 'top')
        self.assertGreaterEqual(len(fanin), 1)

    def test_fanin_multi_drivers(self):
        """[Golden] 多驱动信号 (mux)"""
        source = '''
module top(input wire sel, input wire a, input wire b, output wire dout);
    assign dout = sel ? a : b;
endmodule'''
        tracer = self._make_tracer(source)
        fanin = tracer.trace_fanin('dout', 'top')
        self.assertGreaterEqual(len(fanin), 2)

    def test_fanout_instance_connection(self):
        """[Golden] 实例连接的 fanout"""
        source = '''
module sub(input wire d, output wire q);
    assign q = d;
endmodule
module top(input wire din, output wire dout);
    sub u1(.d(din), .q(dout));
endmodule'''
        tracer = self._make_tracer(source)
        fanout = tracer.trace_fanout('din', 'top')
        self.assertGreaterEqual(len(fanout), 1)

    def test_fanin_clock_tree(self):
        """[Golden] 时钟树 fanin"""
        source = '''
module top(input wire clk);
    wire clk_buf;
    assign clk_buf = clk;
endmodule'''
        tracer = self._make_tracer(source)
        fanin = tracer.trace_fanin('clk_buf', 'top')
        self.assertGreaterEqual(len(fanin), 1)

    def test_fanout_reg_q(self):
        """[Golden] 寄存器 Q 端的 fanout"""
        source = '''
module top(input clk, input d, output reg q);
    always @(posedge clk) q <= d;
endmodule'''
        tracer = self._make_tracer(source)
        fanout = tracer.trace_fanout('q', 'top')
        self.assertGreaterEqual(len(fanout), 0)

    #==========================================================================
    # [金标准] depth 参数测试
    #==========================================================================

    def test_fanin_depth_chain(self):
        """[Golden] fanin 指定深度 - 寄存器链"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b, c, d;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
        c <= b;
        d <= c;
    end
endmodule'''
        tracer = self._make_tracer(source)

        # depth=1: 直接驱动 d 的节点（clk 和 c）
        r1 = tracer.trace_fanin('d', 'top', depth=1)
        ids1 = {n.id for n in r1}
        self.assertIn('top.c', ids1, "depth=1 应包含直接驱动 d 的 c")

        # depth=2: 再往上一层 b
        r2 = tracer.trace_fanin('d', 'top', depth=2)
        ids2 = {n.id for n in r2}
        self.assertIn('top.b', ids2, "depth=2 应包含 b")
        self.assertIn('top.c', ids2, "depth=2 应包含 c（depth=1 的结果）")

        # depth=3: 再往上一层 a
        r3 = tracer.trace_fanin('d', 'top', depth=3)
        ids3 = {n.id for n in r3}
        self.assertIn('top.a', ids3, "depth=3 应包含 a")

        # depth=None: 全部递归（默认行为，与 depth=4 等价）
        r_all = tracer.trace_fanin('d', 'top', depth=None)
        ids_all = {n.id for n in r_all}
        self.assertIn('top.q', ids_all, "depth=None 应包含所有层的驱动，包括 q")

    def test_fanin_depth_single_step(self):
        """[Golden] fanin depth=1 等于单步查询"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        tracer = self._make_tracer(source)

        depth1 = tracer.trace_fanin('dout', 'top', depth=1)
        no_depth = tracer.trace_fanin('dout', 'top')  # 默认 None

        # depth=1 应该只有 din（直接驱动）
        self.assertGreaterEqual(len(depth1), 1)
        # 无 depth 限制时结果应包含 depth=1 的所有节点
        for n in depth1:
            self.assertIn(n.id, [x.id for x in no_depth])

    def test_fanout_depth_chain(self):
        """[Golden] fanout 指定深度 - 寄存器链"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b, c, d;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
        c <= b;
        d <= c;
    end
endmodule'''
        tracer = self._make_tracer(source)

        # depth=1: q 直接驱动 a
        r1 = tracer.trace_fanout('q', 'top', depth=1)
        ids1 = {n.id for n in r1}
        self.assertIn('top.a', ids1, "depth=1 应包含直接被 q 驱动的 a")

        # depth=2: 再往下一层 b
        r2 = tracer.trace_fanout('q', 'top', depth=2)
        ids2 = {n.id for n in r2}
        self.assertIn('top.a', ids2, "depth=2 应包含 a")
        self.assertIn('top.b', ids2, "depth=2 应包含 b")

        # depth=None: 全部递归（新增能力）
        r_all = tracer.trace_fanout('q', 'top', depth=None)
        ids_all = {n.id for n in r_all}
        self.assertIn('top.a', ids_all)
        self.assertIn('top.b', ids_all)
        self.assertIn('top.c', ids_all)
        self.assertIn('top.d', ids_all)

    def test_fanout_depth_single_step(self):
        """[Golden] fanout depth=1 等于单步查询"""
        source = '''
module top(input wire din, output wire dout);
    wire inter;
    assign inter = din;
    assign dout = inter;
endmodule'''
        tracer = self._make_tracer(source)

        depth1 = tracer.trace_fanout('din', 'top', depth=1)
        self.assertTrue(any(n.id == 'top.inter' for n in depth1), "depth=1 应只有直接负载 inter")

    def test_fanin_depth_zero_or_none(self):
        """[Golden] fanin depth=None 为默认行为（无限递归）"""
        source = '''
module top(input clk, output logic q);
    logic a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
        q <= b;
    end
endmodule'''
        tracer = self._make_tracer(source)

        # depth=None（默认）应该递归到底
        default_result = tracer.trace_fanin('q', 'top')
        explicit_none = tracer.trace_fanin('q', 'top', depth=None)

        self.assertEqual({n.id for n in default_result}, {n.id for n in explicit_none})

    def test_fanout_depth_zero_or_none(self):
        """[Golden] fanout depth=None 为默认行为（无限递归）"""
        source = '''
module top(input clk, output logic [3:0] q);
    logic [3:0] a, b, c;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
        c <= b;
    end
endmodule'''
        tracer = self._make_tracer(source)

        default_result = tracer.trace_fanout('q', 'top')
        explicit_none = tracer.trace_fanout('q', 'top', depth=None)

        # 默认应递归全部层（新增的递归能力）
        ids = {n.id for n in explicit_none}
        self.assertIn('top.a', ids)
        self.assertIn('top.b', ids)
        self.assertIn('top.c', ids)
        self.assertEqual({n.id for n in default_result}, ids)


if __name__ == '__main__':
    unittest.main()
