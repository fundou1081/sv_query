#==============================================================================
# test_complex_conditions.py - 复杂条件语句测试
# [P1] if嵌套、case、条件组合
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestNestedIfExtraction(unittest.TestCase):
    """嵌套 if Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_nested_if_two_levels(self):
        """[Golden] 2级嵌套 if"""
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
        
        # 应提取多个驱动
        driver_count = len(result.drivers)
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain')
        self.assertEqual(result.confidence, 'high')
    
    def test_nested_if_three_levels(self):
        """[Golden] 3级嵌套 if"""
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
        
        self.assertIn(result.confidence, ['high', 'medium'])
    
    def test_if_with_else_if(self):
        """[Golden] else if 链"""
        source = '''
module top(input clk, a, b, c, d, output reg q);
    always_ff @(posedge clk)
        if (a) q <= b;
        else if (c) q <= d;
        else q <= 0;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 多个分支
        self.assertGreaterEqual(len(result.drivers), 1)


class TestCaseStatementExtraction(unittest.TestCase):
    """case 语句 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_case_simple(self):
        """[Golden] 简单 case"""
        source = '''
module top(input [1:0] sel, a, b, output y);
    always_comb
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = 0;
        endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        driver_count = len(result.drivers)
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain')
    
    def test_case_priority(self):
        """[Golden] priority case"""
        source = '''
module top(input a, b, output y);
    priority case (1'b1)
        a: y = 1;
        b: y = 0;
    endpriority
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])
    
    def test_case_unique(self):
        """[Golden] unique case"""
        source = '''
module top(input [1:0] sel, a, b, output reg y);
    always_ff @(posedge clk)
        unique case (sel)
            2'b00: y <= a;
            2'b01: y <= b;
        endunique
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])


class TestMixedConditionsExtraction(unittest.TestCase):
    """混合条件 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_if_case_mix(self):
        """[Golden] if + case 混合"""
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
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_operator_in_condition(self):
        """[Golden] 运算符在条件中"""
        source = '''
module top(input clk, a, b, c, output reg y);
    always_ff @(posedge clk)
        if (a & b)
            y <= c;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])
    
    def test_case_inside_if(self):
        """[Golden] case 在 if 内部"""
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
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_multi_else_branch(self):
        """[Golden] 多个 else 分支"""
        source = '''
module top(input clk, en1, en2, d1, d2, output reg q);
    always_ff @(posedge clk)
        if (en1) q <= d1;
        else if (en2) q <= d2;
        else q <= 0;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 多个可能的驱动
        self.assertGreaterEqual(len(result.drivers), 1)


class TestComplexPatternExtraction(unittest.TestCase):
    """复杂模式 Driver 提取"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_ternary_in_if(self):
        """[Golden] 三元在 if 中"""
        source = '''
module top(input clk, sel, a, b, output reg y);
    always_ff @(posedge clk)
        if (sel) y <= sel ? a : b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])
    
    def test_array_index_in_condition(self):
        """[Golden] 数组索引在条件中"""
        source = '''
module top(input clk, mem, idx, output reg y);
    always_ff @(posedge clk)
        if (mem[idx]) y <= 1;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_shift_in_condition(self):
        """[Golden] 移位在条件中"""
        source = '''
module top(input clk, a, b, output reg y);
    always_ff @(posedge clk)
        if (a >> b) y <= 1;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])


if __name__ == '__main__':
    unittest.main()
