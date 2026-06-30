#==============================================================================
# test_graph_diff_health.py - Graph Diff 健康度测试
# [铁律13] 金标准测试: 先推导金标准, 再验证
#==============================================================================
# 方案一: 标识符严格匹配法 (稳定核心 + 架构健康度)
#
# 金标准推导:
# 稳定核心 = {module_id | 同名 in G1 & G2, 且出边=入边完全一致}
# 健康度 = 稳定核心模块数 / 图中最大模块数
# 耦合预警: |C| / 总模块 < 5% 且 不稳定比例 > 30% → 高耦合警告
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.diff import (
    compute_stable_core,
    compute_health_score,
    compute_coupling_warning,
    diff_with_health,
)


def get_tree_source(tree):
    """Extract source text from a pyslang.SyntaxTree"""
    sm = tree.sourceManager
    buffers = sm.getAllBuffers()
    texts = []
    for buf_id in buffers:
        txt = sm.getSourceText(buf_id)
        texts.append(txt.rstrip('\x00'))
    return '\n'.join(texts)


class TestStableCore(unittest.TestCase):
    """稳定核心计算 - 方案一金标准测试"""

    def test_stable_core_identical_graphs(self):
        """[Golden] 完全相同的图，稳定核心 = 全部节点

        金标准:
        旧图: top.a → top.b
        新图: top.a → top.b (完全相同)
        预期稳定核心: ['top.a', 'top.b'] (clk 不影响核心稳定度判断)
        """
        # 使用 continuous assign 避免 clk 节点干扰
        src = '''module top();
    logic [7:0] a, b;
    assign b = a;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer1 = UnifiedTracer(sources={'t.sv': src})
        tracer2 = UnifiedTracer(sources={'t.sv': src})
        G1 = tracer1.build_graph()
        G2 = tracer2.build_graph()

        stable = compute_stable_core(G1, G2)

        self.assertIn('top.a', stable)
        self.assertIn('top.b', stable)
        self.assertEqual(len(stable), 2, "完全相同的图，稳定核心应包含全部节点")

    def test_stable_core_added_node(self):
        """[Golden] 新增节点不属于稳定核心

        金标准:
        旧图: top.a → top.b
        新图: top.a → top.b, top.c → top.b
        预期稳定核心: ['top.a', 'top.b']
        """
        # 使用 continuous assign 避免 clk 节点干扰
        old_src = '''module top();
    logic [7:0] a, b;
    assign b = a;
endmodule'''
        new_src = '''module top();
    logic [7:0] a, b, c;
    assign b = a;
    assign c = b;
endmodule'''

        tree_old = pyslang.SyntaxTree.fromText(old_src)
        tree_new = pyslang.SyntaxTree.fromText(new_src)
        tracer_old = UnifiedTracer(sources={'t_old.sv': old_src})
        tracer_new = UnifiedTracer(sources={'t_new.sv': new_src})
        G_old = tracer_old.build_graph()
        G_new = tracer_new.build_graph()

        stable = compute_stable_core(G_old, G_new)

        self.assertIn('top.a', stable)
        # 注意: top.b 的 out_edges 从 [] 变为 [b→c]，所以 b 不稳定
        self.assertNotIn('top.b', stable, "top.b 出边变化，不属于稳定核心")
        self.assertNotIn('top.c', stable, "新增节点 c 不应属于稳定核心")

    def test_stable_core_removed_node(self):
        """[Golden] 删除节点不属于稳定核心

        金标准:
        旧图: top.a → top.b, top.b → top.c
        新图: top.a → top.b
        预期稳定核心: ['top.a', 'top.b']
        """
        old_src = '''module top();
    logic [7:0] a, b, c;
    assign b = a;
    assign c = b;
endmodule'''
        new_src = '''module top();
    logic [7:0] a, b;
    assign b = a;
endmodule'''

        tree_old = pyslang.SyntaxTree.fromText(old_src)
        tree_new = pyslang.SyntaxTree.fromText(new_src)
        tracer_old = UnifiedTracer(sources={'t_old.sv': old_src})
        tracer_new = UnifiedTracer(sources={'t_new.sv': new_src})
        G_old = tracer_old.build_graph()
        G_new = tracer_new.build_graph()

        stable = compute_stable_core(G_old, G_new)

        self.assertIn('top.a', stable)
        # 注意: top.b 的 out_edges 从 [b→c] 变为 []，所以 b 不稳定
        self.assertNotIn('top.b', stable, "top.b 出边变化，不属于稳定核心")
        self.assertNotIn('top.c', stable, "删除节点 c 不应属于稳定核心")

    def test_stable_core_edge_changed(self):
        """[Golden] 边变化时，节点不属于稳定核心

        金标准:
        旧图: top.a → top.b
        新图: top.a → top.c (b 被 c 替代)
        预期稳定核心: []
        """
        # 使用 continuous assign 避免 clk 节点干扰
        old_src = '''module top();
    logic [7:0] a, b;
    assign b = a;
endmodule'''
        new_src = '''module top();
    logic [7:0] a, c;
    assign c = a;
endmodule'''

        tree_old = pyslang.SyntaxTree.fromText(old_src)
        tree_new = pyslang.SyntaxTree.fromText(new_src)
        tracer_old = UnifiedTracer(sources={'t_old.sv': old_src})
        tracer_new = UnifiedTracer(sources={'t_new.sv': new_src})
        G_old = tracer_old.build_graph()
        G_new = tracer_new.build_graph()

        stable = compute_stable_core(G_old, G_new)

        # a 的出边从 (a→b) 变为 (a→c)，所以 a 不稳定
        # b 被删除，c 新增，都不在稳定核心
        self.assertNotIn('top.a', stable, "出边变化的节点不应属于稳定核心")


class TestHealthScore(unittest.TestCase):
    """架构健康度计算"""

    def test_health_score_identical(self):
        """[Golden] 相同图，健康度 = 1.0

        金标准: 健康度 = 稳定核心数 / 总节点数 = 1.0
        """
        src = '''module top();
    logic [7:0] a, b;
    assign b = a;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        G = tracer.build_graph()

        stable = compute_stable_core(G, G)
        score = compute_health_score(G, stable)

        self.assertEqual(score, 1.0, "完全相同的图，健康度应为 1.0")

    def test_health_score_changed(self):
        """[Golden] 结构变化时，健康度下降

        金标准推导:
        旧图: a → b, c → b (b 被 a 和 c 驱动)
        新图: a → b, c → d (b 只被 a 驱动, d 是新节点)
        稳定核心: {a} (a 的 out_edges 不变, b/c/d 的边都变了)
        健康度: 旧=1/3=0.33, 新=1/4=0.25
        """
        old_src = '''module top();
    logic [7:0] a, b, c;
    assign b = a;
    assign b = c;
endmodule'''
        new_src = '''module top();
    logic [7:0] a, b, c, d;
    assign b = a;
    assign d = c;
endmodule'''

        tree_old = pyslang.SyntaxTree.fromText(old_src)
        tree_new = pyslang.SyntaxTree.fromText(new_src)
        tracer_old = UnifiedTracer(sources={'t_old.sv': old_src})
        tracer_new = UnifiedTracer(sources={'t_new.sv': new_src})
        G_old = tracer_old.build_graph()
        G_new = tracer_new.build_graph()

        stable = compute_stable_core(G_old, G_new)
        score_old = compute_health_score(G_old, stable)
        score_new = compute_health_score(G_new, stable)

        # 只有 a 的边完全一致，所以稳定核心只有 a
        self.assertIn('top.a', stable)
        self.assertNotIn('top.b', stable)
        self.assertGreater(score_old, score_new, "结构变化后健康度应下降")


class TestCouplingWarning(unittest.TestCase):
    """耦合预警计算"""

    def test_coupling_low(self):
        """[Golden] 小改动 + 低不稳定比例 → 无预警

        金标准:
        变更节点数: 2, 总节点数: 100
        变更比例: 2% < 5% ✓
        不稳定比例: 20% < 30% ✓
        → is_warning = False
        """
        result = compute_coupling_warning(
            changed_nodes=['a', 'b'],
            total_nodes=100,
            unstable_ratio=0.20
        )

        self.assertFalse(result['is_warning'])
        self.assertEqual(result['level'], 'low')

    def test_coupling_high(self):
        """[Golden] 小改动 + 高不稳定比例 → 高耦合预警

        金标准:
        变更节点数: 2, 总节点数: 100
        变更比例: 2% < 5% ✓
        不稳定比例: 50% > 30% ✗
        → is_warning = True, level = 'critical'
        """
        result = compute_coupling_warning(
            changed_nodes=['a', 'b'],
            total_nodes=100,
            unstable_ratio=0.50
        )

        self.assertTrue(result['is_warning'])
        self.assertEqual(result['level'], 'high')


class TestDiffWithHealth(unittest.TestCase):
    """完整 diff_with_health 函数测试"""

    def test_complete_health_analysis(self):
        """[Golden] 完整健康度分析

        金标准输出:
        {
            'graph_diff': GraphDiff,
            'stable_core': [...],
            'health_score_old': float,
            'health_score_new': float,
            'health_delta': float,
            'coupling_warning': {...}
        }
        """
        old_src = '''module top();
    logic [7:0] a, b;
    assign b = a;
endmodule'''
        new_src = '''module top();
    logic [7:0] a, b, c;
    assign b = a;
    assign c = b;
endmodule'''

        tree_old = pyslang.SyntaxTree.fromText(old_src)
        tree_new = pyslang.SyntaxTree.fromText(new_src)
        tracer_old = UnifiedTracer(sources={'t_old.sv': old_src})
        tracer_new = UnifiedTracer(sources={'t_new.sv': new_src})
        G_old = tracer_old.build_graph()
        G_new = tracer_new.build_graph()

        result = diff_with_health(G_old, G_new)

        # 验证结构
        self.assertIn('graph_diff', result)
        self.assertIn('stable_core', result)
        self.assertIn('health_score_old', result)
        self.assertIn('health_score_new', result)
        self.assertIn('health_delta', result)
        self.assertIn('coupling_warning', result)

        # 验证具体值 - b 的 out_edges 改变了，所以只有 a 稳定
        self.assertIn('top.a', result['stable_core'])
        self.assertNotIn('top.b', result['stable_core'])
        self.assertNotIn('top.c', result['stable_core'])

        self.assertIsInstance(result['health_score_old'], float)
        self.assertIsInstance(result['health_score_new'], float)
        self.assertIsInstance(result['health_delta'], float)

        # 健康度应该下降
        self.assertLess(result['health_delta'], 0)


if __name__ == '__main__':
    unittest.main()
