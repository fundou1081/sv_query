#==============================================================================
# test_functions.py - 函数和任务测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestFunctions(unittest.TestCase):
    """函数和任务测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_function_simple(self):
        """[Complex] 简单函数"""
        source = '''
module top(
    input wire [7:0] a,
    input wire [7:0] b,
    output wire [7:0] y
);
    function [7:0] add;
        input [7:0] x;
        input [7:0] y;
        add = x + y;
    endfunction
    
    assign y = add(a, b);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_function_recursive(self):
        """[Complex] 递归函数"""
        source = '''
module top(
    input wire [7:0] n,
    output wire [7:0] result
);
    function [7:0] factorial;
        input [7:0] x;
        if (x <= 1)
            factorial = 1;
        else
            factorial = x * factorial(x - 1);
    endfunction
    
    assign result = factorial(n);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('result', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_task_simple(self):
        """[Complex] 简单任务"""
        source = '''
module top(
    input wire clk,
    input wire [7:0] data
);
    task send_byte_task;
        input [7:0] byte_data;
        begin
            // send logic
        end
    endtask
    
    always @(posedge clk)
        send_byte_task(data);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_function_with_extends(self):
        """[Complex] 函数返回类型"""
        source = '''
module top(
    input wire [7:0] a,
    output wire [15:0] y
);
    function [15:0] extend;
        input [7:0] x;
        extend = {8'h00, x};
    endfunction
    
    assign y = extend(a);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_static_function(self):
        """[Complex] 静态函数"""
        source = '''
module top(input wire [7:0] a, output wire [7:0] y);
    function static [7:0] incr;
        input [7:0] x;
        incr = x + 1;
    endfunction
    assign y = incr(a);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
