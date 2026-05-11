"""
test_modport_direction.py - P0-3 Modport 方向解析测试
[P0-3] 支持 modport 方向解析

测试目标: 能够正确解析 modport 的方向 (input/output/inout) 并填充到 TraceNode
"""

import unittest
import sys
sys.path.insert(0, 'src')

import pyslang
from trace import UnifiedTracer


class TestModportDirection(unittest.TestCase):
    """Modport 方向解析测试"""
    
    def test_simple_modport_output(self):
        """测试 modport output 方向解析"""
        source = '''
interface bus_if;
    logic [7:0] data;
    modport master(output data);
endinterface

module top(bus_if.master m, input [7:0] din);
    assign m.data = din;
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'top': tree})
        tracer.build_graph()
        g = tracer.get_graph()
        
        # 检查 m.data 节点存在
        node = g.get_node('top.m.data')
        self.assertIsNotNone(node, "top.m.data 节点应该存在")
        
        # 检查 modport_dir 字段存在且为 output
        self.assertTrue(hasattr(node, 'modport_dir'), 
                        "TraceNode 应该有 modport_dir 字段")
        self.assertEqual(node.modport_dir, 'output',
                         "m.data 在 master modport 中是 output 方向")
    
    def test_simple_modport_input(self):
        """测试 modport input 方向解析"""
        source = '''
interface bus_if;
    logic [7:0] data;
    modport slave(input data);
endinterface

module top(bus_if.slave s, output [7:0] dout);
    assign dout = s.data;
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'top': tree})
        tracer.build_graph()
        g = tracer.get_graph()
        
        node = g.get_node('top.s.data')
        self.assertIsNotNone(node, "top.s.data 节点应该存在")
        self.assertTrue(hasattr(node, 'modport_dir'),
                        "TraceNode 应该有 modport_dir 字段")
        self.assertEqual(node.modport_dir, 'input',
                         "s.data 在 slave modport 中是 input 方向")
    
    def test_multiple_signals(self):
        """测试多信号 modport (master: output data, input addr)"""
        source = '''
interface bus_if;
    logic [7:0] data;
    logic [7:0] addr;
    modport master(output data, input addr);
endinterface

module top(bus_if.master m, input [7:0] din, input [7:0] addr_in);
    assign m.data = din;
    assign m.addr = addr_in;
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'top': tree})
        tracer.build_graph()
        g = tracer.get_graph()
        
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
    
    def test_master_and_slave(self):
        """测试 master 和 slave 组合"""
        source = '''
interface bus_if;
    logic [7:0] data;
    modport master(output data);
    modport slave(input data);
endinterface

module top(bus_if.master m, bus_if.slave s, input [7:0] din);
    assign m.data = din;
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'top': tree})
        tracer.build_graph()
        g = tracer.get_graph()
        
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


if __name__ == '__main__':
    unittest.main()
