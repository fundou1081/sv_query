#==============================================================================
# test_case_extraction.py - case 语句 Driver 提取
# Bug: case 内部多分支赋值未提取
# 原因: pyslang CaseStatement API 结构复杂
# 状态: 已知限制 (需进一步研究)
# [iter_064 2026-08-29] 行为断言加强: 验证 case 各分支确实生成 DRIVER 边
# + 条件 (sel == N'bM) 标注 — 这是 case 提取的真正行为金标准.
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestCaseKnownLimitation(unittest.TestCase):
    """case 语句 - 已知 API 限制"""

    def test_case_compiles(self):
        """验证 case 能够解析 + 多分支 DRIVER 边提取 (行为金标准)

        RTL:
          module top(input [1:0] sel, input a, b, output logic y);
              always_comb begin
                  case (sel)
                      2'b00: y = a;
                      2'b01: y = b;
                      default: y = 0;
                  endcase
              end
          endmodule

        行为金标准 (module 域):
          - top.a → top.y   DRIVER 边 (条件: sel == 2'b0)
          - top.b → top.y   DRIVER 边 (条件: sel == 2'b1)
          - 0      → top.y  DRIVER 边 (条件: sel == default)
        """
        source = '''
module top(input [1:0] sel, input a, b, output logic y);
    always_comb begin
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = 0;
        endcase
    end
endmodule'''

        pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()

        # 原断言: 基础功能可用
        graph = tracer.get_graph()
        self.assertIsNotNone(graph)

        # [iter_064] 行为断言: case 每个分支都生成带条件的 DRIVER 边
        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a, "case 分支 2'b00:a 应生成 a→y DRIVER 边")
        self.assertEqual(edge_a.condition, "sel == 2'b0",
                         "case 2'b00 分支的 DRIVER 边 condition 应为 sel == 2'b0")

        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_b, "case 分支 2'b01:b 应生成 b→y DRIVER 边")
        self.assertEqual(edge_b.condition, "sel == 2'b1",
                         "case 2'b01 分支的 DRIVER 边 condition 应为 sel == 2'b1")


if __name__ == '__main__':
    unittest.main()
