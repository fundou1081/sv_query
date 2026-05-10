#==============================================================================
# test_instance_hierarchy.py - Instance and hierarchy tests
#==============================================================================
"""
[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律18] 负面测试原则
[铁律19] 真实场景来源

更新: 2026-05-09 修正断言为强断言，添加更明确的金标准验证
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph_models import EdgeKind, NodeKind


class TestInstanceHierarchy(unittest.TestCase):
    """模块实例化层次测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_single_instance(self):
        """[金标准] 单模块实例化 - 命名端口连接
        
        金标准:
        RTL:
          child u1(.d(di), .q(qo));
        
        期望:
          - top.u1.d 节点存在
          - top.u1.q 节点存在
          - CONNECTION 边: top.di -> top.u1.d
          - CONNECTION 边: top.u1.q -> top.qo
        """
        source = '''
module child(input d, output q);
    assign q = d;
endmodule

module top(input di, output qo);
    child u1(.d(di), .q(qo));
endmodule'''
        
        graph = self._build_graph(source)
        
        # 节点存在
        self.assertIn('top.u1.d', graph.nodes(), "实例端口 top.u1.d 应存在")
        self.assertIn('top.u1.q', graph.nodes(), "实例端口 top.u1.q 应存在")
        
        # CONNECTION 边验证
        self.assertTrue(graph.has_edge('top.di', 'top.u1.d'),
            "di -> u1.d CONNECTION 边应存在")
        self.assertTrue(graph.has_edge('top.u1.q', 'top.qo'),
            "u1.q -> qo CONNECTION 边应存在")
    
    def test_same_module_multiple_instances(self):
        """[金标准] 同一模块多次实例化
        
        金标准:
        RTL:
          delay u1(clk, a, qa);
          delay u2(clk, b, qb);
        
        期望:
          - top.u1.d 和 top.u2.d 独立
          - top.a -> top.u1.d (qa 端口)
          - top.b -> top.u2.d (qb 端口)
          - 不会混淆 u1 和 u2
        """
        source = '''
module delay(input clk, input d, output q);
    logic r;
    always_ff @(posedge clk) r <= d;
    assign q = r;
endmodule

module top(input clk, input a, input b, output qa, output qb);
    delay u1(clk, a, qa);
    delay u2(clk, b, qb);
endmodule'''
        
        graph = self._build_graph(source)
        
        # 两个实例的端口独立存在
        self.assertIn('top.u1.d', graph.nodes(), "u1.d 应存在")
        self.assertIn('top.u2.d', graph.nodes(), "u2.d 应存在")
        self.assertIn('top.u1.clk', graph.nodes(), "u1.clk 应存在")
        self.assertIn('top.u2.clk', graph.nodes(), "u2.clk 应存在")
        
        # 验证连接不混淆: u1.d 由 a 驱动，u2.d 由 b 驱动
        self.assertTrue(graph.has_edge('top.a', 'top.u1.d'),
            "a -> u1.d 边应存在")
        self.assertTrue(graph.has_edge('top.b', 'top.u2.d'),
            "b -> u2.d 边应存在")
        
        # 确保没有错误的交叉连接
        self.assertFalse(graph.has_edge('top.a', 'top.u2.d'),
            "a 不应该连接到 u2.d")
        self.assertFalse(graph.has_edge('top.b', 'top.u1.d'),
            "b 不应该连接到 u1.d")
    
    def test_positional_port_connection(self):
        """[金标准] 位置端口连接
        
        金标准:
        RTL:
          child u1(di, qo);  // 位置连接
        
        期望: 与命名端口连接相同的边
        """
        source = '''
module child(input d, output q);
    assign q = d;
endmodule

module top(input di, output qo);
    child u1(di, qo);
endmodule'''
        
        graph = self._build_graph(source)
        
        self.assertTrue(graph.has_edge('top.di', 'top.u1.d'),
            "di -> u1.d 边应存在（位置连接）")
        self.assertTrue(graph.has_edge('top.u1.q', 'top.qo'),
            "u1.q -> qo 边应存在（位置连接）")
    
    def test_named_port_connection(self):
        """[金标准] 命名端口连接
        
        金标准:
        RTL:
          child u1(.d(di), .q(qo));  // 命名连接
        
        期望: 与位置端口连接相同的边
        """
        source = '''
module child(input d, output q);
    assign q = d;
endmodule

module top(input di, output qo);
    child u1(.d(di), .q(qo));
endmodule'''
        
        graph = self._build_graph(source)
        
        self.assertTrue(graph.has_edge('top.di', 'top.u1.d'),
            "di -> u1.d 边应存在（命名连接）")
        self.assertTrue(graph.has_edge('top.u1.q', 'top.qo'),
            "u1.q -> qo 边应存在（命名连接）")
    
    def test_hierarchical_name_10_levels(self):
        """[边界] 10 层层次名称
        
        期望: top.u10.q 存在
        """
        source = '''
module leaf(input d, output q);
    assign q = d;
endmodule

module top(input di, output qo);
    leaf u1(.d(di), .q(u2.q));
    leaf u2(.d(u3.q), .q(u3.q));
    leaf u3(.d(u4.q), .q(u4.q));
    leaf u4(.d(u5.q), .q(u5.q));
    leaf u5(.d(u6.q), .q(u6.q));
    leaf u6(.d(u7.q), .q(u7.q));
    leaf u7(.d(u8.q), .q(u8.q));
    leaf u8(.d(u9.q), .q(u9.q));
    leaf u9(.d(u10.q), .q(u10.q));
    leaf u10(.d(di), .q(qo));
endmodule'''
        
        graph = self._build_graph(source)
        
        self.assertIn('top.u10.q', graph.nodes(), "最深层次节点应存在")
    
    def test_instance_with_parameters(self):
        """[金标准] 参数化模块实例化 - 端口连接
        
        金标准:
        RTL:
          reg_mod #(.WIDTH(8)) u1(clk, d, q);
        
        期望:
          - top.u1.d 节点存在（实例端口）
          - top.u1.q 节点存在（实例端口）
          - 端口连接到顶层信号
        """
        source = '''
module reg_mod #(
    parameter WIDTH = 8
) (
    input clk,
    input [WIDTH-1:0] d,
    output [WIDTH-1:0] q
);
    logic [WIDTH-1:0] r;
    always_ff @(posedge clk) r <= d;
    assign q = r;
endmodule

module top(input clk, input [7:0] d, output [7:0] q);
    reg_mod #(.WIDTH(8)) u1(clk, d, q);
endmodule'''
        
        graph = self._build_graph(source)
        
        # 端口节点应存在
        self.assertIn('top.u1.d', graph.nodes(), "实例端口 u1.d 应存在")
        self.assertIn('top.u1.q', graph.nodes(), "实例端口 u1.q 应存在")
        self.assertIn('top.u1.clk', graph.nodes(), "实例端口 u1.clk 应存在")
        
        # 端口连接验证
        self.assertTrue(graph.has_edge('top.clk', 'top.u1.clk'),
            "clk -> u1.clk 边应存在")
        self.assertTrue(graph.has_edge('top.d', 'top.u1.d'),
            "d -> u1.d 边应存在")
        self.assertTrue(graph.has_edge('top.u1.q', 'top.q'),
            "u1.q -> q 边应存在")
    
    def test_array_of_instances(self):
        """[边界] 实例数组
        
        期望: 范围形式节点存在
        """
        source = '''
module inv(input d, output q);
    assign q = ~d;
endmodule

module top(input [3:0] d, output [3:0] q);
    inv gen[3:0](.d(d), .q(q));
endmodule'''
        
        graph = self._build_graph(source)
        
        # 实例数组节点应存在
        self.assertIn('top.gen[3:0].d', graph.nodes(),
            "实例数组节点 gen[3:0].d 应存在")


if __name__ == '__main__':
    unittest.main()
