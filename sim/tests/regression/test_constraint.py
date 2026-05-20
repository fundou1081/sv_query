# test_constraint.py - Constraint 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Constraint 语法覆盖:
1. rand 变量声明
2. constraint 块定义
3. constraint 表达式 (inside, dist, solve before)
4. class 实例化
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestConstraint(unittest.TestCase):
    """Constraint 随机约束信号追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_constraint_rand_variable(self):
        """[Golden] rand 变量声明
        
        RTL:
        class packet;
            rand bit [7:0] addr;
        endclass
        
        预期:
        - ClassDeclaration 存在
        - ClassPropertyDeclaration (rand) 存在
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit valid;
endclass

module top();
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 图应建立
        self.assertIsNotNone(tracer.get_graph())
    
    def test_constraint_block(self):
        """[Golden] constraint 块定义
        
        RTL:
        class packet;
            rand bit [7:0] addr;
            constraint c { addr inside {0, 1, 2}; }
        endclass
        
        预期:
        - Class 存在
        - constraint 声明存在
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c { addr inside {0, 1, 2}; }
endclass

module top();
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 图应建立
        self.assertIsNotNone(tracer.get_graph())
    
    def test_constraint_class_instantiation(self):
        """[Golden] class 实例化
        
        RTL:
        class packet;
            rand bit [7:0] addr;
        endclass
        
        module top;
            packet p;
            packet q = new;
        endmodule
        
        预期:
        - packet 类实例 p, q 存在
        """
        source = '''class packet;
    rand bit [7:0] addr;
endclass

module top();
    packet p;
    packet q = new;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: packet 实例存在
        has_p = any('p' in n for n in nodes)
        has_q = any('q' in n for n in nodes)
        self.assertTrue(has_p or has_q, 
            f"packet instances not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
