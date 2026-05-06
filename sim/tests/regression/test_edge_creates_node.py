#==============================================================================
# test_edge_creates_node.py - 回归测试: Edge 创建时同时创建 Node
# Bug: Edge 存在但 Node 数据为空
# 修复: DriverExtractor.extract() 中同时创建 TraceNode
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestEdgeCreatesNode(unittest.TestCase):
    """回归测试 - Edge 必须创建对应 Node (Bug #1)"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_assign_creates_node(self):
        """[BugFix] assign 边必须创建节点"""
        # 之前: Edge 存在但 get_node() 返回 None
        # 修复后: 创建 Edge 时同时创建 TraceNode
        
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        # 验证节点存在
        self.assertTrue(graph.has_node('top.din'))
        self.assertTrue(graph.has_node('top.dout'))
        
        # 验证 get_node 返回数据
        node = graph.get_node('top.dout')
        self.assertIsNotNone(node)
    
    def test_driver_lookup_after_trace(self):
        """[BugFix] 追踪后能正确找到驱动"""
        # 之前: drivers 列表为空
        # 修复后: drivers 包含正确的节点
        
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        # drivers 不应为空
        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.din', driver_ids)
    
    def test_load_lookup_after_trace(self):
        """[BugFix] 追踪后能正确找到负载"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('din', 'top')
        
        # loads 不应为空
        load_ids = [l.id for l in result.loads]
        self.assertIn('top.dout', load_ids)


if __name__ == '__main__':
    unittest.main()
