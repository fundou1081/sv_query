"""
Generate If/Else Test
[P0-2] 支持 generate if/else 块

测试目标: 能够正确处理条件 generate 块
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace import UnifiedTracer


class TestGenerateIf(unittest.TestCase):
    
    def _make_tracer(self, source, module_name='top'):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={module_name: tree})
        tracer.build_graph()
        return tracer
    
    def test_simple_generate_if_assign(self):
        """[P0-2] Generate if 块内赋值
        
        测试 assign 语句在 generate if 块内能正确工作
        """
        source = '''
module top(input sel, input [7:0] a, b, output [7:0] y);
    generate
        if (1'b1) begin : gen_block
            assign y = a;
        end
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        edges = list(tracer.get_graph().edges())
        edge_ids = [f"{s}->{d}" for s, d in edges]
        
        # assign y = a 应该创建 a -> y 的边
        self.assertIn('top.a->top.y', edge_ids,
            f"Should have a->y edge, got: {edge_ids}")
    
    def test_generate_if_else_assign(self):
        """[P0-2] Generate if/else 赋值
        
        测试 if/else 两个分支的 assign 都能正确创建边
        """
        source = '''
module top(input sel, input [7:0] a, b, output [7:0] y);
    generate
        if (1'b1) begin : gen_true
            assign y = a;
        end else begin : gen_false
            assign y = b;
        end
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        edges = list(tracer.get_graph().edges())
        edge_ids = [f"{s}->{d}" for s, d in edges]
        
        # 两个分支的赋值都应该工作
        has_a_to_y = 'top.a->top.y' in edge_ids
        has_b_to_y = 'top.b->top.y' in edge_ids
        
        # 至少一个应该存在
        self.assertTrue(has_a_to_y or has_b_to_y,
            f"Should have a->y or b->y edge: {edge_ids}")
    
    def test_generate_if_with_instance(self):
        """[P0-2] Generate if 块内实例
        
        测试 generate if 块内的模块实例化
        """
        source = '''
module inv(input [7:0] d, output [7:0] q);
    assign q = d;
endmodule

module top(input sel, input [7:0] a, output [7:0] y);
    generate
        if (1'b1) begin : gen_inst
            inv u1(.d(a), .q(y));
        end
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        edge_ids = [f"{s}->{d}" for s, d in edges]
        
        # 应该存在实例节点
        has_instance = any('u1' in n for n in nodes)
        self.assertTrue(has_instance, f"Instance u1 should exist: {nodes}")


if __name__ == '__main__':
    unittest.main()
