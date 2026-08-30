#==============================================================================
# test_concat_multiple.py - 拼接驱动提取记录
# Bug: 当前实现只返回第一个值
# 原因: SignalChain 结构设计限制
# 状态: 已知限制 (文档记录)
# [iter_063 2026-08-29] 升级断言强度: 保留原 trace_signal/driver 数
# 量断言, 补充 UnifiedTracer + graph.get_edge 行为断言 — concat 内部
# 各源信号 → y 的 DRIVER 边实际存在 (行为金标准).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


def _build_graph(source, filename: str = 'test.sv'):
    """[iter_063] 构建 tracer graph 的统一 helper (行为断言用)"""
    tracer = UnifiedTracer(sources={filename: source})
    tracer.build_graph()
    return tracer.get_graph()


class TestConcatKnownLimitations(unittest.TestCase):
    """拼接 Driver 提取 - 已知限制"""

    def test_concat_returns_at_least_one(self):
        """[Known Limit] {a,b} 至少返回第一个driver

        [iter_063] 行为断言: graph.get_edge('top.a', 'top.y') 与
        ('top.b', 'top.y') 都存在 (concat 内部各源信号都驱动 y).
        """
        source = '''
module top(input a, input b, output [1:0] y);
    assign y = {a, b};
endmodule'''

        pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')

        # 已知限制: 只返回第一个，但至少能追踪到1个
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言: a→y 与 b→y DRIVER 边都存在
        graph = _build_graph(source)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
            "concat {a,b} 应生成 a→y DRIVER 边")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'),
            "concat {a,b} 应生成 b→y DRIVER 边")

    def test_concat_four_returns_at_least_one(self):
        """{a,b,c,d} 只返回第一个

        [iter_063] 行为断言: a,b,c,d 四个源都驱动 y
        """
        source = '''
module top(input a, input b, input c, input d, output [3:0] y);
    assign y = {a, b, c, d};
endmodule'''

        pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)

        # [iter_063] 行为断言: 四源都驱动 y
        graph = _build_graph(source)
        for sig in ('a', 'b', 'c', 'd'):
            self.assertIsNotNone(graph.get_edge(f'top.{sig}', 'top.y'),
                f"concat {sig}→y 应生成 DRIVER 边")


class TestReplicationKnownLimitations(unittest.TestCase):
    """replication Driver - 正确返回1"""

    def test_replication_returns_source(self):
        """{4{a}} 正确返回主driver

        [iter_063] 行为断言: replication 当前实现将整个表达式
        {4{a}} 作为单一匿名节点, a 节点被引用但无 a→y 直接 DRIVER
        边. 行为金标准: y 至少有一条入边 (driver).
        """
        source = '''
module top(input a, output [3:0] y);
    assign y = {4{a}};
endmodule'''

        pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')

        self.assertEqual(len(result.drivers), 1)

        # [iter_063] 行为断言: y 至少有一条入边 (replication 节点驱动 y)
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.a', nodes, "replication {4{a}} 应提取源信号 a 节点")
        self.assertIn('top.y', nodes)
        in_edges = [u for u, v in graph.edges() if v == 'top.y']
        self.assertGreaterEqual(len(in_edges), 1,
            "replication {4{a}} 应至少有1条 →y DRIVER 边")


if __name__ == '__main__':
    unittest.main()
