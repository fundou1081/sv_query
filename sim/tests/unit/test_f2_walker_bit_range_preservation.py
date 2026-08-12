"""
test_f2_walker_bit_range_preservation.py — [Plan F2.5 2026-08-13] walker 修 bug

[BUG 2026-08-13 真实发现] coverage_generator._extract_atomics_from_expr_tree
在 BitSelect-wrapped SignalRef 路径丢失 bit_range:

  Standalone `assign [3:0] y = a[3:0];`
  pyslang 构建: BitSelect(label='a[3:0]', children=[SignalRef('a')])
  walker 抽:    atomic(name='a', base='a', bit_range=None)  ❌ 丢失 (3, 0)

  Mixed `assign y = a[3:0] + b;`
  pyslang 构建: Add(+, [SignalRef('a[3:0]'), SignalRef('b')])
  walker 抽:    atomic(name='a[3:0]', base='a', bit_range=(3, 0))  ✅ 保留

不一致: 同样的 slice `a[3:0]`, 不同上下文得到不同 bit_range.
下游 consumer (coverage report / condition analysis) 会看到 atomic 失去精度.

[Plan F2.5 FIX] walker 必须在 BitSelect 节点提取 bit_range from label,
传给 SignalRef child. 用 _split_identifier 解析 BitSelect label.

[铁律13] 金标准测试优先 — regression test 锁定 bug
[铁律17] 强断言 (bit_range tuple 精确)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.coverage_generator import ControlCoverageGenerator


def _walker_for(src: str):
    """直接拿 walker 实例 (不需要 graph 完整 build)"""
    t = UnifiedTracer(sources={'test.sv': src}, strict=False)
    t.build_graph()
    g = t.get_graph()
    trees = getattr(g, '_expr_trees', {})
    if not trees:
        return None
    return list(trees.values())[0]


def _walk_atomics(tree_dict: dict):
    gen = ControlCoverageGenerator.__new__(ControlCoverageGenerator)
    return gen._extract_atomics_from_expr_tree(tree_dict)


class TestF2WalkerBitRangePreservation(unittest.TestCase):
    """[Plan F2.5] walker 必须保留 BitSelect 的 bit_range 上下文"""

    def test_standalone_slice_preserves_bit_range(self):
        """[BUG REGRESSION] standalone `a[3:0]` 必须保留 bit_range=(3,0)"""
        src = '''module top(input [7:0] a, output [3:0] y);
    assign y = a[3:0];
endmodule'''
        tree = _walker_for(src)
        self.assertIsNotNone(tree)
        atomics = _walk_atomics(tree)
        # 找到 base='a' 的 atomic
        a_atomics = [a for a in atomics if a.base_name == 'a']
        self.assertEqual(len(a_atomics), 1)
        self.assertEqual(a_atomics[0].bit_range, (3, 0),
                         f"[F2.5 BUG FIX] bit_range must be preserved: "
                         f"got {a_atomics[0].bit_range}, expected (3, 0)")

    def test_standalone_partial_bit_select_preserves_bit_range(self):
        """[BUG REGRESSION] standalone `a[3]` 必须保留 bit_range=(3,3)"""
        src = '''module top(input [7:0] a, output y);
    assign y = a[3];
endmodule'''
        tree = _walker_for(src)
        self.assertIsNotNone(tree)
        atomics = _walk_atomics(tree)
        a_atomics = [a for a in atomics if a.base_name == 'a']
        self.assertEqual(len(a_atomics), 1)
        self.assertEqual(a_atomics[0].bit_range, (3, 3),
                         f"[F2.5 BUG FIX] single bit select must have (3,3): "
                         f"got {a_atomics[0].bit_range}")

    def test_mixed_slice_bit_range_consistent(self):
        """[一致性] `a[3:0] + b` 跟 `a[3:0]` 独立 必须都保留 bit_range

        [NOTE 2026-08-13] 必须用 width-matching LHS/RHS 才能拿到 tree:
        - standalone: y[3:0] = a[3:0] (4bit = 4bit)
        - mixed: y[7:0] = a[3:0] + b (4bit + 8bit, 警告但 tree 仍建)
        """
        src_mixed = '''module top(input [7:0] a, input [7:0] b, output [7:0] y);
    assign y = a[3:0] + b;
endmodule'''
        src_standalone = '''module top(input [7:0] a, output [3:0] y);
    assign y = a[3:0];
endmodule'''

        tree_mixed = _walker_for(src_mixed)
        tree_standalone = _walker_for(src_standalone)

        self.assertIsNotNone(tree_mixed, "mixed case tree must exist")
        self.assertIsNotNone(tree_standalone, "standalone case tree must exist")

        mixed_atomics = _walk_atomics(tree_mixed)
        standalone_atomics = _walk_atomics(tree_standalone)

        # 两个 a[3:0] 的 atomic bit_range 必须一致
        mixed_a = [a for a in mixed_atomics if a.base_name == 'a'][0]
        standalone_a = [a for a in standalone_atomics if a.base_name == 'a'][0]
        self.assertEqual(mixed_a.bit_range, standalone_a.bit_range,
                         "[F2.5 FIX] bit_range must be consistent across contexts")
        self.assertEqual(standalone_a.bit_range, (3, 0))

    def test_concat_preserves_inner_bit_range(self):
        """`{a[3:0], b[7:0]}` — Concat 包裹, inner BitSelect bit_range 必须保留

        [NOTE 2026-08-13] 必须用 width-matching LHS:
        y[11:0] = {a[3:0], b[7:0]} (4+8=12bit)
        """
        src = '''module top(input [7:0] a, input [7:0] b, output [11:0] y);
    assign y = {a[3:0], b[7:0]};
endmodule'''
        tree = _walker_for(src)
        self.assertIsNotNone(tree)
        atomics = _walk_atomics(tree)
        # a bit_range=(3,0), b bit_range=(7,0)
        a_atomic = next(a for a in atomics if a.base_name == 'a')
        b_atomic = next(a for a in atomics if a.base_name == 'b')
        self.assertEqual(a_atomic.bit_range, (3, 0))
        self.assertEqual(b_atomic.bit_range, (7, 0))


class TestF2WalkerNoFalsePositives(unittest.TestCase):
    """[Plan F2.5] walker 不能产生 false positive atomic"""

    def test_no_literal_signal_false_positive(self):
        """`a + 8'd100` — 8'd100 必须是 Const, walker 只抽 'a'"""
        src = '''module top(input [7:0] a, output [7:0] y);
    assign y = a + 8'd100;
endmodule'''
        tree = _walker_for(src)
        atomics = _walk_atomics(tree)
        names = {a.name for a in atomics}
        # 严格断言: 只有 'a', 不能有 'd100' 或 '8' 或其他字面量片段
        self.assertEqual(names, {'a'},
                         f"[F2.5 NO FP] expected only 'a', got {names}")

    def test_concat_inner_signal_refs(self):
        """`{a, b}` Concat — 两个 inner SignalRef 都抽"""
        src = '''module top(input [3:0] a, b, output [7:0] y);
    assign y = {a, b};
endmodule'''
        tree = _walker_for(src)
        atomics = _walk_atomics(tree)
        names = {a.base_name for a in atomics}
        self.assertEqual(names, {'a', 'b'})

    def test_nested_arithmetic_all_signals(self):
        """`a + b * c - d` 嵌套 — 4 个信号全抽"""
        src = '''module top(input [7:0] a, b, c, d, output [7:0] y);
    assign y = a + b * c - d;
endmodule'''
        tree = _walker_for(src)
        atomics = _walk_atomics(tree)
        names = {a.base_name for a in atomics}
        self.assertEqual(names, {'a', 'b', 'c', 'd'})


if __name__ == '__main__':
    unittest.main()