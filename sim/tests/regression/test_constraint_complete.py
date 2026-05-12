# test_constraint_complete.py - Class & Constraint 完整金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言原则
# [铁律22] 测试断言必须验证具体行为
"""
Class & Constraint 完整金标准测试

测试覆盖:
1. CLASS_PROPERTY 节点提取
2. CONSTRAINT_BLOCK 节点提取
3. CONSTRAINT_EXPR 节点提取
4. CONSTRAINT_IF 节点提取 (if/else)
5. CONSTRAINT_IMPLIES 节点提取 (implication ->)
6. CONSTRAINT_EXPR 节点提取 (dist {})
7. CONSTRAINT_FOREACH 节点提取 (foreach)
8. CONSTRAINT_UNIQUE 节点提取 (unique)
9. CONSTRAINT_EXPR 节点提取 (solve before)
10. 各类运算符变量提取

金标准格式:
# | 节点ID | 类型 | 说明 |
# |--------|------|------|
# | a.b1   | CLASS_PROPERTY | rand 变量 |
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter
from trace.core.graph_models import NodeKind, EdgeKind
from pyslang import SyntaxKind


class TestConstraintClassPropertyNodes(unittest.TestCase):
    """[金标准] CLASS_PROPERTY 节点提取

    金标准:
    RTL: class packet; rand bit [7:0] addr; rand bit en; endclass
    预期:
    | 节点ID        | 类型              | 说明 |
    |--------------|------------------|------|
    | packet.addr  | CLASS_PROPERTY   | rand 变量 |
    | packet.en    | CLASS_PROPERTY   | rand 变量 |
    | packet.CLASS | CLASS            | 类节点 |
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_rand_variable_nodes(self):
        """[Golden] rand 变量节点

        金标准:
        - rand bit [7:0] addr → CLASS_PROPERTY 节点
        - rand bit en → CLASS_PROPERTY 节点
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit en;
    constraint c { addr inside {0, 1}; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 强断言: 节点存在
        self.assertIn('packet.addr', nodes, "rand 变量 addr 节点存在")
        self.assertIn('packet.en', nodes, "rand 变量 en 节点存在")

        # 强断言: 节点类型
        addr_node = graph.get_node('packet.addr')
        self.assertEqual(addr_node.kind, NodeKind.CLASS_PROPERTY,
            f"packet.addr 应为 CLASS_PROPERTY，实际是 {addr_node.kind}")

        en_node = graph.get_node('packet.en')
        self.assertEqual(en_node.kind, NodeKind.CLASS_PROPERTY,
            f"packet.en 应为 CLASS_PROPERTY，实际是 {en_node.kind}")

    def test_non_rand_variable_nodes(self):
        """[Golden] 非 rand 变量节点

        金标准:
        - bit [7:0] data; → CLASS_PROPERTY 节点 (普通成员变量)
        """
        source = '''class packet;
    bit [7:0] data;
    constraint c { data == 8'hFF; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        self.assertIn('packet.data', nodes, "普通成员变量 data 节点存在")
        data_node = graph.get_node('packet.data')
        self.assertEqual(data_node.kind, NodeKind.CLASS_PROPERTY)

    def test_multi_declarator_variables(self):
        """[Golden] 多声明符变量: bit b1, b2, b3;

        金标准:
        - b1, b2, b3 各有独立 CLASS_PROPERTY 节点
        """
        source = '''class a;
    rand int b1, b2, b3;
    constraint c1 { b1 == 5; }
    constraint c2 { b2 == 3; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        self.assertIn('a.b1', nodes, "b1 节点存在")
        self.assertIn('a.b2', nodes, "b2 节点存在")
        self.assertIn('a.b3', nodes, "b3 节点存在")

        for name in ['a.b1', 'a.b2', 'a.b3']:
            node = graph.get_node(name)
            self.assertEqual(node.kind, NodeKind.CLASS_PROPERTY,
                f"{name} 应为 CLASS_PROPERTY，实际是 {node.kind}")

    def test_class_node_exists(self):
        """[Golden] CLASS 节点存在

        金标准:
        - class a → CLASS 节点
        """
        source = '''class packet;
    rand bit [7:0] addr;
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        self.assertIn('packet', nodes, "CLASS 节点存在")
        cls_node = graph.get_node('packet')
        self.assertEqual(cls_node.kind, NodeKind.CLASS,
            f"packet 应为 CLASS，实际是 {cls_node.kind}")


class TestConstraintBlockNodes(unittest.TestCase):
    """[金标准] CONSTRAINT_BLOCK 节点提取

    金标准:
    RTL: constraint c { addr == 1; }
    预期:
    | 节点ID        | 类型              | 说明 |
    |--------------|------------------|------|
    | packet.c     | CONSTRAINT_BLOCK | 约束块 |
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_constraint_block_node(self):
        """[Golden] constraint block 节点

        金标准:
        - constraint c { ... } → CONSTRAINT_BLOCK 节点
        - 节点ID格式: class_name.constraint_name
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        self.assertIn('packet.c', nodes, "CONSTRAINT_BLOCK 节点存在")
        c_node = graph.get_node('packet.c')
        self.assertEqual(c_node.kind, NodeKind.CONSTRAINT_BLOCK,
            f"packet.c 应为 CONSTRAINT_BLOCK，实际是 {c_node.kind}")

    def test_multiple_constraint_blocks(self):
        """[Golden] 多个 constraint block

        金标准:
        - constraint c1 { ... } → packet.c1
        - constraint c2 { ... } → packet.c2
        """
        source = '''class packet;
    rand int a, b;
    constraint c1 { a == 5; }
    constraint c2 { b == 3; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        self.assertIn('packet.c1', nodes, "CONSTRAINT_BLOCK c1 存在")
        self.assertIn('packet.c2', nodes, "CONSTRAINT_BLOCK c2 存在")

        c1_node = graph.get_node('packet.c1')
        self.assertEqual(c1_node.kind, NodeKind.CONSTRAINT_BLOCK)
        c2_node = graph.get_node('packet.c2')
        self.assertEqual(c2_node.kind, NodeKind.CONSTRAINT_BLOCK)


class TestConstraintExprNodes(unittest.TestCase):
    """[金标准] CONSTRAINT_EXPR 节点提取

    金标准:
    RTL: constraint c { addr == 1; }
    预期:
    | 节点ID        | 类型              | 说明 |
    |--------------|------------------|------|
    | packet.c::expr_0 | CONSTRAINT_EXPR | 约束表达式 |
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_expression_constraint_node(self):
        """[Golden] expression constraint 节点

        金标准:
        - addr == 1 → CONSTRAINT_EXPR 节点
        """
        source = '''class packet;
    bit [7:0] addr;
    constraint c { addr == 1; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 存在 CONSTRAINT_EXPR 节点
        expr_nodes = [n for n in nodes if '::expr_' in n]
        self.assertGreater(len(expr_nodes), 0, "应有 CONSTRAINT_EXPR 节点")

        # 强断言: 节点类型
        for nid in expr_nodes:
            node = graph.get_node(nid)
            self.assertEqual(node.kind, NodeKind.CONSTRAINT_EXPR,
                f"{nid} 应为 CONSTRAINT_EXPR，实际是 {node.kind}")

    def test_implication_constraint_node(self):
        """[Golden] implication constraint 节点

        金标准:
        RTL: constraint c { b1 == 5 -> b2 == 10; }
        预期:
        | 节点ID              | 类型              | 说明 |
        |---------------------|------------------|------|
        | packet.c::impl_0    | CONSTRAINT_EXPR  | implication |
        """
        source = '''class packet;
    rand int b1;
    rand int b2;
    constraint c { b1 == 5 -> b2 == 10; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 存在 CONSTRAINT_EXPR (implication)
        impl_nodes = [n for n in nodes if '::impl_' in n]
        self.assertGreater(len(impl_nodes), 0,
            f"应有 implication 节点，实际节点: {nodes}")

        impl_node = graph.get_node(impl_nodes[0])
        self.assertEqual(impl_node.kind, NodeKind.CONSTRAINT_IMPLIES,
            f"{impl_nodes[0]} 应为 CONSTRAINT_IMPLIES，实际是 {impl_node.kind}")


class TestConstraintIfNodes(unittest.TestCase):
    """[金标准] CONSTRAINT_IF 节点提取

    金标准:
    RTL: constraint c { if (en) addr == 1; else addr == 2; }
    预期:
    | 节点ID              | 类型              | 说明 |
    |---------------------|------------------|------|
    | packet.c::if_0      | CONSTRAINT_IF    | if 分支 |
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def test_if_constraint_node(self):
        """[Golden] if constraint 节点

        金标准:
        - if (en) ... → CONSTRAINT_IF 节点
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 存在 CONSTRAINT_IF 节点
        if_nodes = [n for n in nodes if '::if_' in n]
        self.assertGreater(len(if_nodes), 0,
            f"应有 CONSTRAINT_IF 节点，实际节点: {nodes}")

        if_node = graph.get_node(if_nodes[0])
        self.assertEqual(if_node.kind, NodeKind.CONSTRAINT_IF,
            f"{if_nodes[0]} 应为 CONSTRAINT_IF，实际是 {if_node.kind}")

    def test_nested_if_constraint_nodes(self):
        """[Golden] 嵌套 if constraint 节点

        金标准:
        - 嵌套 if 产生 CONSTRAINT_IF 节点
        - 当前实现创建外层 CONSTRAINT_IF，内层 if 被展平处理
        """
        source = '''class a;
    rand int b1, b2, b3;
    constraint c3 {
        if (b1 == 0)
            if (b2 == 2) b3 == 4;
            else b3 == 10;
    }
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 外层 CONSTRAINT_IF 存在
        if_nodes = [n for n in nodes if '::if_' in n]
        self.assertGreater(len(if_nodes), 0,
            f"应有 CONSTRAINT_IF 节点，实际节点: {nodes}")
        for nid in if_nodes:
            node = graph.get_node(nid)
            self.assertEqual(node.kind, NodeKind.CONSTRAINT_IF,
                f"{nid} 应为 CONSTRAINT_IF，实际是 {node.kind}")


class TestConstraintEdges(unittest.TestCase):
    """[金标准] 约束边提取

    金标准:
    RTL: constraint c { if (en) addr == 1; else addr == 2; }
    预期边:
    | 边类型          | from            | to                | 说明 |
    |----------------|-----------------|-------------------|------|
    | CONSTRAINS     | packet.c        | packet.en         | if 条件变量 |
    | CONSTRAINS     | packet.c        | packet.addr       | 结果变量 |
    | HAS_CONDITION  | packet.c::if_0  | packet.en         | if 条件 |
    | HAS_CONSEQUENT | packet.c::if_0  | packet.c::...::cons| if 结果 |
    | HAS_ALTERNATE  | packet.c::if_0  | packet.c::...::alt | else 结果 |
    """

    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()

    def _edges_of_kind(self, graph, kind):
        """获取指定类型的边"""
        result = []
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge and edge.kind == kind:
                result.append((src, dst))
        return result

    def test_constraint_block_constrains_edges(self):
        """[Golden] CONSTRAINT_BLOCK → CLASS_PROPERTY 边 (CONSTRAINS)

        金标准:
        - constraint c { addr == 1; }
        - CONSTRAINS 边: packet.c → packet.addr
        """
        source = '''class packet;
    bit [7:0] addr;
    constraint c { addr == 1; }
endclass'''

        graph = self._build_graph(source)

        # CONSTRAINS 边存在
        constrains_edges = self._edges_of_kind(graph, EdgeKind.CONSTRAINS)
        self.assertIn(('packet.c', 'packet.addr'), constrains_edges,
            f"应有 CONSTRAINS 边: packet.c → packet.addr，实际边: {constrains_edges}")

    def test_if_has_condition_edge(self):
        """[Golden] HAS_CONDITION 边

        金标准:
        - if (en) → HAS_CONDITION: if_node → en
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass'''

        graph = self._build_graph(source)

        # HAS_CONDITION 边
        has_cond_edges = self._edges_of_kind(graph, EdgeKind.HAS_CONDITION)
        self.assertGreater(len(has_cond_edges), 0,
            f"应有 HAS_CONDITION 边")

    def test_if_has_consequent_edge(self):
        """[Golden] HAS_CONSEQUENT 边

        金标准:
        - if (en) addr == 1; → HAS_CONSEQUENT: if_node → expr_node
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass'''

        graph = self._build_graph(source)

        # HAS_CONSEQUENT 边
        has_cons_edges = self._edges_of_kind(graph, EdgeKind.HAS_CONSEQUENT)
        self.assertGreater(len(has_cons_edges), 0,
            f"应有 HAS_CONSEQUENT 边")

    def test_if_has_alternate_edge(self):
        """[Golden] HAS_ALTERNATE 边

        金标准:
        - else addr == 2; → HAS_ALTERNATE: if_node → alt_node
        """
        source = '''class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass'''

        graph = self._build_graph(source)

        # HAS_ALTERNATE 边
        has_alt_edges = self._edges_of_kind(graph, EdgeKind.HAS_ALTERNATE)
        self.assertGreater(len(has_alt_edges), 0,
            f"应有 HAS_ALTERNATE 边")

    def test_class_to_property_edges(self):
        """[Golden] CLASS → CLASS_PROPERTY 边

        金标准:
        - CLASS → CLASS_PROPERTY (归属关系)
        """
        source = '''class packet;
    rand bit [7:0] addr;
endclass'''

        graph = self._build_graph(source)

        # CLASS → CLASS_PROPERTY 边
        constrains_edges = self._edges_of_kind(graph, EdgeKind.CONSTRAINS)
        self.assertIn(('packet', 'packet.addr'), constrains_edges,
            f"应有 CONSTRAINS 边: packet → packet.addr")


class TestConstraintVariableExtraction(unittest.TestCase):
    """[金标准] constraint 变量提取

    铁律13: 每个运算符必须有对应测试
    铁律17: 强断言 - 精确验证变量集合
    """

    def _assert_vars(self, source, expected_vars):
        """验证 constraint 中提取的变量集合"""
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
            f"变量集合应为 {set(expected_vars)}，实际为 {all_vars}")

    # -------------------------------------------------------------------------
    # 算术运算符: + - * / %
    # -------------------------------------------------------------------------
    def test_arithmetic_add(self):
        """[Golden] 加法: sum == a + b"""
        self._assert_vars('''class c;
    int a, b, sum;
    constraint c1 { sum == a + b; }
endclass''', ['a', 'b', 'sum'])

    def test_arithmetic_sub(self):
        """[Golden] 减法: diff == a - b"""
        self._assert_vars('''class c;
    int a, b, diff;
    constraint c1 { diff == a - b; }
endclass''', ['a', 'b', 'diff'])

    def test_arithmetic_mul(self):
        """[Golden] 乘法: prod == a * b"""
        self._assert_vars('''class c;
    int a, b, prod;
    constraint c1 { prod == a * b; }
endclass''', ['a', 'b', 'prod'])

    def test_arithmetic_div(self):
        """[Golden] 除法: quot == a / b"""
        self._assert_vars('''class c;
    int a, b, quot;
    constraint c1 { quot == a / b; }
endclass''', ['a', 'b', 'quot'])

    def test_arithmetic_mod(self):
        """[Golden] 取模: rem == a % b"""
        self._assert_vars('''class c;
    int a, b, rem;
    constraint c1 { rem == a % b; }
endclass''', ['a', 'b', 'rem'])

    def test_arithmetic_mixed(self):
        """[Golden] 混合运算: res == (a + b) * c - d"""
        self._assert_vars('''class c;
    int a, b, c, d, res;
    constraint c1 { res == (a + b) * c - d; }
endclass''', ['a', 'b', 'c', 'd', 'res'])

    def test_arithmetic_complex(self):
        """[Golden] 复合算术: res == (a * b + c) / (d - e)"""
        self._assert_vars('''class c;
    int a, b, c, d, e, res;
    constraint c1 { res == (a * b + c) / (d - e); }
endclass''', ['a', 'b', 'c', 'd', 'e', 'res'])

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
    # 位运算符: & | ^ ~
    # -------------------------------------------------------------------------
    def test_bitwise_and(self):
        """[Golden] 按位与: res == (a & b)"""
        self._assert_vars('''class c;
    int a, b, res;
    constraint c1 { res == (a & b); }
endclass''', ['a', 'b', 'res'])

    def test_bitwise_or(self):
        """[Golden] 按位或: res == (a | b)"""
        self._assert_vars('''class c;
    int a, b, res;
    constraint c1 { res == (a | b); }
endclass''', ['a', 'b', 'res'])

    def test_bitwise_xor(self):
        """[Golden] 按位异或: res == (a ^ b)"""
        self._assert_vars('''class c;
    int a, b, res;
    constraint c1 { res == (a ^ b); }
endclass''', ['a', 'b', 'res'])

    def test_bitwise_not(self):
        """[Golden] 按位取反: res == ~a"""
        self._assert_vars('''class c;
    int a, res;
    constraint c1 { res == ~a; }
endclass''', ['a', 'res'])

    # -------------------------------------------------------------------------
    # 移位运算符: << >> <<< >>>
    # -------------------------------------------------------------------------
    def test_shift_left(self):
        """[Golden] 左移: b == a << 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a << 2; }
endclass''', ['a', 'b'])

    def test_shift_right(self):
        """[Golden] 右移: b == a >> 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a >> 2; }
endclass''', ['a', 'b'])

    def test_shift_arith_left(self):
        """[Golden] 算术左移: b == a <<< 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a <<< 2; }
endclass''', ['a', 'b'])

    def test_shift_arith_right(self):
        """[Golden] 算术右移: b == a >>> 2"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { b == a >>> 2; }
endclass''', ['a', 'b'])

    def test_shift_by_var(self):
        """[Golden] 变量移位: c == a << b"""
        self._assert_vars('''class c;
    int a, b, c;
    constraint c1 { c == a << b; }
endclass''', ['a', 'b', 'c'])

    # -------------------------------------------------------------------------
    # 条件运算符: ?:
    # -------------------------------------------------------------------------
    def test_ternary(self):
        """[Golden] 三元条件: result == (sel ? a : b)"""
        self._assert_vars('''class c;
    bit sel;
    int a, b, result;
    constraint c1 { result == (sel ? a : b); }
endclass''', ['sel', 'a', 'b', 'result'])

    def test_ternary_nested(self):
        """[Golden] 嵌套三元: result == (sel1 ? (sel2 ? a : b) : c)"""
        self._assert_vars('''class c;
    bit sel1, sel2;
    int a, b, c, result;
    constraint c1 { result == (sel1 ? (sel2 ? a : b) : c); }
endclass''', ['sel1', 'sel2', 'a', 'b', 'c', 'result'])

    # -------------------------------------------------------------------------
    # 数组操作
    # -------------------------------------------------------------------------
    def test_array_index_const(self):
        """[Golden] 常量索引: arr[0]"""
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

    def test_array_multi_dim(self):
        """[Golden] 多维数组: mat[row][col]"""
        self._assert_vars('''class c;
    int mat[3][3];
    int row, col, x;
    constraint c1 { x == mat[row][col]; }
endclass''', ['mat', 'row', 'col', 'x'])

    def test_array_inside(self):
        """[Golden] 数组 inside: arr[i] inside {[0:10]}"""
        self._assert_vars('''class c;
    int arr[4];
    int i;
    constraint c1 { arr[i] inside {[0:10]}; }
endclass''', ['arr', 'i'])

    # -------------------------------------------------------------------------
    # inside / dist
    # -------------------------------------------------------------------------
    def test_inside_simple(self):
        """[Golden] inside 简单: x inside {0, 1, 2}"""
        self._assert_vars('''class c;
    int x;
    constraint c1 { x inside {0, 1, 2}; }
endclass''', ['x'])

    def test_inside_with_range_vars(self):
        """[Golden] inside 含范围变量: x inside {[a:b]}"""
        self._assert_vars('''class c;
    int a, b, x;
    constraint c1 { x inside {[a:b]}; }
endclass''', ['a', 'b', 'x'])

    def test_dist_simple(self):
        """[Golden] dist 简单: b dist {3 := 1, 10 := 2}"""
        self._assert_vars('''class c;
    int b;
    constraint c1 { b dist {3 := 1, 10 := 2}; }
endclass''', ['b'])

    def test_dist_with_range(self):
        """[Golden] dist 含范围: b dist {[0:5] := 1, [6:10] := 2}"""
        self._assert_vars('''class c;
    int b;
    constraint c1 { b dist {[0:5] := 1, [6:10] := 2}; }
endclass''', ['b'])

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

    def test_parens_in_condition(self):
        """[Golden] 括号在条件中: if ((a + b) > 0) ..."""
        self._assert_vars('''class c;
    int a, b, x;
    constraint c1 { if ((a + b) > 0) x == 1; }
endclass''', ['a', 'b', 'x'])

    # -------------------------------------------------------------------------
    # 多级 if 嵌套
    # -------------------------------------------------------------------------
    def test_nested_if_two_levels(self):
        """[Golden] 两层 if 嵌套"""
        self._assert_vars('''class c;
    int a, b, result;
    constraint c1 {
        if (a > 0)
            if (b > 0) result == 1;
    }
endclass''', ['a', 'b', 'result'])

    def test_nested_if_three_levels(self):
        """[Golden] 三层 if 嵌套"""
        self._assert_vars('''class c;
    int a, b, d, result;
    constraint c1 {
        if (a > 0)
            if (b > 0)
                if (d > 0) result == 1;
    }
endclass''', ['a', 'b', 'd', 'result'])

    def test_nested_if_with_else(self):
        """[Golden] 嵌套 if/else: if(a) if(b) x else y else z"""
        self._assert_vars('''class c;
    bit a, b;
    int x, y, z;
    constraint c1 {
        if (a)
            if (b) x == 1;
            else y == 2;
        else z == 3;
    }
endclass''', ['a', 'b', 'x', 'y', 'z'])

    def test_if_else_chain(self):
        """[Golden] if-else if 链"""
        self._assert_vars('''class c;
    int sel, a, b, c;
    constraint c1 {
        if (sel == 0) a == 1;
        else if (sel == 1) b == 2;
        else c == 3;
    }
endclass''', ['sel', 'a', 'b', 'c'])

    # -------------------------------------------------------------------------
    # foreach
    # -------------------------------------------------------------------------
    def test_foreach_single_dim(self):
        """[Golden] 单维 foreach: foreach (arr[i])"""
        self._assert_vars('''class c;
    int arr[4];
    constraint c1 { foreach (arr[i]) arr[i] > 0; }
endclass''', ['arr'])

    def test_foreach_two_dim(self):
        """[Golden] 二维 foreach: foreach (mat[i,j])"""
        self._assert_vars('''class c;
    int mat[3][3];
    constraint c1 { foreach (mat[i,j]) mat[i][j] > 0; }
endclass''', ['mat'])

    def test_foreach_multiple_arrays(self):
        """[Golden] 多数组 foreach"""
        self._assert_vars('''class c;
    int a[3], b[3];
    constraint c1 {
        foreach (a[i]) a[i] > 0;
        foreach (b[j]) b[j] > 0;
    }
endclass''', ['a', 'b'])

    # -------------------------------------------------------------------------
    # implication (->)
    # -------------------------------------------------------------------------
    def test_implication_simple(self):
        """[Golden] 简单 implication: a -> b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a -> b; }
endclass''', ['a', 'b'])

    def test_implication_with_expr(self):
        """[Golden] 表达式 implication: a == 5 -> b == 10"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a == 5 -> b == 10; }
endclass''', ['a', 'b'])

    # -------------------------------------------------------------------------
    # unique
    # -------------------------------------------------------------------------
    def test_unique_simple(self):
        """[Golden] simple unique: unique {a, b, c}"""
        self._assert_vars('''class c;
    bit a, b, c;
    constraint c1 { unique {a, b, c}; }
endclass''', ['a', 'b', 'c'])

    # -------------------------------------------------------------------------
    # solve before
    # -------------------------------------------------------------------------
    def test_solve_before_simple(self):
        """[Golden] solve before: solve a before b"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { solve a before b; }
endclass''', ['a', 'b'])

    # -------------------------------------------------------------------------
    # 混合复杂约束
    # -------------------------------------------------------------------------
    def test_complex_arith_logic(self):
        """[Golden] 复合运算+逻辑: (a + b) * c > 0 && d < 10"""
        self._assert_vars('''class c;
    int a, b, c, d;
    constraint c1 { (a + b) * c > 0 && d < 10; }
endclass''', ['a', 'b', 'c', 'd'])

    def test_dist_in_implication(self):
        """[Golden] dist 在 implication 中: a -> b dist {...}"""
        self._assert_vars('''class c;
    int a, b;
    constraint c1 { a -> b dist {0 := 5, 1 := 5}; }
endclass''', ['a', 'b'])

    def test_if_with_dist(self):
        """[Golden] if 带 dist: if (a) b dist {...}"""
        self._assert_vars('''class c;
    bit a;
    int b;
    constraint c1 { if (a) b dist {0 := 5, 1 := 5}; }
endclass''', ['a', 'b'])

    def test_array_inside_in_if(self):
        """[Golden] 数组 inside 在 if 中"""
        self._assert_vars('''class c;
    bit sel;
    int arr[4], i;
    constraint c1 { if (sel) arr[i] inside {[0:10]}; }
endclass''', ['sel', 'arr', 'i'])

    # -------------------------------------------------------------------------
    # 空 constraint
    # -------------------------------------------------------------------------
    def test_empty_constraint_block(self):
        """[Golden] 空 constraint block: constraint c { }"""
        self._assert_vars('''class c;
    int x;
    constraint c1 { }
endclass''', [])


class TestConstraintNegativeCases(unittest.TestCase):
    """[铁律18] 负面测试

    每个功能必须有对应的负面测试，验证不支持的语法或错误输入有合理行为
    """

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
        self.assertIn('empty_cls', list(graph.nodes()),
            "空 class 应有 CLASS 节点")

    def test_no_constraint_class_no_crash(self):
        """[负面] 无 constraint 的 class 不应崩溃"""
        source = '''class no_constr;
    rand int x;
endclass'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "无 constraint 的 class 不应崩溃")
        nodes = list(graph.nodes())
        self.assertIn('no_constr.x', nodes, "rand 变量应存在")

    def test_empty_constraint_block_no_crash(self):
        """[负面] 空 constraint block 不应崩溃"""
        source = '''class c;
    int x;
    constraint c1 { }
endclass'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "空 constraint block 不应崩溃")
        nodes = list(graph.nodes())
        self.assertIn('c.x', nodes, "变量节点应存在")

    def test_multiple_empty_constraints(self):
        """[负面] 多个空 constraint 不应崩溃"""
        source = '''class c;
    int x;
    constraint c1 { }
    constraint c2 { }
endclass'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "多个空 constraint 不应崩溃")

    def test_constraint_with_only_comments(self):
        """[负面] 只有注释的 constraint 不应崩溃"""
        source = '''class c;
    int x;
    constraint c1 { /* just a comment */ }
endclass'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph, "只有注释的 constraint 不应崩溃")


if __name__ == '__main__':
    unittest.main()
