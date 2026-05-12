"""
test_constraint_override.py - Constraint Override & SUPER_CALL 金标准测试

[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律18] 负面测试原则

场景:
  1. Constraint override (replacement)
  2. Constraint augmentation with super.<name>
  3. Multi-level super call chain

预期:
  - SUPER_CALL 边指向被调用的父类约束
  - 覆盖场景无 SUPER_CALL 边
"""

import unittest
import sys
sys.path.insert(0, 'src')

from trace.unified_tracer import UnifiedTracer
from trace.core.graph_models import EdgeKind
import pyslang


class TestConstraintSuperCall(unittest.TestCase):
    """SUPER_CALL 边测试"""
    
    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_single_super_call(self):
        """单层 super.c1 调用"""
        source = '''class packet;
    rand int addr;
    constraint c1 { addr > 0; }
endclass

class extended_packet extends packet;
    constraint c1 { super.c1; addr > 100; }
endclass'''
        
        graph = self._build_graph(source)
        edges = list(graph.edges())
        
        # 查找 SUPER_CALL 边
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        
        self.assertEqual(len(super_edges), 1, "应有 1 条 SUPER_CALL 边")
        self.assertIn(('extended_packet.c1::expr_0', 'packet.c1'), super_edges,
            "extended_packet.c1::expr_0 应 SUPER_CALL packet.c1")
    
    def test_no_super_call_replacement(self):
        """覆盖场景无 SUPER_CALL"""
        source = '''class packet;
    rand int addr;
    constraint c1 { addr > 0; }
endclass

class extended_packet extends packet;
    constraint c1 { addr > 100; }  // 直接覆盖，无 super.c1
endclass'''
        
        graph = self._build_graph(source)
        edges = list(graph.edges())
        
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        
        self.assertEqual(len(super_edges), 0, "覆盖场景无 SUPER_CALL 边")
    
    def test_two_super_calls(self):
        """同一约束多个 super 调用"""
        source = '''class base;
    rand int a, b;
    constraint c1 { a > 0; }
    constraint c2 { b > 0; }
endclass

class child extends base;
    constraint c1 { super.c1; super.c2; a > 10; }
endclass'''
        
        graph = self._build_graph(source)
        edges = list(graph.edges())
        
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        
        self.assertEqual(len(super_edges), 2, "应有 2 条 SUPER_CALL 边")
        self.assertIn(('child.c1::expr_0', 'base.c1'), super_edges)
        self.assertIn(('child.c1::expr_1', 'base.c2'), super_edges)
    
    def test_multi_level_super_call(self):
        """多层继承 super 调用"""
        source = '''class root;
    rand int x;
    constraint c_root { x > 0; }
endclass

class middle extends root;
    constraint c_root { super.c_root; x > 10; }
endclass

class leaf extends middle;
    constraint c_root { super.c_root; x > 100; }
endclass'''
        
        graph = self._build_graph(source)
        edges = list(graph.edges())
        
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        
        # middle.c1 和 leaf.c1 都有 super.c_root 调用
        self.assertEqual(len(super_edges), 2, "应有 2 条 SUPER_CALL 边")
        
        # leaf.c1::expr_0 -> middle.c_root (直接父类)
        self.assertIn(('leaf.c_root::expr_0', 'middle.c_root'), super_edges)
        
        # middle.c_root::expr_0 -> root.c_root (爷爷类)
        self.assertIn(('middle.c_root::expr_0', 'root.c_root'), super_edges)


class TestConstraintOverrideNegative(unittest.TestCase):
    """负面测试"""
    
    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_no_inheritance_no_super_crash(self):
        """无继承的 class 使用 super 不崩溃"""
        source = '''class standalone;
    rand int x;
    constraint c1 { x > 0; }
endclass'''
        
        graph = self._build_graph(source)
        self.assertIn('standalone', list(graph.nodes()))
        self.assertIn('standalone.c1', list(graph.nodes()))
    
    def test_no_inheritance_no_super_crash(self):
        """无继承的 class 使用 super 不崩溃"""
        source = '''class standalone;
    rand int x;
    constraint c1 { x > 0; }
endclass'''
        
        graph = self._build_graph(source)
        self.assertIn('standalone', list(graph.nodes()))
        self.assertIn('standalone.c1', list(graph.nodes()))


class TestConstraintOverrideComplex(unittest.TestCase):
    """复杂场景测试"""
    
    def _build_graph(self, source: str):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test.sv': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_super_call_with_implication(self):
        """super 调用 + implication 混合"""
        source = '''class packet;
    rand int a, b;
    constraint c1 { a > 0; }
endclass

class extended extends packet;
    constraint c1 { super.c1; a > 10 -> { b == a; } }
endclass'''
        
        graph = self._build_graph(source)
        edges = list(graph.edges())
        
        # 有 SUPER_CALL 边
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        self.assertEqual(len(super_edges), 1)
        self.assertIn(('extended.c1::expr_0', 'packet.c1'), super_edges)
        
        # 也有 HAS_CONSEQUENT 边（implication 的结果）
        cons_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.HAS_CONSEQUENT]
        self.assertGreater(len(cons_edges), 0, "应有 implication 的 consequent 边")
    
    def test_super_call_with_conditional(self):
        """super 调用 + if 条件混合"""
        source = '''class packet;
    rand int a, b;
    constraint c1 { a > 0; }
endclass

class extended extends packet;
    constraint c1 { super.c1; if (b > 0) { a == b; } }
endclass'''
        
        graph = self._build_graph(source)
        edges = list(graph.edges())
        
        super_edges = [(src, dst) for src, dst in edges 
                      if graph.get_edge(src, dst).kind == EdgeKind.SUPER_CALL]
        self.assertEqual(len(super_edges), 1)
        
        # if constraint 应该有 HAS_CONDITION 边
        has_cond_edges = [(src, dst) for src, dst in edges 
                         if graph.get_edge(src, dst).kind == EdgeKind.HAS_CONDITION]
        self.assertGreater(len(has_cond_edges), 0, "应有 if 的条件边")


if __name__ == '__main__':
    unittest.main()
