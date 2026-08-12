"""
test_f2_expression_tree_coverage.py — [Plan F2.4.3 2026-08-13] Verify coverage_generator uses ExpressionTree

[Plan F2] drive_dependencies refactor step 3:
coverage_generator 应该优先用结构化 ExpressionTree walk 提取原子信号,
而不是 fallback 到 string parsing. 这消除字面量 / 嵌套表达式 / SV 关键字
的 false-positive.

本文件验证:
  1. `_extract_atomics_from_expr_tree` 正确从 ExpressionTree dict 抽 SignalRef 叶子
  2. 字面量 (8'd100) 不被误识为信号名 (string parsing 的已知 bug)
  3. 嵌套表达式 (a + b * c) 正确抽所有 SignalRef
  4. _trace_drivers 优先用 expression_tree (跟 string parsing 一致时)

[铁律13] 金标准测试优先
[铁律17] 强断言 (具体行为)

[NOTE 2026-08-13] 用内部 wire signal (不是 PORT_OUT) 测试 _trace_drivers —
PORT_OUT 会触发 _is_module_port early-return, 让 _trace_drivers 直接返空.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.coverage_generator import ControlCoverageGenerator, NO_TREE_MARKER
from trace.unified_tracer import UnifiedTracer


class TestF2ExpressionTreeCoverage(unittest.TestCase):
    """[Plan F2.4.3] coverage_generator 用 ExpressionTree 抽 atomic"""

    def _make_tracer_and_graph(self, source: str, name: str = 'test.sv'):
        tracer = UnifiedTracer(sources={name: source}, strict=False)
        tracer.build_graph()
        return tracer.get_graph()

    def _make_cov(self, graph):
        return ControlCoverageGenerator(graph)

    def test_extract_simple_signal_ref(self):
        """`assign y = a` → ExpressionTree 1 个 SignalRef"""
        src = '''module top(input a, output y);
    assign y = a;
endmodule'''
        g = self._make_tracer_and_graph(src)
        cov = self._make_cov(g)

        tree = g._expr_trees.get('top.y')
        atomics = cov._extract_atomics_from_expr_tree(tree)
        self.assertEqual(len(atomics), 1)
        self.assertEqual(atomics[0].name, 'a')
        self.assertEqual(atomics[0].bit_range, None)

    def test_extract_nested_expression_all_signals(self):
        """`assign y = a + b * c` → 3 个 SignalRef (a, b, c)"""
        src = '''module top(input a, b, c, output [7:0] y);
    assign y = a + b * c;
endmodule'''
        g = self._make_tracer_and_graph(src)
        cov = self._make_cov(g)

        tree = g._expr_trees.get('top.y')
        atomics = cov._extract_atomics_from_expr_tree(tree)

        names = [a.name for a in atomics]
        self.assertEqual(set(names), {'a', 'b', 'c'})
        self.assertEqual(len(atomics), 3)  # 全部, 无重复

    def test_literal_not_misidentified_as_signal(self):
        """[Plan F2 核心收益] 字面量 `8'd100` 不被误识为信号

        之前 string parsing: `8'd100` 可能被解析成 `d100` 标识符 (false positive)
        现在 ExpressionTree walk: `8'd100` 是 Const 节点, 直接 skip
        """
        src = '''module top(input a, output [7:0] y);
    assign y = a + 8'd100;
endmodule'''
        g = self._make_tracer_and_graph(src)
        cov = self._make_cov(g)

        tree = g._expr_trees.get('top.y')
        # 验证 tree 里有 Const 节点
        self.assertEqual(tree['op'], 'Add')
        children_ops = [c['op'] for c in tree['children']]
        self.assertIn('Const', children_ops,
                      f"Expected Const node, got children ops: {children_ops}")

        atomics = cov._extract_atomics_from_expr_tree(tree)
        names = [a.name for a in atomics]

        # 只有 'a', 没有 'd100' 或 '8'd100'
        self.assertEqual(names, ['a'],
                         f"Expected only 'a', got {names} (literal '8\\'d100' should NOT be extracted)")

    def test_slice_in_expression_keeps_bit_range(self):
        """`assign y = a[3:0] + b` → 2 个 SignalRef, a 带 bit_range (3,0)"""
        src = '''module top(input [7:0] a, b, output [7:0] y);
    assign y = a[3:0] + b;
endmodule'''
        g = self._make_tracer_and_graph(src)
        cov = self._make_cov(g)

        tree = g._expr_trees.get('top.y')
        atomics = cov._extract_atomics_from_expr_tree(tree)

        # 应该有 2 个 SignalRef
        self.assertEqual(len(atomics), 2)
        # 用 _split_identifier 拆分结果找 'a' base_name
        a_atomic = next(a for a in atomics if a.base_name == 'a')
        b_atomic = next(a for a in atomics if a.base_name == 'b')
        # a 的 name 是 'a[3:0]', bit_range 是 (3, 0)
        self.assertEqual(a_atomic.name, 'a[3:0]')
        self.assertEqual(a_atomic.bit_range, (3, 0))
        # b 是裸 SignalRef
        self.assertEqual(b_atomic.name, 'b')
        self.assertIsNone(b_atomic.bit_range)

    def test_trace_drivers_uses_expression_tree_internal_signal(self):
        """[Plan F2.4.3] _trace_drivers 优先用 expression_tree

        用内部 wire signal 测 (不是 PORT_OUT, 否则 _is_module_port early-return).
        """
        src = '''module top(input a, b, c, output [7:0] y);
    wire [7:0] tmp;
    assign tmp = a + b;
    assign y = tmp + c;
endmodule'''
        g = self._make_tracer_and_graph(src)
        cov = self._make_cov(g)

        # 'top.tmp' 是内部 wire, 不是 port
        node = g.get_node('top.tmp')
        self.assertIsNotNone(node, "expected internal node 'top.tmp'")
        # 验证 _is_module_port 返回 False (才会 walk tree)
        self.assertFalse(cov._is_module_port(node),
                         "top.tmp should NOT be a module port")

        # _trace_drivers 应该用 expression_tree 拿到 2 个 atomic (a, b)
        atomics = cov._trace_drivers('top.tmp', None, 0, 10, set())
        names = [a.name for a in atomics]
        self.assertEqual(set(names), {'a', 'b'},
                         f"Expected {{a, b}}, got {names}")

    def test_trace_drivers_no_string_fallback_returns_marker(self):
        """[Plan F2.7 2026-08-13] 强制不 fallback 到 string parsing

        [USER 2026-08-13 06:06] "不需要 string fallback... 不要 fallback"
        [F2.7 设计] tree 拿不到 → 返回 NO_TREE_MARKER + log WARNING.
        绝不调用 _parse_expression_to_atomics.

        [之前 F2.4.3] 老版本测试 'test_trace_drivers_falls_back_to_string_when_no_tree'
        锁定 string fallback 行为. F2.7 拆除 fallback 后, 这个 test 必须改为
        锁定「拿不到 tree → 返回 error marker, 不调用 string parsing」.
        """
        src = '''module top(input a, b, c, output [7:0] y);
    wire [7:0] tmp;
    assign tmp = a + b;
    assign y = tmp + c;
endmodule'''
        g = self._make_tracer_and_graph(src)

        # 删除 _expr_trees 模拟 tree 不可用
        if hasattr(g, '_expr_trees'):
            delattr(g, '_expr_trees')

        # Capture log
        import logging
        log_records = []
        handler = logging.Handler()
        handler.emit = lambda record: log_records.append(record)
        logger = logging.getLogger('trace.core.coverage_generator')
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        try:
            cov = self._make_cov(g)
            atomics = cov._trace_drivers('top.tmp', None, 0, 10, set())
            names = [a.name for a in atomics]

            # [F2.7] 应该只有 NO_TREE_MARKER (不能有 'a'/'b' — 那意味着 fallback 被调了)
            self.assertEqual(len(atomics), 1,
                             f"[F2.7] Should return exactly 1 NO_TREE_MARKER, got {len(atomics)}")
            self.assertEqual(atomics[0].name, NO_TREE_MARKER,
                             f"[F2.7] Should return NO_TREE_MARKER, got {atomics[0].name}")
            self.assertNotIn('a', names,
                             f"[F2.7] String fallback should NOT be called, but got 'a' in {names}")
            self.assertNotIn('b', names,
                             f"[F2.7] String fallback should NOT be called, but got 'b' in {names}")

            # [F2.7] WARNING 应该 log, 含 NO_EXPR_TREE + signal_id + tree_key
            self.assertGreater(len(log_records), 0,
                               "[F2.7] Should log WARNING when tree missing")
            msg = log_records[-1].getMessage()
            self.assertIn('NO_EXPR_TREE', msg,
                          f"[F2.7] WARNING should mention NO_EXPR_TREE, got: {msg}")
            self.assertIn('top.tmp', msg,
                          f"[F2.7] WARNING should include signal_id, got: {msg}")
        finally:
            logger.removeHandler(handler)


if __name__ == '__main__':
    unittest.main()
