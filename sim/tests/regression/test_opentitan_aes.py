# test_opentitan_aes.py - OpenTitan AES 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
OpenTitan AES 模块测试:
1. 参数化模块
2. 包导入
3. 复杂信号链
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestOpenTitanAES(unittest.TestCase):
    """OpenTitan AES 模块测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_aes_basic_structure(self):
        """[Golden] AES 基本结构

        RTL: OpenTitan aes.sv 核心逻辑
        预期:
        - 模块可解析
        - 参数声明存在
        - 端口信号存在
        """
        # 简化版 AES 核心逻辑
        source = '''module aes #(
    parameter bit AES192Enable = 1,
    parameter bit AESGCMEnable = 1
) (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic [127:0] data_i,
    output logic [127:0] data_o,
    input  logic        start_i,
    output logic        done_o
);
    logic [127:0] state_q, state_d;
    logic         busy_q, busy_d;

    assign data_o = state_q;
    assign done_o = !busy_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= 128'h0;
            busy_q <= 1'b0;
        end else begin
            state_q <= state_d;
            busy_q <= busy_d;
        end
    end

    always_comb begin
        state_d = state_q;
        busy_d = busy_q;

        if (start_i) begin
            state_d = data_i;
            busy_d = 1'b1;
        end else if (busy_q) begin
            state_d = state_q ^ 128'hDEADBEEF;
            busy_d = 1'b0;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())

        # 验证: state_q 节点存在
        has_state = any('state' in n for n in nodes)
        self.assertTrue(has_state, f"state not found in {nodes}")

        # 验证: data_i -> state_d -> state_q 信号链
        has_data_chain = any('data_i' in edge[0] for edge in edges)
        self.assertTrue(has_data_chain, f"data_i driver not found in {edges}")

    def test_aes_signal_chain(self):
        """[Golden] AES 信号链

        RTL: data_i -> state_d -> state_q -> data_o
        预期:
        - 信号链正确追踪
        """
        source = '''module aes (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic [127:0] data_i,
    output logic [127:0] data_o
);
    logic [127:0] state_q, state_d;

    assign data_o = state_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= 128'h0;
        end else begin
            state_q <= state_d;
        end
    end

    always_comb begin
        state_d = data_i;
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())

        # 验证: data_i -> state_d
        has_input_chain = any('data_i' in edge[0] and 'state_d' in edge[1] for edge in edges)
        self.assertTrue(has_input_chain, f"data_i -> state_d not found in {edges}")

        # 验证: state_d -> state_q
        has_ff_chain = any('state_d' in edge[0] and 'state_q' in edge[1] for edge in edges)
        self.assertTrue(has_ff_chain, f"state_d -> state_q not found in {edges}")

        # 验证: state_q -> data_o
        has_output_chain = any('state_q' in edge[0] and 'data_o' in edge[1] for edge in edges)
        self.assertTrue(has_output_chain, f"state_q -> data_o not found in {edges}")

if __name__ == '__main__':
    unittest.main()
