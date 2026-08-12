"""
test_f2_expression_tree_injection.py — [Plan F2.4.2 2026-08-13] Verify DriverInfo.expression_tree injection

[Plan F2] drive_dependencies refactor: 把结构化 ExpressionTree 注入到 DriverInfo,
让 checker / cdc_analyzer / coverage_generator 能静态分析 driver 表达式 (不再依赖
string parsing).

本文件验证:
  1. trace_fanin_detailed 返回的每个 DriverInfo 都有 expression_tree 字段
  2. tree_dict 结构正确 (op / label / children 跟 driver_extractor 构建的一致)
  3. 向后兼容: graph 没 _expr_trees 时 expression_tree 是 None (不 crash)
  4. tree_key 跟 signal_id namespace 一致 (driver_extractor 用 module.lhs, graph 用全路径)

[铁律13] 金标准测试优先
[铁律17] 强断言 (具体行为)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.query.signal import SignalTracer
from trace.core.graph.models import DriverInfo
from trace.unified_tracer import UnifiedTracer


class TestF2ExpressionTreeInjection(unittest.TestCase):
    """[Plan F2.4.2] DriverInfo.expression_tree 注入验证"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source}, strict=False)

    def test_simple_assignment_injects_expression_tree(self):
        """`assign y = a + b` → 2 driver 都拿到 Add(a, b) expression tree"""
        source = '''module top(input a, b, output y);
    assign y = a + b;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        g = tracer.get_graph()

        q = SignalTracer(g)
        drivers = q.trace_fanin_detailed('y', module='top')

        # 预期 2 个 driver: top.a, top.b
        self.assertEqual(len(drivers), 2)
        driver_ids = {d.id for d in drivers}
        self.assertEqual(driver_ids, {'top.a', 'top.b'})

        # 每个 driver 都应该拿到 expression_tree (不是 None)
        for d in drivers:
            self.assertIsNotNone(
                d.expression_tree,
                f"DriverInfo for {d.id} has no expression_tree injected",
            )

        # expression_tree 应该是 Add 节点, children 是 2 个 SignalRef
        for d in drivers:
            tree = d.expression_tree
            self.assertEqual(tree['op'], 'Add', f"{d.id}: expected op=Add, got {tree.get('op')}")
            self.assertEqual(tree['label'], '+')
            self.assertEqual(len(tree['children']), 2)
            child_ops = sorted(c['op'] for c in tree['children'])
            self.assertEqual(child_ops, ['SignalRef', 'SignalRef'])

    def test_nested_expression_preserves_structure(self):
        """嵌套表达式 `assign y = (a + b) * c` → 所有 driver 拿到同一个 root tree

        [Plan F2.4.2 设计决策] graph._expr_trees[key] 是按 LHS 存的单个 root tree,
        不是按 driver 存 sub-tree. 所以所有 driver of y 都拿到相同的
        Multiply(Add(a, b), c) — 调用者需自己 walk tree 找特定 driver.
        """
        source = '''module top(input a, b, c, output [15:0] y);
    assign y = (a + b) * c;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        g = tracer.get_graph()

        q = SignalTracer(g)
        drivers = q.trace_fanin_detailed('y', module='top')

        # 应该有 3 个 driver: a, b, c
        driver_ids = {d.id for d in drivers}
        self.assertEqual(driver_ids, {'top.a', 'top.b', 'top.c'})

        # 所有 driver 拿到同一个 root tree (Multiply)
        # 这是 by design: tree_key 是 LHS, 不是 driver
        tree_shapes = set()
        for d in drivers:
            self.assertIsNotNone(d.expression_tree, f"{d.id} missing tree")
            tree_shapes.add(d.expression_tree['op'])

        # 只应该有一种 root op (Multiply) — 3 个 driver 全共享
        self.assertEqual(tree_shapes, {'Multiply'},
                         f"all drivers should share root tree, got {tree_shapes}")

        # 验证 root tree 结构: Multiply → Add(a,b) + SignalRef(c)
        sample_tree = drivers[0].expression_tree
        self.assertEqual(sample_tree['op'], 'Multiply')
        # [FIX 2026-08-13] label 是 Unicode 乘号 '×' (expression_tree.py:134 _kind_to_label
        # 转换), 不是 ASCII '*'. Add 同理是 '+'.
        self.assertEqual(sample_tree['label'], '×')
        self.assertEqual(len(sample_tree['children']), 2)

        # 第一个 child 是 Add, 第二个是 SignalRef
        add_child = sample_tree['children'][0]
        cref_child = sample_tree['children'][1]
        self.assertEqual(add_child['op'], 'Add')
        self.assertEqual(len(add_child['children']), 2)  # a, b
        self.assertEqual(cref_child['op'], 'SignalRef')
        self.assertEqual(cref_child['label'], 'c')

        # 收集所有 SignalRef 叶子 (consumer 通常需要找这些)
        def _collect_signal_refs(node):
            refs = []
            if node['op'] == 'SignalRef':
                refs.append(node['label'])
            for c in node.get('children', []):
                refs.extend(_collect_signal_refs(c))
            return refs

        refs = _collect_signal_refs(sample_tree)
        self.assertEqual(set(refs), {'a', 'b', 'c'})

    def test_signal_ref_leaf_node(self):
        """简单赋值 `assign y = a` → expression tree 是单个 SignalRef leaf"""
        source = '''module top(input a, output y);
    assign y = a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        g = tracer.get_graph()

        q = SignalTracer(g)
        drivers = q.trace_fanin_detailed('y', module='top')

        self.assertEqual(len(drivers), 1)
        d = drivers[0]
        self.assertEqual(d.id, 'top.a')
        self.assertIsNotNone(d.expression_tree)
        self.assertEqual(d.expression_tree['op'], 'SignalRef')
        self.assertEqual(d.expression_tree['label'], 'a')
        self.assertEqual(d.expression_tree['children'], [])

    def test_backward_compatible_when_no_expr_trees(self):
        """graph 没 _expr_trees 属性 → expression_tree 是 None, 不 crash"""
        source = '''module top(input a, output y);
    assign y = a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        g = tracer.get_graph()

        # 模拟老 graph (无 _expr_trees)
        if hasattr(g, '_expr_trees'):
            delattr(g, '_expr_trees')

        q = SignalTracer(g)
        drivers = q.trace_fanin_detailed('y', module='top')

        # expression_tree 应该是 None (向后兼容)
        self.assertEqual(len(drivers), 1)
        self.assertIsNone(drivers[0].expression_tree)

    def test_signal_with_no_assignment_has_no_tree(self):
        """input port 没有 assignment → _expr_trees 里没记录 → expression_tree 是 None"""
        source = '''module top(input a, output y);
    assign y = a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        g = tracer.get_graph()

        # trace_fanin_detailed 查 'a' (input port, 无 assignment)
        q = SignalTracer(g)
        drivers = q.trace_fanin_detailed('a', module='top')

        # 没 driver, expression_tree 也无从注入
        self.assertEqual(len(drivers), 0)


if __name__ == '__main__':
    unittest.main()
