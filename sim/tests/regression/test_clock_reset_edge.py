# test_clock_reset_edge.py - CLOCK/RESET 边测试
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
CLOCK/RESET 边相关测试:
1. 嵌套 always_ff
2. 异步复位组合
3. 同步复位
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestClockResetEdge(unittest.TestCase):
    """CLOCK/RESET 边测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'t': tree})
    
    def test_nested_always_ff(self):
        """[Golden] 嵌套 always_ff
        
        RTL: 两个 always_ff 块共享相同时钟
        
        预期:
        - q1, q2 节点存在
        - d1 -> q1, d2 -> q2 驱动关系
        """
        source = '''
module top (
    input logic clk,
    input logic rst_n,
    input logic d1, d2,
    output logic q1, q2
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q1 <= 1'b0;
        else
            q1 <= d1;
    end
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q2 <= 1'b0;
        else
            q2 <= d2;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        nodes = list(graph.nodes())
        
        # 金标准: q1, q2 节点存在
        self.assertTrue(any('q1' in n for n in nodes), f"q1 节点应存在，实际节点: {nodes}")
        self.assertTrue(any('q2' in n for n in nodes), f"q2 节点应存在，实际节点: {nodes}")
    
    def test_async_reset_combination(self):
        """[Golden] 异步复位组合
        
        RTL: always_ff @(posedge clk or negedge rst_n)
        
        预期:
        - rst_n 作为复位信号
        - clk -> q CLOCK 边存在
        """
        source = '''
module top (
    input logic clk,
    input logic rst_n,
    input logic d,
    output logic q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        # 金标准: clk -> q 边存在
        edges = list(graph.edges())
        has_clk_q = any('clk' in s and 'q' in d for s, d in edges)
        self.assertTrue(has_clk_q, f"clk -> q 边应存在，实际边: {edges}")
    
    def test_sync_reset(self):
        """[Golden] 同步复位
        
        RTL: always_ff @(posedge clk) begin if (rst) ...
        
        预期:
        - clk -> q CLOCK 边存在
        - 复位在时钟边沿生效
        """
        source = '''
module top (
    input logic clk,
    input logic rst,
    input logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        if (rst)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        # 金标准: clk -> q 边存在
        edges = list(graph.edges())
        has_clk_q = any('clk' in s and 'q' in d for s, d in edges)
        self.assertTrue(has_clk_q, f"clk -> q 边应存在，实际边: {edges}")


class TestClockEdgeCreation(unittest.TestCase):
    """CLOCK 边创建测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'t': tree})
    
    def test_clock_edge_creation(self):
        """[Golden] CLOCK 边创建
        
        预期:
        - d -> q DRIVER 边存在
        - clk -> q CLOCK 边存在
        """
        source = '''
module top (
    input logic clk,
    input logic d,
    output logic q
);
    always_ff @(posedge clk)
        q <= d;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        # 检查边类型
        from trace.core.graph.models import EdgeKind
        has_driver = False
        has_clock = False
        for (s, d), e in graph._edge_data.items():
            if 'd' in s and 'q' in d and e.kind == EdgeKind.DRIVER:
                has_driver = True
            if 'clk' in s and 'q' in d and e.kind == EdgeKind.CLOCK:
                has_clock = True
        
        self.assertTrue(has_driver, f"d -> q DRIVER 边应存在")
        self.assertTrue(has_clock, f"clk -> q CLOCK 边应存在")


if __name__ == '__main__':
    unittest.main()
