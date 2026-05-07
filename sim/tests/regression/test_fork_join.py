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
        return UnifiedTracer(trees={'test': tree})
    
    def test_fork_join_basic(self):
        """[Golden] Fork/Join 基本结构
        
        注: Fork/Join 是 Token 级别，不是节点级别
        pyslang 将 fork/join 解析为 TokenKind.ForkKeyword/JoinKeyword
        需要特殊处理 SyntaxList 中的 Token 来识别 fork/join 块
        """
        source = '''module top();
    initial fork
        data = 1;
        data = 2;
    join
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # TODO: Fork/Join 需要 Token 级别处理
        # 当前: 不支持 Fork/Join 内赋值提取

if __name__ == '__main__':
    unittest.main()
