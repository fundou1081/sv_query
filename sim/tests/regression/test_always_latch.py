#==============================================================================
# test_always_latch.py - always_latch 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: latch 之前只有 integration/test_latch.py (3 测试), 无 regression 行为断言.
# 已知 (EXTRACTION_COVERAGE #19): always_latch 按普通 always 处理, 无 latch
# 语义 (推断边可能不准确) — 本文件锁定当前行为: 驱动边存在.
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


class TestAlwaysLatch(unittest.TestCase):
    """always_latch — 主路径语法 (当前按普通 always 处理)"""

    def test_latch_simple(self):
        """[Golden] always_latch 简单赋值: always_latch y = a;
        行为: a→y DRIVER 边 (当前按普通 always 处理, 边存在).
        """
        src = 'module top(input logic a, output logic y); always_latch y = a; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
                             "always_latch y = a 应生成 a→y DRIVER 边")

    def test_latch_if_no_else(self):
        """[Golden] always_latch if 无 else (latch 典型):
        always_latch if (clk) y = a;
        行为: a→y 边存在 (latch 保持语义不建模, 只验证边).
        """
        src = ('module top(input logic a, clk, output logic y); '
               'always_latch if (clk) y = a; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
                             "always_latch if 无 else 应生成 a→y 边")

    def test_latch_constant_no_signal(self):
        """[Golden] always_latch 常量赋值无边: y = 1'b0;
        行为: 无 top.* 信号入边 (字面量节点除外).
        """
        src = 'module top(output logic y); always_latch y = 1\'b0; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        y_in = [u for u, v in graph.edges() if v == 'top.y']
        sig_in = [u for u in y_in if u.startswith('top.')]
        self.assertEqual(sig_in, [], f"常量赋值 y 不应有 top.* 信号入边, 实际: {sig_in}")


if __name__ == '__main__':
    unittest.main()
