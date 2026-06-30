# test_verilog_always.py - Verilog always 块识别测试
# [铁律7] 先写测试
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind


def _build(source, filename='test.v'):
    tracer = UnifiedTracer(sources={filename: source})
    return tracer.build_graph()


def _get_regs(graph):
    return [n for n in graph.nodes()
            if graph.get_node(n) and graph.get_node(n).kind == NodeKind.REG]


class TestVerilogAlways(unittest.TestCase):
    """Verilog always @(posedge clk) 识别为寄存器"""

    def test_always_posedge_clk(self):
        """[金标准] Verilog always @(posedge clk) → REG"""
        source = '''module test(input clk, input d, output reg q);
    always @(posedge clk) begin
        q <= d;
    end
endmodule'''
        graph = _build(source)
        regs = _get_regs(graph)
        self.assertGreaterEqual(len(regs), 1,
            f"always @(posedge clk) 应识别为 REG, 实际: {[n for n in graph.nodes()]}")

    def test_always_ff_still_works(self):
        """[金标准] SystemVerilog always_ff 仍然正确"""
        source = '''module test(input clk, input d, output logic q);
    always_ff @(posedge clk) begin
        q <= d;
    end
endmodule'''
        graph = _build(source)
        regs = _get_regs(graph)
        self.assertGreaterEqual(len(regs), 1)

    def test_always_comb_not_reg(self):
        """[负面] always_comb 不应识别为 REG"""
        source = '''module test(input a, b, output logic c);
    always_comb begin
        c = a & b;
    end
endmodule'''
        graph = _build(source)
        regs = _get_regs(graph)
        self.assertEqual(len(regs), 0, "always_comb 不应是 REG")

    def test_verilog_always_negedge_rst(self):
        """[金标准] Verilog always @(posedge clk or negedge rst_n) → REG"""
        source = '''module test(input clk, rst_n, input d, output reg q);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) q <= 0;
        else q <= d;
    end
endmodule'''
        graph = _build(source)
        regs = _get_regs(graph)
        self.assertGreaterEqual(len(regs), 1)


if __name__ == '__main__':
    unittest.main()
