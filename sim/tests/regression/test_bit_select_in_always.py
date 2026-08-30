#==============================================================================
# test_bit_select_in_always.py - 金标准测试: always 块内位选择
# 铁律13: 先推导金标准，再验证
# [iter_063 2026-08-29] 升级断言强度: 保留原有 trace_signal/drivers
# 断言, 补充 UnifiedTracer + graph.get_edge 行为断言 — 验证位选
# /三元/concat-LHS 等结构确实生成了 DRIVER 边 (行为金标准).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


def _build_graph(source, filename: str = 't.sv'):
    """[iter_063] 构建 tracer graph 的统一 helper (行为断言用)"""
    tracer = UnifiedTracer(sources={filename: source})
    tracer.build_graph()
    return tracer.get_graph()


class TestBitSelectInAlways(unittest.TestCase):
    """always 块内位选择驱动提取"""

    def test_always_comb_bit_select_fixed(self):
        """[Golden] always_comb 中固定位选择
        RTL: always_comb y = data[3];
        金标准:
        | 信号 | 驱动源   | 来源        |
        |------|----------|-------------|
        | y    | [data]   | always_comb |
        - [iter_063] 位选节点 data[3] → y DRIVER 边; data 节点被引用
        """
        src = '''
module top(input [7:0] data, output reg y);
    always_comb y = data[3];
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_comb y = data[3] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 位选节点 data[3] → y DRIVER 边存在
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        self.assertIn('top.data[3]', nodes, "固定位选应生成 data[3] 节点")
        edge = graph.get_edge('top.data[3]', 'top.y')
        self.assertIsNotNone(edge, "位选 data[3]→y 应生成 DRIVER 边")

    def test_always_comb_bit_select_dynamic(self):
        """[Golden] always_comb 中动态位选择
        RTL: always_comb y = data[idx];
        金标准:
        | 信号 | 驱动源   | 来源        |
        |------|----------|-------------|
        | y    | [data]   | always_comb |
        - [iter_063] data → y DRIVER 边; idx 不直接驱动 y (作为索引)
        """
        src = '''
module top(input [7:0] data, input [2:0] idx, output reg y);
    always_comb y = data[idx];
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_comb y = data[idx] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: data → y DRIVER 边 (动态索引保留 data 主信号)
        graph = _build_graph(src)
        edge = graph.get_edge('top.data', 'top.y')
        self.assertIsNotNone(edge, "动态位选 data[idx] 应生成 data→y DRIVER 边")

    def test_always_comb_range_select(self):
        """[Golden] always_comb 中范围选择
        RTL: always_comb y = data[7:4];
        金标准:
        | 信号 | 驱动源   | 来源        |
        |------|----------|-------------|
        | y    | [data]   | always_comb |
        - [iter_063] 范围选择节点 data[7:4] → y DRIVER 边
        """
        src = '''
module top(input [7:0] data, output reg [3:0] y);
    always_comb y = data[7:4];
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_comb y = data[7:4] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 范围选择节点 data[7:4] → y DRIVER 边
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        self.assertIn('top.data[7:4]', nodes, "范围选择应生成 data[7:4] 节点")
        edge = graph.get_edge('top.data[7:4]', 'top.y')
        self.assertIsNotNone(edge, "范围选择 data[7:4]→y 应生成 DRIVER 边")

    def test_if_else_bit_select(self):
        """[Golden] if/else 中位选择
        RTL: if (sel) y = data[7]; else y = data[0];
        金标准:
        | 信号 | 驱动源         | 来源        |
        |------|----------------|-------------|
        | y    | [data, data]   | always_comb |
        - [iter_063] data[7]→y (条件 sel) 与 data[0]→y (条件 !sel) DRIVER 边
        """
        src = '''
module top(input [7:0] data, input sel, output reg y);
    always_comb begin
        if (sel) y = data[7];
        else y = data[0];
    end
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        # data[7] 和 data[0] 剥离位选择后都变成 data，去重后为1条边
        self.assertGreaterEqual(len(result.drivers), 1,
            "if/else 中位选择应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 两个位选节点各自驱动 y, 条件互补
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        self.assertIn('top.data[7]', nodes, "if 分支位选节点应存在")
        self.assertIn('top.data[0]', nodes, "else 分支位选节点应存在")
        edge_true = graph.get_edge('top.data[7]', 'top.y')
        self.assertIsNotNone(edge_true, "if 分支应生成 data[7]→y DRIVER 边")
        self.assertEqual(edge_true.condition, 'sel', "if 分支条件应为 sel")
        edge_false = graph.get_edge('top.data[0]', 'top.y')
        self.assertIsNotNone(edge_false, "else 分支应生成 data[0]→y DRIVER 边")
        self.assertEqual(edge_false.condition, '!sel', "else 分支条件应为 !sel")

    def test_case_bit_select(self):
        """[Golden] case 中位选择
        RTL: case(sel) 00: y=a[0]; 01: y=a[1]; default: y=a[2];
        金标准:
        | 信号 | 驱动源              | 来源        |
        |------|---------------------|-------------|
        | y    | [a, a, a]           | always_comb |
        - [iter_063] a[0]→y, a[1]→y, a[2]→y 各带 case 条件 DRIVER 边
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
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        # a[0], a[1], a[2] 剥离位选择后都变成 a，去重后为1条边
        self.assertGreaterEqual(len(result.drivers), 1,
            "case 中位选择应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 三个 case 分支位选节点各自驱动 y
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        for slice in ('a[0]', 'a[1]', 'a[2]'):
            self.assertIn(f'top.{slice}', nodes, f"case 分支 {slice} 节点应存在")
        # 每个位选节点应驱动 y
        for slice in ('a[0]', 'a[1]', 'a[2]'):
            edge = graph.get_edge(f'top.{slice}', 'top.y')
            self.assertIsNotNone(edge, f"case 分支 {slice}→y 应生成 DRIVER 边")

    def test_always_ff_bit_select(self):
        """[Golden] always_ff 中位选择
        RTL: always_ff @(posedge clk) q <= data[3];
        金标准:
        | 信号 | 驱动源   | 来源      |
        |------|----------|-----------|
        | q    | [data]   | always_ff |
        - [iter_063] 位选节点 data[3]→q DRIVER 边, assign_type=nonblocking
        """
        src = '''
module top(input clk, input [7:0] data, output reg q);
    always_ff @(posedge clk) q <= data[3];
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('q', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "always_ff q <= data[3] 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 位选节点 data[3] → q DRIVER 边, nonblocking
        graph = _build_graph(src)
        edge = graph.get_edge('top.data[3]', 'top.q')
        self.assertIsNotNone(edge, "always_ff 位选 data[3]→q 应生成 DRIVER 边")
        self.assertEqual(edge.assign_type, 'nonblocking',
            "always_ff 边应标记为 nonblocking")


class TestTernaryOperator(unittest.TestCase):
    """三元运算符多操作数提取"""

    def test_assign_ternary(self):
        """[Golden] assign 中三元运算符
        RTL: assign y = sel ? a : b;
        金标准:
        | 信号 | 驱动源    | 来源   |
        |------|-----------|--------|
        | y    | [a, b]    | assign |
        - [iter_063] a→y (条件 sel) 与 b→y (条件 !sel) 两条 DRIVER 边
        """
        src = '''
module top(input a, b, sel, output y);
    assign y = sel ? a : b;
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 2,
            "assign y = sel ? a : b 应有2个驱动 (a 和 b)")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 三目两侧操作数都驱动 y, 各自条件
        graph = _build_graph(src)
        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a, "三目 sel?a:b 应生成 a→y DRIVER 边")
        self.assertEqual(edge_a.condition, 'sel', "a 的条件应为 sel")
        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_b, "三目 sel?a:b 应生成 b→y DRIVER 边")
        self.assertEqual(edge_b.condition, '!(sel)', "b 的条件应为 !(sel)")

    def test_always_comb_ternary(self):
        """[Golden] always_comb 中三元运算符
        RTL: always_comb y = sel ? a : b;
        金标准:
        | 信号 | 驱动源    | 来源        |
        |------|-----------|-------------|
        | y    | [a, b]    | always_comb |
        - [iter_063] always_comb 内三目应生成 a→y 与 b→y DRIVER 边
        """
        src = '''
module top(input a, b, sel, output reg y);
    always_comb y = sel ? a : b;
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 2,
            "always_comb y = sel ? a : b 应有2个驱动 (a 和 b)")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
            "always_comb 三目应生成 a→y DRIVER 边")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'),
            "always_comb 三目应生成 b→y DRIVER 边")

    def test_assign_ternary_complex(self):
        """[Golden] assign 中嵌套三元运算符
        RTL: assign y = sel1 ? a : (sel2 ? b : c);
        金标准:
        | 信号 | 驱动源       | 来源   |
        |------|--------------|--------|
        | y    | [a, b, c]    | assign |
        - [iter_063] 嵌套三目 a→y, b→y, c→y 三条 DRIVER 边
        """
        src = '''
module top(input a, b, c, sel1, sel2, output y);
    assign y = sel1 ? a : (sel2 ? b : c);
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 3,
            "嵌套三元应有3个驱动 (a, b, c)")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 三个操作数都驱动 y, 条件各不相同
        graph = _build_graph(src)
        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a, "嵌套三目应生成 a→y DRIVER 边")
        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_b, "嵌套三目应生成 b→y DRIVER 边")
        edge_c = graph.get_edge('top.c', 'top.y')
        self.assertIsNotNone(edge_c, "嵌套三目应生成 c→y DRIVER 边")
        # 三个条件互不相同 (sel1 / !(sel1) && sel2 / !(sel1) && !(sel2))
        conds = {edge_a.condition, edge_b.condition, edge_c.condition}
        self.assertEqual(len(conds), 3, "嵌套三目三条边的条件应各不相同")


class TestConcatLHS(unittest.TestCase):
    """拼接赋值 LHS 多信号提取"""

    def test_assign_concat_lhs(self):
        """[Golden] 拼接赋值 LHS
        RTL: assign {y[2], y[1], y[0]} = {a, b, c};
        金标准:
        | 信号 | 驱动源    | 来源   |
        |------|-----------|--------|
        | y    | [a, b, c] | assign |
        - [iter_063] concat LHS 应生成 y[0/1/2] 子节点, 三个源各自驱动所有位
        """
        src = '''
module top(input a, b, c, output [2:0] y);
    assign {y[2], y[1], y[0]} = {a, b, c};
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 3,
            "assign {y[2], y[1], y[0]} = {a, b, c} 应有3个驱动")
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: concat LHS 拆分 y 为 y[2], y[1], y[0] 三个
        # 子节点, 每个源 (a/b/c) 驱动一个子节点 (而非所有).
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        # y 的位选子节点应存在
        for bit in ('y[2]', 'y[1]', 'y[0]'):
            self.assertIn(f'top.{bit}', nodes, f"concat LHS 应生成 {bit} 子节点")
        # a→y[2], b→y[1], c→y[0] (concat LHS 按位拼接)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y[2]'),
            "concat LHS a→y[2] DRIVER 边")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y[1]'),
            "concat LHS b→y[1] DRIVER 边")
        self.assertIsNotNone(graph.get_edge('top.c', 'top.y[0]'),
            "concat LHS c→y[0] DRIVER 边")


if __name__ == '__main__':
    unittest.main()
