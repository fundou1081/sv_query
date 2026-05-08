#==============================================================================
# test_subroutine_params.py - 金标准测试: task/function 参数映射
# 铁律13: 先推导金标准，再验证
#==============================================================================
# 问题: task/function 调用时，参数映射未解析
# 例: do_work(a, y) 应映射 a→in, y→out
#     内部 out = in + 1 应解析为 y 的驱动 = a
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestTaskParams(unittest.TestCase):
    """task 参数映射"""

    def test_task_output_param(self):
        """[Golden] task output 参数
        RTL:
            task do_work; input in; output out; out = in + 1; endtask
            always_comb do_work(a, y);
        金标准:
        | 信号 | 驱动源 | 来源        |
        |------|--------|-------------|
        | y    | [a]    | always_comb |
        """
        src = '''
module top(input [7:0] a, output reg [7:0] y);
    task automatic do_work;
        input [7:0] in;
        output [7:0] out;
        out = in + 1;
    endtask
    always_comb do_work(a, y);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'top': tree})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "task output 参数应有驱动")
        self.assertEqual(result.confidence, 'high')

    def test_task_input_output(self):
        """[Golden] task input + output
        RTL:
            task do_work; input a; output c; c = a + 1; endtask
            always_comb do_work(x, c);
        金标准:
        | 信号 | 驱动源 | 来源        |
        |------|--------|-------------|
        | c    | [a]    | always_comb |
        """
        src = '''
module top(input [7:0] a, output reg [7:0] c);
    task automatic do_work;
        input [7:0] in;
        output [7:0] out;
        out = in + 1;
    endtask
    always_comb do_work(a, c);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'top': tree})
        result = tracer.trace_signal('c', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "task output 参数应有驱动")

    def test_task_input_only(self):
        """[Golden] task 只读（无 output）
        RTL:
            task do_work; input in; // 无 output
            // 内部操作不影响外部
            endtask
        金标准:
        | 信号 | 驱动源 | 来源        |
        |------|--------|-------------|
        | -    | -      | -           |
        注意: 只读 task 不应产生驱动
        """
        src = '''
module top(input [7:0] a);
    task automatic do_work;
        input [7:0] in;
        // 无 output 参数，内部操作不影响外部
    endtask
    always_comb do_work(a);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'top': tree})
        result = tracer.trace_signal('a', 'top')

        # a 是输入端口，不应被 task 内部改变
        self.assertEqual(len(result.drivers), 0,
            "只读 task 不应产生新驱动")


class TestFunctionParams(unittest.TestCase):
    """function 参数映射"""

    def test_function_output_param(self):
        """[Golden] function 返回值
        RTL:
            function [7:0] calc; input x; calc = x + 1; endfunction
            always_comb y = calc(a);
        金标准:
        | 信号 | 驱动源 | 来源        |
        |------|--------|-------------|
        | y    | [a]    | always_comb |
        """
        src = '''
module top(input [7:0] a, output reg [7:0] y);
    function automatic [7:0] calc;
        input [7:0] x;
        begin
            calc = x + 1;
        end
    endfunction
    always_comb y = calc(a);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'top': tree})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "function 返回值应有驱动")
        self.assertEqual(result.confidence, 'high')


class TestEnumSelfDrive(unittest.TestCase):
    """自更新场景（enum 计数器等）"""

    def test_counter_self_update(self):
        """[Golden] 计数器自更新
        RTL:
            always_ff @(posedge clk) state <= state + 1;
        金标准:
        | 信号  | 驱动源     | 来源      |
        |-------|------------|-----------|
        | state | [state]   | always_ff | (自环)
        """
        src = '''
module top(input clk, output reg [1:0] state);
    always_ff @(posedge clk) state <= state + 1;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'top': tree})
        result = tracer.trace_signal('state', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "计数器自更新应有驱动 (自环)")

    def test_enum_self_update(self):
        """[Golden] enum 自更新
        RTL:
            always_ff @(posedge clk) state <= state + 1;
        金标准:
        | 信号  | 驱动源     | 来源      |
        |-------|------------|-----------|
        | state | [state]   | always_ff | (自环)
        """
        src = '''
module top(input clk, output reg [1:0] state);
    always_ff @(posedge clk) begin
        state <= state + 1;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'top': tree})
        result = tracer.trace_signal('state', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "enum 自更新应有驱动 (自环)")


if __name__ == '__main__':
    unittest.main()
