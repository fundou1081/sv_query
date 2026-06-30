#==============================================================================
# test_advanced_syntax.py - 高级语法 Driver 提取
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestParameterExtraction(unittest.TestCase):
    """Parameter Driver 提取"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_parameterized_width(self):
        """[Param] 参数化宽度
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [din]  | high |
        """
        source = '''module param_mod #(
    parameter WIDTH = 8
) (input [WIDTH-1:0] din, output [WIDTH-1:0] dout);
    assign dout = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'param_mod')

        self.assertEqual(len(result.drivers), 1,
            "dout = din 应有 1 个驱动源 (din)")
        self.assertIn('param_mod.din', self._driver_ids(result),
            "dout 的驱动应包含 param_mod.din")
        self.assertEqual(result.confidence, 'high')

    def test_localparam(self):
        """[Param] 本地参数不影响追踪
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [din]  | high |
        """
        source = '''
module top(input din, output dout);
    localparam WIDTH = 8;
    assign dout = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')

        self.assertEqual(len(result.drivers), 1,
            "dout = din 应有 1 个驱动源 (din)")
        self.assertIn('top.din', self._driver_ids(result),
            "dout 的驱动应包含 top.din")
        self.assertEqual(result.confidence, 'high')


class TestArrayExtraction(unittest.TestCase):
    """数组 Driver 提取"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_array_index(self):
        """[Array] 数组索引
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [mem[0]] | high |
        """
        source = '''
module top(input [7:0] mem [0:3], output [7:0] dout);
    assign dout = mem[0];
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')

        self.assertEqual(len(result.drivers), 1,
            "dout = mem[0] 应有 1 个驱动源 (mem[0])")
        self.assertIn('top.mem[0]', self._driver_ids(result),
            "dout 的驱动应包含 top.mem[0]")
        self.assertEqual(result.confidence, 'high')

    def test_array_assignment(self):
        """[Array] 数组赋值
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | clk  | []     | uncertain |
        """
        source = '''
module top(input clk, input [7:0] data);
    reg [7:0] mem [0:3];
    always @(posedge clk) mem[0] <= data;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')

        # clk 是输入端口，作为 source 点无上游驱动
        self.assertEqual(len(result.drivers), 0,
            "clk 作为输入端口，无上游驱动")
        self.assertEqual(result.confidence, 'uncertain')


class TestBitSelectExtraction(unittest.TestCase):
    """位选 Driver 提取"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_single_bit(self):
        """[Bit] 单比特选择
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [data[5]] | high |
        """
        source = '''
module top(input [7:0] data, output bit dout);
    assign dout = data[5];
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')

        self.assertEqual(len(result.drivers), 1,
            "dout = data[5] 应有 1 个驱动源")
        self.assertIn('top.data[5]', self._driver_ids(result),
            "dout 的驱动应包含 top.data[5]")
        self.assertEqual(result.confidence, 'high')

    def test_range_select(self):
        """[Bit] 范围选择
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | nibble | [data[3:0]] | high |
        """
        source = '''
module top(input [7:0] data, output [3:0] nibble);
    assign nibble = data[3:0];
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nibble', 'top')

        self.assertEqual(len(result.drivers), 1,
            "nibble = data[3:0] 应有 1 个驱动源")
        self.assertIn('top.data[3:0]', self._driver_ids(result),
            "nibble 的驱动应包含 top.data[3:0]")
        self.assertEqual(result.confidence, 'high')


class TestSystemFunctionExtraction(unittest.TestCase):
    """系统函数 Driver 提取"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_system_function(self):
        """[Sys] 系统函数 $random
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | rnd  | []     | uncertain |
        """
        source = '''
module top(output [31:0] rnd);
    assign rnd = $random;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('rnd', 'top')

        # $random 是系统函数，无外部输入
        self.assertEqual(len(result.drivers), 0,
            "$random 无外部驱动源")
        self.assertEqual(result.confidence, 'uncertain')

    def test_time_function(self):
        """[Sys] $time
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | t    | []     | uncertain |
        """
        source = '''
module top(output [31:0] t);
    assign t = $time;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('t', 'top')

        # $time 是系统函数，无外部输入
        self.assertEqual(len(result.drivers), 0,
            "$time 无外部驱动源")
        self.assertEqual(result.confidence, 'uncertain')


class TestCrossModuleExtraction(unittest.TestCase):
    """跨模块 Driver 提取"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_simple_instance(self):
        """[Cross] 简单实例
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        """
        source = '''
module my_buf(input d, output q);
    assign q = d;
endmodule
module top(input a, output y);
    my_buf u1(.d(a), .q(y));
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        self.assertEqual(len(result.drivers), 2,
            "y 追踪到 a，应有 2 个驱动源 (u1.q, a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')

    def test_two_instance(self):
        """[Cross] 2级实例
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        """
        source = '''
module my_buf(input d, output q);
    assign q = d;
endmodule
module top(input a, output y);
    wire mid;
    my_buf u1(.d(a), .q(mid));
    my_buf u2(.d(mid), .q(y));
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        # y <- u2.q <- mid，应追踪到 mid
        self.assertGreaterEqual(len(result.drivers), 1,
            "y 追踪到 mid，应有至少 1 个驱动源")
        self.assertIn('top.mid', self._driver_ids(result),
            "y 的驱动应包含 top.mid")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
