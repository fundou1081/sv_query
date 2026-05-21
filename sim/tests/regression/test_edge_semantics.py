#==============================================================================
# test_edge_semantics.py - 金标准测试: 边语义上下文
# 铁律13: 先推导金标准，再验证
#==============================================================================
# 目标: TraceEdge 携带 clock_domain 和 condition 信息
# 场景:
#   1. always_ff 的驱动边携带时钟域
#   2. if/else 的驱动边携带条件
#   3. if/else + always_ff 组合
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind


class TestClockDomainOnEdge(unittest.TestCase):
    """驱动边携带时钟域信息"""

    def test_always_ff_clock_on_edge(self):
        """[Golden] always_ff 驱动边携带时钟
        RTL: always_ff @(posedge clk) q <= d;
        金标准:
        | 边      | clock_domain |
        |---------|-------------|
        | d → q   | clk         |
        """
        src = '''
module top(input clk, d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        # 找到 d → q 的驱动边
        edge = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge, "应有 d → q 的驱动边")
        self.assertEqual(edge.clock_domain, 'clk',
            "驱动边应携带时钟域 'clk'")

    def test_always_ff_async_reset_clock(self):
        """[Golden] 异步复位 always_ff 时钟域
        RTL: always_ff @(posedge clk or posedge rst) ...
        金标准: clock_domain = clk (主时钟)
        """
        src = '''
module top(input clk, rst, d, output reg q);
    always_ff @(posedge clk or posedge rst) begin
        if (rst) q <= 0;
        else q <= d;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge)
        self.assertEqual(edge.clock_domain, 'clk')

    def test_always_comb_no_clock(self):
        """[Golden] always_comb 无时钟域
        RTL: always_comb y = a & b;
        金标准: clock_domain = '' (无时钟)
        """
        src = '''
module top(input a, b, output reg y);
    always_comb y = a & b;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge)
        self.assertEqual(edge.clock_domain, '',
            "always_comb 边不应有时钟域")

    def test_assign_no_clock(self):
        """[Golden] assign 无时钟域
        RTL: assign y = a;
        金标准: clock_domain = ''
        """
        src = '''
module top(input a, output y);
    assign y = a;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge)
        self.assertEqual(edge.clock_domain, '')


class TestConditionOnEdge(unittest.TestCase):
    """驱动边携带 if/else 条件"""

    def test_if_else_condition(self):
        """[Golden] if/else 驱动边携带条件
        RTL: if (sel) y = a; else y = b;
        金标准:
        | 边      | condition |
        |---------|-----------|
        | a → y   | sel       |
        | b → y   | !sel      |
        """
        src = '''
module top(input a, b, sel, output reg y);
    always_comb begin
        if (sel) y = a;
        else y = b;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge_a = graph.get_edge('top.a', 'top.y')
        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_a)
        self.assertIsNotNone(edge_b)
        self.assertEqual(edge_a.condition, 'sel',
            "a → y 的条件应为 'sel'")
        self.assertEqual(edge_b.condition, '!sel',
            "b → y 的条件应为 '!sel'")

    def test_nested_if_condition(self):
        """[Golden] 嵌套 if 条件
        RTL: if (sel1) begin if (sel2) y = a; else y = b; end else y = c;
        金标准:
        | 边      | condition    |
        |---------|-------------|
        | a → y   | sel1 && sel2 |
        | b → y   | sel1 && !sel2|
        | c → y   | !sel1        |
        """
        src = '''
module top(input a, b, c, sel1, sel2, output reg y);
    always_comb begin
        if (sel1) begin
            if (sel2) y = a;
            else y = b;
        end else y = c;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge_a = graph.get_edge('top.a', 'top.y')
        edge_b = graph.get_edge('top.b', 'top.y')
        edge_c = graph.get_edge('top.c', 'top.y')
        self.assertIsNotNone(edge_a)
        self.assertIsNotNone(edge_b)
        self.assertIsNotNone(edge_c)
        # 条件可能用不同格式，只要语义正确即可
        self.assertIn('sel1', edge_a.condition)
        self.assertIn('sel2', edge_a.condition)
        self.assertIn('sel1', edge_b.condition)
        self.assertIn('!sel2', edge_b.condition)
        self.assertIn('!sel1', edge_c.condition)

    def test_partial_if_no_else(self):
        """[Golden] 无 else 的 if
        RTL: if (sel) y = a;
        金标准: a → y condition = sel
        """
        src = '''
module top(input a, sel, output reg y);
    always_comb begin
        if (sel) y = a;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a)
        self.assertEqual(edge_a.condition, 'sel')


class TestCombinedClockAndCondition(unittest.TestCase):
    """时钟域 + 条件组合"""

    def test_ff_with_if(self):
        """[Golden] always_ff 中 if/else
        RTL: always_ff @(posedge clk) if (en) q <= d;
        金标准:
        | 边      | clock_domain | condition |
        |---------|-------------|-----------|
        | d → q   | clk         | en        |
        """
        src = '''
module top(input clk, en, d, output reg q);
    always_ff @(posedge clk) begin
        if (en) q <= d;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge)
        self.assertEqual(edge.clock_domain, 'clk')
        self.assertEqual(edge.condition, 'en')

    def test_ff_if_else(self):
        """[Golden] always_ff 中 if/else 双分支
        RTL: always_ff @(posedge clk) if (sel) q <= a; else q <= b;
        金标准:
        | 边      | clock_domain | condition |
        |---------|-------------|-----------|
        | a → q   | clk         | sel       |
        | b → q   | clk         | !sel      |
        """
        src = '''
module top(input clk, sel, a, b, output reg q);
    always_ff @(posedge clk) begin
        if (sel) q <= a;
        else q <= b;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        tracer.build_graph()
        graph = tracer.get_graph()

        edge_a = graph.get_edge('top.a', 'top.q')
        edge_b = graph.get_edge('top.b', 'top.q')
        self.assertIsNotNone(edge_a)
        self.assertIsNotNone(edge_b)
        self.assertEqual(edge_a.clock_domain, 'clk')
        self.assertEqual(edge_b.clock_domain, 'clk')
        self.assertEqual(edge_a.condition, 'sel')
        self.assertEqual(edge_b.condition, '!sel')


if __name__ == '__main__':
    unittest.main()
