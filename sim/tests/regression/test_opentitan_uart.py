# test_opentitan_uart.py - OpenTitan UART 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
OpenTitan UART 模块测试:
1. 端口声明解析
2. always_ff 时序逻辑
3. always_comb 组合逻辑
4. 信号驱动关系
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestOpenTitanUART(unittest.TestCase):
    """OpenTitan UART 模块测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_uart_rx_ports(self):
        """[Golden] UART RX 端口声明
        
        RTL: OpenTitan uart_rx.sv
        预期:
        - 模块可解析
        - 端口信号存在
        """
        # 简化版 uart_rx 核心逻辑
        source = '''module uart_rx (
    input           clk_i,
    input           rst_ni,
    input           rx_enable,
    input           tick_baud_x16,
    output logic    tick_baud,
    output logic    rx_valid,
    output [7:0]    rx_data,
    output logic    idle,
    input           rx
);
    logic [10:0] sreg_q, sreg_d;
    logic [3:0]  bit_cnt_q, bit_cnt_d;
    logic [3:0]  baud_div_q, baud_div_d;
    
    assign tick_baud = 1'b0;
    assign idle = 1'b1;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            sreg_q <= 11'h0;
        end else begin
            sreg_q <= sreg_d;
        end
    end
    
    always_comb begin
        sreg_d = sreg_q;
        if (rx_enable) begin
            sreg_d = 11'h0;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: 关键信号存在
        has_sreg = any('sreg' in n for n in nodes)
        self.assertTrue(has_sreg, f"sreg not found in {nodes}")
    
    def test_uart_rx_signal_chain(self):
        """[Golden] UART RX 信号链
        
        RTL: sreg_d -> sreg_q (always_ff)
        预期:
        - sreg_d -> sreg_q 驱动关系
        """
        source = '''module uart_rx (
    input           clk_i,
    input           rst_ni,
    input           rx_enable,
    output [10:0]   sreg_q
);
    logic [10:0] sreg_d;
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            sreg_q <= 11'h0;
        end else begin
            sreg_q <= sreg_d;
        end
    end
    
    always_comb begin
        sreg_d = sreg_q;
        if (rx_enable) begin
            sreg_d = 11'h0;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: sreg_d -> sreg_q
        has_sreg_chain = any('sreg_d' in edge[0] and 'sreg_q' in edge[1] for edge in edges)
        self.assertTrue(has_sreg_chain, f"sreg_d -> sreg_q not found in {edges}")
    
    def test_uart_tx_ports(self):
        """[Golden] UART TX 端口声明
        
        RTL: OpenTitan uart_tx.sv
        预期:
        - 模块可解析
        - 端口信号存在
        """
        # 简化版 uart_tx 核心逻辑
        source = '''module uart_tx (
    input           clk_i,
    input           rst_ni,
    input           tx_enable,
    input           tick_baud,
    input           tx_valid,
    input [7:0]     tx_data,
    output logic    tx_ready,
    output logic    tx
);
    logic [10:0] sreg_q, sreg_d;
    logic [3:0]  bit_cnt_q, bit_cnt_d;
    
    assign tx = sreg_q[0];
    
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            sreg_q <= 11'h0;
            bit_cnt_q <= 4'h0;
        end else begin
            sreg_q <= sreg_d;
            bit_cnt_q <= bit_cnt_d;
        end
    end
    
    always_comb begin
        sreg_d = sreg_q;
        bit_cnt_d = bit_cnt_q;
        if (tx_enable && tx_valid) begin
            sreg_d = {1'b1, tx_data, 1'b0, 1'b1};
            bit_cnt_d = 4'd11;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: tx 信号存在
        has_tx = any('tx' in n for n in nodes)
        self.assertTrue(has_tx, f"tx not found in {nodes}")
        
        # 验证: sreg_q[0] -> tx
        has_tx_driver = any('sreg_q' in edge[0] and 'tx' in edge[1] for edge in edges)
        self.assertTrue(has_tx_driver, f"sreg_q -> tx not found in {edges}")

if __name__ == '__main__':
    unittest.main()
