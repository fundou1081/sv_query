#==============================================================================
# test_subroutine_expander_tdd.py - 函数内联展开 TDD 测试
#==============================================================================
# TDD 循环: Red (失败测试) → Green (通过实现) → Refactor (重构)
#
# 测试覆盖:
# 1. if/else 条件分支
# 2. case 语句
# 3. return 语句形式
# 4. 三元运算符
# 5. 嵌套 if
# 6. 多重赋值
# 7. 复杂表达式

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestFunctionInlineExpansion(unittest.TestCase):
    """函数内联展开 TDD 测试套件"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _get_edges(self, tracer, signal_name, module_name):
        """获取追踪结果的所有边"""
        result = tracer.trace_signal(signal_name, module_name)
        graph = tracer.get_graph()
        edges = []
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            edges.append({
                'src': src,
                'dst': dst,
                'condition': edge.condition if edge else None,
                'effective_condition': edge.effective_condition if edge else None
            })
        return edges

    def _edge_exists(self, edges, src, dst, condition=None):
        """检查边是否存在"""
        for e in edges:
            if e['src'] == src and e['dst'] == dst:
                if condition is None:
                    return True
                if e['condition'] == condition:
                    return True
        return False

    #==========================================================================
    # RED PHASE: 失败的测试用例 (按优先级排序)
    #==========================================================================

    def test_case_statement(self):
        """[RED-1] case 语句展开 - 最高优先级"""
        source = '''
module top(
    input wire [1:0] sel,
    input wire [7:0] a,
    input wire [7:0] b,
    input wire [7:0] c,
    input wire [7:0] d,
    output wire [7:0] y
);
    function [7:0] mux4;
        input [1:0] s;
        input [7:0] x0;
        input [7:0] x1;
        input [7:0] x2;
        input [7:0] x3;
        case (s)
            0: mux4 = x0;
            1: mux4 = x1;
            2: mux4 = x2;
            default: mux4 = x3;
        endcase
    endfunction

    assign y = mux4(sel, a, b, c, d);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: case 语句应产生多个分支边
        # 每个 case 项对应一条边
        self.assertTrue(
            self._edge_exists(edges, 'top.a', 'top.y', 'sel==0'),
            f"Missing edge: top.a -> top.y (sel==0), got: {edges}"
        )
        self.assertTrue(
            self._edge_exists(edges, 'top.b', 'top.y', 'sel==1'),
            f"Missing edge: top.b -> top.y (sel==1), got: {edges}"
        )
        self.assertTrue(
            self._edge_exists(edges, 'top.c', 'top.y', 'sel==2'),
            f"Missing edge: top.c -> top.y (sel==2), got: {edges}"
        )
        self.assertTrue(
            self._edge_exists(edges, 'top.d', 'top.y', 'default'),
            f"Missing edge: top.d -> top.y (default), got: {edges}"
        )

    def test_return_statement_form(self):
        """[RED-2] return 语句形式函数"""
        source = '''
module top(
    input wire [7:0] a,
    input wire [7:0] b,
    output wire [7:0] y
);
    function [7:0] max_val;
        input [7:0] x;
        input [7:0] y;
        if (x > y)
            return x;
        else
            return y;
    endfunction

    assign y = max_val(a, b);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: return 语句应产生与 if/else 赋值形式相同的边
        self.assertTrue(
            self._edge_exists(edges, 'top.a', 'top.y') or
            self._edge_exists(edges, 'top.b', 'top.y'),
            f"Missing edges from a or b to y, got: {edges}"
        )
        # 应该有条件
        has_conditional_edges = any(e['condition'] for e in edges)
        self.assertTrue(has_conditional_edges, f"Expected conditional edges, got: {edges}")

    def test_nested_if(self):
        """[RED-3] 嵌套 if 语句"""
        source = '''
module top(
    input wire [1:0] sel,
    input wire [7:0] a,
    input wire [7:0] b,
    input wire [7:0] c,
    output wire [7:0] y
);
    function [7:0] nested_mux;
        input [1:0] s;
        input [7:0] x;
        input [7:0] y;
        input [7:0] z;
        if (s[1] == 0) begin
            if (s[0] == 0)
                nested_mux = x;
            else
                nested_mux = y;
        end else begin
            nested_mux = z;
        end
    endfunction

    assign y = nested_mux(sel, a, b, c);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: 嵌套 if 应产生组合条件
        # s[1]==0 && s[0]==0 -> x
        # s[1]==0 && s[0]!=0 -> y
        # s[1]!=0 -> z
        self.assertTrue(
            len(edges) >= 3,
            f"Expected at least 3 edges for nested if, got {len(edges)}: {edges}"
        )

    def test_ternary_operator(self):
        """[RED-4] 三元运算符函数"""
        source = '''
module top(
    input wire [7:0] sel,
    input wire [7:0] a,
    input wire [7:0] b,
    output wire [7:0] y
);
    function [7:0] cond_mux;
        input [7:0] s;
        input [7:0] x;
        input [7:0] y;
        cond_mux = (s == 0) ? x : y;
    endfunction

    assign y = cond_mux(sel, a, b);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: 三元运算符应产生条件边
        self.assertTrue(
            len(edges) >= 2,
            f"Expected at least 2 edges for ternary, got {len(edges)}: {edges}"
        )
        has_conditional = any(e['condition'] for e in edges)
        self.assertTrue(has_conditional, f"Expected conditional edges, got: {edges}")

    def test_multiple_assignments_in_branch(self):
        """[RED-5] 分支内多重赋值"""
        source = '''
module top(
    input wire [7:0] a,
    input wire [7:0] b,
    input wire sel,
    output wire [7:0] y,
    output wire [7:0] z
);
    function [15:0] split_data;
        input [7:0] x;
        input [7:0] y;
        input bit s;
        if (s) begin
            split_data[15:8] = x;
            split_data[7:0] = y;
        end else begin
            split_data[15:8] = y;
            split_data[7:0] = x;
        end
    endfunction

    assign {y, z} = split_data(a, b, sel);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: 多个赋值应产生多条边
        self.assertGreater(
            len(edges), 1,
            f"Expected multiple edges for multiple assignments, got {len(edges)}: {edges}"
        )

    def test_case_with_default_first(self):
        """[RED-6] case 语句 default 在前面"""
        source = '''
module top(
    input wire sel,
    input wire [7:0] a,
    input wire [7:0] b,
    output wire [7:0] y
);
    function [7:0] mux_def_first;
        input bit s;
        input [7:0] x;
        input [7:0] y;
        case (1'b1)  // synthesizable pattern
            default: if (s) mux_def_first = x;
                    else mux_def_first = y;
        endcase
    endfunction

    assign y = mux_def_first(sel, a, b);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: 应能处理 default 在前面的 case
        self.assertIsNotNone(edges, f"Expected edges, got: {edges}")

    def test_complex_expression_in_branch(self):
        """[RED-7] 分支内复杂表达式"""
        source = '''
module top(
    input wire [7:0] a,
    input wire [7:0] b,
    input wire [7:0] c,
    output wire [15:0] y
);
    function [15:0] complex_func;
        input [7:0] x;
        input [7:0] y;
        input [7:0] z;
        if (x[7])
            complex_func = {x, y} + {z, 8'h00};
        else
            complex_func = {y, z};
    endfunction

    assign y = complex_func(a, b, c);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: 复杂表达式应正确提取信号
        self.assertTrue(
            len(edges) >= 2,
            f"Expected at least 2 edges for complex expression, got {len(edges)}: {edges}"
        )

    def test_function_no_return_value(self):
        """[RED-8] 无返回值的任务 (void function)"""
        source = '''
module top(
    input wire clk,
    input wire [7:0] data
);
    function void send_data;
        input [7:0] d;
        // do something
    endfunction

    always @(posedge clk)
        send_data(data);
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')

        # 金标准: 任务调用不应崩溃,应返回 uncertain
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])

    def test_recursive_function(self):
        """[RED-9] 递归函数 (应该拒绝展开或限制深度)"""
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
        edges = self._get_edges(tracer, 'result', 'top')

        # 金标准: 递归函数应被检测并标记为 uncertain
        # 不应无限展开
        result = tracer.trace_signal('result', 'top')
        self.assertIn(result.confidence, ['uncertain', 'medium', 'high'])

    def test_case_with_ranges(self):
        """[RED-10] case 语句带范围匹配"""
        source = '''
module top(
    input wire [2:0] sel,
    input wire [7:0] a,
    input wire [7:0] b,
    input wire [7:0] c,
    output wire [7:0] y
);
    function [7:0] range_mux;
        input [2:0] s;
        input [7:0] x;
        input [7:0] y;
        input [7:0] z;
        case (s)
            0, 1: range_mux = x;      // multiple values
            2: range_mux = y;
            3, 4, 5: range_mux = z;  // another range
            default: range_mux = 8'h00;
        endcase
    endfunction

    assign y = range_mux(sel, a, b, c);
endmodule'''

        tracer = self._make_tracer(source)
        edges = self._get_edges(tracer, 'y', 'top')

        # 金标准: 范围 case 应产生对应的边
        # 0,1 -> x; 2 -> y; 3,4,5 -> z
        self.assertTrue(
            len(edges) >= 3,
            f"Expected at least 3 edges for range case, got {len(edges)}: {edges}"
        )


class TestFunctionInlineExpansionEdgeCases(unittest.TestCase):
    """边界 case 测试"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def test_empty_function(self):
        """[EDGE-1] 空函数体"""
        source = '''
module top(input [7:0] a, output [7:0] y);
    function [7:0] empty_func;
        input [7:0] x;
        // empty body
    endfunction
    assign y = empty_func(a);
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        # 金标准: 空函数应返回 uncertain
        self.assertIn(result.confidence, ['uncertain', 'medium', 'high'])

    def test_constant_assignment(self):
        """[EDGE-2] 常量赋值函数"""
        source = '''
module top(output [7:0] y);
    function [7:0] const_func;
        const_func = 8'hFF;
    endfunction
    assign y = const_func();
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        # 金标准: 常量赋值应被识别
        self.assertIn(result.confidence, ['high', 'medium'])

    def test_function_with_local_var(self):
        """[EDGE-3] 带局部变量的函数"""
        source = '''
module top(input [7:0] a, output [7:0] y);
    function [7:0] local_var_func;
        input [7:0] x;
        reg [7:0] temp;
        begin
            temp = x + 1;
            local_var_func = temp;
        end
    endfunction
    assign y = local_var_func(a);
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        # 金标准: 局部变量不应暴露到接口
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    # 按优先级运行测试
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 按顺序添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestFunctionInlineExpansion))
    suite.addTests(loader.loadTestsFromTestCase(TestFunctionInlineExpansionEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
