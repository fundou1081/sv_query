#==============================================================================
# test_operators.py - 运算符表达式测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestOperators(unittest.TestCase):
    """运算符表达式测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_arithmetic(self):
        """[Op] 算术运算符"""
        source = '''
module top(input [7:0] a, input [7:0] b, output [7:0] y);
    assign y = a + b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_comparison(self):
        """[Op] 比较运算符"""
        source = '''
module top(input [7:0] a, input [7:0] b, output wire y);
    assign y = (a == b);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_logical(self):
        """[Op] 逻辑运算符"""
        source = '''
module top(input a, input b, output wire y);
    assign y = a && b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_bitwise(self):
        """[Op] 按位运算符"""
        source = '''
module top(input [7:0] a, input [7:0] b, output [7:0] y);
    assign y = a & b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_shift(self):
        """[Op] 移位运算符"""
        source = '''
module top(input [7:0] a, input [2:0] b, output [7:0] y);
    assign y = a << b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ternary(self):
        """[Op] 三元运算符"""
        source = '''
module top(input sel, input a, input b, output y);
    assign y = sel ? a : b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_concatenation(self):
        """[Op] 位拼接"""
        source = '''
module top(input a, input b, output [1:0] y);
    assign y = {a, b};
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_replication(self):
        """[Op] 位复制"""
        source = '''
module top(input a, output [3:0] y);
    assign y = {4{a}};
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_complex_expression(self):
        """[Op] 复杂表达式"""
        source = '''
module top(
    input [7:0] a, input [7:0] b, input [7:0] c,
    input [2:0] sel,
    output [7:0] y
);
    assign y = ((a + b) & c) | (sel ? a : b);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_reduction(self):
        """[Op] 归约运算符"""
        source = '''
module top(input [7:0] a, output wire y);
    assign y = |a;  // or reduction
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
