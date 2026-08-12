"""
test_f2_expression_tree_shapes.py — [Plan F2.4.4 2026-08-13] ExpressionTree 形状 assertion

[Plan F2] 核心收益: checker 现在能静态分析 driver 表达式结构 (不是只 string parse).
本文件验证常见 SV 表达式在 ExpressionTree dict 里的具体形状:
  - arithmetic (Add, Multiply)
  - slice / bit-select (BitSelect op, child 是 SignalRef)
  - ternary (Ternary op, 3 children: cond, true, false)
  - 嵌套组合

[NOTE 2026-08-13] 验证发现 ExpressionTree 实际 op 名字:
  - `a[7:0]` → BitSelect(SignalRef(a))   (不是 SignalRef 直接)
  - `sel ? a : b` → Ternary(sel, a, b)   (不是 ConditionalExpression)
  - `a[3]` (单 bit) → pyslang 不生成 tree
  - `{a, b}` concat → pyslang 不生成 tree
  - `{8'd0, a[7:0]} + b*c - d` 复杂 → pyslang 不生成 tree

[为什么重要]:
  形状 test 是 F2 的"checker" — 任何 expression_tree.py 的 bug 或 pyslang AST 解析
  变化都会自动 fail. 之前 Plan F1 暴露的 pre-existing test bug (F1.3/F1.6) 用 string
  parsing 时根本看不出问题; 现在用 tree shape 一眼就能 catch.

[铁律13] 金标准测试优先
[铁律17] 强断言 (具体行为, op/label/children 形状)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


def _tracer_for(src: str, name: str = 'test.sv'):
    tracer = UnifiedTracer(sources={name: src}, strict=False)
    tracer.build_graph()
    return tracer.get_graph()


def _tree_for(graph, signal_id: str):
    """从 graph._expr_trees 拿 signal 的 tree_dict, 找不到返回 None."""
    expr_trees = getattr(graph, '_expr_trees', {})
    return expr_trees.get(signal_id)


def _collect_signal_refs(node: dict) -> list[str]:
    """递归 walk 收集所有 SignalRef 叶子 label."""
    refs = []
    if node.get('op') == 'SignalRef':
        refs.append(node.get('label'))
    for c in node.get('children', []) or []:
        refs.extend(_collect_signal_refs(c))
    return refs


class TestExpressionTreeShapesArithmetic(unittest.TestCase):
    """[Plan F2.4.4] 算术表达式形状"""

    def test_add_shape(self):
        """`a + b` → Add(+ , [SignalRef(a), SignalRef(b)])"""
        src = '''module top(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree, "ExpressionTree should exist for 'top.y'")
        self.assertEqual(tree['op'], 'Add')
        self.assertEqual(tree['label'], '+')
        self.assertEqual(len(tree['children']), 2)
        for c in tree['children']:
            self.assertEqual(c['op'], 'SignalRef')
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

    def test_nested_precedence_mul_over_add(self):
        """`a + b * c` → Add(+ , [SignalRef(a), Multiply(×, [b, c])])

        pyslang AST 正确处理运算符优先级: * 比 + 优先.
        """
        src = '''module top(input [7:0] a, b, c, output [7:0] y);
    assign y = a + b * c;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertEqual(tree['op'], 'Add')
        right = tree['children'][1]
        self.assertEqual(right['op'], 'Multiply')
        self.assertEqual(right['label'], '×')

    def test_parenthesized_explicit_grouping(self):
        """`(a + b) * c` → Multiply(×, [Add(a, b), SignalRef(c)])"""
        src = '''module top(input [7:0] a, b, c, output [7:0] y);
    assign y = (a + b) * c;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertEqual(tree['op'], 'Multiply')
        left = tree['children'][0]
        self.assertEqual(left['op'], 'Add')
        self.assertEqual(tree['children'][1]['op'], 'SignalRef')
        self.assertEqual(tree['children'][1]['label'], 'c')


class TestExpressionTreeShapesSlice(unittest.TestCase):
    """[Plan F2.4.4] bit-select / slice 形状

    [NOTE 2026-08-13] pyslang 把 `a[7:0]` 拆成 BitSelect(SignalRef(a)) — 不是 SignalRef 直接.
    BitSelect 的 label 是 'a[7:0]' (含 bit range), child 是 SignalRef('a').
    """

    def test_simple_slice_bit_select_with_signalref_child(self):
        """`a[7:0]` → BitSelect(label='a[7:0]', child=SignalRef('a'))"""
        src = '''module top(input [7:0] a, output [7:0] y);
    assign y = a[7:0];
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree, "ExpressionTree should exist for slice")
        self.assertEqual(tree['op'], 'BitSelect')
        self.assertEqual(tree['label'], 'a[7:0]')
        # child 是 SignalRef('a')
        self.assertEqual(len(tree['children']), 1)
        self.assertEqual(tree['children'][0]['op'], 'SignalRef')
        self.assertEqual(tree['children'][0]['label'], 'a')

    def test_slice_plus_other_signal(self):
        """`a[3:0] + b` → Add(+ , [<a[3:0]>, SignalRef(b)])

        [NOTE 2026-08-13] pyslang 实际行为: 跟独立 slice 不同 — 在较大表达式里
        pyslang 把 `a[3:0]` 拍扁成 SignalRef(label='a[3:0]'), 不是 BitSelect.
        两种行为都是 pyslang 合法输出 (取决于上下文); 接受两种.
        """
        src = '''module top(input [7:0] a, b, output [7:0] y);
    assign y = a[3:0] + b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Add')
        # 第一个 child 是 SignalRef('a[3:0]') 或 BitSelect('a[3:0]')
        first_child = tree['children'][0]
        self.assertIn(first_child['op'], ('SignalRef', 'BitSelect'),
                      f"Expected SignalRef or BitSelect, got '{first_child['op']}'")
        self.assertEqual(first_child['label'], 'a[3:0]')
        # 第二个 child 是 SignalRef('b')
        self.assertEqual(tree['children'][1]['op'], 'SignalRef')
        self.assertEqual(tree['children'][1]['label'], 'b')

    def test_partial_bit_select_width_match(self):
        """[Plan F2.4.4 修正] `a[3]` 单 bit select (width 匹配) → BitSelect tree ✅

        [NOTE 2026-08-13 修正] F2.4.4 初版误判为 pyslang 限制. 实际实验证实:
        pyslang 11 完全支持 `a[3]` 的 ExpressionTree, 只要 LHS/RHS width 匹配.
        原 'test_partial_bit_select_no_tree' 假设错了 (用了 [7:0] y, width 不匹配).
        """
        src = '''module top(input [7:0] a, output y);
    assign y = a[3];
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree, "BitSelect tree should exist when width matches")
        self.assertEqual(tree['op'], 'BitSelect')
        self.assertEqual(tree['label'], 'a[3]')
        self.assertEqual(len(tree['children']), 1)
        self.assertEqual(tree['children'][0]['op'], 'SignalRef')
        self.assertEqual(tree['children'][0]['label'], 'a')

    def test_partial_bit_select_width_mismatch_no_tree(self):
        """[F2.4.4 修正] 真正的 limitation — width mismatch 时 pyslang 不生成 tree

        [NOTE 2026-08-13 实际发现] `assign [7:0] y = a[3];` (LHS 8bit, RHS 1bit):
        pyslang 走 elaboration error path, 不生成 ExpressionTree.
        不是 pyslang 11 inherent 限制, 而是 width mismatch 触发.

        这个 limitation 应该被 coverage_generator 正确处理:
        _extract_atomics_from_expr_tree 在 tree 是 None 时 fallback 到 string parsing.
        """
        src = '''module top(input [7:0] a, output [7:0] y);
    assign y = a[3];
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        # width mismatch → 无 tree. 锁定 limitation 真实原因 (不是 pyslang)
        # 如果未来修了, 这个 test 自动 fail 提示修复
        self.assertIsNone(tree,
                          "[F2.4.4 锁定] width-mismatch partial select 不生成 tree. "
                          "如果这修好了, 验证 tree 形状.")


class TestExpressionTreeShapesTernary(unittest.TestCase):
    """[Plan F2.4.4] ternary (cond ? a : b) 形状"""

    def test_ternary_shape(self):
        """`sel ? a : b` → Ternary(label='?:', 3 children: sel, a, b)"""
        src = '''module top(input sel, input [7:0] a, b, output [7:0] y);
    assign y = sel ? a : b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Ternary')
        self.assertEqual(tree['label'], '?:')
        self.assertEqual(len(tree['children']), 3)
        # 三个 child 都是 SignalRef (sel, a, b)
        labels = [c['label'] for c in tree['children']]
        self.assertEqual(labels, ['sel', 'a', 'b'])
        for c in tree['children']:
            self.assertEqual(c['op'], 'SignalRef')


class TestExpressionTreeShapesComplex(unittest.TestCase):
    """[Plan F2.4.4] 复杂组合 + 一致性"""

    def test_signal_refs_extracted_correctly_from_complex_expr(self):
        """[Plan F2 核心收益] 收集所有 SignalRef 叶子, 跟 string parsing 对比

        之前的 string parsing 在 concat/literal 会 false-positive. 现在 tree walk
        准确识别所有 SignalRef. (concat tree pyslang 11 暂不支持, 用 mixed 测)
        """
        src = '''module top(input [7:0] a, b, c, d, output [7:0] y);
    assign y = a + b * c - d;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        refs = _collect_signal_refs(tree)
        # 应该有 a, b, c, d — 没有 literal false-positive
        self.assertEqual(set(refs), {'a', 'b', 'c', 'd'},
                         f"Expected exact {{a, b, c, d}}, got {refs}")

    def test_tree_key_matches_signal_id(self):
        """[一致性] graph._expr_trees 的 key 跟 signal_id 完全一致

        [Plan F2.4.2 假设] 如果 key 跟 signal_id 不一致, expression_tree injection
        会 fail. 这个 test 锁定一致性.
        """
        src = '''module top(input a, output y);
    assign y = a;
endmodule'''
        g = _tracer_for(src)
        expr_trees = getattr(g, '_expr_trees', {})
        # 应该有 'top.y' key (跟 graph node ID 一致)
        self.assertIn('top.y', expr_trees,
                      f"Expected 'top.y' key, got {list(expr_trees.keys())}")


class TestExpressionTreeShapesConcat(unittest.TestCase):
    """[Plan F2.4.4 修正] concat `{a, b}` 形状

    [NOTE 2026-08-13 修正] F2.4.4 初版误判为 pyslang 限制. 实际实验证实:
    pyslang 11 完全支持 `{a, b}` 的 ExpressionTree, 只要 LHS/RHS width 匹配.
    原 'test_concat_no_tree_pyslang_limit' 假设错了 (用了 1bit y, width 不匹配).
    """

    def test_concat_width_match(self):
        """`{a, b}` (width 匹配 4+4=8bit) → Concat tree ✅"""
        src = '''module top(input [3:0] a, b, output [7:0] y);
    assign y = {a, b};
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree, "Concat tree should exist when widths match")
        self.assertEqual(tree['op'], 'Concat')
        self.assertEqual(tree['label'], '{}')
        self.assertEqual(len(tree['children']), 2)
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

    def test_concat_width_mismatch_no_tree(self):
        """[F2.6 修正 2026-08-13] width mismatch 现在也能建 tree (Conversion unwrap)

        [BUG REGRESSION F2.4.4] 原本锁定 width-mismatch concat 不生成 tree.
        [F2.6 FIX] driver_extractor._store_expr_tree 加 Conversion unwrap 后,
        这种情况 pyslang 会包成 ExpressionKind.Conversion (width truncate), unwrap 后拿到 tree.
        这是 F2.6 的额外收益.
        """
        src = '''module top(input [3:0] a, b, output y);
    assign y = {a, b};
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        # [F2.6 FIX] 现在有 tree — Concat({a, b})
        self.assertIsNotNone(tree,
                             "[F2.6 FIX] width-mismatch concat 现在能建 tree. "
                             "如果这又 break 了, 是新 regression.")
        self.assertEqual(tree['op'], 'Concat')
        self.assertEqual(tree['label'], '{}')
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])


class TestExpressionTreeShapesExtra(unittest.TestCase):
    """[Plan F2.4.4 扩展] 高价值常见 RTL 表达式形状

    [NOTE 2026-08-13] pyslang 实测形状:
    - 左结合 `a + b + c` → Add(Add(a, b), c)  (左嵌套)
    - Reduction OR + binary AND: `|a & |b` → BinaryAnd(ReduceOr(a), ReduceOr(b))
    - 比较 op `a > b` → GreaterThan
    - always block 内 `<=` (NBA): tree 仍建 (顶层是 Add), expression 形状跟 assign 一致
    - 嵌套 ternary `sel1 ? (sel2 ? a : b) : (sel2 ? c : d)` → 3-level Ternary nesting
    """

    def test_left_associative_chained_add(self):
        """`a + b + c` → Add(Add(a, b), c) 左结合嵌套"""
        src = '''module top(input [7:0] a, b, c, output [7:0] y);
    assign y = a + b + c;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Add')
        # 左 child 是嵌套 Add(a, b), 右 child 是 SignalRef(c)
        left = tree['children'][0]
        right = tree['children'][1]
        self.assertEqual(left['op'], 'Add', "left should be nested Add (left-assoc)")
        self.assertEqual(right['op'], 'SignalRef')
        self.assertEqual(right['label'], 'c')
        # 验证所有 leaf SignalRef
        refs = sorted(_collect_signal_refs(tree))
        self.assertEqual(refs, ['a', 'b', 'c'])

    def test_reduction_or_with_binary_and(self):
        """`|a & |b` → BinaryAnd(ReduceOr(a), ReduceOr(b))"""
        src = '''module top(input [7:0] a, b, output y);
    assign y = (|a) & (|b);
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'BinaryAnd')
        # 两个 child 都是 ReduceOr
        for c in tree['children']:
            self.assertEqual(c['op'], 'ReduceOr',
                             f"Expected ReduceOr child, got '{c['op']}'")
        # 每个 ReduceOr 有一个 SignalRef child
        refs = sorted(_collect_signal_refs(tree))
        self.assertEqual(refs, ['a', 'b'])

    def test_comparison_greater_than(self):
        """`a > b` → GreaterThan(>, [SignalRef(a), SignalRef(b)])"""
        src = '''module top(input [7:0] a, b, output y);
    assign y = a > b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'GreaterThan')
        self.assertEqual(tree['label'], '>')
        self.assertEqual(len(tree['children']), 2)
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

    def test_always_block_nonblocking_assignment(self):
        """`always @(posedge clk) y <= a + b` 块内 NBA tree 仍建 ✅

        [NOTE 2026-08-13] driver_extractor 应该对 NBA (<=) 也建 tree, 跟连续赋值 (=) 一致.
        这是 F1+F2 集成测试 — generate/always 块内 expression tree 仍正确.
        """
        src = '''module top(input clk, input [7:0] a, b, output reg [7:0] y);
    always @(posedge clk) y <= a + b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree, "always block NBA should still build tree")
        self.assertEqual(tree['op'], 'Add')
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

    def test_nested_ternary_three_levels(self):
        """嵌套 ternary `sel1 ? (sel2 ? a : b) : (sel2 ? c : d)` → 3-level Ternary"""
        src = '''module top(input [1:0] sel, input [7:0] a, b, c, d, output [7:0] y);
    assign y = sel[1] ? (sel[0] ? a : b) : (sel[0] ? c : d);
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Ternary')
        # 顶层 3 children: cond, true_branch, false_branch
        self.assertEqual(len(tree['children']), 3)
        # true_branch 和 false_branch 都是 Ternary (嵌套 level 2)
        true_branch = tree['children'][1]
        false_branch = tree['children'][2]
        self.assertEqual(true_branch['op'], 'Ternary',
                         "true branch should be nested Ternary")
        self.assertEqual(false_branch['op'], 'Ternary',
                         "false branch should be nested Ternary")
        # 收集所有叶子 SignalRef: sel[0] 出现两次 (作为两个内层 ternary 的 condition),
        # 所以 refs 列表含 sel[0] × 2. 用 set 断言叶子类型集合.
        refs = _collect_signal_refs(tree)
        unique_refs = set(refs)
        self.assertEqual(unique_refs, {'a', 'b', 'c', 'd', 'sel[0]', 'sel[1]'},
                         f"Expected leaves {{a,b,c,d,sel[0],sel[1]}}, got {unique_refs}")
        # sel[0] 应该出现 2 次 (被两个内层 ternary 共用)
        self.assertEqual(refs.count('sel[0]'), 2,
                         "sel[0] should appear twice (cond of both inner ternaries)")
        self.assertEqual(refs.count('sel[1]'), 1)


if __name__ == '__main__':
    unittest.main()
