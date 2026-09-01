#==============================================================================
# test_parameter.py - parameter/localparam 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: parameter 之前无独立 regression 行为断言.
# 行为金标准 (EXTRACTION_COVERAGE #17): parameter/localparam 是编译期符号,
# 自动过滤为非信号 (Fix F 2026-07-14) — 不产生信号节点/边.
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


class TestParameter(unittest.TestCase):
    """parameter / localparam — 编译期符号过滤"""

    def test_parameter_not_signal(self):
        """[Golden] parameter 定义不产生信号节点:
        parameter W = 4; → 无 top.W 节点.
        """
        src = ('module top(input logic [3:0] a, output logic [3:0] y); '
               'parameter W = 4; assign y = a; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertNotIn('top.W', graph.nodes(), "parameter W 不应是信号节点")

    def test_localparam_not_signal(self):
        """[Golden] localparam 定义不产生信号节点:
        localparam W = 4; → 无 top.W 节点.
        """
        src = ('module top(input logic [3:0] a, output logic [3:0] y); '
               'localparam W = 4; assign y = a; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertNotIn('top.W', graph.nodes(), "localparam W 不应是信号节点")

    def test_parameter_as_width(self):
        """[Golden] parameter 作位宽: logic [W-1:0] y;
        行为: 信号正常提取 (a→y 边存在), parameter 本身被过滤.
        """
        src = ('module top(input logic [3:0] a, output logic [3:0] y); '
               'parameter W = 4; logic [W-1:0] t; assign t = a; assign y = t; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.t'), "a→t 应存在 (W-1 位宽)")
        self.assertIsNotNone(graph.get_edge('top.t', 'top.y'), "t→y 应存在")
        self.assertNotIn('top.W', graph.nodes(), "parameter W 不应是信号节点")

    def test_parameter_in_rhs_no_signal_edge(self):
        """[Golden] parameter 作 RHS: assign y = PARAM;
        行为: PARAM 是编译期常量, y 不应有 top.PARAM 信号入边.
        """
        src = ('module top(output logic [3:0] y); '
               'parameter PARAM = 4\'b1010; assign y = PARAM; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertNotIn('top.PARAM', graph.nodes(),
                         "RHS 的 parameter PARAM 不应是信号节点")


if __name__ == '__main__':
    unittest.main()
