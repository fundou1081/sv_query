# test_opentitan_i2c.py - OpenTitan I2C 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
OpenTitan I2C 模块测试:
1. 接口信号
2. 双向信号
3. 中断信号
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestOpenTitanI2C(unittest.TestCase):
    """OpenTitan I2C 模块测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_i2c_basic_structure(self):
        """[Golden] I2C 基本结构
        
        RTL: OpenTitan i2c.sv 核心逻辑
        预期:
        - 模块可解析
        - I2C 信号存在
        """
        # 简化版 I2C 核心逻辑
        source = '''module i2c (
    input  logic clk_i,
    input  logic rst_ni,
    
    // I2C signals
    input  logic cio_scl_i,
    output logic cio_scl_o,
    output logic cio_scl_en_o,
    input  logic cio_sda_i,
    output logic cio_sda_o,
    output logic cio_sda_en_o,
    
    // Interrupts
    output logic intr_fmt_threshold_o,
    output logic intr_rx_threshold_o
);
    logic scl_q, sda_q;
    logic scl_d, sda_d;
    
    assign cio_scl_o = scl_q;
    assign cio_sda_o = sda_q;
    assign cio_scl_en_o = 1'b1;
    assign cio_sda_en_o = 1'b1;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            scl_q <= 1'b1;
            sda_q <= 1'b1;
        end else begin
            scl_q <= scl_d;
            sda_q <= sda_d;
        end
    end
    
    always_comb begin
        scl_d = cio_scl_i;
        sda_d = cio_sda_i;
    end
    
    assign intr_fmt_threshold_o = 1'b0;
    assign intr_rx_threshold_o = 1'b0;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: I2C 信号存在
        has_scl = any('scl' in n for n in nodes)
        has_sda = any('sda' in n for n in nodes)
        self.assertTrue(has_scl, f"scl not found in {nodes}")
        self.assertTrue(has_sda, f"sda not found in {nodes}")
    
    def test_i2c_signal_chain(self):
        """[Golden] I2C 信号链
        
        RTL: cio_scl_i -> scl_d -> scl_q -> cio_scl_o
        预期:
        - 信号链正确追踪
        """
        source = '''module i2c (
    input  logic clk_i,
    input  logic rst_ni,
    input  logic cio_scl_i,
    output logic cio_scl_o
);
    logic scl_q, scl_d;
    
    assign cio_scl_o = scl_q;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            scl_q <= 1'b1;
        end else begin
            scl_q <= scl_d;
        end
    end
    
    always_comb begin
        scl_d = cio_scl_i;
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: cio_scl_i -> scl_d
        has_input_chain = any('cio_scl_i' in edge[0] and 'scl_d' in edge[1] for edge in edges)
        self.assertTrue(has_input_chain, f"cio_scl_i -> scl_d not found in {edges}")
        
        # 验证: scl_d -> scl_q
        has_ff_chain = any('scl_d' in edge[0] and 'scl_q' in edge[1] for edge in edges)
        self.assertTrue(has_ff_chain, f"scl_d -> scl_q not found in {edges}")
        
        # 验证: scl_q -> cio_scl_o
        has_output_chain = any('scl_q' in edge[0] and 'cio_scl_o' in edge[1] for edge in edges)
        self.assertTrue(has_output_chain, f"scl_q -> cio_scl_o not found in {edges}")

if __name__ == '__main__':
    unittest.main()
