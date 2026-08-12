"""
test_f2_generate_for_indexed_lhs.py — [Plan F2.6 2026-08-13] driver_extractor generate for 块内 indexed LHS

[BUG 2026-08-13 真实发现] `assign y[i] = a + b;` 在 generate for 块内:
- Edge 建了: ('top.a', 'top.y[0]'), ('top.a', 'top.y[1]') 等 ✅
- 但 graph._expr_trees 完全空 ❌

[根因] pyslang 把 generate for 内的 `a + b` 包成 `ExpressionKind.Conversion`
(整数提升/类型转换), .syntax 是 None. driver_extractor._store_expr_tree
早返 `if syntax is None: return`, tree 永远不存.

[F2.6 FIX] 在 _store_expr_tree 加 unwrap helper, 处理 Conversion wrapper:
- Conversion kind → 递归 .operand 直到非 Conversion
- 然后拿非 wrapper expression 的 .syntax

[Plan F2.4.4 limitation 锁定] generate for indexed LHS 边建 tree 缺 — 这是
F2.4.4 锁定的 limitation. F2.6 修复.

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
    expr_trees = getattr(graph, '_expr_trees', {})
    return expr_trees.get(signal_id)


class TestF2GenerateForIndexedLHS(unittest.TestCase):
    """[Plan F2.6] generate for 块内 indexed LHS 必须建 tree"""

    def test_generate_for_indexed_lhs_builds_tree(self):
        """[F2.6 修复] generate for 块内 `assign y[i] = a + b` 必须建 tree

        [BUG REGRESSION] 修复前: _expr_trees 完全空
        [FIX 后] tree_key='top.y[0]'/'top.y[1]' 各有 Add tree
        """
        src = '''module top(input [7:0] a, b, output [1:0] y);
    genvar i;
    generate
        for (i = 0; i < 2; i = i + 1) begin : gen_loop
            assign y[i] = a + b;
        end
    endgenerate
endmodule'''
        g = _tracer_for(src)
        trees = getattr(g, '_expr_trees', {})

        # 修复前 trees 是空 dict. 修复后应该有两个 Add tree.
        self.assertEqual(len(trees), 2,
                         f"[F2.6 FIX] Expected 2 trees (y[0], y[1]), got {len(trees)}: {list(trees.keys())}")

        # 'top.y[0]' 应该有 Add tree
        tree = _tree_for(g, 'top.y[0]')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Add')
        self.assertEqual(tree['label'], '+')
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

        # 'top.y[1]' 也应该有同样的 Add tree
        tree = _tree_for(g, 'top.y[1]')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Add')
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

    def test_generate_for_indexed_lhs_with_complex_rhs(self):
        """generate for + 复杂 RHS `a * b + c` 应该建多层 tree"""
        src = '''module top(input [7:0] a, b, c, output [1:0] y);
    genvar i;
    generate
        for (i = 0; i < 2; i = i + 1) begin : gen_loop
            assign y[i] = a * b + c;
        end
    endgenerate
endmodule'''
        g = _tracer_for(src)
        trees = getattr(g, '_expr_trees', {})

        # 修复后应该有 2 个 tree, 都是 Add 顶层
        self.assertEqual(len(trees), 2,
                         f"[F2.6 FIX] Expected 2 trees, got {len(trees)}")
        for k, v in trees.items():
            self.assertEqual(v['op'], 'Add',
                             f"[F2.6] tree[{k}] should be Add, got {v['op']}")

    def test_generate_for_indexed_lhs_tree_key_format(self):
        """[一致性] tree_key 必须跟 signal_id 完全一致 'top.y[0]'

        [Plan F2.4.2 假设] 锁定 key 格式
        """
        src = '''module top(input [7:0] a, output [1:0] y);
    genvar i;
    generate
        for (i = 0; i < 2; i = i + 1) begin : gen_loop
            assign y[i] = a;
        end
    endgenerate
endmodule'''
        g = _tracer_for(src)
        trees = getattr(g, '_expr_trees', {})

        # 应该有 'top.y[0]' 和 'top.y[1]' 两个 key
        keys = sorted(trees.keys())
        self.assertEqual(keys, ['top.y[0]', 'top.y[1]'],
                         f"[F2.4.2 一致性] expected keys, got {keys}")


class TestF2NonGenerateAssignStillWorks(unittest.TestCase):
    """[Plan F2.6] 修复后不能破坏既有 non-generate assign 行为"""

    def test_plain_assign_still_builds_tree(self):
        """[REGRESSION] 普通 `assign y = a + b` 必须继续工作"""
        src = '''module top(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Add')

    def test_ternary_assign_still_builds_tree(self):
        """[REGRESSION] ternary `assign y = sel ? a : b` 必须继续工作"""
        src = '''module top(input sel, input [7:0] a, b, output [7:0] y);
    assign y = sel ? a : b;
endmodule'''
        g = _tracer_for(src)
        tree = _tree_for(g, 'top.y')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['op'], 'Ternary')


if __name__ == '__main__':
    unittest.main()