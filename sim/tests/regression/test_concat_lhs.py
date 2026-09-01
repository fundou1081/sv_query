#==============================================================================
# test_concat_lhs.py - 拼接赋值 {a,b} 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: 拼接已有 test_concat_multiple (RHS), 补 LHS 拼接独立断言.
# 行为金标准 (module 域):
#   LHS 拼接 assign {y1, y2} = x; → x→拼接节点 top.{y1, y2} DRIVER 边
#   RHS 拼接 assign y = {a, b}; → a→y, b→y 边
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


class TestConcatLHS(unittest.TestCase):
    """拼接赋值 — LHS 展开"""

    def test_concat_lhs_simple(self):
        """[Golden] LHS 拼接: assign {y1, y2} = x;
        行为: x → 拼接节点 top.{y1, y2} DRIVER 边.
        """
        src = ('module top(input logic [1:0] x, output logic y1, y2); '
               'assign {y1, y2} = x; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.x', 'top.{y1, y2}'),
                             "LHS 拼接应生成 x→{y1,y2} DRIVER 边")

    def test_concat_rhs_simple(self):
        """[Golden] RHS 拼接: assign y = {a, b};
        行为: a→y, b→y DRIVER 边.
        """
        src = ('module top(input logic a, b, output logic [1:0] y); '
               'assign y = {a, b}; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a→y 应存在")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'), "b→y 应存在")

    def test_concat_mixed(self):
        """[Golden] RHS 混合拼接: assign y = {a, 1'b0};
        行为: a→y 存在; y 无其他 top.* 信号入边.
        """
        src = ('module top(input logic a, output logic [1:0] y); '
               'assign y = {a, 1\'b0}; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a→y 应存在")
        y_in = [u for u, v in graph.edges() if v == 'top.y']
        sig_in = [u for u in y_in if u.startswith('top.')]
        self.assertEqual(sig_in, ['top.a'],
                         f"y 的 top.* 入边应只有 a, 实际: {sig_in}")


if __name__ == '__main__':
    unittest.main()
