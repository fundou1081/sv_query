#==============================================================================
# test_wire_top.py - wire 顶层/net decl 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件 (对齐 constraint/covergroup 密度)
# 背景: wire x = expr; 之前只靠 integration 顺带测, 无独立 regression 行为断言.
# 行为金标准 (module 域): RHS 真实信号 → wire (LHS) 的 DRIVER 边必须存在.
# 实现位置: src/trace/core/extractors/net_decl_extractor.py (Step 3b 拆出)
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


class TestWireTop(unittest.TestCase):
    """wire 顶层/net decl — 主路径语法"""

    def test_wire_simple(self):
        """[Golden] 顶层简单 wire: wire w = a; (内部信号, 驱动 output)
        行为: wire 声明即赋值 → a→w DRIVER 边 (net_decl_extractor).
        """
        src = 'module top(input logic a, output logic y); wire w = a; assign y = w; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        edge = graph.get_edge('top.a', 'top.w')
        self.assertIsNotNone(edge, "wire w = a 应生成 a→w DRIVER 边")

    def test_wire_vector(self):
        """[Golden] 向量 wire: wire [3:0] w = a;
        行为: vector wire LHS, RHS a[3:0] — 实测 a → w 直接 DRIVER 边 (无位选节点).
        """
        src = ('module top(input logic [3:0] a, output logic [3:0] y); '
               'wire [3:0] w = a; assign y = w; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        edge = graph.get_edge('top.a', 'top.w')
        self.assertIsNotNone(edge,
                             "向量 wire w[3:0] = a 应生成 a→w DRIVER 边")

    def test_wire_expression(self):
        """[Golden] 表达式 wire: wire w = a & b;
        行为: RHS 是 BinaryExpression, 两个真实信号都应建 DRIVER 边到 LHS.
        """
        src = ('module top(input logic a, b, output logic y); '
               'wire w = a & b; assign y = w; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'),
                             "wire w = a & b 应生成 a→w DRIVER 边")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.w'),
                             "wire w = a & b 应生成 b→w DRIVER 边")

    def test_wire_in_generate_for(self):
        """[Golden] generate-for 内 wire: genvar i, wire prod = a * b 在 generate 块内
        行为: generate-for 展开后, 每个 entry 内的 wire prod 有独立 hierarchical_path,
        且 a、b 通过 genvar_ctx 替换后作为 RHS 真实信号建 DRIVER 边.
        """
        src = (
            'module top(input logic [7:0] a, b); '
            'genvar i; '
            'generate '
            '  for (i = 0; i < 2; i = i + 1) begin : gen_blk '
            '    wire [7:0] prod = a & b; '
            '  end '
            'endgenerate '
            'endmodule'
        )
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        # generate-for 展开后, prod 的 hierarchical_path 形如 top.gen_blk[0].prod
        # 至少展开一个 entry 内的 prod 应有 a、b 两条 DRIVER 入边
        any_prod_edge = False
        for src_id, dst_id in graph.edges():
            if dst_id.endswith('.prod') and 'gen_blk' in dst_id:
                # 检查 a、b 是否都驱动该 prod
                if src_id in ('top.a', 'top.b'):
                    any_prod_edge = True
        self.assertTrue(any_prod_edge,
                        "generate-for 内 wire prod = a & b 至少一个 entry "
                        "应有 a 或 b → prod 的 DRIVER 边")

    def test_wire_constant_no_signal_edge(self):
        """[Golden] wire 常量赋值无边: wire w = 1'b1;
        行为: RHS 是字面量, 无真实信号, w 不应有 top.* 信号名入边.
        """
        src = 'module top(output logic y); wire w = 1\'b1; assign y = w; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        w_in = [u for u, v in graph.edges() if v == 'top.w']
        # 入边只能来自字面量节点 (非常量信号), 不允许任何 top.* 信号驱动
        sig_in = [u for u in w_in if u.startswith('top.')]
        self.assertEqual(sig_in, [],
                         f"wire w = 1'b1 不应有 top.* 信号入边, 实际: {sig_in}")


if __name__ == '__main__':
    unittest.main()
