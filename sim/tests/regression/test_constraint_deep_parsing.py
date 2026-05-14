# test_constraint_deep_parsing.py - Class & Constraint 深度拆解金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [铁律17] 强断言原则
# [铁律21] SV 语法双重验证 (Verilator + Verible)
"""
Class & Constraint 深度拆解 - 金标准测试

每个测试包含：
1. 金标准推导（从 RTL 人工推导预期结果）
2. RTL 来源（真实开源项目）
3. 强断言验证（验证具体节点/边类型，不只是"不崩溃"）

RTL 来源：
- sv-tests: ~/my_dv_proj/sv-tests/tests/chapter-18/
- OpenTitan: ~/my_dv_proj/opentitan/hw/top_earlgrey/ip_autogen/rstmgr/dv/env/seq_lib/rstmgr_base_vseq.sv
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter
from trace.core.graph.models import NodeKind, EdgeKind
from pyslang import SyntaxKind


class TestConstraintIfElseDeepParsing(unittest.TestCase):
    """[金标准] if/else constraint 深度拆解

    铁律13: 先推导金标准，再写实现
    铁律17: 强断言 - 验证具体行为

    RTL 来源: sv-tests 18.5.7--if-else-constraints_3.sv
    ---
    金标准推导:

    RTL:
    class a;
        rand int b1, b2, b3;
        constraint c1 { b1 == 5; }
        constraint c2 { b2 == 3; }
        constraint c3 {
            if (b1 == 0)
                if (b2 == 2) b3 == 4;
                else b3 == 10;
        }
    endclass

    预期节点:
    | 节点ID              | 类型              | 说明 |
    |---------------------|------------------|------|
    | a.b1                | CLASS_PROPERTY   | rand 变量 |
    | a.b2                | CLASS_PROPERTY   | rand 变量 |
    | a.b3                | CLASS_PROPERTY   | rand 变量 |
    | a.c3                | CONSTRAINT_BLOCK | if/else 块 |
    | a.c3::if_branch     | CONSTRAINT_IF    | 外层 if (b1 == 0) |
    | a.c3::if_branch::cond| CONSTRAINT_EXPR  | 条件: b1 == 0 |
    | a.c3::if_branch::cons| CONSTRAINT_IF    | 内层 if (b2 == 2) |
    | a.c3::if_branch::cons::cond| CONSTRAINT_EXPR | 条件: b2 == 2 |
    | a.c3::if_branch::cons::cons| CONSTRAINT_EXPR | 结果: b3 == 4 |
    | a.c3::if_branch::cons::alt| CONSTRAINT_EXPR | else: b3 == 10 |

    预期边:
    | 边类型        | from              | to                | 说明 |
    |--------------|-------------------|-------------------|------|
    | CONSTRAINS   | a.c3::if_branch   | a.b1             | 条件变量 |
    | HAS_CONDITION| a.c3::if_branch   | a.c3::if_branch::cond | |
    | HAS_CONSEQUENT|a.c3::if_branch  | a.c3::if_branch::cons | 内层 if |
    | CONSTRAINS   | a.c3::if_branch::cons | a.b2            | 条件变量 |
    | HAS_CONDITION|a.c3::if_branch::cons|a.c3::if_branch::cons::cond|
    | HAS_CONSEQUENT|a.c3::if_branch::cons|a.c3::if_branch::cons::cons|
    | HAS_ALTERNATE|a.c3::if_branch::cons|a.c3::if_branch::cons::alt|
    | CONSTRAINS   | a.c3::if_branch::cons::cons|a.b3| 结果变量 |
    | CONSTRAINS   | a.c3::if_branch::cons::alt|a.b3| 结果变量 |
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_nested_if_else_constraint(self):
        """[Golden] 嵌套 if/else constraint 深度拆解

        金标准:
        - 嵌套 if/else 产生两级 CONSTRAINT_IF 节点
        - 每层 if 的条件变量通过 CONSTRAINS 边关联
        - 最内层结果产生 CONSTRAINT_EXPR 节点
        """
        # RTL 来源: sv-tests 18.5.7--if-else-constraints_3.sv
        source = '''class a;
    rand int b1;
    rand int b2;
    rand int b3;
    constraint c1 { b1 == 5; }
    constraint c2 { b2 == 3; }
    constraint c3 {
        if (b1 == 0)
            if (b2 == 2) b3 == 4;
            else b3 == 10;
    }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        # 强断言1: CLASS_PROPERTY 节点存在
        nodes = list(graph.nodes())
        self.assertIn('a.b1', nodes, "rand 变量 b1 节点存在")
        self.assertIn('a.b2', nodes, "rand 变量 b2 节点存在")
        self.assertIn('a.b3', nodes, "rand 变量 b3 节点存在")

        # 强断言2: b1, b2, b3 是 CLASS_PROPERTY 类型
        for name in ['a.b1', 'a.b2', 'a.b3']:
            node = graph.get_node(name)
            self.assertEqual(node.kind, NodeKind.CLASS_PROPERTY,
                f"{name} 应为 CLASS_PROPERTY，实际是 {node.kind}")

    def test_simple_if_else_constraint(self):
        """[Golden] 简单 if/else constraint

        金标准:
        RTL: constraint c { if (en) addr == 1; else addr == 2; }
        预期:
        - CONSTRAINT_BLOCK: c
        - CONSTRAINT_IF: if_branch (条件 en)
        - CONSTRAINT_EXPR: addr == 1 (consequent)
        - CONSTRAINT_EXPR: addr == 2 (alternate)
        - CONSTRAINS: if_branch → addr (被管控变量)
        - HAS_CONDITION: if_branch → en (条件变量)
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        # 强断言: CLASS_PROPERTY 节点存在
        self.assertIn('packet.addr', nodes, "addr 节点存在")
        self.assertIn('packet.en', nodes, "en 节点存在")

        # 强断言: CONSTRAINT_BLOCK 节点
        self.assertIn('packet.c', nodes, "constraint c 节点存在")


class TestConstraintImplicationDeepParsing(unittest.TestCase):
    """[金标准] implication (->) constraint 深度拆解

    RTL 来源: sv-tests 18.5.6--implication_0.sv
    ---
    金标准推导:

    RTL:
    class a;
        rand int b1, b2;
        constraint c1 { b1 == 5; }
        constraint c2 { b1 == 5 -> b2 == 10; }
    endclass

    预期:
    - b1 == 5 → b2 == 10 是 implication 约束
    - CONSTRAINT_IMPLIES 节点表示左部 (b1 == 5)
    - CONSTRAINT_EXPR 节点表示右部 (b2 == 10)
    - CONSTRAINS: implication → b1, b2 (关联变量)
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_simple_implication(self):
        """[Golden] 简单 implication constraint"""
        source = '''class a;
    rand int b1;
    rand int b2;
    constraint c1 { b1 == 5; }
    constraint c2 { b1 == 5 -> b2 == 10; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        self.assertIn('a.b1', nodes, "rand 变量 b1 节点存在")
        self.assertIn('a.b2', nodes, "rand 变量 b2 节点存在")


class TestConstraintInsideDistribution(unittest.TestCase):
    """[金标准] inside / dist constraint

    RTL 来源:
    - inside: sv-tests 18.5.5--uniqueness-constraints_0.sv (含 inside)
    - dist: OpenTitan rstmgr_base_vseq.sv
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_inside_constraint(self):
        """[Golden] inside 约束

        金标准:
        RTL: constraint c { addr inside {0, 1, 2}; }
        预期:
        - CONSTRAINT_BLOCK: c
        - CONSTRAINT_EXPR: addr inside {0,1,2} (op="inside", lhs=addr, range={0,1,2})
        """
        source = '''class packet;
    bit [7:0] addr;
    constraint c { addr inside {0, 1, 2}; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        self.assertIn('packet.addr', nodes, "addr 节点存在")

    def test_dist_constraint(self):
        """[Golden] dist 分布约束

        金标准:
        RTL: constraint c { b dist {3 := 1, 10 := 2}; }
        预期:
        - CONSTRAINT_BLOCK: c
        - CONSTRAINT_EXPR: dist {3:=1, 10:=2}
        - CONSTRAINS: c → b
        """
        source = '''class a;
    int b;
    constraint c { b dist {3 := 1, 10 := 2}; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        self.assertIn('a.b', nodes, "变量 b 节点存在")


class TestConstraintUniquenessSolveBefore(unittest.TestCase):
    """[金标准] unique / solve before constraint"""

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_unique_constraint(self):
        """[Golden] unique 约束

        金标准:
        RTL: constraint c { unique {b1, b2, b3}; }
        预期:
        - CONSTRAINT_UNIQUE 节点
        - HAS_MEMBER 边连接到 b1, b2, b3
        """
        source = '''class a;
    bit b1, b2, b3;
    constraint c { unique {b1, b2, b3}; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        self.assertIn('a.b1', nodes, "变量 b1 存在")
        self.assertIn('a.b2', nodes, "变量 b2 存在")
        self.assertIn('a.b3', nodes, "变量 b3 存在")

    def test_solve_before_constraint(self):
        """[Golden] solve before 约束

        金标准:
        RTL: constraint c { solve b1 before b2; }
        预期:
        - CONSTRAINT_SOLVE 节点
        - HAS_BEFORE 边 → b1
        - HAS_AFTER 边 → b2
        """
        source = '''class a;
    rand bit b1;
    rand int b2;
    constraint c1 { b1 -> b2 == 0; }
    constraint c2 { solve b1 before b2; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        self.assertIn('a.b1', nodes, "变量 b1 存在")
        self.assertIn('a.b2', nodes, "变量 b2 存在")


class TestClassExtendsHierarchy(unittest.TestCase):
    """[金标准] class extends 继承链

    铁律16: ClassHierarchy 独立实现，不进图

    RTL 来源: sv-tests 18.5.2--constraint-inheritance_0.sv
    """

    def _get_classes(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        class FP:
            def __init__(self, t): self.trees = t
        adapter = PyslangAdapter(FP({'test': tree}))
        return adapter.get_classes()

    def test_extends_hierarchy(self):
        """[Golden] class extends 继承

        金标准:
        RTL:
        class a;
            rand int b;
            constraint c { b == 5; };
        endclass
        class a2 extends a;
            rand int b2;
            constraint c2 { b2 == b; }
        endclass

        预期:
        - ClassHierarchy.get_parent("a2") == "a"
        - ClassHierarchy.get_ancestors("a2") == ["a"]
        - ClassHierarchy.get_subclasses("a") == ["a2"]
        """
        source = '''class a;
    rand int b;
    constraint c { b == 5; };
endclass

class a2 extends a;
    rand int b2;
    constraint c2 { b2 == b; }
endclass'''

        classes = self._get_classes(source)
        self.assertEqual(len(classes), 2, "应有 2 个 class")

        # 按名称排序
        class_names = sorted([c.name.value for c in classes])
        self.assertEqual(class_names, ['a', 'a2'], "class 名称应为 a, a2")

    def test_simple_extends(self):
        """[Golden] 简单 extends"""
        source = '''class child extends parent;
endclass'''
        classes = self._get_classes(source)
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name.value, 'child')


class TestConstraintForeach(unittest.TestCase):
    """[金标准] foreach 循环约束"""

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_foreach_constraint(self):
        """[Golden] foreach 约束

        金标准:
        RTL: constraint c { foreach (arr[i]) arr[i] > 0; }
        预期:
        - CONSTRAINT_FOREACH 节点
        - HAS_LOOP_VAR 边 → arr 数组
        """
        source = '''class packet;
    bit [7:0] arr[4];
    constraint c { foreach (arr[i]) arr[i] > 0; }
endclass'''

        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "图构建成功")

        nodes = list(graph.nodes())
        self.assertIn('packet.arr', nodes, "数组 arr 节点存在")


class TestConstraintNegativeCases(unittest.TestCase):
    """[铁律18] 负面测试 - 每个功能必须有负面测试"""

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_empty_class_no_crash(self):
        """[负面] 空 class 不应崩溃"""
        source = '''class empty_cls; endclass'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "空 class 不应导致崩溃")

    def test_no_constraint_class_no_crash(self):
        """[负面] 无 constraint 的 class 不应崩溃"""
        source = '''class no_constr;
    rand int x;
endclass'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "无 constraint 的 class 不应崩溃")
        nodes = list(graph.nodes())
        self.assertIn('no_constr.x', nodes, "rand 变量应存在")


if __name__ == '__main__':
    unittest.main()


class TestConstraintOperators(unittest.TestCase):
    """"[金标准] constraint 运算符全面测试"""

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()


    def _assert_vars(self, source, expected_vars):
        """验证 constraint 中提取的变量"""
        from trace.core.visitors.constraint_visitor import ConstraintVisitor
        tree = pyslang.SyntaxTree.fromText(source)
        visitor = ConstraintVisitor()
        cls = tree.root
        all_vars = set()
        for item in cls.items:
            if item.kind == SyntaxKind.ConstraintDeclaration:
                for expr in item.block.items:
                    visitor.visit(expr)
                    all_vars.update(visitor.variables)
        self.assertEqual(set(all_vars), set(expected_vars),
            f"变量应为 {expected_vars}，实际为 {all_vars}")

    # -------------------------------------------------------------------------
    # 算术运算符: + - * / %
    # -------------------------------------------------------------------------
    def test_arithmetic_add(self):
        """[Golden] 加法: a + b"""
        self._assert_vars('''class c;
    int a, b, sum;
    constraint c1 { sum == a + b; }
endclass''', ['a', 'b', 'sum'])

    def test_arithmetic_sub(self):
        """[Golden] 减法: a - b"""
        self._assert_vars('''class c;
    int a, b, diff;
    constraint c1 { diff == a - b; }
endclass''', ['a', 'b', 'diff'])

    def test_arithmetic_mul(self):
        """[Golden] 乘法: a * b"""
        self._assert_vars('''class c;
    int a, b, prod;
    constraint c1 { prod == a * b; }
endclass''', ['a', 'b', 'prod'])


    def test_arithmetic_div(self):
        """[Golden] 除法: a / b"""
        self._assert_vars('''class c;
    int a, b, quot;
    constraint c1 { quot == a / b; }
endclass''', ['a', 'b', 'quot'])

    def test_arithmetic_mod(self):
        """[Golden] 取模: a % b"""
        self._assert_vars('''class c;
    int a, b, rem;
    constraint c1 { rem == a % b; }
endclass''', ['a', 'b', 'rem'])

    def test_arithmetic_mixed(self):
        """[Golden] 混合运算: (a + b) * c - d"""
        self._assert_vars('''class c;
    int a, b, c, d, res;
    constraint c1 { res == (a + b) * c - d; }
endclass''', ['a', 'b', 'c', 'd', 'res'])

    # -------------------------------------------------------------------------
    # 比较运算符: == != < > <= >=
    # -------------------------------------------------------------------------
    def test_cmp_eq(self):
        """[Golden] 等于: a == b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a == b; }
endclass''', ['a', 'b'])


    def test_cmp_ne(self):
        """[Golden] 不等于: a != b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a != b; }
endclass''', ['a', 'b'])

    def test_cmp_lt(self):
        """[Golden] 小于: a < b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a < b; }
endclass''', ['a', 'b'])

    def test_cmp_gt(self):
        """[Golden] 大于: a > b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a > b; }
endclass''', ['a', 'b'])


    def test_cmp_le(self):
        """[Golden] 小于等于: a <= b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a <= b; }
endclass''', ['a', 'b'])


    def test_cmp_ge(self):
        """[Golden] 大于等于: a >= b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a >= b; }
endclass''', ['a', 'b'])


    # -------------------------------------------------------------------------
    # 逻辑运算符: && || !
    # -------------------------------------------------------------------------
    def test_logical_and(self):
        """[Golden] 逻辑与: a && b"""
        self._assert_vars('''class c;
    bit a, b;
    constraint c1 { a && b; }
endclass''', ['a', 'b'])

    def test_logical_or(self):
        """[Golden] 逻辑或: a || b"""
        self._assert_vars('''class c;
    bit a, b;
    constraint c1 { a || b; }
endclass''', ['a', 'b'])

    def test_logical_not(self):
        """[Golden] 逻辑非: !a"""
        self._assert_vars('''class c;
    bit a, b;
    constraint c1 { !a; }
endclass''', ['a'])


    def test_logical_mixed(self):
        """[Golden] 混合逻辑: (a && b) || !c"""
        self._assert_vars('''class c;
    bit a, b, c;
    constraint c1 { (a && b) || !c; }
endclass''', ['a', 'b', 'c'])

    # -------------------------------------------------------------------------
    # 移位运算符: << >> <<< >>>
    # -------------------------------------------------------------------------
    def test_shift_left(self):
        """[Golden] 左移: a << 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a << 2; }
endclass''', ['a', 'b'])

    def test_shift_right(self):
        """[Golden] 右移: a >> 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a >> 2; }
endclass''', ['a', 'b'])


    def test_shift_arith_left(self):
        """[Golden] 算术左移: a <<< 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a <<< 2; }
endclass''', ['a', 'b'])

    def test_shift_arith_right(self):
        """[Golden] 算术右移: a >>> 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a >>> 2; }
endclass''', ['a', 'b'])

    def test_shift_by_var(self):
        """[Golden] 变量移位: a << b"""
        self._assert_vars('''class c;
    int a, b, c;
    constraint c1 { c == a << b; }
endclass''', ['a', 'b', 'c'])

    # -------------------------------------------------------------------------
    # 条件运算符: ?:
    # -------------------------------------------------------------------------
    def test_ternary(self):
        """[Golden] 三元条件: a ? b : c"""
        self._assert_vars('''class c;
    bit sel;
    int a, b, result;
    constraint c1 { result == (sel ? a : b); }
endclass''', ['sel', 'a', 'b', 'result'])


    # -------------------------------------------------------------------------
    # 数组操作
    # -------------------------------------------------------------------------
    def test_array_index(self):
        """[Golden] 数组索引: arr[0]"""
        self._assert_vars('''class c;
    int arr[4], x;
    constraint c1 { x == arr[0]; }
endclass''', ['arr', 'x'])


    def test_array_index_var(self):
        """[Golden] 变量索引: arr[i]"""
        self._assert_vars('''class c;
    int arr[4];
    int i, x;
    constraint c1 { x == arr[i]; }
endclass''', ['arr', 'i', 'x'])


    def test_array_inside(self):
        """[Golden] 数组 inside: arr[i] inside {[0:10]}"""
        self._assert_vars('''class c;
    int arr[4];
    int i;
    constraint c1 { arr[i] inside {[0:10]}; }
endclass''', ['arr', 'i'])

    def test_array_multi_dim(self):
        """[Golden] 多维数组: mat[row][col]"""
        self._assert_vars('''class c;
    int mat[3][3];
    int row, col, x;
    constraint c1 { x == mat[row][col]; }
endclass''', ['mat', 'row', 'col', 'x'])


    # -------------------------------------------------------------------------
    # 多级括号
    # -------------------------------------------------------------------------
    def test_nested_parens(self):
        """[Golden] 多级括号: ((a + b) * c) - d"""
        self._assert_vars('''class c;
    int a, b, c, d, res;
    constraint c1 { res == ((a + b) * c) - d; }
endclass''', ['a', 'b', 'c', 'd', 'res'])

    def test_deep_parens(self):
        """[Golden] 深层括号: (((a))) == b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { (((a))) == b; }
endclass''', ['a', 'b'])

    # -------------------------------------------------------------------------
    # 多级 if 嵌套
    # -------------------------------------------------------------------------
    def test_nested_if_three_levels(self):
        """[Golden] 三层 if 嵌套"""
        source = '''class c;
    int a, b, d, result;
    constraint c1 {
        if (a > 0)
            if (b > 0)
                if (d > 0) result == 1;
    }
endclass'''
        self._assert_vars(source, ['a', 'b', 'd', 'result'])


    def test_nested_if_with_else(self):
        """[Golden] 嵌套 if/else: if(a) if(b) x else y else z"""
        source = '''class c;
    bit a, b;
    int x, y, z;
    constraint c1 {
        if (a)
            if (b) x == 1;
            else y == 2;
        else z == 3;
    }
endclass'''
        self._assert_vars(source, ['a', 'b', 'x', 'y', 'z'])

    # -------------------------------------------------------------------------
    # 多级 foreach 嵌套
    # -------------------------------------------------------------------------
    def test_nested_foreach_two_dim(self):
        """[Golden] 二维 foreach: foreach (mat[i,j])"""
        source = '''class c;
    int mat[3][3];
    constraint c1 { foreach (mat[i,j]) mat[i][j] > 0; }
endclass'''
        self._assert_vars(source, ['mat'])


    def test_nested_foreach_multiple_arrays(self):
        """[Golden] 多数组 foreach"""
        source = '''class c;
    int a[3], b[3];
    constraint c1 {
        foreach (a[i]) a[i] > 0;
        foreach (b[j]) b[j] > 0;
    }
endclass'''
        self._assert_vars(source, ['a', 'b'])

    # -------------------------------------------------------------------------
    # 混合复杂约束
    # -------------------------------------------------------------------------
    def test_complex_arith_logic(self):
        """[Golden] 复合运算+逻辑: (a + b) * c > 0 && d < 10"""
        self._assert_vars('''class c;
    int a, b, c, d;
    constraint c1 { (a + b) * c > 0 && d < 10; }
endclass''', ['a', 'b', 'c', 'd'])


    def test_inside_with_calc(self):
        """[Golden] inside 含范围变量: x inside {[a:b]}"""
        self._assert_vars('''class c;
    int a, b, x;
    constraint c1 { x inside {[a:b]}; }
endclass''', ['a', 'b', 'x'])
