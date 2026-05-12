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
from trace.core.graph_models import EdgeKind, NodeKind
import pyslang


class TestCompositionChainBasic(unittest.TestCase):
    """基本组合关系测试"""
    
    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
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
        tracer = UnifiedTracer(trees={'test.sv': tree})
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
        tracer = UnifiedTracer(trees={'test.sv': tree})
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


if __name__ == '__main__':
    unittest.main()
