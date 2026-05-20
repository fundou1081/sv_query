#==============================================================================
# test_rhs_syntax.py - RHS 语法结构系统性测试
# Bug: 多种语法结构未提取
# 按项目纪律: 先写测试，再开发
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestRHSSyntax(unittest.TestCase):
    """RHS 语法结构测试"""
    
    #---------------------------------------------------------------------------
    # 1. 单目运算符
    #---------------------------------------------------------------------------
    def test_unary_not(self):
        """[Golden] 单目 NOT (!)"""
        src = 'module top(input a, output y); assign y = !a; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_unary_tilde(self):
        """[Golden] 单目按位取反 (~)"""
        src = 'module top(input [3:0] a, output [3:0] y); assign y = ~a; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_unary_minus(self):
        """[Golden] 单目负号 (-)"""
        src = 'module top(input [7:0] a, output [7:0] y); assign y = -a; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_unary_and(self):
        """[Golden] 单目归约与 (&)"""
        src = 'module top(input [3:0] a, output y); assign y = &a; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    #---------------------------------------------------------------------------
    # 2. 双目运算符
    #---------------------------------------------------------------------------
    def test_binary_plus(self):
        """[Golden] 加法 (+)"""
        src = 'module top(input a,b, output y); assign y = a + b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_minus(self):
        """[Golden] 减法 (-)"""
        src = 'module top(input a,b, output y); assign y = a - b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_mult(self):
        """[Golden] 乘法 (*)"""
        src = 'module top(input a,b, output y); assign y = a * b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_and(self):
        """[Golden] 按位与 (&)"""
        src = 'module top(input a,b, output y); assign y = a & b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_or(self):
        """[Golden] 按位或 (|)"""
        src = 'module top(input a,b, output y); assign y = a | b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_xor(self):
        """[Golden] 按位异或 (^)"""
        src = 'module top(input a,b, output y); assign y = a ^ b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_sll(self):
        """[Golden] 逻辑左移 (<<)"""
        src = 'module top(input a,b, output y); assign y = a << b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_srl(self):
        """[Golden] 逻辑右移 (>>)"""
        src = 'module top(input a,b, output y); assign y = a >> b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_eq(self):
        """[Golden] 等于 (==)"""
        src = 'module top(input a,b, output y); assign y = (a == b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_ne(self):
        """[Golden] 不等于 (!=)"""
        src = 'module top(input a,b, output y); assign y = (a != b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_lt(self):
        """[Golden] 小于 (<)"""
        src = 'module top(input a,b, output y); assign y = (a < b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_le(self):
        """[Golden] 小于等于 (<=)"""
        src = 'module top(input a,b, output y); assign y = (a <= b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_gt(self):
        """[Golden] 大于 (>)"""
        src = 'module top(input a,b, output y); assign y = (a > b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_binary_ge(self):
        """[Golden] 大于等于 (>=)"""
        src = 'module top(input a,b, output y); assign y = (a >= b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    #---------------------------------------------------------------------------
    # 3. 三目运算符
    #---------------------------------------------------------------------------
    def test_ternary(self):
        """[Golden] 三目运算符 (?😃"""
        src = 'module top(input sel,a,b, output y); assign y = sel ? a : b; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_ternary_nested(self):
        """[Golden] 嵌套三目"""
        src = 'module top(input sel1,sel2,a,b,c,d, output y); assign y = sel1 ? (sel2 ? a : b) : c; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    #---------------------------------------------------------------------------
    # 4. 括号表达式
    #---------------------------------------------------------------------------
    def test_paren(self):
        """[Golden] 括号表达式"""
        src = 'module top(input a,b, output y); assign y = (a + b); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_paren_nested(self):
        """[Golden] 嵌套括号"""
        src = 'module top(input a,b,c, output y); assign y = ((a + b) * c); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    #---------------------------------------------------------------------------
    # 5. 函数调用
    #---------------------------------------------------------------------------
    def test_function_call(self):
        """[Golden] 函数调用"""
        src = '''
module top(input [7:0] a, output [7:0] y);
    function [7:0] foo;
        input [7:0] in;
        begin foo = in + 1; end
    endfunction
    assign y = foo(a);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    #---------------------------------------------------------------------------
    # 6. 复杂表达式
    #---------------------------------------------------------------------------
    def test_complex_expression(self):
        """[Golden] 复杂表达式"""
        src = 'module top(input a,b,c,d, output y); assign y = (a + b) * (c - d); endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_mixed_operators(self):
        """[Golden] 混合运算符"""
        src = 'module top(input a,b,c, output y); assign y = a & b | c; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)


class TestLHSSyntax(unittest.TestCase):
    """LHS 多信号结构测试"""
    
    def test_multi_bit_lhs(self):
        """[Golden] 多位信号"""
        src = 'module top(input [3:0] a, output [3:0] y); assign y = a; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_concat_lhs(self):
        """[Golden] concat LHS"""
        src = 'module top(input a,b,c,d, output [1:0] y); assign y = {a,b}; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_replication_lhs(self):
        """[Golden] 重复复制 LHS"""
        src = 'module top(input a, output [3:0] y); assign y = {2{a}}; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
