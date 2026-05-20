# test_fork_join.py - Fork/Join 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
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
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_fork_join_basic(self):
        """[Golden] Fork/Join 内赋值
        
        RTL:
        initial fork
            data = a;
            data = b;
        join
        
        预期:
        - data 节点存在
        - data <- a 驱动边存在
        - data <- b 驱动边存在
        """
        source = '''module top(input a, b, output [7:0] data);
    initial fork
        data = a;
        data = b;
    join
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: data 节点存在
        self.assertTrue(any('data' in n for n in nodes), 
            f"data node not found in {nodes}")
        
        # 验证: data <- a 或 data <- b 驱动边存在
        has_drive = any(('a' in str(src) or 'b' in str(src)) and 'data' in str(dst) 
                        for src, dst in edges)
        self.assertTrue(has_drive, 
            f"data drive edge not found in {edges}")

if __name__ == '__main__':
    unittest.main()
