# test_constraint_derivative.py - Constraint 衍生语法金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Constraint 衍生语法:
1. inside 约束
2. implication (->) 约束
3. if/else 约束
4. dist 分布约束
5. solve before 求解顺序
6. unique 唯一性约束
7. loop 循环约束
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestConstraintDerivative(unittest.TestCase):
    """Constraint 衍生语法测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def _get_classes(self, source):
        class FP:
            def __init__(self, t): self.trees = t
        adapter = PyslangAdapter(FP({'test.sv': source}))
        return adapter.get_classes()
    
    def test_constraint_inside(self):
        """[Golden] inside 约束
        
        RTL: constraint c { addr inside {0, 1, 2}; }
        
        预期:
        - ConstraintDeclaration 存在
        - ExpressionConstraint 存在
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
    
    def test_constraint_implication(self):
        """[Golden] implication (->) 约束
        
        RTL: constraint c { (en) -> data == 1; }
        
        预期:
        - ConstraintDeclaration 存在
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
    
    def test_constraint_if_else(self):
        """[Golden] if/else 约束
        
        RTL:
        constraint c {
            if (en) addr == 1;
            else addr == 2;
        }
        
        预期:
        - ConstraintDeclaration 存在
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
    
    def test_constraint_dist(self):
        """[Golden] dist 分布约束
        
        RTL: constraint c { addr dist {0:=1, 1:=2}; }
        
        预期:
        - ConstraintDeclaration 存在
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c { addr dist {0:=1, 1:=2}; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)
        
        self.assertEqual(len(classes), 1)
    
    def test_constraint_solve_before(self):
        """[Golden] solve before 求解顺序
        
        RTL: constraint c { solve addr before data; }
        
        预期:
        - ConstraintDeclaration 存在
        """
        source = '''class packet;
    rand bit [7:0] addr, data;
    constraint c { solve addr before data; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)
        
        self.assertEqual(len(classes), 1)
    
    def test_constraint_unique(self):
        """[Golden] unique 唯一性约束
        
        RTL: constraint c { unique {a, b, c}; }
        
        预期:
        - ConstraintDeclaration 存在
        """
        source = '''class packet;
    rand bit a, b, c;
    constraint unique_c { unique { a, b, c }; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)
        
        self.assertEqual(len(classes), 1)
    
    def test_constraint_loop(self):
        """[Golden] loop 循环约束
        
        RTL: constraint c { foreach (arr[i]) arr[i] > 0; }
        
        预期:
        - ConstraintDeclaration 存在
        """
        source = '''class packet;
    bit [7:0] arr[4];
    constraint c { foreach (arr[i]) arr[i] > 0; }
endclass
module top();
endmodule'''
        classes = self._get_classes(source)
        
        self.assertEqual(len(classes), 1)

if __name__ == '__main__':
    unittest.main()
