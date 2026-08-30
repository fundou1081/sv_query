#==============================================================================
# test_always_ff.py - 回归测试: always_ff 内部赋值提取
# Bug: always_ff 非阻塞赋值未提取
#
# [iter_064 2026-08-29] 升级断言强度: 保留原有节点存在断言, 补充
# UnifiedTracer + graph.get_edge 行为断言 — 验证 always_ff 的非阻塞
# 赋值确实生成了 DRIVER 边 (assign_type=nonblocking) + CLOCK 边 +
# 异步复位 RESET 边 (行为金标准).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.graph.models import EdgeKind
from trace.unified_tracer import UnifiedTracer


class TestAlwaysFFExtraction(unittest.TestCase):
    """回归测试 - always_ff 内部赋值提取"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        """[iter_064] 构建 tracer graph 的统一 helper (行为断言用)"""
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_simple_ff_chain(self):
        """[Limit] 简单 always_ff 追踪
        RTL: always_ff @(posedge clk) q <= d;
        金标准:
        - top.clk / top.d / top.q 节点存在
        - [iter_064] top.d → top.q DRIVER 边存在 (assign_type=nonblocking)
        - [iter_064] top.clk → top.q CLOCK 边存在 (assign_type=nonblocking)
        """
        # Note: 这是已知限制 - always_ff 内联提取问题

        source = '''
module top(input wire clk, input wire d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''

        graph = self._build_graph(source)

        # 基本节点应该有
        nodes = list(graph.nodes())
        self.assertIn('top.clk', nodes)
        self.assertIn('top.d', nodes)
        self.assertIn('top.q', nodes)

        # [iter_064] 行为断言: always_ff 非阻塞赋值应生成 DRIVER + CLOCK 边
        driver_edge = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(driver_edge, "always_ff q <= d 应生成 d→q DRIVER 边")
        self.assertEqual(driver_edge.assign_type, 'nonblocking',
            "always_ff q <= d 边应标记为 nonblocking")

        clock_edge = graph.get_edge('top.clk', 'top.q')
        self.assertIsNotNone(clock_edge, "always_ff @(posedge clk) 应生成 clk→q CLOCK 边")
        self.assertEqual(clock_edge.kind, EdgeKind.CLOCK,
            f"clk→q 边 kind 应为 CLOCK, 实际 {clock_edge.kind}")
        self.assertEqual(clock_edge.assign_type, 'nonblocking',
            "CLOCK 边 assign_type 应为 nonblocking (沿用所属 always_ff 块)")

    def test_ff_with_reset(self):
        """[Limit] 带复位的 always_ff
        RTL: always_ff @(posedge clk or negedge rst_n) begin
                 if (!rst_n) q <= 0;
                 else         q <= d;
             end
        金标准:
        - 节点数 ≥ 4 (clk, rst_n, d, q)
        - [iter_064] top.d → top.q DRIVER 边存在 (assign_type=nonblocking),
          条件为复位后使能路径
        - [iter_064] top.rst_n → top.q RESET 边存在
        - [iter_064] top.clk → top.q CLOCK 边存在 (异步复位多分支)
        """
        source = '''
module top(
    input wire clk,
    input wire rst_n,
    input wire d,
    output reg q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule'''

        graph = self._build_graph(source)

        # 节点应该有
        self.assertGreaterEqual(graph.number_of_nodes(), 4)

        # [iter_064] 行为断言: always_ff 异步复位结构应生成 DRIVER/CLOCK/RESET 三类边
        # 数据路径: d → q (复位后使能)
        driver_edges = graph.get_edges('top.d', 'top.q')
        self.assertGreaterEqual(len(driver_edges), 1,
            "复位后数据路径应生成 d→q DRIVER 边")
        # 数据路径的 assign_type 应为 nonblocking
        self.assertTrue(any(e.assign_type == 'nonblocking' for e in driver_edges),
            "d→q DRIVER 边 assign_type 应为 nonblocking")

        # 异步复位: rst_n → q RESET 边
        reset_edges = graph.get_edges('top.rst_n', 'top.q')
        self.assertGreaterEqual(len(reset_edges), 1,
            "异步复位应生成 rst_n→q RESET 边")
        self.assertTrue(all(e.kind == EdgeKind.RESET for e in reset_edges),
            f"rst_n→q 边 kind 应全为 RESET, 实际 {[e.kind for e in reset_edges]}")

        # 时钟: clk → q CLOCK 边
        clock_edges = graph.get_edges('top.clk', 'top.q')
        self.assertGreaterEqual(len(clock_edges), 1,
            "异步复位结构应生成 clk→q CLOCK 边")
        self.assertTrue(all(e.kind == EdgeKind.CLOCK for e in clock_edges),
            f"clk→q 边 kind 应全为 CLOCK, 实际 {[e.kind for e in clock_edges]}")


if __name__ == '__main__':
    unittest.main()
