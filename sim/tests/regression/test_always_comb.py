#==============================================================================
# test_always_comb.py - always_comb 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件 (对齐 constraint/covergroup 密度)
# 背景: always_comb 之前只靠 integration 顺带测, 无独立 regression 行为断言.
# 行为金标准 (module 域): 过程赋值 RHS 信号 → LHS 的 DRIVER 边必须存在.
# 已知 (EXTRACTION_COVERAGE #31): 阻塞/非阻塞 assign_type 无差别 (metadata 层面).
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


class TestAlwaysComb(unittest.TestCase):
    """always_comb — 主路径语法"""

    def test_comb_simple(self):
        """[Golden] always_comb 简单赋值: always_comb y = a;"""
        src = 'module top(input logic a, output logic y); always_comb y = a; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
                             "always_comb y = a 应生成 a→y DRIVER 边")

    def test_comb_if_else(self):
        """[Golden] always_comb if-else: if (s) y = a; else y = 0;
        行为: a→y (条件分支) + 常量 1'b0→y (else 分支).
        """
        src = ('module top(input logic a, s, output logic y); '
               'always_comb if (s) y = a; else y = 1\'b0; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
                             "if 分支 a→y 应存在")
        # else 分支是常量, 不应有信号名驱动 y
        y_in = [u for u, v in graph.edges() if v == 'top.y']
        sig_in = [u for u in y_in if u.startswith('top.')]
        self.assertEqual(sig_in, ['top.a'],
                         f"y 的 top.* 入边应只有 a, 实际: {sig_in}")

    def test_comb_case(self):
        """[Golden] always_comb case: case 分支驱动"""
        src = '''
module top(input logic [1:0] sel, input logic a, b, output logic y);
    always_comb begin
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = 1'b0;
        endcase
    end
endmodule'''
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
                             "case 分支 a→y 应存在")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'),
                             "case 分支 b→y 应存在")

    def test_comb_multi_stmt_intermediate(self):
        """[Golden] always_comb 多语句 (中间变量):
        always_comb begin w = a & b; y = w; end
        行为: a→w, b→w, w→y 三段链.
        """
        src = ('module top(input logic a, b, output logic y); '
               'logic w; always_comb begin w = a & b; y = w; end endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'), "a→w 应存在")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.w'), "b→w 应存在")
        self.assertIsNotNone(graph.get_edge('top.w', 'top.y'), "w→y 应存在")

    def test_comb_constant_no_signal(self):
        """[Golden] always_comb 常量赋值无边: y = 1'b0;
        行为: 无 top.* 信号入边 (字面量节点除外).
        """
        src = 'module top(output logic y); always_comb y = 1\'b0; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        y_in = [u for u, v in graph.edges() if v == 'top.y']
        sig_in = [u for u in y_in if u.startswith('top.')]
        self.assertEqual(sig_in, [], f"常量赋值 y 不应有 top.* 信号入边, 实际: {sig_in}")


if __name__ == '__main__':
    unittest.main()
