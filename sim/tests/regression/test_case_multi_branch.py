#==============================================================================
# test_case_multi_branch.py - case 语句多分支 Driver 提取
# Bug: case 语句内部多分支未提取
# 按项目纪律: 先写测试，再开发
# [iter_064 2026-08-29] 行为断言加强: 保留原有 driver count + trace_signal 断言,
# 补充 UnifiedTracer + graph.get_edge 行为断言 — 验证每个 case 分支都生成
# DRIVER 边且 condition 标注正确 (branch sel == N'bM).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestCaseMultiBranch(unittest.TestCase):
    """case 多分支 Driver 提取"""

    def test_case_simple(self):
        """[Golden] 简单 case - 应提取多个驱动

        RTL:
          case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = c;
          endcase

        行为金标准 (module 域):
          - top.a → top.y  DRIVER 边 (条件: sel == 2'b0)
          - top.b → top.y  DRIVER 边 (条件: sel == 2'b1)
          - top.c → top.y  DRIVER 边 (条件: sel == default)
        """

        source = '''
module top(input [1:0] sel, input a, input b, input c, output logic y);
    always_comb begin
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = c;
        endcase
    end
endmodule'''

        pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')

        # 原断言: 至少能提取到驱动
        driver_count = len(result.drivers)
        self.assertGreaterEqual(driver_count, 1, "应至少提取1个driver")
        self.assertEqual(result.confidence, 'high')

        # [iter_064] 行为断言: 三个分支都有带条件的 DRIVER 边
        graph = tracer.get_graph()
        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a, "case 2'b00:a 应生成 a→y DRIVER 边")
        self.assertEqual(edge_a.condition, "sel == 2'b0")

        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_b, "case 2'b01:b 应生成 b→y DRIVER 边")
        self.assertEqual(edge_b.condition, "sel == 2'b1")

        edge_c = graph.get_edge('top.c', 'top.y')
        self.assertIsNotNone(edge_c, "case default:c 应生成 c→y DRIVER 边")
        self.assertEqual(edge_c.condition, "sel == default")

    def test_case_two_branch(self):
        """[Golden] 2分支 case

        RTL:
          case (sel)
            1'b0: y = a;
            default: y = b;
          endcase

        行为金标准:
          - top.a → top.y  DRIVER (条件: sel == 1'b0)
          - top.b → top.y  DRIVER (条件: sel == default)
        """
        source = '''
module top(input sel, input a, input b, output logic y);
    always_comb begin
        case (sel)
            1'b0: y = a;
            default: y = b;
        endcase
    end
endmodule'''

        pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')

        # 原断言
        self.assertGreaterEqual(len(result.drivers), 1)

        # [iter_064] 行为断言: 两个分支都有 DRIVER 边
        graph = tracer.get_graph()
        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a, "case 1'b0:a 应生成 a→y DRIVER 边")
        self.assertEqual(edge_a.condition, "sel == 1'b0")

        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_b, "case default:b 应生成 b→y DRIVER 边")
        self.assertEqual(edge_b.condition, "sel == default")


if __name__ == '__main__':
    unittest.main()
