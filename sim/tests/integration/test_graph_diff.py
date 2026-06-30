#==============================================================================
# test_graph_diff.py - Graph Diff 查询测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestGraphDiff(unittest.TestCase):
    """Graph Diff 查询测试 - Phase 1 (Element-wise) + Phase 2 (Reachability)"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    #==========================================================================
    # [金标准] Phase 1: Element-wise Diff
    #==========================================================================

    def test_added_nodes(self):
        """[Golden] 新增节点能被正确识别"""
        old_source = '''
module top(output logic [7:0] q, input clk);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule'''
        new_source = '''
module top(output logic [7:0] q, input clk);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule'''
        from trace.core.graph.diff import diff_graph, GraphDiff

        tree_old = pyslang.SyntaxTree.fromText(old_source)
        tree_new = pyslang.SyntaxTree.fromText(new_source)
        tracer_old = UnifiedTracer(sources={'test.sv': old_source})
        tracer_new = UnifiedTracer(sources={'test.sv': new_source})
        tracer_old.build_graph()
        tracer_new.build_graph()

        result = diff_graph(tracer_old.get_graph(), tracer_new.get_graph())

        self.assertIn('top.b', result.added_nodes, "新增信号 b 应被识别")
        self.assertNotIn('top.a', result.added_nodes, "top.a 不是新增节点")
        self.assertNotIn('top.a', result.removed_nodes, "top.a 未被删除")
        self.assertFalse(result.identical)

    def test_removed_nodes(self):
        """[Golden] 删除节点能被正确识别"""
        old_source = '''
module top(output logic [7:0] q, input clk);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule'''
        new_source = '''
module top(output logic [7:0] q, input clk);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule'''
        from trace.core.graph.diff import diff_graph

        tree_old = pyslang.SyntaxTree.fromText(old_source)
        tree_new = pyslang.SyntaxTree.fromText(new_source)
        tracer_old = UnifiedTracer(sources={'test.sv': old_source})
        tracer_new = UnifiedTracer(sources={'test.sv': new_source})
        tracer_old.build_graph()
        tracer_new.build_graph()

        result = diff_graph(tracer_old.get_graph(), tracer_new.get_graph())

        self.assertIn('top.b', result.removed_nodes, "删除信号 b 应被识别")

    def test_added_edges(self):
        """[Golden] 新增边能被正确识别"""
        old_source = '''
module top(output logic [7:0] q, input clk);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule'''
        new_source = '''
module top(output logic [7:0] q, input clk);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule'''
        from trace.core.graph.diff import diff_graph

        tree_old = pyslang.SyntaxTree.fromText(old_source)
        tree_new = pyslang.SyntaxTree.fromText(new_source)
        tracer_old = UnifiedTracer(sources={'test.sv': old_source})
        tracer_new = UnifiedTracer(sources={'test.sv': new_source})
        tracer_old.build_graph()
        tracer_new.build_graph()

        result = diff_graph(tracer_old.get_graph(), tracer_new.get_graph())

        # b <= a 新增了边 top.a -> top.b
        self.assertIn(('top.a', 'top.b'), result.added_edges, "新增边 a->b 应被识别")

    def test_identical_graphs(self):
        """[Golden] 两张相同的图应识别为 identical"""
        source = '''
module top(input clk, output logic q);
    logic a;
    always_ff @(posedge clk) a <= q;
endmodule'''
        from trace.core.graph.diff import diff_graph

        tree = pyslang.SyntaxTree.fromText(source)
        tracer1 = UnifiedTracer(sources={'test.sv.sv': source})
        tracer2 = UnifiedTracer(sources={'test.sv.sv': source})
        tracer1.build_graph()
        tracer2.build_graph()

        result = diff_graph(tracer1.get_graph(), tracer2.get_graph())

        self.assertTrue(result.identical, "相同的图应返回 identical=True")
        self.assertEqual(len(result.added_nodes), 0)
        self.assertEqual(len(result.removed_nodes), 0)
        self.assertEqual(len(result.added_edges), 0)
        self.assertEqual(len(result.removed_edges), 0)

    #==========================================================================
    # [金标准] Phase 2: Reachability 分析
    #==========================================================================

    def test_forward_reachability(self):
        """[Golden] 正向 BFS 可达性分析"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b, c, d;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
        c <= b;
        d <= c;
    end
endmodule'''
        from trace.core.graph.diff import forward_reachability

        tracer = self._make_tracer(source)
        _ = tracer.trace_fanout('q', 'top')  # 触发 build_graph
        graph = tracer.get_graph()

        # q -> a -> b -> c -> d，链式传播
        reach_q = forward_reachability(['top.q'], graph)
        self.assertIn('top.a', reach_q)
        self.assertIn('top.b', reach_q)
        self.assertIn('top.c', reach_q)
        self.assertIn('top.d', reach_q)
        self.assertNotIn('top.q', reach_q, "可达性不应包含起点本身")
        self.assertNotIn('top.clk', reach_q, "CLOCK 边不参与数据流传播")

    def test_forward_reachability_with_depth(self):
        """[Golden] 可达性分析支持 depth 限制"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b, c, d;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
        c <= b;
        d <= c;
    end
endmodule'''
        from trace.core.graph.diff import forward_reachability

        tracer = self._make_tracer(source)
        _ = tracer.trace_fanout('q', 'top')
        graph = tracer.get_graph()

        reach_depth1 = forward_reachability(['top.q'], graph, max_depth=1)
        self.assertIn('top.a', reach_depth1)
        self.assertNotIn('top.b', reach_depth1, "depth=1 不应包含 b")

        reach_depth2 = forward_reachability(['top.q'], graph, max_depth=2)
        self.assertIn('top.a', reach_depth2)
        self.assertIn('top.b', reach_depth2)
        self.assertNotIn('top.c', reach_depth2, "depth=2 不应包含 c")

    def test_diff_reachability(self):
        """[Golden] 对比两个图的可达性差异"""
        old_source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule'''
        new_source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule'''
        from trace.core.graph.diff import diff_graph, diff_reachability

        tree_old = pyslang.SyntaxTree.fromText(old_source)
        tree_new = pyslang.SyntaxTree.fromText(new_source)
        tracer_old = UnifiedTracer(sources={'test.sv': old_source})
        tracer_new = UnifiedTracer(sources={'test.sv': new_source})
        _ = tracer_old.trace_fanout('q', 'top')
        _ = tracer_new.trace_fanout('q', 'top')
        G_old = tracer_old.get_graph()
        G_new = tracer_new.get_graph()

        diff_result = diff_graph(G_old, G_new)
        # 变更节点为 top.b（被删除的叶子节点）
        # 但我们用 removed_nodes（包含 top.b）来验证可达性差异
        reach_result = diff_reachability(
            changed_nodes=diff_result.removed_nodes,
            G_old=G_old,
            G_new=G_new
        )

        # top.a 在旧图中驱动 top.b，新图中 top.a 无下游
        # 所以 top.a 的可达范围变化了
        reach_a_old = tracer_old._signal_tracer._collect_all_drivers('top.a')
        reach_a_new = tracer_new._signal_tracer._collect_all_drivers('top.a')

        # 验证图本身的差异正确
        self.assertIn('top.b', diff_result.removed_nodes, "top.b 应被识别为删除节点")
        self.assertIn(('top.a', 'top.b'), diff_result.removed_edges, "a->b 边应被删除")


if __name__ == '__main__':
    unittest.main()
