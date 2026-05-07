# test_fork_join.py - Fork/Join 金标准
# [铁律13] 金标准测试
# 当前状态: Fork/Join 内赋值未正确提取
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestForkJoin(unittest.TestCase):
    """Fork/Join 并行线程信号追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_fork_join_requires_implementation(self):
        """[Golden] Fork/Join 需要实现
        
        问题: 
        - Fork/Join 是 Token 级别 (TokenKind.ForkKeyword/JoinKeyword)
        - 内部语句在 SyntaxList 中，未被 get_assignments() 处理
        - 需要在 base.py 的 _collect_assignments_recursive 中处理 ForkKeyword
        
        当前状态: 不支持
        """
        source = '''module top(input a, b, output [7:0] data);
    initial fork
        data = a;
        data = b;
    join
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 当前状态: 有节点但无边 (fork 内赋值未提取)
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: data 节点存在
        self.assertTrue(any('data' in n for n in nodes), 
            f"data node not found in {nodes}")
        
        # TODO: 需要实现 Fork/Join 内赋值提取
        # 预期: data <- a 和 data <- b 边

if __name__ == '__main__':
    unittest.main()
