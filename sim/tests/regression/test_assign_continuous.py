#==============================================================================
# test_assign_continuous.py - assign (continuous) 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件 (对齐 constraint/covergroup 密度)
# 背景: assign 之前只靠 integration 顺带测, 无独立 regression 行为断言.
# 行为金标准 (module 域): RHS 信号 → LHS 的 DRIVER 边必须存在.
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


class TestAssignContinuous(unittest.TestCase):
    """assign (continuous) — 主路径语法"""

    def test_simple_assign(self):
        """[Golden] 简单 assign: assign y = a;"""
        src = 'module top(input logic a, output logic y); assign y = a; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        edge = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge, "assign y = a 应生成 a→y DRIVER 边")

    def test_assign_expression(self):
        """[Golden] 表达式 assign: assign y = a & b;"""
        src = 'module top(input logic a, b, output logic y); assign y = a & b; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'), "a 应驱动 y")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'), "b 应驱动 y")

    def test_assign_vector(self):
        """[Golden] 向量 assign: assign y[3:0] = a[3:0];"""
        src = 'module top(input logic [3:0] a, output logic [3:0] y); assign y = a; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        edge = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge, "向量 assign 应生成 a→y DRIVER 边")

    def test_assign_bit_select_rhs(self):
        """[Golden] RHS 位选: assign y = a[2];

        行为: 位选节点 a[2] 驱动 y (bit-select 节点, 非 base a).
        """
        src = 'module top(input logic [3:0] a, output logic y); assign y = a[2]; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a[2]', 'top.y'),
                             "RHS 位选 assign 应生成 a[2]→y DRIVER 边")

    def test_assign_multiple(self):
        """[Golden] 多 assign 独立: assign y1 = a; assign y2 = b;"""
        src = ('module top(input logic a, b, output logic y1, y2); '
               'assign y1 = a; assign y2 = b; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y1'), "a→y1 应存在")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y2'), "b→y2 应存在")
        self.assertIsNone(graph.get_edge('top.a', 'top.y2'), "a 不应驱动 y2 (独立 assign)")

    def test_assign_constant_no_signal(self):
        """[Golden] 常量 assign 无边: assign y = 1'b1;

        行为: 字面量节点 1'b1 → y 是常量边 (非信号驱动); y 不应有**信号名**入边.
        """
        src = 'module top(output logic y); assign y = 1\'b1; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        y_in = [u for u, v in graph.edges() if v == 'top.y']
        # 入边只能是字面量 (非常量信号), 不允许任何 top.* 信号驱动
        sig_in = [u for u in y_in if u.startswith('top.')]
        self.assertEqual(sig_in, [], f"常量 assign y 不应有信号入边, 实际: {sig_in}")


if __name__ == '__main__':
    unittest.main()
