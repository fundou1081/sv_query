# test_constraint_derivative.py - Constraint 衍生语法金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_065] 行为断言: 在 AST 节点断言基础上, 补充 CONSTRAINS 边断言
#             (约束块 → 被约束的 CLASS_PROPERTY 变量).
#             参考 iter_063/064 升级的 test_constraint_advanced.py 模式.
"""
Constraint 衍生语法:
1. inside 约束
2. implication (->) 约束
3. if/else 约束
4. dist 分布约束
5. solve before 求解顺序
6. unique 唯一性约束
7. loop 循环约束

[iter_065 行为金标准] constraint 域的"行为" = CONSTRAINS 边
(约束块 → 被约束的 CLASS_PROPERTY 变量)。AST 断言只能证明"解析不崩",
不能证明"分析正确"。本文件 7 个测试中:
- 6 个可加 CONSTRAINS 边断言 (inside / implication / if_else / dist / unique / loop)
- 1 个 (solve_before) 解释性保留 AST 断言: 求解顺序不是值约束,
  提取器**不**产生到变量的 CONSTRAINS 边 (仅生成 solve_0 子节点),
  行为金标准不适用。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.base import PyslangAdapter
from trace.core.graph.models import EdgeKind
from trace.unified_tracer import UnifiedTracer


def _build_graph(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    tracer.build_graph()
    return tracer.get_graph()


def _edges_of_kind(graph, kind):
    """获取指定类型的边 [(src, dst), ...]"""
    result = []
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge and edge.kind == kind:
            result.append((src, dst))
    return result


def _assert_constrains(test_case, graph, block_id, var_ids):
    """断言约束块 CONSTRAINS 边到指定变量 (行为金标准, iter_065)."""
    edges = _edges_of_kind(graph, EdgeKind.CONSTRAINS)
    for var_id in var_ids:
        test_case.assertIn(
            (block_id, var_id),
            edges,
            f"应有 CONSTRAINS 边 {block_id} → {var_id}, 实际: {edges}",
        )


class TestConstraintDerivative(unittest.TestCase):
    """Constraint 衍生语法测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _get_classes(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        class FP:
            def __init__(self, t): self.trees = t
        adapter = PyslangAdapter(FP({'test.sv': tree}))
        return adapter.get_classes()

    def test_constraint_inside(self):
        """[Golden] inside 约束

        RTL: constraint c { addr inside {0, 1, 2}; }

        预期:
        - ConstraintDeclaration 存在
        - ExpressionConstraint 存在
        - [iter_065 行为] c CONSTRAINS → addr (约束块约束 addr)
        """
        source = '''class packet;
    bit [7:0] addr;
    constraint c { addr inside {0, 1, 2}; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)
        cls = classes[0]
        members = cls.items if hasattr(cls, 'items') else []
        has_constraint = any('Constraint' in str(getattr(m, 'kind', None)) for m in members)
        self.assertTrue(has_constraint, "ConstraintDeclaration not found")

        # [iter_065] 行为断言: 约束块 → 被约束变量的 CONSTRAINS 边
        graph = _build_graph(source)
        self.assertIn('packet.c', list(graph.nodes()), "约束块节点应生成")
        self.assertIn('packet.addr', list(graph.nodes()), "addr CLASS_PROPERTY 节点应生成")
        _assert_constrains(self, graph, 'packet.c', ['packet.addr'])

    def test_constraint_implication(self):
        """[Golden] implication (->) 约束

        RTL: constraint c { (en) -> data == 1; }

        预期:
        - ConstraintDeclaration 存在
        - [iter_065 行为] c CONSTRAINS → data (被约束值) + en (条件变量,
          提取器不区分条件与值, 均建模为 CONSTRAINS 边)
        """
        source = '''class packet;
    bit [7:0] data;
    bit en;
    constraint c { (en) -> data == 1; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)
        self.assertTrue(any('Constraint' in str(getattr(m, 'kind', None))
                            for m in (classes[0].items if hasattr(classes[0], 'items') else [])),
                        "ConstraintDeclaration not found")

        # [iter_065] 行为断言: 约束块 → 条件变量 + 被约束值
        graph = _build_graph(source)
        self.assertIn('packet.c', list(graph.nodes()), "约束块节点应生成")
        _assert_constrains(self, graph, 'packet.c', ['packet.data', 'packet.en'])

    def test_constraint_if_else(self):
        """[Golden] if/else 约束

        RTL:
        constraint c {
            if (en) addr == 1;
            else addr == 2;
        }

        预期:
        - ConstraintDeclaration 存在
        - [iter_065 行为] c CONSTRAINS → addr (consequent+alternate) + en (条件)
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)

        # [iter_065] 行为断言: 约束块 → 条件变量 + 被约束值
        graph = _build_graph(source)
        self.assertIn('packet.c', list(graph.nodes()), "约束块节点应生成")
        self.assertIn('packet.c::if_0', list(graph.nodes()), "if_0 子节点应生成")
        _assert_constrains(self, graph, 'packet.c', ['packet.addr', 'packet.en'])

    def test_constraint_dist(self):
        """[Golden] dist 分布约束

        RTL: constraint c { addr dist {0:=1, 1:=2}; }

        预期:
        - ConstraintDeclaration 存在
        - [iter_065 行为] c CONSTRAINS → addr (dist 表达式约束 addr)
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c { addr dist {0:=1, 1:=2}; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)

        # [iter_065] 行为断言: 约束块 → addr (dist 的 left)
        graph = _build_graph(source)
        self.assertIn('packet.c', list(graph.nodes()), "约束块节点应生成")
        _assert_constrains(self, graph, 'packet.c', ['packet.addr'])

    def test_constraint_solve_before(self):
        """[Golden] solve before 求解顺序

        RTL: constraint c { solve addr before data; }

        预期:
        - ConstraintDeclaration 存在
        - [iter_065 解释性保留] solve addr before data 是**求解顺序声明**
          (约束求解器中谁先求谁后求), 不是值约束。提取器合理地**不**建模
          到变量的 CONSTRAINS 边, 仅生成 solve_0 子节点 (block → solve_0)。
          行为金标准 (CONSTRAINS 到变量) 在此不适用, 保留 AST 断言。
        """
        source = '''class packet;
    rand bit [7:0] addr, data;
    constraint c { solve addr before data; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)

        # [iter_065] 仅验证 AST: 约束块节点 + solve_0 子节点
        # (无 CONSTRAINS 到变量 — 这是设计选择, 不是工具缺口)
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet.c', nodes, "约束块节点应生成")
        self.assertIn('packet.c::solve_0', nodes, "solve_0 子节点应生成")
        # 确认不存在到变量的 CONSTRAINS 边 (求解顺序 ≠ 值约束)
        constrains = _edges_of_kind(graph, EdgeKind.CONSTRAINS)
        self.assertNotIn(
            ('packet.c', 'packet.addr'), constrains,
            "solve_before 不应产生到 addr 的 CONSTRAINS 边 (非值约束)",
        )
        self.assertNotIn(
            ('packet.c', 'packet.data'), constrains,
            "solve_before 不应产生到 data 的 CONSTRAINS 边 (非值约束)",
        )

    def test_constraint_unique(self):
        """[Golden] unique 唯一性约束

        RTL: constraint c { unique {a, b, c}; }

        预期:
        - ConstraintDeclaration 存在
        - [iter_065 行为] c CONSTRAINS → a, b, c (unique 约束所有变量)
        """
        source = '''class packet;
    rand bit a, b, c;
    constraint unique_c { unique { a, b, c }; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)

        # [iter_065] 行为断言: 约束块 → unique 内全部变量
        graph = _build_graph(source)
        self.assertIn('packet.unique_c', list(graph.nodes()), "unique 约束块节点应生成")
        _assert_constrains(self, graph, 'packet.unique_c',
                           ['packet.a', 'packet.b', 'packet.c'])

    def test_constraint_loop(self):
        """[Golden] loop 循环约束

        RTL: constraint c { foreach (arr[i]) arr[i] > 0; }

        预期:
        - ConstraintDeclaration 存在
        - [iter_065 行为] c CONSTRAINS → arr (foreach 约束数组 arr)
        """
        source = '''class packet;
    bit [7:0] arr[4];
    constraint c { foreach (arr[i]) arr[i] > 0; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)

        self.assertEqual(len(classes), 1)

        # [iter_065] 行为断言: 约束块 → foreach 的数组
        graph = _build_graph(source)
        self.assertIn('packet.c', list(graph.nodes()), "约束块节点应生成")
        self.assertIn('packet.c::foreach_0', list(graph.nodes()), "foreach_0 子节点应生成")
        _assert_constrains(self, graph, 'packet.c', ['packet.arr'])


if __name__ == '__main__':
    unittest.main()
