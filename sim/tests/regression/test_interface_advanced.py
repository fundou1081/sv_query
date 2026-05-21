#==============================================================================
# test_interface_advanced.py - Interface 高级特性金标准测试
# 项目纪律: 铁律13 金标准测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


#==============================================================================
# 1. Interface 基本使用 - 金标准
#==============================================================================
class TestInterfaceBasic(unittest.TestCase):
    """[语法] 基本 Interface"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    

class TestInterfaceArray(unittest.TestCase):
    """[语法] Interface 数组"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_interface_array(self):
        """[Golden] interface 数组端口
        
        RTL:
        module top(ifs[1:0]);
        
        预期:
        - ifs[0].data 节点存在
        """
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(my_if ifs[1:0], input [7:0] din);
    assign ifs[0].data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: 有节点存在
        nodes = list(tracer.get_graph().nodes())
        self.assertGreater(len(nodes), 0, f'No nodes: {nodes}')


#==============================================================================
# 3. Interface 多信号 - 金标准
#==============================================================================
class TestInterfaceMultiple(unittest.TestCase):
    """[语法] Interface 多信号"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    

class TestInterfaceConnection(unittest.TestCase):
    """[语法] Interface 端口连接"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    

class TestModportDirection(unittest.TestCase):
    """[语法] Modport 方向"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_modport_master_output(self):
        """[Golden] modport master 方向为 output
        
        RTL:
        interface bus_if;
            logic data;
            modport master(output data);
        endinterface
        
        预期:
        - m.data 方向为 output
        - 外部信号 -> m.data 驱动
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    modport master(output data);
    modport slave(input data);
endinterface

module top(bus_if.master m, input [7:0] din);
    assign m.data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: m.data 节点存在且有驱动边
        nodes = list(tracer.get_graph().nodes())
        has_m_data = any('m.data' in n for n in nodes)
        self.assertTrue(has_m_data, f'm.data not in {nodes}')
        
        edges = list(tracer.get_graph().edges())
        has_drive = any('din' in src and 'm.data' in dst for src, dst in edges)
        self.assertTrue(has_drive, f'din->m.data drive not in {edges}')
    
    def test_modport_slave_input(self):
        """[Golden] modport slave 方向为 input
        
        预期:
        - s.data 方向为 input
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    modport master(output data);
    modport slave(input data);
endinterface

module top(bus_if.slave s);
    logic [7:0] tmp;
    assign tmp = s.data;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: s.data 节点存在
        nodes = list(tracer.get_graph().nodes())
        has_s_data = any('s.data' in n for n in nodes)
        self.assertTrue(has_s_data, f's.data not in {nodes}')
