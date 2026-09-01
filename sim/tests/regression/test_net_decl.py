#==============================================================================
# test_net_decl.py - net 声明 (logic/wire 声明) 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: net 声明之前只靠 integration 顺带测, 无独立 regression 行为断言.
# 行为金标准: 声明节点存在; 声明+assign 组合产生驱动边; 纯声明无入边.
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


class TestNetDecl(unittest.TestCase):
    """net 声明 — 主路径语法"""

    def test_logic_decl_plus_assign(self):
        """[Golden] logic 声明 + assign: logic w; assign w = a;
        行为: a→w DRIVER 边.
        """
        src = ('module top(input logic a, output logic y); '
               'logic w; assign w = a; assign y = w; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'), "a→w 应存在")
        self.assertIsNotNone(graph.get_edge('top.w', 'top.y'), "w→y 应存在")

    def test_wire_decl_plus_assign(self):
        """[Golden] wire 声明 + assign: wire w; assign w = a;
        行为: a→w DRIVER 边.
        """
        src = ('module top(input logic a, output logic y); '
               'wire w; assign w = a; assign y = w; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'), "a→w 应存在")

    def test_logic_decl_no_assign(self):
        """[Golden] logic 声明无赋值: logic w;
        行为: 节点 top.w 存在, 无信号入边.
        """
        src = 'module top(output logic y); logic w; assign y = 1\'b0; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIn('top.w', graph.nodes(), "声明的 logic w 节点应存在")
        w_in = [u for u, v in graph.edges() if v == 'top.w']
        self.assertEqual(w_in, [], f"无赋值的 w 不应有入边, 实际: {w_in}")

    def test_vector_decl(self):
        """[Golden] 向量声明: logic [7:0] w;
        行为: 节点存在 (宽度 8), 无入边.
        """
        src = 'module top(input logic [7:0] a, output logic [7:0] y); logic [7:0] w; assign w = a; assign y = w; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIn('top.w', graph.nodes(), "向量 w 节点应存在")
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'), "a→w 应存在")

    def test_decl_initial_value(self):
        """[Golden] wire 声明即赋值: wire w = a;
        行为: a→w DRIVER 边 (net_decl_extractor).
        """
        src = 'module top(input logic a, output logic y); wire w = a; assign y = w; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.w'),
                             "wire w = a 声明即赋值应生成 a→w 边")


if __name__ == '__main__':
    unittest.main()
