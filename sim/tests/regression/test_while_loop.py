# test_while_loop.py - While 循环金标准
# [铁律13] 金标准测试
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestWhileLoop(unittest.TestCase):
    """While 循环信号追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_while_basic(self):
        """[Golden] While 循环内非阻塞赋值
        
        RTL:
        always @(posedge clk) begin
            while (cnt > 0) begin
                q <= cnt;
            end
        end
        
        预期:
        - q 节点存在
        - q <- cnt 驱动边存在 (while 循环体内)
        """
        source = '''module top(input clk, output logic [7:0] q);
    logic [7:0] cnt = 8;
    always @(posedge clk) begin
        while (cnt > 0) begin
            q <= cnt;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: q 节点存在
        self.assertTrue(any('q' in n for n in nodes), 
            f"q node not found in {nodes}")
        
        # 验证: q <- cnt 驱动边存在
        has_drive = any('cnt' in str(src) and 'q' in str(dst) for src, dst in edges)
        self.assertTrue(has_drive, 
            f"q <- cnt edge not found in {edges}")

if __name__ == '__main__':
    unittest.main()
