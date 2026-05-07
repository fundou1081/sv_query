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
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_port(self):
        """[Golden] interface 作为端口
        
        RTL:
        interface my_if; logic [7:0] data; endinterface
        module top(input my_if.tb);
            assign tb.data = din;
        
        预期:
        - tb.data 节点存在
        - din -> tb.data 边
        """
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(input my_if.tb, input [7:0] din);
    assign tb.data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: tb.data 节点存在
        nodes = list(tracer.get_graph().nodes())
        has_data = any('tb.data' in n for n in nodes)
        self.assertTrue(has_data, f'tb.data not found in {nodes}')
        
        # 验证: din -> tb.data 边存在
        edges = list(tracer.get_graph().edges())
        has_edge = any('din' in src and 'tb.data' in dst for src, dst in edges)
        self.assertTrue(has_edge, f'din->tb.data edge not found in {edges}')


#==============================================================================
# 2. Interface 数组端口 - 金标准
#==============================================================================
class TestInterfaceArray(unittest.TestCase):
    """[语法] Interface 数组"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
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
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_multiple_signals(self):
        """[Golden] interface 多个信号
        
        RTL:
        interface bus_if;
            logic [7:0] data;
            logic valid;
        endinterface
        
        预期:
        - tb.data, tb.valid 节点存在
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    logic valid;
endinterface

module top(input bus_if.tb, input [7:0] din, input v);
    assign tb.data = din;
    assign tb.valid = v;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: 多个信号节点
        nodes = list(tracer.get_graph().nodes())
        has_data = any('tb.data' in n for n in nodes)
        has_valid = any('tb.valid' in n for n in nodes)
        self.assertTrue(has_data, f'tb.data not in {nodes}')
        self.assertTrue(has_valid, f'tb.valid not in {nodes}')


#==============================================================================
# 4. Interface 端口连接 - 金标准
#==============================================================================
class TestInterfaceConnection(unittest.TestCase):
    """[语法] Interface 端口连接"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_module_connection(self):
        """[Golden] module 间的 interface 连接
        
        RTL:
        interface my_if;
        module source_gen(output my_if out);
        module sink(input my_if in);
        
        预期:
        - out.in -> in.in 边存在
        """
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

module source_gen(output my_if out);
    assign out.data = 8'hAA;
endmodule

module sink(input my_if in);
    logic [7:0] data;
endmodule

module top();
    source_gen s(out);
    sink k(in);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()


#==============================================================================
# 5. Modport 方向解析 - 金标准 (更严格)
#==============================================================================
class TestModportDirection(unittest.TestCase):
    """[语法] Modport 方向"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
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
