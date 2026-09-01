#==============================================================================
# test_ternary.py - 三元 ?: 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: 三元之前只靠 integration 顺带测, 无独立 regression 行为断言.
# 行为金标准 (module 域): assign y = s ? a : b; → a→y, b→y DRIVER 边 +
# 条件 s → y.ternary_s (条件节点) → y 边.
# 已知 (EXTRACTION_COVERAGE #15): 嵌套限 5 层解包装.
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


class TestTernary(unittest.TestCase):
    """三元 ?: — 主路径语法"""

    def test_ternary_simple(self):
        """[Golden] assign y = s ? a : b;
        行为: a→y, b→y DRIVER 边 + s→y.ternary_s 条件节点→y.
        """
        src = ('module top(input logic a, b, s, output logic y); '
               'assign y = s ? a : b; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a→y 应存在")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'), "b→y 应存在")
        # 条件 s 通过 ternary_s 节点驱动 y (条件边)
        self.assertIsNotNone(graph.get_edge('top.s', 'top.y.ternary_s'),
                             "s→y.ternary_s 条件边应存在")

    def test_ternary_nested2(self):
        """[Golden] 嵌套三元 2 层: assign y = s1 ? (s2 ? a : b) : c;
        行为: a, b, c 都驱动 y; 两个条件节点存在.
        """
        src = ('module top(input logic a, b, c, s1, s2, output logic y); '
               'assign y = s1 ? (s2 ? a : b) : c; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a→y 应存在 (内层真分支)")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'), "b→y 应存在 (内层假分支)")
        self.assertIsNotNone(graph.get_edge('top.c', 'top.y'), "c→y 应存在 (外层假分支)")

    def test_ternary_in_always_comb(self):
        """[Golden] always_comb 内三元: y = s ? a : b;
        行为: a→y, b→y 边存在.
        """
        src = ('module top(input logic a, b, s, output logic y); '
               'always_comb y = s ? a : b; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a→y 应存在")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'), "b→y 应存在")

    def test_ternary_constant_branch(self):
        """[Golden] 三元常量分支: assign y = s ? a : 1'b0;
        行为: a→y 存在; y 入边除 a 和条件节点 (y.ternary_s) 外无其他信号.
        """
        src = ('module top(input logic a, s, output logic y); '
               'assign y = s ? a : 1\'b0; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a→y 应存在")
        y_in = [u for u, v in graph.edges() if v == 'top.y']
        # 允许: a (真分支) + y.ternary_s (条件节点, 内部机制); 不允许其他信号
        sig_in = [u for u in y_in if u.startswith('top.') and not u.endswith('.ternary_s')]
        self.assertEqual(sig_in, ['top.a'],
                         f"y 的 top.* 信号入边应只有 a, 实际: {sig_in}")


if __name__ == '__main__':
    unittest.main()
