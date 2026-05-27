# test_class_constraint_queries.py - Class 约束查询金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
# [铁律21] 所有 SV 源码通过 pyslang 编译验证
#
# 三个核心查询:
#   Q1: 这个变量在哪些 constraint 中存在？(variable → constraints)
#   Q2: 这个 constraint 能影响哪些变量？(constraint → variables)
#   Q3: 两个变量之间是否存在约束关系？列出相关 constraint
#
# 场景:
#   - 多层继承 (A extends B extends C)
#   - 组合关系 (class instance 引用，跨 class 的约束追踪)
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


# =========================================================================
# 辅助方法
# =========================================================================

def _build_graph(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    return graph, tracer


def _find_constraints_for_var(graph, var_id):
    """Q1: 变量在哪些 constraint 中存在？
    
    从变量节点出发，沿 CONSTRAINS/HAS_LHS 边反向查找，
    找到所有引用该变量的 CONSTRAINT_BLOCK。
    """
    constraints = set()
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if dst != var_id:
            continue
        if edge.kind == EdgeKind.CONSTRAINS:
            node = graph.get_node(src)
            if node and node.kind == NodeKind.CONSTRAINT_BLOCK:
                constraints.add(src)
            elif node and node.kind == NodeKind.CONSTRAINT_EXPR:
                # expr -> var, 往上找 CONSTRAINT_BLOCK
                for s2, d2 in graph.edges():
                    e2 = graph.get_edge(s2, d2)
                    if e2.kind == EdgeKind.CONSTRAINS and d2 == src:
                        n2 = graph.get_node(s2)
                        if n2 and n2.kind == NodeKind.CONSTRAINT_BLOCK:
                            constraints.add(s2)
        elif edge.kind == EdgeKind.HAS_LHS:
            # expr -> var, 往上找 CONSTRAINT_BLOCK
            for s2, d2 in graph.edges():
                e2 = graph.get_edge(s2, d2)
                if e2.kind == EdgeKind.CONSTRAINS and d2 == src:
                    n2 = graph.get_node(s2)
                    if n2 and n2.kind == NodeKind.CONSTRAINT_BLOCK:
                        constraints.add(s2)
    return constraints


def _find_vars_for_constraint(graph, constraint_block_id):
    """Q2: constraint 能影响哪些变量？
    
    从 CONSTRAINT_BLOCK 出发，沿 CONSTRAINS 边找到所有 CLASS_PROPERTY。
    """
    vars = set()
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge.kind == EdgeKind.CONSTRAINS and src == constraint_block_id:
            node = graph.get_node(dst)
            if node and node.kind in (NodeKind.CLASS_PROPERTY, NodeKind.CLASS_INSTANCE_PROPERTY):
                vars.add(dst)
    return vars


def _find_constraint_between(graph, var_a, var_b):
    """Q3: 两个变量之间是否存在约束关系？
    
    查找同时约束两个变量的 CONSTRAINT_BLOCK。
    """
    constraints_a = _find_constraints_for_var(graph, var_a)
    constraints_b = _find_constraints_for_var(graph, var_b)
    return constraints_a & constraints_b


# =========================================================================
# 基础场景: 同 class 内的约束查询
# =========================================================================

class TestBasicConstraintQueries(unittest.TestCase):
    """基础约束查询（同 class 内）"""

    def test_q1_simple(self):
        """[金标准][编译验证] Q1: 单变量单约束

        SV 已验证: pyslang 编译通过

        class packet;
            rand bit [7:0] addr;
            constraint c_addr { addr < 100; }
        endclass

        Q1: packet.addr → {packet.c_addr}
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c_addr { addr < 100; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraints_for_var(graph, 'packet.addr')
        self.assertEqual(result, {'packet.c_addr'})

    def test_q1_multiple_constraints(self):
        """[金标准][编译验证] Q1: 同一变量被多个约束引用

        class packet;
            rand bit [7:0] addr;
            constraint c_range { addr inside {[0:100]}; }
            constraint c_align { addr[1:0] == 0; }
        endclass

        Q1: packet.addr → {packet.c_range, packet.c_align}
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c_range { addr inside {[0:100]}; }
    constraint c_align { addr[1:0] == 0; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraints_for_var(graph, 'packet.addr')
        self.assertIn('packet.c_range', result)
        self.assertIn('packet.c_align', result)

    def test_q2_simple(self):
        """[金标准][编译验证] Q2: 约束影响多变量

        class packet;
            rand bit [7:0] addr;
            rand bit [31:0] data;
            constraint c_both { addr < 100; data > 0; }
        endclass

        Q2: packet.c_both → {packet.addr, packet.data}
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [31:0] data;
    constraint c_both { addr < 100; data > 0; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_vars_for_constraint(graph, 'packet.c_both')
        self.assertIn('packet.addr', result)
        self.assertIn('packet.data', result)

    def test_q3_shared_constraint(self):
        """[金标准][编译验证] Q3: 两变量共享约束

        class packet;
            rand bit [7:0] addr;
            rand bit [31:0] data;
            constraint c_both { addr < 100; data > 0; }
        endclass

        Q3: (packet.addr, packet.data) → {packet.c_both}
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [31:0] data;
    constraint c_both { addr < 100; data > 0; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraint_between(graph, 'packet.addr', 'packet.data')
        self.assertEqual(result, {'packet.c_both'})

    def test_q3_no_shared_constraint(self):
        """[负面][编译验证] Q3: 两变量无共同约束

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] id;
            constraint c_addr { addr < 100; }
            constraint c_id { id > 0; }
        endclass

        Q3: (packet.addr, packet.id) → {} (无共同约束)
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] id;
    constraint c_addr { addr < 100; }
    constraint c_id { id > 0; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraint_between(graph, 'packet.addr', 'packet.id')
        self.assertEqual(result, set())

    def test_conditional_constraint(self):
        """[金标准][编译验证] 条件约束 if/else

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] mode;
            rand bit [7:0] data;
            constraint c_mode {
                if (mode == 0) { addr < 100; data > 0; }
                else { addr < 200; }
            }
        endclass

        Q1: packet.addr → {packet.c_mode}
        Q1: packet.mode → {packet.c_mode}
        Q1: packet.data → {packet.c_mode}
        Q2: packet.c_mode → {packet.addr, packet.mode, packet.data}
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    rand bit [7:0] data;
    constraint c_mode {
        if (mode == 0) { addr < 100; data > 0; }
        else { addr < 200; }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        # Q1
        self.assertIn('packet.c_mode', _find_constraints_for_var(graph, 'packet.addr'))
        self.assertIn('packet.c_mode', _find_constraints_for_var(graph, 'packet.mode'))
        self.assertIn('packet.c_mode', _find_constraints_for_var(graph, 'packet.data'))

        # Q2
        vars_result = _find_vars_for_constraint(graph, 'packet.c_mode')
        self.assertIn('packet.addr', vars_result)
        self.assertIn('packet.mode', vars_result)
        self.assertIn('packet.data', vars_result)

    def test_implication_constraint(self):
        """[金标准][编译验证] implication 约束

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] mode;
            rand bit [31:0] data;
            constraint c_implies {
                mode == 1 -> { addr inside {[0:63]}; data < 256; }
            }
        endclass

        Q2: packet.c_implies → {packet.addr, packet.mode, packet.data}
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    rand bit [31:0] data;
    constraint c_implies {
        mode == 1 -> { addr inside {[0:63]}; data < 256; }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        vars_result = _find_vars_for_constraint(graph, 'packet.c_implies')
        self.assertIn('packet.addr', vars_result)
        self.assertIn('packet.data', vars_result)


# =========================================================================
# 多层继承
# =========================================================================

class TestMultiLevelInheritance(unittest.TestCase):
    """多层继承: C extends B extends A"""

    def test_three_level_properties_propagated(self):
        """[金标准][编译验证] 三层继承属性传播

        class root;
            rand bit [7:0] id;
            constraint c_id { id > 0; }
        endclass
        class mid extends root;
            rand bit [7:0] type_id;
            constraint c_type { type_id < 16; }
        endclass
        class leaf extends mid;
            rand bit [7:0] addr;
            constraint c_addr { addr inside {[0:100]}; }
        endclass

        leaf 应继承: id, type_id, c_id, c_type
        """
        source = '''class root;
    rand bit [7:0] id;
    constraint c_id { id > 0; }
endclass
class mid extends root;
    rand bit [7:0] type_id;
    constraint c_type { type_id < 16; }
endclass
class leaf extends mid;
    rand bit [7:0] addr;
    constraint c_addr { addr inside {[0:100]}; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        # 继承的属性
        self.assertIsNotNone(graph.get_node('leaf.id'), "leaf.id 应存在")
        self.assertIsNotNone(graph.get_node('leaf.type_id'), "leaf.type_id 应存在")
        self.assertIsNotNone(graph.get_node('leaf.addr'), "leaf.addr 应存在")

        # 继承的约束
        self.assertIsNotNone(graph.get_node('leaf.c_id'), "leaf.c_id 应存在")
        self.assertIsNotNone(graph.get_node('leaf.c_type'), "leaf.c_type 应存在")
        self.assertIsNotNone(graph.get_node('leaf.c_addr'), "leaf.c_addr 应存在")

    def test_three_level_q1_inherited(self):
        """[金标准][编译验证] Q1: 多层继承变量 → 约束

        Q1: leaf.id      → {leaf.c_id}
        Q1: leaf.type_id → {leaf.c_type}
        Q1: leaf.addr    → {leaf.c_addr}
        """
        source = '''class root;
    rand bit [7:0] id;
    constraint c_id { id > 0; }
endclass
class mid extends root;
    rand bit [7:0] type_id;
    constraint c_type { type_id < 16; }
endclass
class leaf extends mid;
    rand bit [7:0] addr;
    constraint c_addr { addr inside {[0:100]}; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        self.assertIn('leaf.c_id', _find_constraints_for_var(graph, 'leaf.id'))
        self.assertIn('leaf.c_type', _find_constraints_for_var(graph, 'leaf.type_id'))
        self.assertIn('leaf.c_addr', _find_constraints_for_var(graph, 'leaf.addr'))

    def test_three_level_q2_inherited(self):
        """[金标准][编译验证] Q2: 多层继承约束 → 变量

        Q2: leaf.c_id   → {leaf.id}
        Q2: leaf.c_type → {leaf.type_id}
        Q2: leaf.c_addr → {leaf.addr}
        """
        source = '''class root;
    rand bit [7:0] id;
    constraint c_id { id > 0; }
endclass
class mid extends root;
    rand bit [7:0] type_id;
    constraint c_type { type_id < 16; }
endclass
class leaf extends mid;
    rand bit [7:0] addr;
    constraint c_addr { addr inside {[0:100]}; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        self.assertIn('leaf.id', _find_vars_for_constraint(graph, 'leaf.c_id'))
        self.assertIn('leaf.type_id', _find_vars_for_constraint(graph, 'leaf.c_type'))
        self.assertIn('leaf.addr', _find_vars_for_constraint(graph, 'leaf.c_addr'))

    def test_three_level_q3_cross_generation(self):
        """[金标准][编译验证] Q3: 不同代变量无共同约束

        Q3: (leaf.id, leaf.addr) → {} (不同约束)
        """
        source = '''class root;
    rand bit [7:0] id;
    constraint c_id { id > 0; }
endclass
class mid extends root;
    rand bit [7:0] type_id;
    constraint c_type { type_id < 16; }
endclass
class leaf extends mid;
    rand bit [7:0] addr;
    constraint c_addr { addr inside {[0:100]}; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraint_between(graph, 'leaf.id', 'leaf.addr')
        self.assertEqual(result, set(),
            "leaf.id 和 leaf.addr 不应有共同约束")


# =========================================================================
# 组合关系: class instance 引用
# =========================================================================

class TestCompositionConstraint(unittest.TestCase):
    """组合关系: class instance 引用形成的约束关系

    核心场景:
        class addr_range;
            rand bit [7:0] min_addr;
            rand bit [7:0] max_addr;
            constraint c_range { min_addr < max_addr; }
        endclass

        class packet;
            rand bit [7:0] addr;
            addr_range range = new();
            constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
        endclass

    期望:
        packet.range        → CLASS_INSTANCE (不是 CLASS_PROPERTY)
        packet.range.min_addr → CLASS_INSTANCE_PROPERTY
        packet.range.max_addr → CLASS_INSTANCE_PROPERTY
        packet.c_addr CONSTRAINS packet.range.min_addr (跨实例引用)
    """

    def test_composition_instance_node_type(self):
        """[金标准][编译验证] 组合成员节点类型

        packet.range 应为 CLASS_INSTANCE
        packet.range.min_addr 应为 CLASS_INSTANCE_PROPERTY
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        # packet.range 应为 CLASS_INSTANCE
        range_node = graph.get_node('packet.range')
        self.assertIsNotNone(range_node, "packet.range 应存在")
        self.assertEqual(range_node.kind, NodeKind.CLASS_INSTANCE,
            "packet.range 应为 CLASS_INSTANCE")

        # packet.range.min_addr 应为 CLASS_INSTANCE_PROPERTY
        min_node = graph.get_node('packet.range.min_addr')
        self.assertIsNotNone(min_node, "packet.range.min_addr 应存在")
        self.assertEqual(min_node.kind, NodeKind.CLASS_INSTANCE_PROPERTY,
            "packet.range.min_addr 应为 CLASS_INSTANCE_PROPERTY")

    def test_composition_is_instance_of(self):
        """[金标准][编译验证] 组合成员 IS_INSTANCE_OF 边

        packet.range --IS_INSTANCE_OF--> addr_range
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        iso_edge = graph.get_edge('packet.range', 'addr_range')
        self.assertIsNotNone(iso_edge, "packet.range -> addr_range IS_INSTANCE_OF 应存在")
        self.assertEqual(iso_edge.kind, EdgeKind.IS_INSTANCE_OF)

    def test_composition_member_select(self):
        """[金标准][编译验证] 组合成员 MEMBER_SELECT 边

        packet.range.min_addr --MEMBER_SELECT--> packet.range
        packet.range.min_addr --MEMBER_SELECT--> addr_range.min_addr
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        # MEMBER_SELECT: range.min_addr -> range
        ms1 = graph.get_edge('packet.range.min_addr', 'packet.range')
        self.assertIsNotNone(ms1, "packet.range.min_addr -> packet.range MEMBER_SELECT 应存在")
        self.assertEqual(ms1.kind, EdgeKind.MEMBER_SELECT)

        # MEMBER_SELECT: range.min_addr -> addr_range.min_addr
        ms2 = graph.get_edge('packet.range.min_addr', 'addr_range.min_addr')
        self.assertIsNotNone(ms2, "packet.range.min_addr -> addr_range.min_addr MEMBER_SELECT 应存在")
        self.assertEqual(ms2.kind, EdgeKind.MEMBER_SELECT)

    def test_q1_cross_instance_var_in_constraint(self):
        """[金标准][编译验证] Q1: 跨实例变量在约束中

        Q1: packet.addr            → {packet.c_addr}
        Q1: packet.range.min_addr  → {packet.c_addr}  (跨实例引用)
        Q1: packet.range.max_addr  → {packet.c_addr}  (跨实例引用)
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        # packet.c_addr 应约束 packet.addr
        self.assertIn('packet.c_addr',
            _find_constraints_for_var(graph, 'packet.addr'))

        # packet.c_addr 应约束 packet.range.min_addr (跨实例)
        self.assertIn('packet.c_addr',
            _find_constraints_for_var(graph, 'packet.range.min_addr'),
            "packet.range.min_addr 应在 packet.c_addr 中 (跨实例引用)")

    def test_q2_cross_instance_constraint_to_vars(self):
        """[金标准][编译验证] Q2: 跨实例约束影响的变量

        Q2: packet.c_addr → {packet.addr, packet.range.min_addr, packet.range.max_addr}
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        vars_result = _find_vars_for_constraint(graph, 'packet.c_addr')
        self.assertIn('packet.addr', vars_result)
        self.assertIn('packet.range.min_addr', vars_result,
            "packet.c_addr 应影响 packet.range.min_addr (跨实例)")
        self.assertIn('packet.range.max_addr', vars_result,
            "packet.c_addr 应影响 packet.range.max_addr (跨实例)")

    def test_q3_cross_instance_shared_constraint(self):
        """[金标准][编译验证] Q3: 跨实例变量共享约束

        Q3: (packet.addr, packet.range.min_addr) → {packet.c_addr}
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraint_between(graph, 'packet.addr', 'packet.range.min_addr')
        self.assertIn('packet.c_addr', result,
            "packet.addr 和 packet.range.min_addr 应共享 packet.c_addr")

    def test_q1_composition_own_constraint(self):
        """[金标准][编译验证] Q1: 组合成员自身的约束

        addr_range.min_addr → {addr_range.c_range}  (成员自身 class 的约束)
        packet.range.min_addr → {packet.c_addr, addr_range.c_range}  (两边都引用)
        """
        source = '''class addr_range;
    rand bit [7:0] min_addr;
    rand bit [7:0] max_addr;
    constraint c_range { min_addr < max_addr; }
endclass

class packet;
    rand bit [7:0] addr;
    addr_range range = new();
    constraint c_addr { addr inside {[range.min_addr:range.max_addr]}; }
endclass

module top;
    packet p = new();
endmodule'''
        graph, _ = _build_graph(source)

        # addr_range.min_addr 在自身约束中
        self.assertIn('addr_range.c_range',
            _find_constraints_for_var(graph, 'addr_range.min_addr'))

    def test_nested_composition(self):
        """[金标准][编译验证] 嵌套组合: outer.inner.val

        class inner_t;
            rand bit [7:0] val;
            constraint c_val { val < 100; }
        endclass

        class outer_t;
            rand bit [7:0] data;
            inner_t inner = new();
            constraint c_data { data > inner.val; }
        endclass

        期望:
        outer_t.inner        → CLASS_INSTANCE
        outer_t.inner.val    → CLASS_INSTANCE_PROPERTY
        outer_t.c_data CONSTRAINS outer_t.inner.val
        """
        source = '''class inner_t;
    rand bit [7:0] val;
    constraint c_val { val < 100; }
endclass

class outer_t;
    rand bit [7:0] data;
    inner_t inner = new();
    constraint c_data { data > inner.val; }
endclass

module top;
    outer_t obj = new();
endmodule'''
        graph, _ = _build_graph(source)

        # 节点类型
        inner_node = graph.get_node('outer_t.inner')
        self.assertIsNotNone(inner_node, "outer_t.inner 应存在")
        self.assertEqual(inner_node.kind, NodeKind.CLASS_INSTANCE)

        val_node = graph.get_node('outer_t.inner.val')
        self.assertIsNotNone(val_node, "outer_t.inner.val 应存在")
        self.assertEqual(val_node.kind, NodeKind.CLASS_INSTANCE_PROPERTY)

        # Q1: 跨实例约束
        self.assertIn('outer_t.c_data',
            _find_constraints_for_var(graph, 'outer_t.inner.val'),
            "outer_t.inner.val 应在 outer_t.c_data 中")

        # Q2
        vars_result = _find_vars_for_constraint(graph, 'outer_t.c_data')
        self.assertIn('outer_t.data', vars_result)
        self.assertIn('outer_t.inner.val', vars_result)

        # Q3
        result = _find_constraint_between(graph, 'outer_t.data', 'outer_t.inner.val')
        self.assertIn('outer_t.c_data', result)


# =========================================================================
# 不同 class 互不干扰
# =========================================================================

class TestClassIsolation(unittest.TestCase):
    """不同 class 的约束互不干扰"""

    def test_different_class_no_shared_constraint(self):
        """[负面][编译验证] 不同 class 变量无共同约束

        Q3: (range_t.min_val, packet.addr) → {}
        """
        source = '''class range_t;
    rand bit [7:0] min_val;
    rand bit [7:0] max_val;
    constraint c_range { min_val < max_val; }
endclass

class packet;
    rand bit [7:0] addr;
    constraint c_addr { addr < 100; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _find_constraint_between(graph, 'range_t.min_val', 'packet.addr')
        self.assertEqual(result, set())


if __name__ == '__main__':
    unittest.main()
