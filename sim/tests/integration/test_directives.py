#==============================================================================
# test_directives.py - 预处理指令测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestDirectives(unittest.TestCase):
    """预处理指令测试"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    def test_define(self):
        """[Dir] `define 宏定义
        RTL: `define WIDTH 8; assign y = a;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        """
        source = '''
`define WIDTH 8
module top(input [`WIDTH-1:0] a, output [`WIDTH-1:0] y);
    assign y = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "`define WIDTH 8 后 y = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_include(self):
        """[Dir] `include 文件包含
        金标准: `include "defines.sv" 文件不存在时被跳过
        """
        source = '''
`include "defines.sv"
module top(input a, output y);
    assign y = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "`include 文件不存在时 y = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_ifdef(self):
        """[Dir] `ifdef 条件编译
        RTL: `ifdef FEATURE; assign y = a; `else; assign y = 1'b0; `endif
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        
        FEATURE 已定义，走 `ifdef 分支
        """
        source = '''
`define FEATURE 1
module top(input a, output y);
`ifdef FEATURE
    assign y = a;
`else
    assign y = 1'b0;
`endif
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "`ifdef FEATURE (已定义) y = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_ifndef(self):
        """[Dir] `ifndef 条件编译
        RTL: `ifndef DISABLE; assign y = a; `endif
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [a]    | high |
        
        DISABLE 未定义，走 `ifndef 分支
        """
        source = '''
`ifndef DISABLE
module top(input a, output y);
    assign y = a;
`endif
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "`ifndef DISABLE (未定义) y = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_undef(self):
        """[Dir] `undef 取消宏定义
        金标准: `undef 只影响后续代码，当前 assign 不受影响
        """
        source = '''
`define MY_MACRO 1
`undef MY_MACRO
module top(input a, output y);
    assign y = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "`undef MY_MACRO 后 y = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_pragma(self):
        """[Dir] (* ... *) 属性编译指令
        RTL: always_ff @(posedge clk) dout <= din;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [din]  | high |
        """
        source = '''
module top(
    input wire clk,
    input wire din,
    output reg dout
);
    (* ASYNC_REG = "FALSE" *)
    always_ff @(posedge clk)
        dout <= din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "always_ff @(posedge clk) dout <= din 应有 1 个驱动源 (din)")
        self.assertIn('top.din', self._driver_ids(result),
            "dout 的驱动应包含 top.din")
        self.assertEqual(result.confidence, 'high')
    
    def test_full_case(self):
        """[Dir] synthesis full_case
        RTL: always_comb case (sel) ... endcase
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a]    | high |
        """
        source = '''
module top(
    input [1:0] sel,
    input a,
    output reg q
);
    always_comb begin
        // synthesis full_case
        case (sel)
            2'b00: q = a;
            2'b01: q = a;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "always_comb q = a; 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "q 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_parallel_case(self):
        """[Dir] synthesis parallel_case
        RTL: always_comb case (sel) ... default: q = a; endcase
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a, b] | high |
        """
        source = '''
module top(
    input [1:0] sel,
    input a,
    input b,
    output reg q
);
    always_comb begin
        // synthesis parallel_case
        case (1)
            sel[0]: q = a;
            sel[1]: q = b;
            default: q = a;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertEqual(len(result.drivers), 2,
            "always_comb q = a 或 b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "q 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "q 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()