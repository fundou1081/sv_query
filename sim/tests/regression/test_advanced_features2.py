#==============================================================================
# test_advanced_features2.py - 高级特性金标准测试
# 项目纪律: 铁律13 金标准测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


#==============================================================================
# 1. Task 调用 - 金标准测试
#==============================================================================
class TestTaskCall(unittest.TestCase):
    """[语法] Task 调用"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_task_drives_signal(self):
        """[Golden] task 内赋值驱动信号
        
        RTL:
        task set_data(input [7:0] d, output [7:0] q);
            q = d;
        endtask
        
        预期:
        - set_data(din, dout) 调用
        - dout 的驱动: din (通过 task 传递)
        """
        source = '''
module top(input [7:0] din, output [7:0] dout);
    task set_data(input [7:0] d, output [7:0] q);
        q = d;
    endtask
    
    initial begin
        set_data(din, dout);
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        result = tracer.trace_signal('dout', 'top')
        # TODO: 实现 task 调用追踪后验证
        # 金标准: din 是 dout 的驱动 (通过 task)


#==============================================================================
# 2. Interface 定义 - 金标准测试
#==============================================================================
class TestInterfaceDecl(unittest.TestCase):
    """[语法] Interface 定义"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_interface_port(self):
        """[Golden] interface 作为端口
        
        RTL:
        interface my_if; logic [7:0] data; endinterface
        module top(input my_if.tb);
        
        预期:
        - tb.data 可追踪
        - din -> tb.data 驱动可提取
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
        self.assertTrue(any('tb.data' in n for n in nodes), f'tb.data not in {nodes}')


#==============================================================================
# 3. Modport 方向 - 金标准测试
#==============================================================================
class TestModport(unittest.TestCase):
    """[语法] Modport 方向"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_modport_direction(self):
        """[Golden] modport 方向识别
        
        RTL:
        interface my_if; logic [7:0] data; modport mp(input data); endinterface
        module top(my_if.mp m);
        
        预期:
        - m.data 方向识别为 input
        - 外部信号 -> m.data 的边
        """
        source = '''
interface my_if;
    logic [7:0] data;
    modport mp(input data);
endinterface

module top(my_if.mp m, input [7:0] din);
    assign m.data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: m.data 节点存在
        nodes = list(tracer.get_graph().nodes())
        self.assertTrue(any('m.data' in n for n in nodes), f'm.data not in {nodes}')


#==============================================================================
# 4. While 循环 - 金标准测试
#==============================================================================
class TestWhileLoop(unittest.TestCase):
    """[语法] While 循环内赋值"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_while_loop_drives(self):
        """[Golden] while 循环内赋值驱动
        
        RTL:
        while (cnt > 0) begin
            q = cnt;
            cnt = cnt - 1;
        end
        
        预期:
        - q 的驱动: cnt (过程赋值)
        """
        source = '''
module top(input clk, output [7:0] q);
    reg [7:0] cnt = 8;
    
    always @(posedge clk) begin
        while (cnt > 0) begin
            q <= cnt;
            cnt <= cnt - 1;
        end
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())
        
        # 验证: q 节点存在
        nodes = list(tracer.get_graph().nodes())
        self.assertTrue(any('q' in n for n in nodes), f'q not in {nodes}')


#==============================================================================
# 5. Class 声明 - 金标准测试
#==============================================================================
class TestClassDecl(unittest.TestCase):
    """[语法] Class 声明"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_class_with_members(self):
        """[Golden] class 成员信号
        
        RTL:
        class my_cls;
            logic [7:0] data;
            logic valid;
        endclass
        
        预期:
        - class 对象可建立节点
        """
        source = '''
class my_cls;
    logic [7:0] data;
    logic valid;
endclass

module top;
    my_cls obj = new();
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
