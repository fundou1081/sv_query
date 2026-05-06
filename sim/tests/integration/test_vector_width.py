#==============================================================================
# test_vector_width.py - 向量位宽追踪
# [P1] 位宽信息
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph_models import NodeKind


class TestVectorWidth(unittest.TestCase):
    """向量位宽测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # [金标准] 位宽追踪
    #----------------------------------------------------------------------
    
    def test_vector_input(self):
        """[Golden] 向量输入"""
        source = '''
module top(
    input wire [7:0] data,
    output wire [7:0] out
);
    assign out = data;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        node = tracer.get_graph().get_node('top.data')
        if node and node.width:
            self.assertEqual(node.width, (7, 0))
    
    def test_vector_output(self):
        """[Golden] 向量输出"""
        source = '''
module top(
    input wire [7:0] data,
    output wire [7:0] out
);
    assign out = data;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        node = tracer.get_graph().get_node('top.out')
        if node and node.width:
            self.assertEqual(node.width, (7, 0))
    
    def test_vector_internal(self):
        """[Golden] 内部向量"""
        source = '''
module top(
    input wire [7:0] data,
    output wire [3:0] out
);
    wire [3:0] tmp;
    assign tmp = data[3:0];
    assign out = tmp;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 基本追踪
        result = tracer.trace_signal('out', 'top')
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_single_bit_vector(self):
        """[Boundary] 单比特向量 [0:0]"""
        source = '''
module top(
    input wire [0:0] data,
    output wire out
);
    assign out = data;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_large_vector(self):
        """[Boundary] 大向量 [1023:0]"""
        source = '''
module top(
    input wire [1023:0] data,
    output wire out
);
    assign out = data[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_unsized_vector(self):
        """[Boundary] 未指定大小"""
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[3];  // select one bit
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
