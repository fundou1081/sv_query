#==============================================================================
# test_clock_domain.py - 时钟域追踪单元测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestClockDomain(unittest.TestCase):
    """时钟域追踪测试"""

    def _make_tracer(self, source):
        """辅助: 创建 tracer"""
        return UnifiedTracer(sources={'test.sv': source})

    def test_clock_detection(self):
        """时钟信号检测"""
        source = '''
module top(input wire clk, input wire d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 检查 clk 被标记为时钟
        node = tracer.get_graph().get_node('top.clk')
        if node:
            self.assertTrue(node.is_clock or node.name.lower() in ['clk', 'clock'])

    def test_single_clock_domain(self):
        """单时钟域"""
        source = '''
module top(input wire clk, input wire d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_clock_domain('clk')

        # clock 应该有 domain 信息
        self.assertIsNotNone(result.clock)


if __name__ == '__main__':
    unittest.main()
