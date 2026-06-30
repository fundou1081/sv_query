#==============================================================================
# test_clock_edge.py - CLOCK 边金标准测试
#==============================================================================
"""
[铁律13] 金标准测试
测试 always_ff 块创建 CLOCK 边

金标准 (Golden Standard):
RTL: always_ff @(posedge clk) q <= d;
期望:
  - CLOCK 边: clk -> q (EdgeKind.CLOCK)
  - DRIVER 边: d -> q (EdgeKind.DRIVER, clock_domain="clk")
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind


class TestClockEdge(unittest.TestCase):
    """CLOCK 边测试"""

    def _build_graph(self, source):
        """辅助: 构建图"""
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()

    def test_always_ff_clock_edge(self):
        """[金标准] always_ff @(posedge clk) q <= d;

        期望:
        - CLOCK 边: clk -> q (EdgeKind.CLOCK)
        - DRIVER 边: d -> q (EdgeKind.DRIVER)
        """
        source = '''
module top(input clk, input d, output logic q);
    always_ff @(posedge clk) q <= d;
endmodule'''

        graph = self._build_graph(source)

        # 检查 clk -> q (CLOCK) 边
        clock_srcs = []
        driver_srcs = []
        for pred in graph.predecessors('top.q'):
            edge = graph.get_edge(pred, 'top.q')
            if edge:
                if edge.kind == EdgeKind.CLOCK:
                    clock_srcs.append(pred)
                elif edge.kind == EdgeKind.DRIVER:
                    driver_srcs.append(pred)

        # 验证 CLOCK 边: clk -> q
        self.assertIn('top.clk', clock_srcs,
            f"应该有 CLOCK 边: clk -> q，实际前驱是 {clock_srcs}")

        # 验证 DRIVER 边: d -> q
        self.assertIn('top.d', driver_srcs,
            f"应该有 DRIVER 边: d -> q，实际前驱是 {driver_srcs}")

    def test_always_comb_no_clock_edge(self):
        """[金标准] always_comb 块不应创建 CLOCK 边

        期望: 只有 DRIVER 边
        """
        source = '''
module top(input wire clk, input wire d, output logic q);
    always_comb q = d;
endmodule'''

        graph = self._build_graph(source)

        # 检查只有 DRIVER 边，没有 CLOCK 边
        has_clock_edge = False
        for pred in graph.predecessors('top.q'):
            edge = graph.get_edge(pred, 'top.q')
            if edge and edge.kind == EdgeKind.CLOCK:
                has_clock_edge = True
                break

        self.assertFalse(has_clock_edge, "always_comb 不应该有 CLOCK 边")

    def test_multiple_clock_domains(self):
        """[金标准] 多时钟域

        期望: 每个 always_ff 创建独立的 CLOCK 边
        """
        source = '''
module top(input clk1, input clk2, input d1, input d2, output logic q1, q2);
    always_ff @(posedge clk1) q1 <= d1;
    always_ff @(posedge clk2) q2 <= d2;
endmodule'''

        graph = self._build_graph(source)

        # q1: clk1 -> q1 (CLOCK), d1 -> q1 (DRIVER)
        # q2: clk2 -> q2 (CLOCK), d2 -> q2 (DRIVER)

        q1_clock_srcs = []
        q2_clock_srcs = []
        for pred in graph.predecessors('top.q1'):
            edge = graph.get_edge(pred, 'top.q1')
            if edge and edge.kind == EdgeKind.CLOCK:
                q1_clock_srcs.append(pred)
        for pred in graph.predecessors('top.q2'):
            edge = graph.get_edge(pred, 'top.q2')
            if edge and edge.kind == EdgeKind.CLOCK:
                q2_clock_srcs.append(pred)

        self.assertIn('top.clk1', q1_clock_srcs,
            f"q1 的 CLOCK 边源应该是 clk1，实际是 {q1_clock_srcs}")
        self.assertIn('top.clk2', q2_clock_srcs,
            f"q2 的 CLOCK 边源应该是 clk2，实际是 {q2_clock_srcs}")


if __name__ == '__main__':
    unittest.main()
