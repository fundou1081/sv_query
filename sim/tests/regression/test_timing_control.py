"""测试时序控制表达式解析
- 延迟赋值: a <= #5 b;
- repeat timing control: a = repeat(3) @(posedge clk) b;
"""
import sys
sys.path.insert(0, 'src')
import pyslang
from trace.unified_tracer import UnifiedTracer
import unittest


class TestTimingControlParsing(unittest.TestCase):
    """金标准: 时序控制表达式应该被正确解析"""

    def test_delay_expression(self):
        """a <= #5 b; 延迟赋值
        '#5' 是延迟，不是信号名
        边应该是 d -> q，不是 '#5 b' -> q
        """
        src = '''
module test;
    reg a, b;
    initial a <= #5 b;
endmodule
'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        # 检查边是否存在
        edges = list(graph.edges())
        print(f"Edges: {edges}")
        
        # 不应该有 '#5 b' 作为源
        bad_edges = [e for e in edges if '#5' in e[0] or '#5' in e[1]]
        self.assertEqual(bad_edges, [], f"不应有 '#5' 边: {bad_edges}")
        
        # 应该存在 d -> q 边
        self.assertTrue(('test.b', 'test.a') in edges, f"应该有 b -> a 边，实际: {edges}")

    def test_repeat_timing_control(self):
        """a = repeat(3) @(posedge clk) b; repeat timing control
        'repeat(3) @(posedge clk)' 是 timing control，不是信号名
        """
        src = '''
module test;
    reg a, b, clk;
    initial a = repeat(3) @(posedge clk) b;
endmodule
'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        edges = list(graph.edges())
        print(f"Edges: {edges}")
        
        # 不应该有 'repeat(3)' 在边中
        bad_edges = [e for e in edges if 'repeat' in e[0] or 'repeat' in e[1]]
        self.assertEqual(bad_edges, [], f"不应有 'repeat' 边: {bad_edges}")

    def test_simple_event_timing(self):
        """@posedge clk b; 简单事件时序"""
        src = '''
module test;
    reg a, b, clk;
    always @(posedge clk) begin
        a = b;
    end
endmodule
'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        edges = list(graph.edges())
        print(f"Edges: {edges}")
        
        # 应该存在 b -> a 边
        self.assertTrue(('test.b', 'test.a') in edges, f"应该有 b -> a 边，实际: {edges}")


class TestClockDomainEdges(unittest.TestCase):
    """测试 CLOCK/RESET/ENABLE 边类型"""

    def test_clock_edge_creation(self):
        """always @(posedge clk) 应该创建 CLOCK 边"""
        src = '''
module test;
    reg q, d, clk;
    always @(posedge clk) begin
        q <= d;
    end
endmodule
'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        edges = list(graph.edges())
        print(f"Edges: {edges}")
        
        # 检查是否有 clock 相关边
        clock_edges = [e for e in edges if 'clk' in e[0].lower() or 'clk' in e[1].lower()]
        print(f"Clock edges: {clock_edges}")
        
        # 应该存在 d -> q 边
        self.assertTrue(('test.d', 'test.q') in edges, f"应该有 d -> q 边")


if __name__ == '__main__':
    unittest.main()
