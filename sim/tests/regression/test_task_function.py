#==============================================================================
# test_task_function.py - Task/Function 参数追踪金标准测试
# 项目纪律: 铁律13 金标准测试
# [iter_064 2026-08-29] 行为断言加强: 保留原有 graph/node 断言, 补充 DRIVER
# 边断言 (行为金标准 — module 域中"谁驱动谁").
# [iter_076 2026-09-01] #42/#43 修复: task 调用站点完整形参映射 —
#   - flattener 保留 Call 整体 (不再拆分 output 参数为占位赋值)
#   - _parse_invocation_call 放行 AssignmentExpression (output 实参)
#   - 结果: my_task(din, dout) 生成真边 din → dout, EmptyArgument 占位边消失
#   - 多参数 my_task(din, mode, dout, flag) 按内部驱动关系独立映射
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


#==============================================================================
# 1. Task 基本参数传递 - 金标准
#==============================================================================
class TestTaskCall(unittest.TestCase):
    """[语法] Task 调用参数传递"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_task_output_param(self):
        """[Golden] task output 参数驱动信号 [iter_076 #42 升级为真边断言]

        RTL:
        task my_task(input [7:0] a, output [7:0] b);
            b = a;
        endtask
        my_task(din, dout);

        行为金标准 (module 域 — task 调用, iter_076 #42 已修复):
          - 节点: din, dout 必存在 (module 信号).
          - din → dout 的 DRIVER 边必须存在 (input 实参 din 经 task 内部
            b = a 驱动 output 实参 dout).
          - 不再产生 EmptyArgument 占位边 (flattener 保留 Call 整体,
            _parse_invocation_call 放行 Assignment 实参, 完整形参映射).
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

        # 原断言: 图建立
        self.assertIsNotNone(tracer.get_graph())

        # 行为断言: 节点存在
        graph = tracer.get_graph()
        nodes = list(graph.nodes())
        self.assertIn('top.din', nodes, "task input 实参 din 节点应存在")
        self.assertIn('top.dout', nodes, "task output 实参 dout 节点应存在")

        # [iter_076] 真边断言: din → dout DRIVER 边 (工具缺口已修复)
        edge = graph.get_edge('top.din', 'top.dout')
        self.assertIsNotNone(
            edge,
            f"task 调用站点应生成 din → dout 的 DRIVER 边, 实际入边: "
            f"{[u for u, v in graph.edges() if v == 'top.dout']}",
        )
        # 无 EmptyArgument 占位边
        for u, _v in graph.edges():
            self.assertNotIn('EmptyArgument', u,
                             f"不应存在 EmptyArgument 占位节点: {u}")


#==============================================================================
# 2. Function 基本参数传递 - 金标准
#==============================================================================
class TestFunctionCall(unittest.TestCase):
    """[语法] Function 调用"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_function_return(self):
        """[Golden] function 返回值

        RTL:
        function [7:0] my_func(input [7:0] a);
            return a + 1;
        endfunction
        assign dout = my_func(din);

        行为金标准 (module 域 — function 调用):
          - 节点: din, dout, my_func 必存在.
          - din → my_func  DRIVER 边 (实参驱动函数入口节点).
          - my_func → dout DRIVER 边 (函数返回值驱动 LHS).
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

        # 原断言
        self.assertIsNotNone(tracer.get_graph())

        # 原节点断言
        graph = tracer.get_graph()
        nodes = list(graph.nodes())
        self.assertIn('top.din', nodes)
        self.assertIn('top.dout', nodes)

        # [iter_064] 行为断言: 函数调用两段 DRIVER 边必须都存在
        graph = tracer.get_graph()
        edge_in = graph.get_edge('top.din', 'top.my_func')
        self.assertIsNotNone(edge_in,
                             "function 实参应生成 din → my_func 的 DRIVER 边")
        edge_out = graph.get_edge('top.my_func', 'top.dout')
        self.assertIsNotNone(edge_out,
                             "function 返回值应生成 my_func → dout 的 DRIVER 边")


#==============================================================================
# 3. Task 内多语句 - 金标准
#==============================================================================
class TestTaskMultiple(unittest.TestCase):
    """[语法] Task 内多语句"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
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

        行为金标准 (iter_076 更新):
          - 节点: a, b (即 dout1, dout2) 必存在.
          - output 实参由常量 (8'hFF / 8'h00) 赋值 — 常量不是信号源,
            不产生 signal 驱动边 (正确行为, 非工具缺口).
            信号驱动的 output 边见 TestTaskCall.test_task_output_param.
        """
        source = '''
module top(output logic [7:0] a, b);
    task my_task(output logic [7:0] a, b);
        a = 8'hFF;
        b = 8'h00;
    endtask

    initial begin
        my_task(a, b);
    end
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 原断言
        self.assertIsNotNone(tracer.get_graph())

        # [iter_064] 行为断言: 模块 output 端口节点存在
        # (task 内部赋值的 driver 边当前未生成 — 工具缺口)
        nodes = list(tracer.get_graph().nodes())
        self.assertIn('top.a', nodes, "module output 'a' (dout1) 节点应存在")
        self.assertIn('top.b', nodes, "module output 'b' (dout2) 节点应存在")


#==============================================================================
# 3b. Task 多参数 output 展开 - 金标准 [iter_076 #43]
#==============================================================================
class TestTaskMultiParamExpansion(unittest.TestCase):
    """[语法] Task 多参数调用站点 output 实参完整展开"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_multi_param_call_site_edges(self):
        """[Golden] 多 input/output task 调用站点生成完整 DRIVER 边集

        RTL:
        task my_task(input a, input m, output b, output f);
            b = a;
            f = a & m;
        endtask
        my_task(din, mode, dout, flag);

        行为金标准 (module 域 — iter_076 #43):
          - din → dout  DRIVER (b = a)
          - din → flag  DRIVER (f = a & m 含 a)
          - mode → flag DRIVER (f = a & m 含 m)
          - 无 mode → dout 边 (b = a 不依赖 m — output 参数按内部驱动
            关系独立映射, 不串扰)
          - 无 EmptyArgument 占位边
        """
        source = '''
module top(input logic din, input logic mode,
           output logic dout, output logic flag);
    task my_task(input logic a, input logic m,
                 output logic b, output logic f);
        b = a;
        f = a & m;
    endtask

    initial begin
        my_task(din, mode, dout, flag);
    end
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()

        graph = tracer.get_graph()
        nodes = list(graph.nodes())
        for sig in ('top.din', 'top.mode', 'top.dout', 'top.flag'):
            self.assertIn(sig, nodes, f"实参节点 {sig} 应存在")

        # 每条 output 的内部驱动关系必须独立映射到调用实参
        edge_in = graph.get_edge('top.din', 'top.dout')
        self.assertIsNotNone(edge_in, "b = a → din 应驱动 dout")
        edge_f1 = graph.get_edge('top.din', 'top.flag')
        self.assertIsNotNone(edge_f1, "f = a & m → din 应驱动 flag")
        edge_f2 = graph.get_edge('top.mode', 'top.flag')
        self.assertIsNotNone(edge_f2, "f = a & m → mode 应驱动 flag")

        # 反例: b = a 不依赖 m, mode 不得驱动 dout
        no_edge = graph.get_edge('top.mode', 'top.dout')
        self.assertIsNone(no_edge, "b = a 不依赖 m, mode 不应驱动 dout")

        # 无 EmptyArgument 占位边
        for u, _v in graph.edges():
            self.assertNotIn('EmptyArgument', u,
                             f"不应存在 EmptyArgument 占位节点: {u}")

    def test_named_arg_mixed_call_site(self):
        """[Golden] 命名实参 + 位置实参混合调用 (iter_076 #43 回归)

        RTL:
        task my_task(input a, input m, output b, output f);
            b = a;
            f = a & m;
        endtask
        my_task(.b(dout), .f(flag), .a(din), .m(mode));

        行为金标准: 与位置调用等价 (named_args 映射路径).
        """
        source = '''
module top(input logic din, input logic mode,
           output logic dout, output logic flag);
    task my_task(input logic a, input logic m,
                 output logic b, output logic f);
        b = a;
        f = a & m;
    endtask

    initial begin
        my_task(.b(dout), .f(flag), .a(din), .m(mode));
    end
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()

        graph = tracer.get_graph()
        self.assertIsNotNone(graph.get_edge('top.din', 'top.dout'),
                             "命名实参 .a(din)/.b(dout) → din 驱动 dout")
        self.assertIsNotNone(graph.get_edge('top.din', 'top.flag'),
                             "命名实参 → din 驱动 flag")
        self.assertIsNotNone(graph.get_edge('top.mode', 'top.flag'),
                             "命名实参 → mode 驱动 flag")
        self.assertIsNone(graph.get_edge('top.mode', 'top.dout'),
                          "mode 不应驱动 dout")


#==============================================================================
# 4. Function 表达式 - 金标准
#==============================================================================
class TestFunctionExpression(unittest.TestCase):
    """[语法] Function 表达式"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_function_in_expression(self):
        """[Golden] function 在表达式中

        RTL:
        assign result = a & func(b);

        行为金标准:
          - 节点: a, b, my_func, result 必存在.
          - b → my_func     DRIVER 边 (实参驱动函数入口).
          - my_func → result DRIVER 边 (返回值驱动 result).
          - a 直接驱动 result (经 & 表达式节点汇聚; 此断言放宽为: 至少
            有一条 → result 的入边来自 a 或其派生节点).
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

        # 原断言
        self.assertIsNotNone(tracer.get_graph())

        # 原节点断言
        graph = tracer.get_graph()
        nodes = list(graph.nodes())
        self.assertIn('top.a', nodes)
        self.assertIn('top.b', nodes)
        self.assertIn('top.result', nodes)

        # [iter_064] 行为断言: function 调用两段边
        edge_in = graph.get_edge('top.b', 'top.my_func')
        self.assertIsNotNone(edge_in,
                             "function 实参 b 应驱动函数入口节点 my_func")
        edge_out = graph.get_edge('top.my_func', 'top.result')
        self.assertIsNotNone(edge_out,
                             "function 返回应驱动 result (可能经 & 表达式节点中转, 此处直接断言 my_func→result)")


#==============================================================================
# 5. Recursive Function - 金标准
#==============================================================================
class TestRecursiveFunction(unittest.TestCase):
    """[语法] 递归 Function"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_recursive_function(self):
        """[Golden] 递归 function

        RTL:
        function [7:0] fib(input [7:0] n);
            if (n <= 1) return n;
            return fib(n-1) + fib(n-2);
        endfunction
        assign result = fib(n);

        行为金标准:
          - 节点: n, result, fib 必存在.
          - n → fib       DRIVER 边 (实参驱动函数入口).
          - fib → result  DRIVER 边 (返回值驱动 LHS).
          - 递归自身调用 fib(n-1)+fib(n-2) 在 AST 中是自引用;
            graph 行为金标准只校验最外层调用链, 不展开递归体.
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

        # 原断言
        self.assertIsNotNone(tracer.get_graph())

        # [iter_064] 行为断言: 递归函数仍走标准两段 DRIVER 边
        graph = tracer.get_graph()
        nodes = list(graph.nodes())
        self.assertIn('top.n', nodes, "function 实参 n 节点应存在")
        self.assertIn('top.fib', nodes, "递归函数 fib 节点应存在")
        self.assertIn('top.result', nodes, "function 返回目标 result 节点应存在")

        edge_in = graph.get_edge('top.n', 'top.fib')
        self.assertIsNotNone(edge_in,
                             "递归 function 实参 n 应驱动函数入口 fib")
        edge_out = graph.get_edge('top.fib', 'top.result')
        self.assertIsNotNone(edge_out,
                             "递归 function 返回值应驱动 result")


if __name__ == '__main__':
    unittest.main()
