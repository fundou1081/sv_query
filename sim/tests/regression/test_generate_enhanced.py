# test_generate_enhanced.py - Generate 增强金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Generate 增强语法:
1. generate if/else 块内信号追踪
2. generate for 循环内信号追踪
3. generate case 信号追踪
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestGenerateEnhanced(unittest.TestCase):
    """Generate 增强测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_generate_if_else_signal_tracking(self):
        """[Golden] generate if/else 块内信号追踪
        
        RTL:
        module top(input a, b, output y);
            generate
                if (1'b1) begin : gen_true
                    assign y = a;
                end else begin : gen_false
                    assign y = b;
                end
            endgenerate
        endmodule
        
        预期:
        - a -> y 驱动关系
        - b -> y 驱动关系
        """
        source = '''module top(input a, b, output y);
    generate
        if (1'b1) begin : gen_true
            assign y = a;
        end else begin : gen_false
            assign y = b;
        end
    endgenerate
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: a -> y
        has_a_y = any('a' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertTrue(has_a_y, f"a -> y not found in {edges}")
        
        # 验证: b -> y
        has_b_y = any('b' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertTrue(has_b_y, f"b -> y not found in {edges}")
    
    def test_generate_for_signal_tracking(self):
        """[Golden] generate for 循环内信号追踪
        
        RTL:
        module top(input [7:0] data_in, output [7:0] data_out);
            genvar i;
            generate
                for (i = 0; i < 8; i = i + 1) begin : gen_loop
                    assign data_out[i] = data_in[7-i];
                end
            endgenerate
        endmodule
        
        预期:
        - data_in -> data_out 驱动关系
        """
        source = '''module top(input [7:0] data_in, output [7:0] data_out);
    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_loop
            assign data_out[i] = data_in[7-i];
        end
    endgenerate
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: data_in -> data_out
        has_edge = any('data_in' in edge[0] and 'data_out' in edge[1] for edge in edges)
        self.assertTrue(has_edge, f"data_in -> data_out not found in {edges}")

if __name__ == '__main__':
    unittest.main()
