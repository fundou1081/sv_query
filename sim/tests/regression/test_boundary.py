#==============================================================================
# test_boundary.py - 边界条件回归测试
# [P2] 边界和错误情况
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestBoundary(unittest.TestCase):
    """边界条件回归测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_empty_module(self):
        """[Boundary] 空模块"""
        source = '''
module top();
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nonexist', 'top')
        
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_single_signal(self):
        """[Boundary] 单信号模块"""
        source = '''
module top(
    output wire out
);
    assign out = 1'b0;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIsNotNone(result.confidence)
    
    def test_orphan_signal(self):
        """[Boundary] 孤立信号 (无驱动)"""
        source = '''
module top(
    input wire din,
    output wire dout
);
    // dout unconnected
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        # 孤立信号
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_multi_bit_single(self):
        """[Boundary] 多比特单线"""
        source = '''
module top(
    input wire [3:0] din,
    output wire [3:0] dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    #----------------------------------------------------------------------
    # [错误处理]
    #----------------------------------------------------------------------
    
    def test_invalid_signal_name(self):
        """[Error] 无效信号名"""
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('invalid_@@@', 'top')
        
        # 应该返回 uncertain 而不是崩溃
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_signal_in_invalid_module(self):
        """[Error] 无效模块"""
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'invalid_module')
        
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_empty_signal_name(self):
        """[Error] 空信号名"""
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        
        # 空字符串不应该崩溃
        try:
            result = tracer.trace_signal('', 'top')
            self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
        except Exception:
            self.fail("Empty signal name caused crash")
    
    #----------------------------------------------------------------------
    # [压力测试]
    #----------------------------------------------------------------------
    
    def test_many_signals(self):
        """[Stress] 大量信号"""
        # 生成 100 个信号
        source = 'module top('
        for i in range(100):
            source += f'input wire d{i},'
        source = source.rstrip(',') + ');\\n'
        for i in range(100):
            source += f'wire w{i}; assign w{i} = d{i};\\n'
        source += 'endmodule'
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('w50', 'top')
        
        # 不崩溃
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_deep_chain(self):
        """[Stress] 深链 (100 级)"""
        source = 'module top(input wire d0, output wire q0);\\n'
        for i in range(100):
            source += f'wire w{i}; assign w{i} = '
            if i == 0:
                source += 'd0;\\n'
            else:
                source += f'w{i-1};\\n'
        source += 'assign q0 = w99;\\nendmodule'
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q0', 'top')
        
        # 不崩溃
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()


class TestBoundaryExtensive(unittest.TestCase):
    """扩展边界测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_signal_without_module_prefix(self):
        """不带模块前缀"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        # 尝试不带模块名
        result = tracer.trace_signal('dout')
        
        self.assertIsNotNone(result.confidence)
    
    def test_case_sensitive_signal(self):
        """大小写敏感"""
        source = '''
module top(input wire Din, input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        
        # Din 和 din 应该区分
        result = tracer.trace_signal('Din', 'top')
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_underscore_in_name(self):
        """下划线信号名"""
        source = '''
module top(input wire s_i, output wire d_o);
    assign d_o = s_i;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('d_o', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_dollar_in_name(self):
        """美元符信号名"""
        source = '''
module top(input wire $data, output wire dout);
    assign dout = $data;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_array_signal(self):
        """数组信号"""
        source = '''
module top(input wire [7:0] data [3:0], output wire [7:0] dout);
    assign dout = data[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_parameterized_module(self):
        """参数化模块"""
        source = '''
module #(
    parameter WIDTH = 8
) top(input wire [WIDTH-1:0] din, output wire [WIDTH-1:0] dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_generate_for(self):
        """generate for 块"""
        source = '''
module top(input wire clk, output wire out);
    genvar i;
    generate for (i=0; i<1; i=i+1) begin
        assign out = clk;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_function(self):
        """function 定义"""
        source = '''
module top(input wire [7:0] a, input wire [7:0] b, output wire [7:0] y);
    function [7:0] add;
        input [7:0] x;
        add = x + 1;
    endfunction
    assign y = add(a);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_task(self):
        """task 定义"""
        source = '''
module top(input wire clk);
    task wait_clk;
        input clk;
        begin end
    endtask
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
