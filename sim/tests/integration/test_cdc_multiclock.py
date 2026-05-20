#==============================================================================
# test_cdc_multiclock.py - 多时钟域 CDC 测试
#==============================================================================
"""
[铁律13] 金标准测试
测试多时钟域场景下 CLOCK/RESET 边工作正常
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind
from trace.core.query.clock_domain import ClockDomainTracer


class TestCDCMultiClock(unittest.TestCase):
    """多时钟域 CDC 测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_two_independent_clock_domains(self):
        """[金标准] 两个独立时钟域
        
        期望:
        - trace('multi_clk.clk_a').registers 包含 q_a
        - trace('multi_clk.clk_b').registers 包含 q_b
        - 各自有独立的复位树
        """
        source = '''
module multi_clk(
    input wire clk_a, input wire clk_b,
    input wire rst_a_n, input wire rst_b_n,
    input wire d_a, input wire d_b,
    output logic q_a, output logic q_b
);
    always_ff @(posedge clk_a or negedge rst_a_n) begin
        if (!rst_a_n) q_a <= 1'b0;
        else q_a <= d_a;
    end
    always_ff @(posedge clk_b or negedge rst_b_n) begin
        if (!rst_b_n) q_b <= 1'b0;
        else q_b <= d_b;
    end
endmodule'''
        
        graph = self._build_graph(source)
        cdt = ClockDomainTracer(graph)
        
        # 检查 clk_a 时钟域
        result_a = cdt.trace('multi_clk.clk_a')
        self.assertIn('multi_clk.q_a', [r.id for r in result_a.registers],
            f"clk_a 域应该有 q_a，实际寄存器: {[r.id for r in result_a.registers]}")
        self.assertTrue(any(e.src == 'multi_clk.rst_a_n' for e in result_a.reset_tree),
            f"clk_a 域应该有复位树 rst_a_n->q_a")
        
        # 检查 clk_b 时钟域
        result_b = cdt.trace('multi_clk.clk_b')
        self.assertIn('multi_clk.q_b', [r.id for r in result_b.registers],
            f"clk_b 域应该有 q_b，实际寄存器: {[r.id for r in result_b.registers]}")
        self.assertTrue(any(e.src == 'multi_clk.rst_b_n' for e in result_b.reset_tree),
            f"clk_b 域应该有复位树 rst_b_n->q_b")
    
    def test_clock_domain_traces_all_domains(self):
        """[金标准] trace_all_domains 应该找到两个域
        
        期望: 2 个时钟域
        """
        source = '''
module multi_clk(
    input wire clk_a, input wire clk_b,
    input wire rst_a_n, input wire rst_b_n,
    input wire d_a, input wire d_b,
    output logic q_a, output logic q_b
);
    always_ff @(posedge clk_a or negedge rst_a_n) q_a <= d_a;
    always_ff @(posedge clk_b or negedge rst_b_n) q_b <= d_b;
endmodule'''
        
        graph = self._build_graph(source)
        cdt = ClockDomainTracer(graph)
        all_domains = cdt.trace_all_domains()
        
        self.assertEqual(len(all_domains), 2, 
            f"应该找到 2 个时钟域，实际: {len(all_domains)}")
    
    def test_single_register_no_cdc_violation(self):
        """[边界] 单域设计不应有 CDC 违规
        
        期望: check_cdc_violations 返回空列表
        """
        source = '''
module single_clk(
    input wire clk,
    input wire rst_n,
    input wire d,
    output logic q
);
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) q <= 0;
        else q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        cdt = ClockDomainTracer(graph)
        violations = cdt.check_cdc_violations()
        
        self.assertEqual(len(violations), 0,
            f"单域设计不应有 CDC 违规，实际: {violations}")


if __name__ == '__main__':
    unittest.main()
