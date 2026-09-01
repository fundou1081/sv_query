#==============================================================================
# test_genvar_for.py - genvar + generate-for 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: generate-for 之前只靠 case27 truth (4 个) + integration, 无独立
# regression 行为断言 (Plan F1 2026-08-12 引入 genvar_ctx substitute).
# 行为金标准 (EXTRACTION_COVERAGE #18): genvar 是编译期符号, 不产生节点;
# generate-for 展开后 wire/assign 的驱动边存在 (genvar_ctx 替换 RHS).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


def _build_graph(source):
    """构建 tracer graph 的统一 helper"""
    tracer = UnifiedTracer(sources={'t.sv': source})
    tracer.build_graph()
    return tracer.get_graph()


class TestGenvarFor(unittest.TestCase):
    """genvar + generate-for — 主路径语法"""

    def test_genvar_for_wire(self):
        """[Golden] generate-for 内 wire: genvar i; for (...) wire w; assign w = a;
        行为: generate 展开后 a→w DRIVER 边存在 (genvar_ctx substitute).
        """
        src = ('module top(input logic a); '
               'genvar i; '
               'generate for (i = 0; i < 2; i = i + 1) begin : g '
               '  wire w; assign w = a; '
               'end endgenerate '
               'endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'),
                             "generate-for 内 assign w = a 应生成 a→w 边")

    def test_genvar_not_signal(self):
        """[Golden] genvar 不产生信号节点: genvar i; → 无 top.i 节点."""
        src = ('module top(input logic a); '
               'genvar i; '
               'generate for (i = 0; i < 2; i = i + 1) begin : g '
               '  wire w; assign w = a; '
               'end endgenerate '
               'endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertNotIn('top.i', graph.nodes(), "genvar i 不应是信号节点")

    def test_genvar_for_instance(self):
        """[Golden] generate-for 内实例化: 实例节点存在."""
        src = ('module sub(input logic x, output logic y); assign y = x; endmodule\n'
               'module top(input logic a); '
               'genvar i; '
               'generate for (i = 0; i < 2; i = i + 1) begin : g '
               '  sub u_sub(.x(a), .y()); '
               'end endgenerate '
               'endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        # generate 展开后的实例路径含 gen 块名
        insts = [n for n in graph.nodes() if '.u_sub' in n]
        self.assertGreaterEqual(len(insts), 1,
                                f"generate-for 内实例 u_sub 应存在, 实际节点: {insts}")

    def test_genvar_for_indexed_signal(self):
        """[Golden] genvar 索引位选: generate-for 内 sig[i] → 位选节点.
        行为: 展开后 top.sig[0] / top.sig[1] 位选节点存在 (或 base sig 驱动).
        """
        src = ('module top(input logic [1:0] sig, output logic [1:0] y); '
               'genvar i; '
               'generate for (i = 0; i < 2; i = i + 1) begin : g '
               '  assign y[i] = sig[i]; '
               'end endgenerate '
               'endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        # 位选节点或 base 信号驱动 y 的位选
        sel_nodes = [n for n in graph.nodes() if '[0]' in n or '[1]' in n]
        self.assertGreaterEqual(len(sel_nodes), 1,
                                f"genvar 索引应产生位选节点, 实际: {sel_nodes}")


if __name__ == '__main__':
    unittest.main()
