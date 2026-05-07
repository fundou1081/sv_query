# test_constraint.py - Constraint 金标准
# [铁律13] 金标准测试
# 当前状态: ClassDeclaration 未被 get_modules() 返回
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestConstraint(unittest.TestCase):
    """Constraint 随机约束信号追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_constraint_requires_implementation(self):
        """[Golden] Constraint 需要实现
        
        问题:
        - ClassDeclaration 不是 ModuleDeclaration
        - get_modules() 只返回 ModuleDeclaration
        - Constraint 声明在 Class 内，未被提取
        
        当前状态: 不支持 Class 内部
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c { addr inside {0, 1, 2}; }
endclass

module top(output [7:0] data);
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 当前: Class 未被识别
        # TODO: 需要实现 ClassDeclaration 支持

if __name__ == '__main__':
    unittest.main()
