#==============================================================================
# test_operators.py - 运算符表达式测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestOperators(unittest.TestCase):
    """运算符表达式测试"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    #==========================================================================
    # 算术运算符
    #==========================================================================
    
    def test_arithmetic(self):
        """[Op] 算术运算符: assign y = a + b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input [7:0] a, input [7:0] b, output [7:0] y);
    assign y = a + b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "y = a + b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 比较运算符
    #==========================================================================
    
    def test_comparison(self):
        """[Op] 比较运算符: assign y = (a == b);
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input [7:0] a, input [7:0] b, output wire y);
    assign y = (a == b);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "y = (a == b) 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 逻辑运算符
    #==========================================================================
    
    def test_logical(self):
        """[Op] 逻辑运算符: assign y = a && b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input a, input b, output wire y);
    assign y = a && b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "y = a && b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 按位运算符
    #==========================================================================
    
    def test_bitwise(self):
        """[Op] 按位运算符: assign y = a & b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input [7:0] a, input [7:0] b, output [7:0] y);
    assign y = a & b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "y = a & b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 移位运算符
    #==========================================================================
    
    def test_shift(self):
        """[Op] 移位运算符: assign y = a << b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input [7:0] a, input [2:0] b, output [7:0] y);
    assign y = a << b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "y = a << b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 三元运算符 - 关键: sel 是控制信号，必须参与驱动追踪
    #==========================================================================
    
    def test_ternary(self):
        """[Op] 三元运算符: assign y = sel ? a : b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [sel, a, b] | high |
        
        注意: sel 是条件选择信号，控制 a/b 的选择，必须参与驱动追踪
        """
        source = '''
module top(input sel, input a, input b, output y);
    assign y = sel ? a : b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 3,
            "y = sel ? a : b 应有 3 个驱动源 (sel, a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.sel', ids, "y 的驱动应包含 top.sel (控制信号)")
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 位拼接
    #==========================================================================
    
    def test_concatenation(self):
        """[Op] 位拼接: assign y = {a, b};
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input a, input b, output [1:0] y);
    assign y = {a, b};
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "y = {a, b} 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 位复制
    #==========================================================================
    
    def test_replication(self):
        """[Op] 位复制: assign y = {4{a}};
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        """
        source = '''
module top(input a, output [3:0] y);
    assign y = {4{a}};
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "y = {4{a}} 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 复杂表达式 - 三元运算符部分 sel 必须参与
    #==========================================================================
    
    def test_complex_expression(self):
        """[Op] 复杂表达式: assign y = ((a + b) & c) | (sel ? a : b);
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b, c, sel] | high |
        
        注意: sel 是条件选择信号，必须参与驱动追踪
        """
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
        
        self.assertEqual(len(result.drivers), 4,
            "y = ((a + b) & c) | (sel ? a : b) 应有 4 个驱动源 (a, b, c, sel)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertIn('top.c', ids, "y 的驱动应包含 top.c")
        self.assertIn('top.sel', ids, "y 的驱动应包含 top.sel (控制信号)")
        self.assertEqual(result.confidence, 'high')
    
    #==========================================================================
    # 归约运算符
    #==========================================================================
    
    def test_reduction(self):
        """[Op] 归约运算符: assign y = |a;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        """
        source = '''
module top(input [7:0] a, output wire y);
    assign y = |a;  // or reduction
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "y = |a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()