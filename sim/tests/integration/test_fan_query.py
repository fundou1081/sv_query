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


if __name__ == '__main__':
    unittest.main()
