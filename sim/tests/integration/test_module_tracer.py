#==============================================================================
# test_module_tracer.py - 模块查询集成测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestModuleTracer(unittest.TestCase):
    """模块查询测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_trace_module(self):
        """模块追踪"""
        source = '''
module sub(input wire d, output wire q);
    assign q = d;
endmodule
module top(input wire din, output wire dout);
    sub u1(.d(din), .q(dout));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_module('top')
        
        self.assertIsNotNone(result)
    
    def test_trace_port(self):
        """端口追踪"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_port('top', 'din')
        
        self.assertIsNotNone(result)
    
    def test_find_connected_modules(self):
        """查找连接模块"""
        source = '''
module sub(input wire d, output wire q);
    assign q = d;
endmodule
module top(input wire din, output wire dout);
    sub u1(.d(din), .q(dout));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.find_connected_modules('top')
        
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
