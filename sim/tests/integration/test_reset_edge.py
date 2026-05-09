#==============================================================================
# test_reset_edge.py - RESET 边金标准测试
#==============================================================================
"""
[铁律13] 金标准测试
测试 always_ff @(posedge clk or negedge rst_n) 创建 RESET 边

金标准 (Golden Standard):
RTL:
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) q <= 0;
    else q <= d;
  end
期望:
  - CLOCK 边: clk -> q (EdgeKind.CLOCK)
  - RESET 边: rst_n -> q (EdgeKind.RESET)
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph_models import EdgeKind
from trace.core.query_clock_domain import ClockDomainTracer


class TestResetEdge(unittest.TestCase):
    """RESET 边测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_reset_edge_creation(self):
        """[金标准] always_ff with reset 创建 RESET 边
        
        期望:
        - CLOCK 边: clk -> q (EdgeKind.CLOCK)
        - RESET 边: rst_n -> q (EdgeKind.RESET)
        """
        source = '''
module top(input wire clk, input wire rst_n, input wire d, output logic q);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 q 的边
        clock_preds = []
        reset_preds = []
        driver_preds = []
        
        for pred in graph.predecessors('top.q'):
            edge = graph.get_edge(pred, 'top.q')
            if edge:
                if edge.kind == EdgeKind.CLOCK:
                    clock_preds.append(pred)
                elif edge.kind == EdgeKind.RESET:
                    reset_preds.append(pred)
                elif edge.kind == EdgeKind.DRIVER:
                    driver_preds.append(pred)
        
        # 验证 CLOCK 边
        self.assertIn('top.clk', clock_preds,
            f"应该有 CLOCK 边: clk -> q，实际前驱是 {clock_preds}")
        
        # 验证 RESET 边
        self.assertIn('top.rst_n', reset_preds,
            f"应该有 RESET 边: rst_n -> q，实际前驱是 {reset_preds}")
    
    def test_reset_tree_detection(self):
        """[金标准] ClockDomainTracer 应该检测到复位树
        
        期望: trace('clk').reset_tree 非空
        """
        source = '''
module top(input wire clk, input wire rst_n, input wire d, output logic q);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule'''
        
        graph = self._build_graph(source)
        cdt = ClockDomainTracer(graph)
        result = cdt.trace('clk')
        
        reset_tree_strs = [f"{e.src}->{e.dst}" for e in result.reset_tree]
        self.assertIn('top.rst_n->top.q', reset_tree_strs,
            f"复位树应该包含 rst_n->q，实际是 {reset_tree_strs}")
    
    def test_without_reset_no_reset_edge(self):
        """[边界] 没有 reset 的 always_ff 不应创建 RESET 边
        
        期望: 只有 CLOCK 边，没有 RESET 边
        """
        source = '''
module top(input wire clk, input wire d, output logic q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        has_reset_edge = False
        for pred in graph.predecessors('top.q'):
            edge = graph.get_edge(pred, 'top.q')
            if edge and edge.kind == EdgeKind.RESET:
                has_reset_edge = True
                break
        
        self.assertFalse(has_reset_edge, "always_ff 没有 reset 不应该有 RESET 边")


if __name__ == '__main__':
    unittest.main()
