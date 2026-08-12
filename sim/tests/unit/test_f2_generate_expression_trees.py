"""
test_f2_generate_expression_trees.py — [Plan F2.4.4 2026-08-13] F1+F2 连接点

[Plan F2] drive_dependencies refactor step 4:
F1 (generate for/if/case 支持) + F2 (ExpressionTree 注入) 的连接测试.

[NOTE 2026-08-13 F1+F2 真实发现] 验证后现状:

  | 场景                     | Edge 建? | Tree 建? | 测试结果  |
  | ------------------------ | -------- | -------- | --------- |
  | generate if (常开)       | ✅       | ✅       | 通过 ✅   |
  | generate if/else         | ✅       | ✅       | 通过 ✅   |
  | generate for             | ✅       | ❌       | 记录 limitation |
  | generate case (非 const) | ❌       | ❌       | pyslang 限制 |
  | generate case (const)    | ❌       | ❌       | pyslang 限制 |

**真实 limitation 发现**:
- generate for 块内的 `assign y[i] = a + b;` → 边建了 (`top.a → top.y[0]`)
  但 `_expr_trees` 是空 dict. driver_extractor 用的 key 是 `{module}.{lhs_name}`,
  对 generate for 的 LHS (`y[0]`) 没正确建立 tree.
- generate case 在 strict=False 下仍报 [ConstEvalNonConstVariable] —
  pyslang 11 对 generate case + 非 const sel 不展开.

这两个是 F1+F2 真实 gap — 不是我们 ExpressionTree 的 bug, 是 driver_extractor
跟 generate for 的 LHS 索引语法 (`y[i]`) 配合缺处理.

[铁律13] 金标准测试优先
[铁律17] 强断言 (具体行为)
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


class TestF2GenerateIfExpressionTree(unittest.TestCase):
    """[Plan F2.4.4 PASSING] generate if 块内 expression tree"""

    def test_generate_if_branch_has_tree(self):
        """`generate if (1'b1) assign y = a + b;` 块内 Add tree ✅"""
        src = '''module top(input [7:0] a, b, output [7:0] y);
    generate
        if (1'b1) begin : gen_block
            assign y = a + b;
        end
    endgenerate
endmodule'''
        g = _tracer_for(src)
        expr_trees = getattr(g, '_expr_trees', {})
        # 应该有 top.y 的 tree (generate if 真分支)
        self.assertIn('top.y', expr_trees,
                      f"Expected 'top.y' tree, got {list(expr_trees.keys())}")
        tree = expr_trees['top.y']
        self.assertEqual(tree['op'], 'Add')
        self.assertEqual(tree['label'], '+')
        labels = sorted(c['label'] for c in tree['children'])
        self.assertEqual(labels, ['a', 'b'])

    def test_generate_if_else_both_branches_have_trees(self):
        """`generate if/else` (const sel) 应该选一个分支建 tree ✅

        [NOTE 2026-08-13] 选用 const `1'b1` 作为 if condition (pyslang 11 限制):
        runtime sel 会被报 [ConstEvalNonConstVariable], 导致 generate 块不展开.
        本 test 验证 static generate if/else 能建 tree (F1 责任) + tree 是 Add 形状 (F2 责任).
        """
        src = '''module top(input [7:0] a, b, c, d, output [7:0] y);
    generate
        if (1'b1) begin : gen_true
            assign y = a + b;
        end else begin : gen_false
            assign y = c + d;
        end
    endgenerate
endmodule'''
        g = _tracer_for(src)
        expr_trees = getattr(g, '_expr_trees', {})
        # 应该至少有 'top.y' tree (不管哪个分支)
        self.assertIn('top.y', expr_trees,
                      f"Expected 'top.y' tree from generate if/else, "
                      f"got {list(expr_trees.keys())}")
        tree = expr_trees['top.y']
        self.assertEqual(tree['op'], 'Add')
        # 至少包含 a, b, c, d 中的 2 个
        labels = [c.get('label') for c in tree.get('children', [])]
        self.assertEqual(len(labels), 2)


class TestF2GenerateForLimitation(unittest.TestCase):
    """[Plan F2.4.4 LIMITATION 记录] generate for LHS `y[i]` 没建 tree

    [NOTE 2026-08-13 真实发现] driver_extractor 用 {module}.{lhs_name} 作 key.
    generate for 块内 `assign y[i] = a + b;` 展开后是 `assign y[0] = a + b`,
    但 driver_extractor 没把 'y[0]' / 'y[1]' 作 key. 边建了 (`top.a → top.y[0]`),
    tree 没建. 这是 F1+F2 真实 gap — 应该在后续 Plan (F2.5+?) 修.

    本 test 锁定 limitation 让未来修复可见:
      - 旧行为: tree 缺 → test fail (现在 skip with documentation)
      - 新行为: tree 建 → test fail (驱动修复)
    """

    def test_generate_for_indexed_lhs_now_has_tree(self):
        """[F2.6 FIX 2026-08-13] generate for 块内 indexed LHS 现在能建 tree

        [历史 limitation] F2.4.4/F2.5 锁定 limitation: generate for 块内 LHS 带索引
        (e.g. `assign y[i] = a + b`) 边建了但 tree 缺. driver_extractor 限制.

        [F2.6 FIX] _store_expr_tree 加 Conversion unwrap 后, 这种情况也能建 tree.
        - tree_key 应该是 'top.y[0]' / 'top.y[1]'
        - tree 形状应该是 Add(+, [SignalRef(a), SignalRef(b)])
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
        # 边应该建 (F1 OK)
        edges = list(g.edges())
        self.assertGreater(len(edges), 0,
                           "generate for should still create edges (F1 works)")
        # 检查 generate for 创建的 indexed node
        indexed_nodes = [n for n in g.nodes() if n.endswith('[0]') or n.endswith('[1]')]
        self.assertGreater(len(indexed_nodes), 0,
                           "generate for should create indexed signals like y[0], y[1]")

        # [F2.6 FIX] tree 现在建了 — 验证 key + 形状
        expr_trees = getattr(g, '_expr_trees', {})
        indexed_trees = [k for k in expr_trees.keys()
                         if k.endswith('[0]') or k.endswith('[1]')]
        self.assertEqual(len(indexed_trees), 2,
                         f"[F2.6 FIX] Expected 2 indexed trees (y[0], y[1]), "
                         f"got {len(indexed_trees)}: {indexed_trees}")

        # 验证 'top.y[0]' tree 是 Add(a, b)
        tree_y0 = expr_trees.get('top.y[0]')
        self.assertIsNotNone(tree_y0)
        self.assertEqual(tree_y0['op'], 'Add')
        self.assertEqual(tree_y0['label'], '+')
        labels = sorted(c['label'] for c in tree_y0['children'])
        self.assertEqual(labels, ['a', 'b'])

        # 验证 'top.y[1]' 同样
        tree_y1 = expr_trees.get('top.y[1]')
        self.assertIsNotNone(tree_y1)
        self.assertEqual(tree_y1['op'], 'Add')


class TestF2GenerateCaseLimitation(unittest.TestCase):
    """[Plan F2.4.4 LIMITATION 记录] generate case + 非 const sel 不展开

    [NOTE 2026-08-13 pyslang 限制] generate case 的 sel 必须是 const 表达式.
    输入端口 `sel` 不是 const → pyslang 报 [ConstEvalNonConstVariable] →
    case body 不展开 → 没边没 tree.
    """

    def test_generate_case_runtime_sel_limitation(self):
        """[LIMITATION] generate case + 非 const sel → 无边无 tree (pyslang)"""
        src = '''module top(input [1:0] sel, input [7:0] a, b, c, d, output [7:0] y);
    generate
        case (sel)
            2'b00: begin : gen_a
                assign y = a + b;
            end
            2'b01: begin : gen_b
                assign y = c + d;
            end
            default: begin : gen_default
                assign y = a + c;
            end
        endcase
    endgenerate
endmodule'''
        g = _tracer_for(src)
        edges = list(g.edges())
        expr_trees = getattr(g, '_expr_trees', {})

        # pyslang 11 + 非 const sel: case 不展开, 无边无 tree
        # 这是 pyslang 限制 — 锁定 limitation
        # 如果未来支持, 验证展开后有边有 tree
        self.assertEqual(len(edges), 0,
                         f"[F1+] Generate case with runtime sel was fixed! "
                         f"Edges: {edges}. Update test.")
        self.assertEqual(len(expr_trees), 0,
                         f"[F2.5+] Generate case with runtime sel tree was fixed! "
                         f"Trees: {expr_trees}. Update test.")


class TestF2GenerateKeyConsistency(unittest.TestCase):
    """[Plan F2.4.4] generate 块内 tree key 跟 signal_id 一致性"""

    def test_generate_if_tree_key_matches_node_id(self):
        """generate if 块内 tree key 跟 graph node ID 格式一致 ✅"""
        src = '''module top(input [7:0] a, b, output [7:0] y);
    generate
        if (1'b1) begin : gen_block
            assign y = a + b;
        end
    endgenerate
endmodule'''
        g = _tracer_for(src)
        # 所有 node ID 应该以 'top.' 开头
        node_ids = list(g.nodes())
        for nid in node_ids:
            self.assertTrue(nid.startswith('top.'),
                            f"Node '{nid}' should start with 'top.'")

        # 所有 tree key 也应该以 'top.' 开头
        expr_trees = getattr(g, '_expr_trees', {})
        for key in expr_trees.keys():
            self.assertTrue(key.startswith('top.'),
                            f"Tree key '{key}' should start with 'top.'")


if __name__ == '__main__':
    unittest.main()