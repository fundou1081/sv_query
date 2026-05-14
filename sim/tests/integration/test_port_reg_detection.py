#==============================================================================
# test_port_reg_detection.py - 端口+寄存器识别测试
#==============================================================================
"""
[铁律13] 金标准测试
测试 output reg q 的 is_port + REG 双语义

金标准:
RTL: module top(... output reg q); always_ff @(posedge clk) q <= d;
期望:
  - top.q: is_port=True, kind=REG
  - query_module 能找到 q 作为输出端口
  - ClockDomainTracer 能找到 q 作为寄存器
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind
from trace.core.query.module import ModuleTracer
from trace.core.query.clock_domain import ClockDomainTracer


class TestPortRegDetection(unittest.TestCase):
    """端口+寄存器双重语义测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_output_reg_is_port_and_reg(self):
        """[金标准] output reg q 应该是 is_port=True 且 kind=REG
        
        期望:
        - top.q.is_port == True
        - top.q.kind == NodeKind.REG
        """
        source = '''
module top(input clk, input d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        q_node = graph.get_node('top.q')
        
        self.assertIsNotNone(q_node, "q 节点应该存在")
        # is_port 标记
        self.assertTrue(hasattr(q_node, 'is_port'), "TraceNode 应该有 is_port 属性")
        self.assertTrue(q_node.is_port, "q 应该是端口 (is_port=True)")
        # kind 应该是 REG
        self.assertEqual(q_node.kind, NodeKind.REG, f"q.kind 应该是 REG，实际是 {q_node.kind}")
    
    def test_query_module_finds_output_port(self):
        """[金标准] query_module 应该能找到 output reg q
        
        期望: ModuleTracer._get_module_ports() 包含 q
        """
        source = '''
module top(input clk, input d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        tracer = ModuleTracer(graph)
        ports = tracer._get_module_ports('top')
        
        self.assertIn('q', ports, "q 应该被识别为端口")
    
    def test_clock_domain_finds_register(self):
        """[金标准] ClockDomainTracer 应该能找到 output reg q
        
        期望: trace('clk').registers 包含 q
        """
        source = '''
module top(input clk, input d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        cdt = ClockDomainTracer(graph)
        result = cdt.trace('clk')
        
        register_ids = [r.id for r in result.registers]
        self.assertIn('top.q', register_ids, 
            f"q 应该被识别为寄存器，实际 registers={register_ids}")
    
    def test_input_port_is_not_reg(self):
        """[边界] input 端口不应该是 REG
        
        期望: input 端口的 kind 是 PORT_IN，不是 REG
        """
        source = '''
module top(input clk, input d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        clk_node = graph.get_node('top.clk')
        
        self.assertIsNotNone(clk_node, "clk 节点应该存在")
        self.assertNotEqual(clk_node.kind, NodeKind.REG, 
            f"clk 不应该是 REG，实际 kind={clk_node.kind}")
    
    def test_bit_select_reg_with_clock_and_comb(self):
        """[金标准] 位选择端口的双边驱动
        
        RTL:
        output reg [7:0] q;
        always_ff @(posedge clk) q[7:4] <= d_in[7:4];
        always_comb q[3:0] = d_in[3:0];
        
        期望:
        - top.q[7:4]: kind=REG, has CLOCK edge from clk
        - top.q[3:0]: kind=SIGNAL, no CLOCK edge
        """
        source = '''
module top(input clk, input [7:0] d_in, output reg [7:0] q);
    always_ff @(posedge clk) q[7:4] <= d_in[7:4];
    always_comb q[3:0] = d_in[3:0];
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 q[7:4] 节点
        q74_node = graph.get_node('top.q[7:4]')
        self.assertIsNotNone(q74_node, "q[7:4] 节点应该存在")
        self.assertEqual(q74_node.kind, NodeKind.REG, 
            f"q[7:4] kind 应该是 REG，实际是 {q74_node.kind}")
        
        # 检查 q[3:0] 节点
        q30_node = graph.get_node('top.q[3:0]')
        self.assertIsNotNone(q30_node, "q[3:0] 节点应该存在")
        self.assertEqual(q30_node.kind, NodeKind.SIGNAL,
            f"q[3:0] kind 应该是 SIGNAL，实际是 {q30_node.kind}")
        
        # 检查 q[7:4] 有从 clk 来的 CLOCK 边
        q74_clock_preds = []
        for pred in graph.predecessors('top.q[7:4]'):
            edge = graph.get_edge(pred, 'top.q[7:4]')
            if edge and edge.kind == EdgeKind.CLOCK:
                q74_clock_preds.append(pred)
        self.assertIn('top.clk', q74_clock_preds,
            f"q[7:4] 应该有 CLOCK 边从 clk，实际前驱是 {q74_clock_preds}")
        
        # 检查 q[3:0] 没有 CLOCK 边
        q30_has_clock = False
        for pred in graph.predecessors('top.q[3:0]'):
            edge = graph.get_edge(pred, 'top.q[3:0]')
            if edge and edge.kind == EdgeKind.CLOCK:
                q30_has_clock = True
                break
        self.assertFalse(q30_has_clock, "q[3:0] 不应该有 CLOCK 边（always_comb）")


if __name__ == '__main__':
    unittest.main()
