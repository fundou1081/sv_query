# test_generate.py - Generate 块金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestGenerate(unittest.TestCase):
    """Generate 块信号追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_generate_if(self):
        """[Golden] Generate if 语句
        
        RTL:
        generate
            if (1'b1) begin
                assign y = a;
            end
        endgenerate
        
        预期:
        - y 节点存在
        - 驱动边存在 (if 分支被提取)
        
        注: 静态分析提取所有分支
        """
        source = '''module top(input a, output y);
generate
    if (1'b1) begin
        assign y = a;
    end
endgenerate
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: y 节点存在
        self.assertTrue(any('y' in n for n in nodes), 
            f"y node not found in {nodes}")
        
        # 验证: y <- a 驱动边存在
        has_drive = any('a' in str(src) and 'y' in str(dst) for src, dst in edges)
        self.assertTrue(has_drive, 
            f"y <- a edge not found in {edges}")
    
    def test_generate_for(self):
        """[Golden] Generate for 语句
        
        RTL:
        generate
            for (i=0; i<8; i=i+1) begin : gen
                assign out[i] = in[i];
            end
        endgenerate
        
        预期:
        - out 节点存在
        """
        source = '''module top(input [7:0] in, output [7:0] out);
generate
    genvar i;
    for (i = 0; i < 8; i = i + 1) begin : gen
        assign out[i] = in[i];
    end
endgenerate
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # [铁律13] 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        
        # 验证: out 节点存在
        self.assertTrue(any('out' in n for n in nodes), 
            f"out node not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
