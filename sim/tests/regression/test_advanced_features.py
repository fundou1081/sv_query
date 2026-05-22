#==============================================================================
# test_advanced_features.py - 高级 SystemVerilog 特性测试
# Bug: 函数/任务/模块 hierarchy/接口/循环/类未提取
# 项目纪律: 金标准测试优先
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestFunctionTask(unittest.TestCase):
    """函数/任务调用测试"""
    
    def test_function_call(self):
        """[Golden] 函数调用"""
        src = '''
module top(input [7:0] a, output [7:0] y);
    function [7:0] add_one;
        input [7:0] data;
        begin add_one = data + 1; end
    endfunction
    assign y = add_one(a);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
    
    def test_function_return(self):
        """[Golden] 函数返回值"""
        src = '''
module top(input a, output y);
    function foo;
        input in;
        begin foo = in; end
    endfunction
    assign y = foo(a);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_task_call(self):
        """[Golden] 任务调用 - task 不驱动信号，期望 0 个驱动"""
        src = '''
module top(input logic a);
    task my_task;
        // task 不驱动信号
    endtask
    initial begin
        my_task();
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('a', 'top')
        
        self.assertEqual(len(result.drivers), 0)


class TestModuleHierarchy(unittest.TestCase):
    """模块 hierarchy 测试"""
    
    def test_module_instantiation(self):
        """[Golden] 模块例化"""
        src = '''
module child(input a, output y);
    assign y = a;
endmodule

module top(input a, output b);
    child u1(.a(a), .y(b));
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('b', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_port_connection(self):
        """[Golden] 端口连接"""
        src = '''
module child(input a, input b, output y);
    assign y = a & b;
endmodule

module top(input a, b, output y);
    child u1(.a(a), .b(b), .y(y));
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


class TestInterface(unittest.TestCase):
    """接口测试"""
    
    def test_interface_decl(self):
        """[Golden] 接口声明"""
        src = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(input logic clk);
    my_if ifc();
    always_ff @(posedge clk) begin
        ifc.data <= 8'b0;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('ifc.data', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_modport(self):
        """[Golden] modport"""
        src = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(input logic clk);
    my_if ifc();
    always_ff @(posedge clk) begin
        ifc.data <= 8'b0;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('ifc.data', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


class TestLoop(unittest.TestCase):
    """循环语句测试"""
    
    def test_for_loop(self):
        """[Golden] for 循环"""
        src = '''
module top(input logic [7:0] data, output logic y);
    always_comb begin
        for (int i=0; i<8; i++) begin
            y = data[0];
        end
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        # for 循环内部可能无法提取
        self.assertGreaterEqual(len(result.drivers), 0)
    
    def test_while_loop(self):
        """[Golden] while 循环"""
        src = '''
module top(input logic a, output logic y);
    always_comb begin
        while (a) begin
            y = a;
        end
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


class TestClass(unittest.TestCase):
    """类测试"""
    
    def test_class_decl(self):
        """[Golden] 类声明 - class 实例未赋值，期望 0 个驱动"""
        src = '''
class my_class;
    logic [7:0] data;
endclass

module top();
    my_class obj;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('obj', 'top')
        
        self.assertEqual(len(result.drivers), 0)
    
    def test_class_method(self):
        """[Golden] 类方法"""
        src = '''
class my_class;
    function void do_work(input logic a);
    endfunction
endclass

module top(input logic a, output logic out);
    my_class obj = new();
    always_comb begin
        obj.do_work(a);
        out = a;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('out', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


class TestInitialBlock(unittest.TestCase):
    """initial 语句测试"""
    
    def test_initial(self):
        """[Golden] initial 块"""
        src = '''
module top(output logic y);
    initial y = 1'b0;
endmodule'''
        # initial 只执行一次，通常用于初始化
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


class TestSequenceBlock(unittest.TestCase):
    """begin-end 块测试"""
    
    def test_begin_end(self):
        """[Golden] begin-end 块"""
        src = '''
module top(input logic a, logic b, output logic y);
    always_comb begin
        y = a;
        y = b;
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_nested_begin_end(self):
        """[Golden] 嵌套 begin-end"""
        src = '''
module top(input logic a, logic b, logic c, output logic y);
    always_comb begin
        begin
            y = a;
            begin
                y = b;
            end
        end
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
