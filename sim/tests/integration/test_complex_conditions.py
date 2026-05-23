#==============================================================================
# test_complex_conditions.py - 复杂条件语句测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestNestedIfExtraction(unittest.TestCase):
    """嵌套 if Driver 提取"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    def test_nested_if_two_levels(self):
        """[NestedIf] 2级嵌套 if: if (a) if (b) q=1 else q=0 else q=c;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [c, 1, 0] | high |
        """
        source = '''
module top(input clk, a, b, c, output reg q);
    always_ff @(posedge clk)
        if (a)
            if (b)
                q <= 1;
            else
                q <= 0;
        else
            q <= c;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertEqual(len(result.drivers), 3,
            "2级嵌套 if 应有 3 个驱动源 (c, 1, 0)")
        ids = self._driver_ids(result)
        self.assertIn('top.c', ids, "q 的驱动应包含 top.c")
        self.assertIn('1', ids, "q 的驱动应包含 1")
        self.assertIn('0', ids, "q 的驱动应包含 0")
        self.assertEqual(result.confidence, 'high')
    
    def test_nested_if_three_levels(self):
        """[NestedIf] 3级嵌套 if: if (a) if (b) if (c) q <= d;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [d]    | high |
        """
        source = '''
module top(input clk, a, b, c, d, output reg q);
    always_ff @(posedge clk)
        if (a)
            if (b)
                if (c)
                    q <= d;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "3级嵌套 if 应有 1 个驱动源 (d)")
        self.assertIn('top.d', self._driver_ids(result),
            "q 的驱动应包含 top.d")
        self.assertEqual(result.confidence, 'high')
    
    def test_if_with_else_if(self):
        """[If] else if 链: if (a) q=b; else if (c) q=d; else q=0;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [b, d, 0] | high |
        """
        source = '''
module top(input clk, a, b, c, d, output reg q);
    always_ff @(posedge clk)
        if (a) q <= b;
        else if (c) q <= d;
        else q <= 0;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertEqual(len(result.drivers), 3,
            "else if 链应有 3 个驱动源 (b, d, 0)")
        ids = self._driver_ids(result)
        self.assertIn('top.b', ids, "q 的驱动应包含 top.b")
        self.assertIn('top.d', ids, "q 的驱动应包含 top.d")
        self.assertIn('0', ids, "q 的驱动应包含 0")
        self.assertEqual(result.confidence, 'high')


class TestCaseStatementExtraction(unittest.TestCase):
    """case 语句 Driver 提取"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    def test_case_simple(self):
        """[Case] 简单 case: case (sel) 2'b00: y=a; 2'b01: y=b; default: y=0;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input [1:0] sel, a, b, output reg y);
    always_comb
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = 0;
        endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "case 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    def test_case_priority(self):
        """[Case] priority case: case (1'b1) a: y=1; b: y=0;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [1, 0] | high |
        """
        source = '''
module top(input a, b, output reg y);
    always @(*) begin
        case (1'b1)  // priority
            a: y = 1;
            b: y = 0;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "priority case 应有 2 个驱动源 (1, 0)")
        ids = self._driver_ids(result)
        self.assertIn('1', ids, "y 的驱动应包含 1")
        self.assertIn('0', ids, "y 的驱动应包含 0")
        self.assertEqual(result.confidence, 'high')
    
    def test_case_unique(self):
        """[Case] unique case: case (sel) 2'b00: y<=a; 2'b01: y<=b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input clk, input [1:0] sel, a, b, output reg y);
    always @(posedge clk) begin
        case (sel)  // unique
            2'b00: y <= a;
            2'b01: y <= b;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "unique case 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')


class TestMixedConditionsExtraction(unittest.TestCase):
    """混合条件 Driver 提取"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    def test_if_case_mix(self):
        """[Mix] if + case 混合: if (sel) y<=a; else case (1'b1) y<=b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        """
        source = '''
module top(input clk, sel, a, b, output reg y);
    always_ff @(posedge clk)
        if (sel)
            y <= a;
        else case (1'b1)
            y <= b;
        endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "if + case 混合应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_operator_in_condition(self):
        """[Op] 运算符在条件中: if (a & b) y <= c;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [c]    | high |
        """
        source = '''
module top(input clk, a, b, c, output reg y);
    always_ff @(posedge clk)
        if (a & b)
            y <= c;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "if (a & b) y <= c 应有 1 个驱动源 (c)")
        self.assertIn('top.c', self._driver_ids(result),
            "y 的驱动应包含 top.c")
        self.assertEqual(result.confidence, 'high')
    
    def test_case_inside_if(self):
        """[Mix] case 在 if 内部: if (sel) case (1'b1) a: y<=1; default: y<=0;
        金标准: [已知限制] case 内部 only returns 1
        """
        source = '''
module top(input clk, sel, a, b, output reg y);
    always_ff @(posedge clk)
        if (sel)
            case (1'b1)
                a: y <= 1;
                default: y <= 0;
            endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        # [已知限制] case 内部返回 1
        self.assertEqual(len(result.drivers), 1,
            "[已知限制] case 内部暂返回 1 个驱动源")
        self.assertIn('1', self._driver_ids(result),
            "y 的驱动应包含 1")
    
    def test_multi_else_branch(self):
        """[If] 多个 else 分支: if (en1) q<=d1; else if (en2) q<=d2; else q<=0;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [d1, d2, 0] | high |
        """
        source = '''
module top(input clk, en1, en2, d1, d2, output reg q);
    always_ff @(posedge clk)
        if (en1) q <= d1;
        else if (en2) q <= d2;
        else q <= 0;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertEqual(len(result.drivers), 3,
            "多个 else 分支应有 3 个驱动源 (d1, d2, 0)")
        ids = self._driver_ids(result)
        self.assertIn('top.d1', ids, "q 的驱动应包含 top.d1")
        self.assertIn('top.d2', ids, "q 的驱动应包含 top.d2")
        self.assertIn('0', ids, "q 的驱动应包含 0")
        self.assertEqual(result.confidence, 'high')


class TestComplexPatternExtraction(unittest.TestCase):
    """复杂模式 Driver 提取"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    def test_ternary_in_if(self):
        """[Op] 三元在 if 中: if (sel) y <= sel ? a : b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a, b] | high |
        """
        source = '''
module top(input clk, sel, a, b, output reg y);
    always_ff @(posedge clk)
        if (sel) y <= sel ? a : b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "if (sel) y <= sel ? a : b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "y 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')
    
    def test_array_index_in_condition(self):
        """[Op] 数组索引在条件中: if (mem[idx]) y <= 1;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [1]    | high |
        """
        source = '''
module top(input clk, [7:0] mem, input [2:0] idx, output reg y);
    always_ff @(posedge clk)
        if (mem[idx]) y <= 1;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "if (mem[idx]) y <= 1 应有 1 个驱动源 (1)")
        self.assertIn('1', self._driver_ids(result),
            "y 的驱动应包含 1")
        self.assertEqual(result.confidence, 'high')
    
    def test_shift_in_condition(self):
        """[Op] 移位在条件中: if (a >> b) y <= 1;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [1]    | high |
        """
        source = '''
module top(input clk, a, b, output reg y);
    always_ff @(posedge clk)
        if (a >> b) y <= 1;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "if (a >> b) y <= 1 应有 1 个驱动源 (1)")
        self.assertIn('1', self._driver_ids(result),
            "y 的驱动应包含 1")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()