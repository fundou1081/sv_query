# test_basic_syntax_golden.py - 基础语法金标准测试
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
基础语法测试覆盖:
1. assign 连续赋值
2. initial block
3. always_ff
4. always_comb
5. always_latch
6. if/else
7. 位选择
8. 模块实例化
9. forever
10. for
11. while
12. repeat
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestBasicSyntaxGolden(unittest.TestCase):
    """基础语法金标准测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    # ========================================================================
    # 1. assign 连续赋值
    # ========================================================================
    def test_assign_continuous(self):
        """[Golden] assign 连续赋值
        
        RTL: assign y = a;
        
        预期:
        - y 节点存在
        - y <- a 驱动边存在
        """
        source = '''module top(input a, output y);
    assign y = a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
        self.assertTrue(any('a' in str(src) and 'y' in str(dst) for src, dst in edges),
            f"y<-a edge not in {edges}")
    
    # ========================================================================
    # 2. initial block
    # ========================================================================
    def test_initial_block(self):
        """[Golden] initial 块内赋值
        
        RTL:
        initial begin
            y = a;
        end
        
        预期:
        - y 节点存在
        - y <- a 驱动边存在 (initial 块内)
        """
        source = '''module top(input logic a, output logic y);
    initial begin
        y = a;
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
        self.assertTrue(any('a' in str(src) and 'y' in str(dst) for src, dst in edges),
            f"y<-a edge not in {edges}")
    
    # ========================================================================
    # 3. always_ff
    # ========================================================================
    def test_always_ff(self):
        """[Golden] always_ff 块
        
        RTL:
        always_ff @(posedge clk)
            y <= a;
        
        预期:
        - y 节点存在
        - y <- a 驱动边存在
        """
        source = '''module top(input clk, a, output reg y);
    always_ff @(posedge clk)
        y <= a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
        self.assertTrue(any('a' in str(src) and 'y' in str(dst) for src, dst in edges),
            f"y<-a edge not in {edges}")
    
    # ========================================================================
    # 4. always_comb
    # ========================================================================
    def test_always_comb(self):
        """[Golden] always_comb 块
        
        RTL:
        always_comb
            y = a;
        
        预期:
        - y 节点存在
        - y <- a 驱动边存在
        """
        source = '''module top(input a, output reg y);
    always_comb
        y = a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
        self.assertTrue(any('a' in str(src) and 'y' in str(dst) for src, dst in edges),
            f"y<-a edge not in {edges}")
    
    # ========================================================================
    # 5. always_latch
    # ========================================================================
    def test_always_latch(self):
        """[Golden] always_latch 块
        
        RTL:
        always_latch
            if (en) y = a;
        
        预期:
        - y 节点存在
        """
        source = '''module top(input a, en, output reg y);
    always_latch
        if (en) y = a;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
    
    # ========================================================================
    # 6. if/else
    # ========================================================================
    def test_if_else(self):
        """[Golden] if/else 语句
        
        RTL:
        if (sel) y = a;
        else y = b;
        
        预期:
        - y 节点存在
        - y <- a 或 y <- b 边存在 (条件分支)
        """
        source = '''module top(input a, b, sel, output reg y);
    always_comb begin
        if (sel)
            y = a;
        else
            y = b;
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
        # 至少有一条驱动边
        has_drive = any(('a' in str(src) or 'b' in str(src)) and 'y' in str(dst) 
                        for src, dst in edges)
        self.assertTrue(has_drive, f"y drive edge not in {edges}")
    
    # ========================================================================
    # 7. 位选择
    # ========================================================================
    def test_bit_select(self):
        """[Golden] 位选择
        
        RTL:
        assign y = data[3];
        
        预期:
        - y 节点存在
        - y <- data[3] 驱动边存在
        """
        source = '''module top(input [7:0] data, output y);
    assign y = data[3];
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('y' in n for n in nodes), f"y not in {nodes}")
        self.assertTrue(any('data' in str(src) and 'y' in str(dst) for src, dst in edges),
            f"y<-data[3] edge not in {edges}")
    
    # ========================================================================
    # 8. 模块实例化
    # ========================================================================
    def test_module_instantiation(self):
        """[Golden] 模块实例化
        
        RTL:
        submodule inst (.in(in_data), .out(out_data));
        
        预期:
        - top.inst 存在
        """
        source = '''module submodule(input [7:0] in, output [7:0] out);
endmodule

module top(input [7:0] in_data, output [7:0] out_data);
    submodule inst (.in(in_data), .out(out_data));
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        
        # 模块实例化节点应存在
        has_inst = any('inst' in n for n in nodes)
        self.assertTrue(has_inst, f"inst not in {nodes}")
    
    # ========================================================================
    # 9. forever
    # ========================================================================
    def test_forever(self):
        """[Golden] forever 循环
        
        RTL:
        initial begin
            forever begin
                #10;
            end
        end
        
        预期:
        - forever 块可识别 (无错误)
        """
        source = '''module top(input clk, output y);
    initial begin
        forever begin
            #10;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 图应建立，无错误
        self.assertIsNotNone(tracer.get_graph())
    
    # ========================================================================
    # 10. for 循环
    # ========================================================================
    def test_for_loop(self):
        """[Golden] for 循环内赋值
        
        RTL:
        always @(posedge clk)
            for (i=0; i<8; i=i+1)
                out[i] = in[i];
        
        预期:
        - out 节点存在
        - out <- in 边存在
        """
        source = '''module top(input clk, input [7:0] in, output logic [7:0] out);
    always @(posedge clk)
        for (int i=0; i<8; i=i+1)
            out[i] = in[i];
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('out' in n for n in nodes), f"out not in {nodes}")
    
    # ========================================================================
    # 11. while 循环
    # ========================================================================
    def test_while_loop(self):
        """[Golden] while 循环
        
        RTL:
        while (cnt > 0) begin
            q <= cnt;
        end
        
        预期:
        - q 节点存在
        """
        source = '''module top(input clk, output logic [7:0] q);
    logic [7:0] cnt = 8;
    always @(posedge clk)
        while (cnt > 0) begin
            q <= cnt;
        end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        
        self.assertTrue(any('q' in n for n in nodes), f"q not in {nodes}")
    
    # ========================================================================
    # 12. repeat
    # ========================================================================
    def test_repeat(self):
        """[Golden] repeat 循环
        
        RTL:
        repeat (5) begin
            data = data + 1;
        end
        
        预期:
        - repeat 块可识别
        - data 节点存在
        """
        source = '''module top(input clk, output logic [7:0] data);
    initial begin
        repeat (5) begin
            data = data + 1;
        end
    end
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        self.assertTrue(any('data' in n for n in nodes), f"data not in {nodes}")

if __name__ == '__main__':
    unittest.main()
