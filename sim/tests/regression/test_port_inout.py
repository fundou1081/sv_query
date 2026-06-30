# test_port_inout.py - PORT_INOUT 测试
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
PORT_INOUT 相关测试:
1. 多 inout 端口
2. 三态缓冲
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind


class TestPortInout(unittest.TestCase):
    """PORT_INOUT 测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'t.sv': source})

    def test_tri_state_buffer(self):
        """[Golden] 三态缓冲

        RTL: assign bidir = en ? data : 1'bz;

        预期:
        - bidir 节点存在
        - 驱动追溯正确处理三态
        """
        source = '''
module top (
    input logic clk,
    input logic en,
    input logic data,
    inout logic bidir
);
    assign bidir = en ? data : 1'bz;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        nodes = list(graph.nodes())

        # 金标准: bidir 节点存在
        self.assertTrue(any('bidir' in n for n in nodes),
            f"bidir 节点应存在，实际节点: {nodes}")

    def test_multiple_inout_ports(self):
        """[Golden] 多 inout 端口

        RTL: 多个 inout 端口

        预期:
        - 所有 inout 端口节点存在
        """
        source = '''
module top (
    inout logic port_a,
    inout logic port_b,
    inout logic port_c
);
    // 简化：双向端口
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        nodes = list(graph.nodes())

        # 金标准: port_a, port_b, port_c 节点存在
        self.assertTrue(any('port_a' in n for n in nodes), "port_a 应存在")
        self.assertTrue(any('port_b' in n for n in nodes), "port_b 应存在")
        self.assertTrue(any('port_c' in n for n in nodes), "port_c 应存在")

    def test_inout_kind(self):
        """[Golden] inout 端口 kind 正确

        预期:
        - inout 端口 kind 为 PORT_INOUT
        """
        source = '''
module top (
    inout logic bidir
);
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()

        # 金标准: bidir 节点 kind 为 PORT_INOUT
        bidir_node = graph.get_node('top.bidir')
        self.assertIsNotNone(bidir_node, "bidir 节点应存在")
        self.assertEqual(bidir_node.kind, NodeKind.PORT_INOUT,
            f"bidir kind 应为 PORT_INOUT，实际: {bidir_node.kind}")


if __name__ == '__main__':
    unittest.main()
