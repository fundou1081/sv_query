#==============================================================================
# test_unified_tracer.py - 统一入口集成测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestUnifiedTracer(unittest.TestCase):
    """统一入口集成测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_build_graph(self):
        """构建信号图"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''

        tracer = self._make_tracer(source)
        graph = tracer.build_graph()

        self.assertIsNotNone(graph)
        self.assertGreater(graph.number_of_nodes(), 0)

    def test_get_graph(self):
        """获取已构建的图"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()

        graph = tracer.get_graph()
        self.assertIsNotNone(graph)

    def test_trace_signal_builds_graph(self):
        """trace_signal 自动构建图"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''

        tracer = self._make_tracer(source)
        # 不手动 build_graph
        result = tracer.trace_signal('dout', 'top')

        # 内部应该已构建
        self.assertIsNotNone(tracer.get_graph())

    def test_stats(self):
        """统计信息"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()

        stats = tracer.stats()
        self.assertIn('nodes', stats)
        self.assertIn('edges', stats)


if __name__ == '__main__':
    unittest.main()
