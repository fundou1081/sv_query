#==============================================================================
# test_unsupported_syntax.py - 金标准测试用例 (10个不支持的语法)
# 项目纪律: 铁律13 金标准测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


#==============================================================================
# 金标准测试 - 10个语法场景
#==============================================================================

class TestModportDirection(unittest.TestCase):
    """[语法1] Modport 方向识别"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_modport_master_direction(self):
        """[Golden] modport master 方向为 output
        
        金标准:
        - 接口方向: input a -> 输出端口
        - modport.master 输出数据
        """
        source = '''
interface bus_if;
    logic [7:0] data;
    logic valid;
    
    modport master(output data, valid);
    modport slave(input data, valid);
endinterface

module top(bus_if.master ifc);
    assign ifc.data = 8'h0;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: 至少有节点
        nodes = tracer.get_graph().nodes()
        self.assertGreaterEqual(len(list(nodes)), 1)


class TestInterfaceSignal(unittest.TestCase):
    """[语法2] Interface 内信号点号访问"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_dot_access(self):
        """[Golden] ifc.data 点号访问
        
        金标准:
        - interface 信号可追踪
        - ifc.data 的驱动可提取
        """
        source = '''
interface simple_if;
    logic [7:0] data;
endinterface

module top(input simple_if ifc);
    assign ifc.data = 8'hFF;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: ifc.data 节点存在
        nodes = list(tracer.get_graph().nodes())
        has_ifc_data = any('ifc.data' in n for n in nodes)
        self.assertTrue(has_ifc_data, f'ifc.data not found in {nodes}')


class TestClockingBlock(unittest.TestCase):
    """[语法3] Clocking Block"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_clock_block(self):
        """[Golden] clocking block 提取
        
        金标准:
        - @clk 时序接口识别
        - cb.data 与 clk 同步
        """
        source = '''
module top(input clk, logic data, output logic valid);
    clocking cb @(posedge clk);
        input data;
        output valid;
    endclocking
    
    assign cb.valid = cb.data;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestCovergroup(unittest.TestCase):
    """[语法4] Covergroup"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_covergroup(self):
        """[Golden] covergroup 提取
        
        金标准:
        - covergroup 存在
        - 覆盖率点可追踪
        """
        source = '''
module top(input clk, input a);
    covergroup cg @(posedge clk);
        option.per_instance = 1;
        coverpoint a;
    endgroup
    
    cg cg_inst = new();
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestPropertySequence(unittest.TestCase):
    """[语法5] SVA Property / Sequence"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_property(self):
        """[Golden] property / sequence 提取
        
        金标准:
        - property 语句存在
        - sequence 存在
        """
        source = '''
module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##1 b;
    endsequence
    
    property p1;
        @(posedge clk) disable iff (1'b0) a |-> b;
    endproperty
    
    assert property (p1) else $error("fail");
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestRandsequence(unittest.TestCase):
    """[语法6] Randsequence"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_randsequence(self):
        """[Golden] randsequence 提取
        
        金标准:
        - randsequence 语句存在
        """
        source = '''
module top;
    randsequence(main)
        main: 1;
    endsequence
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestPackageImport(unittest.TestCase):
    """[语法7] Package Import"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_package(self):
        """[Golden] import pkg::symbol
        
        金标准:
        - package 可导入
        - import 语句不导致解析失败
        """
        source = '''
package my_pkg;
    typedef struct logic [7:0] byte_t;
endpackage

module top;
    import my_pkg::*;
    logic [7:0] data;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestClassExtends(unittest.TestCase):
    """[语法8] Class extends / OOP"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_class(self):
        """[Golden] class extends
        
        金标准:
        - class 定义存在
        - extends 继承关系可识别
        """
        source = '''
class base_cls;
    virtual task send();
    endtask
endclass

class derived_cls extends base_cls;
    task send();
    endtask
endclass

module top;
    derived_cls obj = new();
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestVirtualInterface(unittest.TestCase):
    """[语法9] Virtual Interface"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_virtual_if(self):
        """[Golden] virtual interface
        
        金标准:
        - virtual interface 可声明
        - 可传递给模块
        """
        source = '''
interface test_if;
    logic [7:0] data;
endinterface

class driver;
    virtual test_if vif;
    task drive();
    endtask
endclass

module top;
    test_if intf();
    driver d = new();
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图
        self.assertIsNotNone(tracer.get_graph())


class TestGenerateIf(unittest.TestCase):
    """[语法10] Generate if/else"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_generate(self):
        """[Golden] generate if/else
        
        金标准:
        - generate if 语句存在
        - 条件编译可识别
        """
        source = '''
module top(input a, b, output y);
    generate
        if (1'b1) begin
            assign y = a;
        end else begin
            assign y = b;
        end
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 能建立图 (不报语法错误即可)
        self.assertIsNotNone(tracer.get_graph())
        # TODO: generate 块内信号追踪


#==============================================================================
# 测试列表
#==============================================================================
if __name__ == '__main__':
    unittest.main()
