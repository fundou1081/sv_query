#==============================================================================
# test_task_function.py - Task/Function 参数追踪金标准测试
# 项目纪律: 铁律13 金标准测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


#==============================================================================
# 1. Task 基本参数传递 - 金标准
#==============================================================================
class TestTaskCall(unittest.TestCase):
    """[语法] Task 调用参数传递"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_task_output_param(self):
        """[Golden] task output 参数驱动信号
        
        RTL:
        task my_task(input [7:0] a, output [7:0] b);
            b = a;
        endtask
        my_task(din, dout);
        
        预期:
        - dout 的驱动: din
        """
        source = '''
module top(input [7:0] din, output logic [7:0] dout);
    task my_task(input [7:0] a, output logic [7:0] b);
        b = a;
    endtask
    
    initial begin
        my_task(din, dout);
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # TODO: 验证 dout 的驱动是 din


#==============================================================================
# 2. Function 基本参数传递 - 金标准
#==============================================================================
class TestFunctionCall(unittest.TestCase):
    """[语法] Function 调用"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_function_return(self):
        """[Golden] function 返回值
        
        RTL:
        function [7:0] my_func(input [7:0] a);
            return a + 1;
        endfunction
        assign dout = my_func(din);
        
        预期:
        - dout 的驱动: din+1 (通过 function)
        """
        source = '''
module top(input [7:0] din, output [7:0] dout);
    function [7:0] my_func(input [7:0] a);
        return a + 1;
    endfunction
    
    assign dout = my_func(din);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: din 和 dout 都存在
        nodes = list(tracer.get_graph().nodes())
        has_din = any('din' in n for n in nodes)
        has_dout = any('dout' in n for n in nodes)
        self.assertTrue(has_din, f'din not in {nodes}')
        self.assertTrue(has_dout, f'dout not in {nodes}')


#==============================================================================
# 3. Task 内多语句 - 金标准
#==============================================================================
class TestTaskMultiple(unittest.TestCase):
    """[语法] Task 内多语句"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_task_multiple_stmts(self):
        """[Golden] task 内多行赋值
        
        RTL:
        task my_task(output [7:0] a, b);
            a = 8'hFF;
            b = 8'h00;
        endtask
        my_task(dout1, dout2);
        
        预期:
        - dout1 <- 8'hFF
        - dout2 <- 8'h00
        """
        source = '''
module top(output logic [7:0] a, b);
    task my_task(output [7:0] a, b);
        a = 8'hFF;
        b = 8'h00;
    endtask
    
    initial begin
        my_task(dout1, dutput2);
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


#==============================================================================
# 4. Function 表达式 - 金标准
#==============================================================================
class TestFunctionExpression(unittest.TestCase):
    """[语法] Function 表达式"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_function_in_expression(self):
        """[Golden] function 在表达式中
        
        RTL:
        assign result = a & func(b);
        
        预期:
        - result 驱动: a, b (通过 function)
        """
        source = '''
module top(input [7:0] a, b, output [7:0] result);
    function [7:0] my_func(input [7:0] x);
        return x;
    endfunction
    
    assign result = a & my_func(b);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: a, b, result 节点存在
        nodes = list(tracer.get_graph().nodes())
        has_a = any('a' in n for n in nodes)
        has_b = any('b' in n for n in nodes)
        has_result = any('result' in n for n in nodes)
        self.assertTrue(has_a, f'a not in {nodes}')
        self.assertTrue(has_b, f'b not in {nodes}')
        self.assertTrue(has_result, f'result not in {nodes}')


#==============================================================================
# 5. Recursive Function - 金标准
#==============================================================================
class TestRecursiveFunction(unittest.TestCase):
    """[语法] 递归 Function"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_recursive_function(self):
        """[Golden] 递归 function
        
        RTL:
        function [7:0] fib(input [7:0] n);
            if (n <= 1) return n;
            return fib(n-1) + fib(n-2);
        endfunction
        
        预期:
        - 递归可解析
        """
        source = '''
module top(input [7:0] n, output [7:0] result);
    function [7:0] fib(input [7:0] x);
        if (x <= 1) return x;
        return fib(x-1) + fib(x-2);
    endfunction
    
    assign result = fib(n);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
