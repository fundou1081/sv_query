#==============================================================================
# test_cdc.py - Clock Domain Crossing 检查
# [P2] 核心价值功能
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestCDC(unittest.TestCase):
    """CDC 检查测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # [金标准] CDC 追踪
    #----------------------------------------------------------------------
    
    def test_single_clock_domain(self):
        """[Golden] 单时钟域 (安全)"""
        source = '''
module top(
    input wire clk,
    input wire din,
    output reg q
);
    always_ff @(posedge clk) q <= din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_clock_domain('clk')
        
        self.assertIsNotNone(result.clock)
    
    def test_dual_clock_domains(self):
        """[Golden] 双时钟域"""
        source = '''
module top(
    input wire clk_a,
    input wire clk_b,
    input wire din_a,
    input wire din_b,
    output reg q_a,
    output reg q_b
);
    always_ff @(posedge clk_a) q_a <= din_a;
    always_ff @(posedge clk_b) q_b <= din_b;
endmodule'''
        
        tracer = self._make_tracer(source)
        
        result_a = tracer.trace_clock_domain('clk_a')
        result_b = tracer.trace_clock_domain('clk_b')
        
        self.assertIsNotNone(result_a.clock)
        self.assertIsNotNone(result_b.clock)
    
    def test_async_reset_considered(self):
        """[Golden] 异步复位"""
        source = '''
module top(
    input wire clk,
    input wire rst_n,
    input wire din,
    output reg q
);
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) q <= 0;
        else q <= din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_clock_domain('clk')
        
        self.assertIsNotNone(result.clock)
    
    #----------------------------------------------------------------------
    # [CDC 规则]
    #----------------------------------------------------------------------
    
    def test_cdc_violation_synchronous(self):
        """[CDC] 同步跨域 (危险)"""
        source = '''
module top(
    input wire clk_a,
    input wire clk_b,
    input wire din,
    output reg q
);
    always @(posedge clk_a or posedge clk_b)  // 错误风格
        q <= din;
endmodule'''
        
        tracer = self._make_tracer(source)
        violations = tracer.check_cdc_violations()
        
        # 应该有违规
        self.assertIsNotNone(violations)
    
    def test_multicycle_path(self):
        """[CDC] 多周期路径 (安全)"""
        source = '''
module top(
    input wire clk,
    input wire valid,
    input wire din,
    output reg q
);
    (* ASYNC_REG = "FALSE" *)
    always_ff @(posedge clk) begin
        if (valid)
            q <= din;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_clock_domain('clk')
        
        self.assertIsNotNone(result.clock)
    
    #----------------------------------------------------------------------
    # [边界]
    #----------------------------------------------------------------------
    
    def test_no_clock(self):
        """[Boundary] 无时钟"""
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_clock_domain('clk')
        
        self.assertIsNone(result.clock)


if __name__ == '__main__':
    unittest.main()
