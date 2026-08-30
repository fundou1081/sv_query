#==============================================================================
# test_case_multi_branch_v2.py - case 多分支 Driver 提取
# Bug: case 内部多分支未正确提取
# 项目纪律: 金标准测试优先
# [iter_063 2026-08-29] 升级断言强度: 保留原 trace_signal/driver 数
# 量断言, 补充 UnifiedTracer + graph.get_edge 行为断言 — case 各分
# 支的源信号 → y DRIVER 边 (带 sel 条件), casez/casex 同.
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


def _build_graph(source, filename: str = 't.sv'):
    """[iter_063] 构建 tracer graph 的统一 helper (行为断言用)"""
    tracer = UnifiedTracer(sources={filename: source})
    tracer.build_graph()
    return tracer.get_graph()


class TestCaseMultiBranch(unittest.TestCase):
    """case 多分支 Driver 提取"""

    def test_case_simple(self):
        """[Golden] 简单 case - 2分支

        [iter_063] 行为断言: a→y 与 b→y DRIVER 边存在, 各带 sel 条件.
        """
        src = '''module top(input sel, a, b, output logic y);
            always_comb begin
                case (sel)
                    1'b0: y = a;
                    default: y = b;
                endcase
            end
        endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        # 期望: 2 drivers (a, b)
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: a→y 与 b→y DRIVER 边
        graph = _build_graph(src)
        edge_a = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge_a, "case 1'b0: y=a 应生成 a→y DRIVER 边")
        # a 的条件应包含 sel == 1'b0
        self.assertIn('sel', edge_a.condition,
            "a→y 边条件应包含 sel (case 标签)")
        edge_b = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge_b, "case default: y=b 应生成 b→y DRIVER 边")
        self.assertIn('sel', edge_b.condition,
            "b→y 边条件应包含 sel (default 分支)")

    def test_case_3branch(self):
        """[Golden] 3分支 case

        [iter_063] 行为断言: a, b, c 都驱动 y, 各自带 sel 条件.
        """
        src = '''module top(input [1:0] sel, a, b, c, output logic y);
            always_comb begin
                case (sel)
                    2'b00: y = a;
                    2'b01: y = b;
                    default: y = c;
                endcase
            end
        endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: 三分支都生成 DRIVER 边
        graph = _build_graph(src)
        for sig in ('a', 'b', 'c'):
            edge = graph.get_edge(f'top.{sig}', 'top.y')
            self.assertIsNotNone(edge,
                f"case 分支 {sig}→y 应生成 DRIVER 边")
            # 条件应包含 sel
            self.assertIn('sel', edge.condition,
                f"{sig}→y 边条件应包含 sel")

    def test_casez(self):
        """[Golden] casez - 支持 don't care

        [iter_063] 行为断言: casez 三分支都生成 DRIVER 边.
        """
        src = '''module top(input [2:0] sel, a, b, c, output logic y);
            always_comb begin
                casez (sel)
                    3'b00?: y = a;
                    3'b01?: y = b;
                    default: y = c;
                endcase
            end
        endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)

        # [iter_063] 行为断言: casez 各分支都生成 DRIVER 边
        graph = _build_graph(src)
        for sig in ('a', 'b', 'c'):
            edge = graph.get_edge(f'top.{sig}', 'top.y')
            self.assertIsNotNone(edge,
                f"casez 分支 {sig}→y 应生成 DRIVER 边")

    def test_casex(self):
        """[Golden] casex - 支持 x

        [iter_063] 行为断言: casex 三分支都生成 DRIVER 边.
        """
        src = '''module top(input [2:0] sel, a, b, c, output logic y);
            always_comb begin
                casex (sel)
                    3'b00x: y = a;
                    3'b01x: y = b;
                    default: y = c;
                endcase
            end
        endmodule'''
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)

        # [iter_063] 行为断言: casex 各分支都生成 DRIVER 边
        graph = _build_graph(src)
        for sig in ('a', 'b', 'c'):
            edge = graph.get_edge(f'top.{sig}', 'top.y')
            self.assertIsNotNone(edge,
                f"casex 分支 {sig}→y 应生成 DRIVER 边")


if __name__ == '__main__':
    unittest.main()
