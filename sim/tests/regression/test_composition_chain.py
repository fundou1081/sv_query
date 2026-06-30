"""
test_composition_chain.py - 组合链 (has-a) 金标准测试

[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律18] 负面测试原则

设计:
  class inner { rand int x; }
  class outer { inner my_inner; rand int y; }

预期 IS_INSTANCE_OF 边:
  outer.my_inner -> inner (IS_INSTANCE_OF)

图表:
  outer -> outer.my_inner (CONSTRAINS)
  outer.my_inner -> inner (IS_INSTANCE_OF)
  outer -> outer.y (CONSTRAINS)
  inner -> inner.x (CONSTRAINS)
"""

import unittest
import sys
sys.path.insert(0, 'src')

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind, NodeKind
import pyslang


class TestCompositionChainBasic(unittest.TestCase):
    """基本组合关系测试"""

    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()

    def test_single_composition(self):
        """基本组合: outer.my_inner 引用 inner"""
        source = '''class inner;
    rand int x;
endclass

class outer;
    inner my_inner;
endclass'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())
        edges = list(graph.edges())

        # 金标准节点
        self.assertIn('inner', nodes, "应有 inner CLASS 节点")
        self.assertIn('inner.x', nodes, "应有 inner.x CLASS_PROPERTY 节点")
        self.assertIn('outer', nodes, "应有 outer CLASS 节点")
        self.assertIn('outer.my_inner', nodes, "应有 outer.my_inner CLASS_PROPERTY 节点")

        # 金标准边
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        self.assertEqual(len(inst_edges), 1, "应有 1 条 IS_INSTANCE_OF 边")
        self.assertIn(('outer.my_inner', 'inner'), inst_edges,
            "outer.my_inner 应 IS_INSTANCE_OF inner")

    def test_composition_with_other_properties(self):
        """组合 + 普通变量混合"""
        source = '''class inner;
    rand int x;
endclass

class outer;
    inner my_inner;
    rand int y;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())

        # outer.my_inner -> inner (IS_INSTANCE_OF)
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        self.assertEqual(len(inst_edges), 1)
        self.assertIn(('outer.my_inner', 'inner'), inst_edges)

        # y 应该是普通变量（int 类型），没有 IS_INSTANCE_OF
        y_inst_edges = [e for e in inst_edges if e[0] == 'outer.y']
        self.assertEqual(len(y_inst_edges), 0, "int 类型变量不应有 IS_INSTANCE_OF 边")

    def test_array_composition(self):
        """数组类型组合"""
        source = '''class inner;
    rand int x;
endclass

class outer;
    inner items[4];
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())

        # items[0-3] 都引用 inner
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        # items 是数组，每个元素都应引用 inner
        self.assertGreaterEqual(len(inst_edges), 1, "数组组合应有 IS_INSTANCE_OF 边")
        # 验证至少有一个 outer.items[*] -> inner 的边
        has_items_ref = any('items' in src for src, dst in inst_edges)
        self.assertTrue(has_items_ref, "items 数组引用应指向 inner")


class TestCompositionChainNegative(unittest.TestCase):
    """负面测试 - 不应崩溃"""

    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()

    def test_int_type_no_inst_edge(self):
        """int/bit 类型不应有 IS_INSTANCE_OF 边"""
        source = '''class c;
    int addr;
    bit [7:0] data;
    rand bit valid;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())

        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        self.assertEqual(len(inst_edges), 0, "内建类型不应有 IS_INSTANCE_OF 边")

    def test_empty_class_no_crash(self):
        """空 class 不应崩溃"""
        source = '''class empty; endclass'''
        graph = self._build_graph(source)
        self.assertIn('empty', list(graph.nodes()))


class TestCompositionChainMultiLevel(unittest.TestCase):
    """多层嵌套组合"""

    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()

    def test_two_level_composition(self):
        """两层嵌套: outer -> middle -> inner"""
        source = '''class inner;
    rand int x;
endclass

class middle;
    inner child;
endclass

class outer;
    middle parent_child;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())

        # 验证两层 IS_INSTANCE_OF
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertEqual(len(inst_edges), 2, "两层嵌套应有 2 条 IS_INSTANCE_OF 边")

        # 第一层: middle.child -> inner
        self.assertIn(('middle.child', 'inner'), inst_edges,
            "middle.child 应指向 inner")

        # 第二层: outer.parent_child -> middle
        self.assertIn(('outer.parent_child', 'middle'), inst_edges,
            "outer.parent_child 应指向 middle")


class TestCompositionChainComplex(unittest.TestCase):
    """复杂组合场景测试"""

    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()

    def test_three_level_composition(self):
        """三层组合: top -> layer1 -> layer2 -> layer3 (has-a chain)"""
        source = '''class layer3;
    rand int x;
endclass

class layer2;
    layer3 obj;
endclass

class layer1;
    layer2 obj;
endclass

class top;
    layer1 obj;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertEqual(len(inst_edges), 3, "三层 has-a 链应有 3 条 IS_INSTANCE_OF 边")
        self.assertIn(('layer2.obj', 'layer3'), inst_edges)
        self.assertIn(('layer1.obj', 'layer2'), inst_edges)
        self.assertIn(('top.obj', 'layer1'), inst_edges)

    def test_multiple_composition_same_level(self):
        """同一 class 多个成员引用同一类型"""
        source = '''class item;
    rand int val;
endclass

class container;
    item first;
    item second;
    item third;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertEqual(len(inst_edges), 3, "三个 item 成员应有 3 条 IS_INSTANCE_OF 边")
        self.assertIn(('container.first', 'item'), inst_edges)
        self.assertIn(('container.second', 'item'), inst_edges)
        self.assertIn(('container.third', 'item'), inst_edges)

    def test_different_types_composition(self):
        """一个 class 引用多种不同类型"""
        source = '''class type_a;
    rand int a_val;
endclass

class type_b;
    rand int b_val;
endclass

class type_c;
    rand int c_val;
endclass

class container;
    type_a member_a;
    type_b member_b;
    type_c member_c;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertEqual(len(inst_edges), 3, "三种不同类型应有 3 条 IS_INSTANCE_OF 边")
        self.assertIn(('container.member_a', 'type_a'), inst_edges)
        self.assertIn(('container.member_b', 'type_b'), inst_edges)
        self.assertIn(('container.member_c', 'type_c'), inst_edges)

    def test_composition_with_inheritance(self):
        """组合 + 继承混合: extends + has-a"""
        source = '''class base_item;
    rand int base_val;
endclass

class extended_item extends base_item;
    rand int ext_val;
endclass

class container;
    extended_item member;
    rand int own_val;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        nodes = list(graph.nodes())

        # container.member -> extended_item (IS_INSTANCE_OF)
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        self.assertEqual(len(inst_edges), 1)
        self.assertIn(('container.member', 'extended_item'), inst_edges)

        # 验证节点存在
        self.assertIn('container', nodes)
        self.assertIn('container.member', nodes)
        self.assertIn('extended_item', nodes)
        self.assertIn('base_item', nodes)

    def test_composition_with_associative_array(self):
        """关联数组类型组合"""
        source = '''class item;
    rand int val;
endclass

class container;
    item items[string];
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertGreaterEqual(len(inst_edges), 1, "关联数组组合应有 IS_INSTANCE_OF 边")
        has_items_ref = any('items' in src for src, dst in inst_edges)
        self.assertTrue(has_items_ref, "items 关联数组引用应指向 item")

    def test_composition_with_queue(self):
        """队列类型组合"""
        source = '''class item;
    rand int val;
endclass

class container;
    item queue_of_items[$];
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertGreaterEqual(len(inst_edges), 1, "队列组合应有 IS_INSTANCE_OF 边")

    def test_composition_with_constraint(self):
        """组合关系 + 约束交叉测试"""
        source = '''class inner;
    rand int x;
    constraint c1 { x inside {1, 2, 3}; }
endclass

class outer;
    inner my_inner;
    rand int y;
    constraint c2 { y == my_inner.x + 10; }
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        nodes = list(graph.nodes())

        # IS_INSTANCE_OF 边存在
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        self.assertEqual(len(inst_edges), 1)
        self.assertIn(('outer.my_inner', 'inner'), inst_edges)

        # 约束节点存在
        self.assertIn('outer.c2', nodes, "应有 constraint block 节点")
        self.assertIn('inner.c1', nodes, "应有 constraint block 节点")

    def test_composition_with_member_instance(self):
        """组合成员实例"""
        source = '''class item_cfg;
    rand int default_val;
endclass

class container;
    item_cfg cfg;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertGreaterEqual(len(inst_edges), 1, "配置成员应有 IS_INSTANCE_OF 边")

    def test_composition_inside_constraint(self):
        """约束中使用组合链变量"""
        source = '''class addr_item;
    rand bit [31:0] addr;
endclass

class packet;
    addr_item item_addr;
    constraint valid_addr { item_addr.addr[31:16] == 16'h1234; }
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        nodes = list(graph.nodes())

        # IS_INSTANCE_OF 边
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]
        self.assertEqual(len(inst_edges), 1)
        self.assertIn(('packet.item_addr', 'addr_item'), inst_edges)

        # 约束存在
        self.assertIn('packet.valid_addr', nodes)

    def test_multi_declarator_with_composition(self):
        """多声明符 + 组合混合"""
        source = '''class item;
    rand int a, b, c;
endclass

class container;
    item x, y;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertEqual(len(inst_edges), 2, "两个多 declarator 成员应有 2 条 IS_INSTANCE_OF 边")
        self.assertIn(('container.x', 'item'), inst_edges)
        self.assertIn(('container.y', 'item'), inst_edges)


class TestCompositionChainEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()

    def test_class_with_only_composition_no_rand(self):
        """只有组合成员无 rand 变量"""
        source = '''class inner;
    int x;
endclass

class outer;
    inner my_ref;
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertEqual(len(inst_edges), 1, "应有 1 条 IS_INSTANCE_OF 边")
        self.assertIn(('outer.my_ref', 'inner'), inst_edges,
            "outer.my_ref 应指向 inner")

    def test_composition_byte_vector(self):
        """byte 向量类型 (少见但有效)"""
        source = '''class inner;
    rand byte data;
endclass

class outer;
    inner bytes[8];
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertGreaterEqual(len(inst_edges), 1)

    def test_composition_logic_vector(self):
        """logic 向量类型"""
        source = '''class inner;
    rand logic [7:0] data;
endclass

class outer;
    inner items[2];
endclass'''

        graph = self._build_graph(source)
        edges = list(graph.edges())
        inst_edges = [(src, dst) for src, dst in edges
                      if graph.get_edge(src, dst).kind == EdgeKind.IS_INSTANCE_OF]

        self.assertGreaterEqual(len(inst_edges), 1)


if __name__ == '__main__':
    unittest.main()
