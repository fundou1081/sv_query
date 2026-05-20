#==============================================================================
# test_instance_connection.py - 模块实例化连接测试
#==============================================================================
"""
[铁律13] 金标准测试
测试模块实例化后的跨模块信号追踪

金标准 (Golden Standard):
RTL:
  module sub(input wire d, output wire q);
    assign q = d;
  endmodule
  
  module top(input wire din, output wire dout);
    sub u1(.d(din), .q(dout));
  endmodule

期望:
  - trace_signal('dout', 'top').drivers 包含 top.din (通过 u1.q -> dout)
  - 或者能追踪到 sub.u1.q -> top.dout 的连接
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind


class TestInstanceConnection(unittest.TestCase):
    """模块实例化连接测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_instance_port_connection(self):
        """[金标准] 实例端口连接
        
        期望:
        - top.u1.d -> top.din (CONNECTION) 
        - top.u1.q -> top.dout (CONNECTION)
        """
        source = '''
module sub(input wire d, output wire q);
    assign q = d;
endmodule

module top(input wire din, output wire dout);
    sub u1(.d(din), .q(dout));
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 din -> u1.d 连接 (外部输入 -> 实例输入)
        din_u1d = graph.get_edge('top.din', 'top.u1.d')
        self.assertIsNotNone(din_u1d, "应该有 din -> u1.d 的 CONNECTION 边")
        self.assertEqual(din_u1d.kind, EdgeKind.CONNECTION,
            f"边类型应该是 CONNECTION，实际是 {din_u1d.kind}")
        
        # 检查 u1.q -> dout 连接
        u1_q_dout = graph.get_edge('top.u1.q', 'top.dout')
        self.assertIsNotNone(u1_q_dout, "应该有 u1.q -> dout 的 CONNECTION 边")
        self.assertEqual(u1_q_dout.kind, EdgeKind.CONNECTION,
            f"边类型应该是 CONNECTION，实际是 {u1_q_dout.kind}")
    
    def test_signal_trace_through_instance(self):
        """[金标准] 信号追踪穿过实例
        
        期望: trace_signal('dout', 'top') 能追踪到 din
        """
        source = '''
module sub(input wire d, output wire q);
    assign q = d;
endmodule

module top(input wire din, output wire dout);
    sub u1(.d(din), .q(dout));
endmodule'''
        
        graph = self._build_graph(source)
        
        # trace_signal 应该能找到 dout 的驱动
        from trace.core.query.signal import SignalTracer
        st = SignalTracer(graph)
        result = st.trace('dout', 'top')
        
        driver_ids = [d.id for d in result.drivers]
        # dout 被 u1.q 驱动（通过 CONNECTION 边）
        # u1.q 是实例输出端口，它应该能追踪到 sub.q
        self.assertIn('top.u1.q', driver_ids,
            f"dout 的驱动应该包含 u1.q，实际驱动: {driver_ids}")
    
    def test_multiple_instances(self):
        """[金标准] 多个实例
        
        期望: 每个实例的端口都有正确的连接
        """
        source = '''
module buffer(input wire d, output wire q);
    assign q = d;
endmodule

module top(input wire a, input wire b, output wire out1, out2);
    buffer buf1(.d(a), .q(out1));
    buffer buf2(.d(b), .q(out2));
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 buf1 连接
        buf1_d_a = graph.get_edge('top.a', 'top.buf1.d')
        self.assertIsNotNone(buf1_d_a, "a -> buf1.d 连接应该存在")
        
        buf1_q_out1 = graph.get_edge('top.buf1.q', 'top.out1')
        self.assertIsNotNone(buf1_q_out1, "buf1.q -> out1 连接应该存在")
        
        # 检查 buf2 连接
        buf2_d_b = graph.get_edge('top.b', 'top.buf2.d')
        self.assertIsNotNone(buf2_d_b, "b -> buf2.d 连接应该存在")
        
        buf2_q_out2 = graph.get_edge('top.buf2.q', 'top.out2')
        self.assertIsNotNone(buf2_q_out2, "buf2.q -> out2 连接应该存在")


if __name__ == '__main__':
    unittest.main()
