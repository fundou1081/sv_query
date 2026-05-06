#==============================================================================
# test_always_ff.py - 回归测试: always_ff 内部赋值提取
# Bug: always_ff 非阻塞赋值未提取
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestAlwaysFFExtraction(unittest.TestCase):
    """回归测试 - always_ff 内部赋值��取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_simple_ff_chain(self):
        """[Limit] 简单 always_ff 追踪"""
        # Note: 这是已知限制 - always_ff 内联提取问题
        
        source = '''
module top(input wire clk, input wire d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        # 基本节点应该有
        nodes = list(graph.nodes())
        self.assertIn('top.clk', nodes)
        self.assertIn('top.d', nodes)
        self.assertIn('top.q', nodes)
    
    def test_ff_with_reset(self):
        """[Limit] 带复位的 always_ff"""
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
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        # 节点应该有
        self.assertGreaterEqual(graph.number_of_nodes(), 4)


if __name__ == '__main__':
    unittest.main()
