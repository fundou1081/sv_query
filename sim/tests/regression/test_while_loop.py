# test_while_loop.py - While 循环金标准
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestWhileLoop(unittest.TestCase):
    def test_while_basic(self):
        """[Golden] While 循环内赋值
        
        RTL: always @(posedge clk) while(cnt > 0) q <= cnt;
        
        预期: q 节点存在
        """
        source = '''module top(input clk, output [7:0] q);
reg [7:0] cnt = 8;
always @(posedge clk) begin
    while (cnt > 0) begin
        q <= cnt;
    end
end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'t': tree})
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        # 验证: q 节点存在
        nodes = list(tracer.get_graph().nodes())
        self.assertTrue(any('q' in n for n in nodes), f'q not in {nodes}')

if __name__ == '__main__':
    unittest.main()
