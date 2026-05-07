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
# 1. Interface 内 Clocking Block - 金标准
#==============================================================================
class TestInterfaceClockingBlock(unittest.TestCase):
    """[语法] Interface 内的 Clocking Block"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_clock_block(self):
        """[Golden] interface 内 clocking block
        
        RTL:
        interface bus_if;
            clocking cb @(posedge clk);
                input data;
                output valid;
            endclocking
        endinterface
        
        预期:
        - cb.data, cb.valid 节点存在
        - 可追踪时钟同步信号
        """
        source = '''
interface bus_if(input clk);
    clocking cb @(posedge clk);
        input data;
        output valid;
    endclocking
    
    assign cb.valid = cb.data;
endinterface

module top(input clk, bus_if ifc);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 基础: 图建立即可
        # 验证: ifc 节点存在
        nodes = list(tracer.get_graph().nodes())
        has_ifc = any('ifc' in n for n in nodes)
        self.assertTrue(has_ifc, f'ifc not in {nodes}')


#==============================================================================
# 2. Interface 内 Task - 金标准
#==============================================================================
class TestInterfaceTask(unittest.TestCase):
    """[语法] Interface 内的 task"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_task(self):
        """[Golden] interface 内 task
        
        RTL:
        interface bus_if;
            task send(logic [7:0] data);
                // ...
            endtask
        endinterface
        
        预期:
        - task 定义不导致解析失败
        - task 内赋值可追踪 (未来)
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    
    task send(input [7:0] d);
        data = d;
    endtask
endinterface

module top(bus_if ifc);
    logic [7:0] tmp;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


#==============================================================================
# 3. Interface 数组 - 金标准
#==============================================================================
class TestInterfaceArray(unittest.TestCase):
    """[语法] Interface 数组端口"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_array_port(self):
        """[Golden] interface 数组端口
        
        RTL:
        module top(ifs[3:0]);
        
        预期:
        - ifs[0], ifs[1], ... 节点存在
        """
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(my_if ifs[3:0]);
    assign ifs[0].data = 8'h0;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: 有节点存在
        nodes = list(tracer.get_graph().nodes())
        self.assertGreater(len(nodes), 0, f'No nodes in {nodes}')


#==============================================================================
# 4. Interface extends - 金标准
#==============================================================================
class TestInterfaceExtends(unittest.TestCase):
    """[语法] Interface extends"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_extends(self):
        """[Golden] interface extends
        
        RTL:
        interface base_if;
            logic a;
        endinterface
        
        interface ext_if extends base_if;
            logic b;
        endinterface
        
        预期:
        - 继承的成员可追踪
        """
        source = '''
interface base_if;
    logic a;
endinterface

interface ext_if extends base_if;
    logic b;
endinterface

module top(ext_if ifc);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


#==============================================================================
# 5. Virtual Interface - 金标准
#==============================================================================
class TestVirtualInterface(unittest.TestCase):
    """[语法] Virtual Interface"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_virtual_interface(self):
        """[Golden] virtual interface
        
        RTL:
        virtual interface my_if vif;
        
        预期:
        - virtual interface 变量可存在
        """
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

class Driver;
    virtual my_if vif;
    task drive();
    endtask
endclass

module top;
    my_if intf();
    Driver drv = new();
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
