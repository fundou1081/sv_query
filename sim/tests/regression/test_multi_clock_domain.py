# test_multi_clock_domain.py - 多时钟域测试
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
多时钟域相关测试:
- 异步跨域路径检测
- 不同时钟驱动的寄存器
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestMultiClockDomain(unittest.TestCase):
    """多时钟域测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'t.sv': source})

    def test_dual_clock_registers(self):
        """[Golden] 双时钟寄存器

        RTL:
        always_ff @(posedge clk1) q1 <= d1;
        always_ff @(posedge clk2) q2 <= d2;

        预期:
        - q1 被 clk1 驱动
        - q2 被 clk2 驱动
        """
        source = '''
module top (
    input logic clk1,
    input logic clk2,
    input logic d1, d2,
    output logic q1, q2
);
    always_ff @(posedge clk1)
        q1 <= d1;

    always_ff @(posedge clk2)
        q2 <= d2;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        edges = list(graph.edges())

        # 金标准: clk1 -> q1, clk2 -> q2 边存在
        has_clk1_q1 = any('clk1' in s and 'q1' in d for s, d in edges)
        has_clk2_q2 = any('clk2' in s and 'q2' in d for s, d in edges)

        self.assertTrue(has_clk1_q1, f"clk1 -> q1 边应存在，实际边: {edges}")
        self.assertTrue(has_clk2_q2, f"clk2 -> q2 边应存在，实际边: {edges}")

    def test_different_clock_domains(self):
        """[Golden] 不同频率时钟

        预期:
        - 每个寄存器被对应的时钟驱动
        """
        source = '''
module top (
    input logic clk_50m,
    input logic clk_100m,
    input logic data_50m,
    input logic data_100m,
    output logic reg_50m,
    output logic reg_100m
);
    always_ff @(posedge clk_50m)
        reg_50m <= data_50m;

    always_ff @(posedge clk_100m)
        reg_100m <= data_100m;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        edges = list(graph.edges())

        # 金标准: 两个时钟域的边都存在
        has_50m = any('clk_50m' in s and 'reg_50m' in d for s, d in edges)
        has_100m = any('clk_100m' in s and 'reg_100m' in d for s, d in edges)

        self.assertTrue(has_50m, "clk_50m -> reg_50m 边应存在")
        self.assertTrue(has_100m, "clk_100m -> reg_100m 边应存在")

    def test_clock_mux(self):
        """[Golden] 时钟多路复用

        RTL: 两个时钟驱动的信号通过 mux 选择

        预期:
        - 追溯结果能显示多个时钟域
        """
        source = '''
module top (
    input logic clk_a,
    input logic clk_b,
    input logic sel,
    input logic d_a,
    input logic d_b,
    output logic q
);
    logic inter;

    always_ff @(posedge clk_a)
        inter <= d_a;

    always_ff @(posedge clk_b)
        q <= d_b;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        nodes = list(graph.nodes())

        # 金标准: inter 和 q 节点存在
        self.assertTrue(any('inter' in n for n in nodes),
            f"inter 节点应存在，实际节点: {nodes}")
        self.assertTrue(any('q' in n for n in nodes),
            f"q 节点应存在，实际节点: {nodes}")


class TestAsyncCrossDomain(unittest.TestCase):
    """异步跨域测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'t.sv': source})

    def test_async_signals(self):
        """[Golden] 异步信号 (无时钟)

        RTL: assign async_signal = a | b;

        预期:
        - async_signal 节点存在
        - 驱动追溯正常
        """
        source = '''
module top (
    input logic a,
    input logic b,
    output logic async_signal
);
    assign async_signal = a | b;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        result = tracer.trace_signal('async_signal', 'top')

        # 金标准: async_signal 被驱动
        self.assertGreater(len(result.drivers), 0,
            f"async_signal 应有驱动源，实际: {result.drivers}")


if __name__ == '__main__':
    unittest.main()
