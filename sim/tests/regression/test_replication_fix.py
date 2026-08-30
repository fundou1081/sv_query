#==============================================================================
# test_replication_fix.py - Replication LHS 修复测试
# Bug: {2{a}} 格式返回 0 drivers
# 项目纪律: 金标准测试优先
# [iter_063 2026-08-29] 升级断言强度: 保留原 trace_signal/drivers
# 数量断言, 补充 UnifiedTracer + graph.get_edge 行为断言 — replication
# 经匿名表达式节点驱动 y (a→y 直接 DRIVER 边当前实现不存在, 记录此
# 限制; 但 →y 至少1条入边是行为金标准).
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


class TestReplicationFix(unittest.TestCase):
    """Replication 修复测试"""

    def test_replication_lhs(self):
        """[Golden] Replication LHS: {2{a}}

        [iter_063] 行为断言: y 应有入边 (replication 节点驱动 y).
        """
        src = 'module top(input a, output [3:0] y); assign y = {2{a}}; endmodule'
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        # 期望: 1 driver
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')

        # [iter_063] 行为断言
        graph = _build_graph(src)
        in_edges = [u for u, v in graph.edges() if v == 'top.y']
        self.assertGreaterEqual(len(in_edges), 1,
            "replication {2{a}} 应至少有1条 →y DRIVER 边")

    def test_replication_triple(self):
        """[Golden] 三次复制: {3{a}}

        [iter_063] 行为断言: {3{a}} 应有 →y 入边
        """
        src = 'module top(input a, output [5:0] y); assign y = {3{a}}; endmodule'
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)

        # [iter_063] 行为断言
        graph = _build_graph(src)
        in_edges = [u for u, v in graph.edges() if v == 'top.y']
        self.assertGreaterEqual(len(in_edges), 1,
            "replication {3{a}} 应至少有1条 →y DRIVER 边")

    def test_replication_mixed(self):
        """[Golden] 混合复制: {2{a},b}

        [iter_063] 行为断言: 混合 replication 应有 →y 入边.
        注意: 当前实现将 {2{a}} 部分打包为单一表达式节点, b
        可能直接驱动 y (或经 {2{a},b} 节点). 验证至少1条入边.
        """
        src = 'module top(input a,b, output [4:0] y); assign y = {2{a},b}; endmodule'
        pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)

        # [iter_063] 行为断言
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        # 源信号 a, b 应被提取
        self.assertIn('top.a', nodes, "replication {2{a},b} 应提取 a")
        self.assertIn('top.b', nodes, "replication {2{a},b} 应提取 b")
        # y 至少1条入边
        in_edges = [u for u, v in graph.edges() if v == 'top.y']
        self.assertGreaterEqual(len(in_edges), 1,
            "replication {2{a},b} 应至少有1条 →y DRIVER 边")


if __name__ == '__main__':
    unittest.main()
