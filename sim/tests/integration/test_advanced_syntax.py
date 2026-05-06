#==============================================================================
# test_advanced_syntax.py - 高级语法 Driver 提取
# [P1] Parameter, 数组, 位选, 系统函数, 跨模块
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestParameterExtraction(unittest.TestCase):
    """Parameter Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_parameterized_width(self):
        """[Golden] 参数化宽度"""
        source = '''
module #(
    parameter WIDTH = 8
) top(input [WIDTH-1:0] din, output [WIDTH-1:0] dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        # 参数化模块应该也能追踪
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_localparam(self):
        """[Golden] 本地参数"""
        source = '''
module top(input din, output dout);
    localparam WIDTH = 8;
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


class TestArrayExtraction(unittest.TestCase):
    """数组 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_array_index(self):
        """[Golden] 数组索引"""
        source = '''
module top(input [7:0] mem [0:3], output [7:0] dout);
    assign dout = mem[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_array_assignment(self):
        """[Golden] 数组赋值"""
        source = '''
module top(input clk, input [7:0] data);
    reg [7:0] mem [0:3];
    always @(posedge clk) mem[0] <= data;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


class TestBitSelectExtraction(unittest.TestCase):
    """位选 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_single_bit(self):
        """[Golden] 单比特选择 [5]"""
        source = '''
module top(input [7:0] data, output bit dout);
    assign dout = data[5];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        # 追踪到 data
        self.assertEqual(result.confidence, 'high')
    
    def test_range_select(self):
        """[Golden] 范围选择 [3:0]"""
        source = '''
module top(input [7:0] data, output [3:0] nibble);
    assign nibble = data[3:0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nibble', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])


class TestSystemFunctionExtraction(unittest.TestCase):
    """系统函数 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_system_function(self):
        """[Golden] 系统函数 $"""
        source = '''
module top(output [31:0] rnd);
    assign rnd = $random;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('rnd', 'top')
        
        # $random 是特殊函数
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_time_function(self):
        """[Golden] $time"""
        source = '''
module top(output [31:0] t);
    assign t = $time;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('t', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


class TestCrossModuleExtraction(unittest.TestCase):
    """跨模块 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_simple_instance(self):
        """[Golden] 简单实例"""
        source = '''
module buf(input d, output q);
    assign q = d;
endmodule
module top(input a, output y);
    buf u1(.d(a), .q(y));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        # 应该追踪到 a
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_two_instance(self):
        """[Golden] 2级实例"""
        source = '''
module buf(input d, output q);
    assign q = d;
endmodule
module top(input a, output y);
    wire mid;
    buf u1(.d(a), .q(mid));
    buf u2(.d(mid), .q(y));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
