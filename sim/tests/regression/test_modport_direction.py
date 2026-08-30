"""
test_modport_direction.py - P0-3 Modport 方向解析测试
[P0-3] 支持 modport 方向解析

测试目标: 能够正确解析 modport 的方向 (input/output/inout) 并填充到 TraceNode

[iter_064 2026-08-29] 升级断言强度: 保留原有 modport_dir 字段断言,
补充 UnifiedTracer + graph.get_edge 行为断言 — 验证 modport 端口
确实生成了 DRIVER 边 (assign_type=continuous), 且 driver 方向
与 modport_dir 一致 (output modport 必有 DRIVER 出边, input modport
必有 DRIVER 入边).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace import UnifiedTracer
from trace.core.graph.models import EdgeKind


def _build_graph(source, filename='top.sv'):
    """[iter_064] 构建 tracer graph 的统一 helper (行为断言用)"""
    pyslang.SyntaxTree.fromText(source)
    tracer = UnifiedTracer(sources={filename: source})
    tracer.build_graph()
    return tracer.get_graph()


class TestModportDirection(unittest.TestCase):
    """Modport 方向解析测试"""

    def test_simple_modport_output(self):
        """测试 modport output 方向解析
        RTL: modport master(output data); assign m.data = din;
        金标准:
        - top.m.data 节点 modport_dir == 'output'
        - [iter_064] top.din → top.m.data DRIVER 边 (assign_type=continuous)
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    modport master(output data);
endinterface

module top(bus_if.master m, input [7:0] din);
    assign m.data = din;
endmodule'''

        g = _build_graph(source)

        # 检查 m.data 节点存在
        node = g.get_node('top.m.data')
        self.assertIsNotNone(node, "top.m.data 节点应该存在")

        # 检查 modport_dir 字段存在且为 output
        self.assertTrue(hasattr(node, 'modport_dir'),
                        "TraceNode 应该有 modport_dir 字段")
        self.assertEqual(node.modport_dir, 'output',
                         "m.data 在 master modport 中是 output 方向")

        # [iter_064] 行为断言: output modport 被驱动时, 应生成 DRIVER 边
        driver_edge = g.get_edge('top.din', 'top.m.data')
        self.assertIsNotNone(driver_edge,
            "assign m.data = din 应生成 din → m.data DRIVER 边")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER,
            f"din → m.data 应为 DRIVER 边, 实际 {driver_edge.kind}")
        self.assertEqual(driver_edge.assign_type, 'continuous',
            "modport 连续赋值应标记 continuous")

    def test_simple_modport_input(self):
        """测试 modport input 方向解析
        RTL: modport slave(input data); assign dout = s.data;
        金标准:
        - top.s.data 节点 modport_dir == 'input'
        - [iter_064] top.s.data → top.dout DRIVER 边 (assign_type=continuous)
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    modport slave(input data);
endinterface

module top(bus_if.slave s, output [7:0] dout);
    assign dout = s.data;
endmodule'''

        g = _build_graph(source)

        node = g.get_node('top.s.data')
        self.assertIsNotNone(node, "top.s.data 节点应该存在")
        self.assertTrue(hasattr(node, 'modport_dir'),
                        "TraceNode 应该有 modport_dir 字段")
        self.assertEqual(node.modport_dir, 'input',
                         "s.data 在 slave modport 中是 input 方向")

        # [iter_064] 行为断言: input modport 作为源时, 应生成 DRIVER 出边
        driver_edge = g.get_edge('top.s.data', 'top.dout')
        self.assertIsNotNone(driver_edge,
            "assign dout = s.data 应生成 s.data → dout DRIVER 边")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER,
            f"s.data → dout 应为 DRIVER 边, 实际 {driver_edge.kind}")
        self.assertEqual(driver_edge.assign_type, 'continuous',
            "input modport 连续赋值应标记 continuous")

    def test_multiple_signals(self):
        """测试多信号 modport (master: output data, input addr)
        RTL: modport master(output data, input addr);
             assign m.data = din;
             // m.addr 没有被驱动 (只声明 input)
        金标准:
        - data 节点 modport_dir == 'output', addr 节点 modport_dir == 'input'
        - [iter_064] top.din → top.m.data DRIVER 边 (data 被驱动)
        - [iter_064] top.m.addr 无 DRIVER 入边 (input modport 未被驱动)
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    logic [7:0] addr;
    modport master(output data, input addr);
endinterface

module top(bus_if.master m, input [7:0] din, input [7:0] addr_in);
    assign m.data = din;
endmodule'''

        g = _build_graph(source)

        # data 应该是 output
        data_node = g.get_node('top.m.data')
        self.assertIsNotNone(data_node)
        self.assertEqual(data_node.modport_dir, 'output',
                         "data 应该是 output 方向")

        # addr 应该是 input
        addr_node = g.get_node('top.m.addr')
        self.assertIsNotNone(addr_node)
        self.assertEqual(addr_node.modport_dir, 'input',
                         "addr 应该是 input 方向")

        # [iter_064] 行为断言: output modport 端有 DRIVER 入边
        driver_edge = g.get_edge('top.din', 'top.m.data')
        self.assertIsNotNone(driver_edge,
            "assign m.data = din 应生成 din → m.data DRIVER 边")
        self.assertEqual(driver_edge.assign_type, 'continuous',
            "modport 连续赋值应标记 continuous")

        # [iter_064] 行为断言: input modport 端未被驱动, 无 DRIVER 入边
        in_edges_addr = [u for u, _v in g.in_edges('top.m.addr')]
        # input modport 允许从外部驱动, 但本模块没有 assign 到 m.addr,
        # 故无模块内 DRIVER 入边 (tool 行为: 模块内未驱动则无入边).
        self.assertEqual(len(in_edges_addr), 0,
            "本模块未驱动 m.addr, 无 DRIVER 入边 (input modport 端由外部模块驱动)")

    def test_master_and_slave(self):
        """测试 master 和 slave 组合
        RTL: bus_if 含 master(output data) 与 slave(input data) 两个 modport;
             同一 bus_if 句柄 m 和 s 同时传入 (实际是同一 interface 的不同视角).
        金标准:
        - master.data 节点 modport_dir == 'output'
        - slave.data 节点 modport_dir == 'input' (如果存在)
        - [iter_064] top.din → top.m.data DRIVER 边 (master.output 被驱动)
        - [iter_064] top.m.data 应至少有一条入边 (output modport 必被驱动)
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    modport master(output data);
    modport slave(input data);
endinterface

module top(bus_if.master m, bus_if.slave s, input [7:0] din);
    assign m.data = din;
endmodule'''

        g = _build_graph(source)

        # master.data 应该是 output
        master_data = g.get_node('top.m.data')
        self.assertEqual(master_data.modport_dir, 'output',
                         "master.data 是 output")

        # s.data 不存在 (因为没有用到 s)，这是正常的
        slave_data = g.get_node('top.s.data')
        # slave.data 如果存在，应该是 input 方向
        if slave_data:
            self.assertEqual(slave_data.modport_dir, 'input',
                             "slave.data 是 input 方向")

        # [iter_064] 行为断言: master.output modport 被驱动, 应有 DRIVER 入边
        driver_edge = g.get_edge('top.din', 'top.m.data')
        self.assertIsNotNone(driver_edge,
            "assign m.data = din 应生成 din → m.data DRIVER 边")
        self.assertEqual(driver_edge.assign_type, 'continuous',
            "master modport 连续赋值应标记 continuous")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER,
            f"din → m.data 应为 DRIVER 边, 实际 {driver_edge.kind}")


if __name__ == '__main__':
    unittest.main()
