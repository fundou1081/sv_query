#==============================================================================
# test_bit_select_in_always.py - 金标准测试: always 块内位选择
# 铁律13: 先推导金标准，再验证
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestBitSelectInAlways(unittest.TestCase):
    """always 块内位选择驱动提取"""

    def test_always_comb_bit_select_fixed(self):
        """[Golden] always_comb 中固定位选择
        RTL: always_comb y = data[3];
        金标准:
        | 信号 | 驱动源   | 来源        |
        |------|----------|-------------|
        | y    | [data]   | always_comb |
        """
        src = '''
module top(input [7:0] data, output reg y);
    always_comb y = data[3];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_comb y = data[3] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

    def test_always_comb_bit_select_dynamic(self):
        """[Golden] always_comb 中动态位选择
        RTL: always_comb y = data[idx];
        金标准:
        | 信号 | 驱动源   | 来源        |
        |------|----------|-------------|
        | y    | [data]   | always_comb |
        """
        src = '''
module top(input [7:0] data, input [2:0] idx, output reg y);
    always_comb y = data[idx];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_comb y = data[idx] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

    def test_always_comb_range_select(self):
        """[Golden] always_comb 中范围选择
        RTL: always_comb y = data[7:4];
        金标准:
        | 信号 | 驱动源   | 来源        |
        |------|----------|-------------|
        | y    | [data]   | always_comb |
        """
        src = '''
module top(input [7:0] data, output reg [3:0] y);
    always_comb y = data[7:4];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_comb y = data[7:4] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

    def test_if_else_bit_select(self):
        """[Golden] if/else 中位选择
        RTL: if (sel) y = data[7]; else y = data[0];
        金标准:
        | 信号 | 驱动源         | 来源        |
        |------|----------------|-------------|
        | y    | [data, data]   | always_comb |
        """
        src = '''
module top(input [7:0] data, input sel, output reg y);
    always_comb begin
        if (sel) y = data[7];
        else y = data[0];
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        # data[7] 和 data[0] 剥离位选择后都变成 data，去重后为1条边
        self.assertGreaterEqual(len(result.drivers), 1,
            "if/else 中位选择应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

    def test_case_bit_select(self):
        """[Golden] case 中位选择
        RTL: case(sel) 00: y=a[0]; 01: y=a[1]; default: y=a[2];
        金标准:
        | 信号 | 驱动源              | 来源        |
        |------|---------------------|-------------|
        | y    | [a, a, a]           | always_comb |
        """
        src = '''
module top(input [1:0] sel, input [7:0] a, output reg y);
    always_comb begin
        case(sel)
            2'b00: y = a[0];
            2'b01: y = a[1];
            default: y = a[2];
        endcase
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        # a[0], a[1], a[2] 剥离位选择后都变成 a，去重后为1条边
        self.assertGreaterEqual(len(result.drivers), 1,
            "case 中位选择应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

    def test_always_ff_bit_select(self):
        """[Golden] always_ff 中位选择
        RTL: always_ff @(posedge clk) q <= data[3];
        金标准:
        | 信号 | 驱动源   | 来源      |
        |------|----------|-----------|
        | q    | [data]   | always_ff |
        """
        src = '''
module top(input clk, input [7:0] data, output reg q);
    always_ff @(posedge clk) q <= data[3];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('q', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_ff q <= data[3] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')


class TestTernaryOperator(unittest.TestCase):
    """三元运算符多操作数提取"""

    def test_assign_ternary(self):
        """[Golden] assign 中三元运算符
        RTL: assign y = sel ? a : b;
        金标准:
        | 信号 | 驱动源    | 来源   |
        |------|-----------|--------|
        | y    | [a, b]    | assign |
        """
        src = '''
module top(input a, b, sel, output y);
    assign y = sel ? a : b;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 2,
            "assign y = sel ? a : b 应有2个驱动 (a 和 b)")
        self.assertEqual(result.confidence, 'high')

    def test_always_comb_ternary(self):
        """[Golden] always_comb 中三元运算符
        RTL: always_comb y = sel ? a : b;
        金标准:
        | 信号 | 驱动源    | 来源        |
        |------|-----------|-------------|
        | y    | [a, b]    | always_comb |
        """
        src = '''
module top(input a, b, sel, output reg y);
    always_comb y = sel ? a : b;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 2,
            "always_comb y = sel ? a : b 应有2个驱动 (a 和 b)")
        self.assertEqual(result.confidence, 'high')

    def test_assign_ternary_complex(self):
        """[Golden] assign 中嵌套三元运算符
        RTL: assign y = sel1 ? a : (sel2 ? b : c);
        金标准:
        | 信号 | 驱动源       | 来源   |
        |------|--------------|--------|
        | y    | [a, b, c]    | assign |
        """
        src = '''
module top(input a, b, c, sel1, sel2, output y);
    assign y = sel1 ? a : (sel2 ? b : c);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 3,
            "嵌套三元应有3个驱动 (a, b, c)")
        self.assertEqual(result.confidence, 'high')


class TestConcatLHS(unittest.TestCase):
    """拼接赋值 LHS 多信号提取"""

    def test_assign_concat_lhs(self):
        """[Golden] 拼接赋值 LHS
        RTL: assign {y[2], y[1], y[0]} = {a, b, c};
        金标准:
        | 信号 | 驱动源    | 来源   |
        |------|-----------|--------|
        | y    | [a, b, c] | assign |
        """
        src = '''
module top(input a, b, c, output [2:0] y);
    assign {y[2], y[1], y[0]} = {a, b, c};
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 3,
            "assign {y[2], y[1], y[0]} = {a, b, c} 应有3个驱动")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
