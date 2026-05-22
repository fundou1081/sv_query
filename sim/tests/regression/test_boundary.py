#==============================================================================
# test_boundary.py - 边界条件回归测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
# 铁律18: 负面测试原则 - 每个功能必须有对应的错误/边界测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestBoundary(unittest.TestCase):
    """边界条件回归测试"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_empty_module(self):
        """[Boundary] 空模块不崩溃
        RTL: module top(); endmodule
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | -    | []     | uncertain |
        """
        source = '''
module top();
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nonexist', 'top')
        
        self.assertEqual(len(result.drivers), 0,
            "空 module 无信号，驱动数应为 0")
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_single_signal(self):
        """[Boundary] 单信号模块
        RTL: assign out = 1'b0;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | out  | [1'b0] | high |
        """
        source = '''
module top(
    output wire out
);
    assign out = 1'b0;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "out = 1'b0 应有 1 个驱动源")
        self.assertIn('1\'b0', self._driver_ids(result),
            "out 的驱动应为字面量 1'b0")
        self.assertEqual(result.confidence, 'high')
    
    def test_orphan_signal(self):
        """[Boundary] 孤立信号 (无驱动)
        RTL: dout 无连接
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | []     | uncertain |
        """
        source = '''
module top(
    input wire din,
    output wire dout
);
    // dout unconnected
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertEqual(len(result.drivers), 0,
            "孤立信号 dout 无驱动源，驱动数应为 0")
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_multi_bit_single(self):
        """[Boundary] 多比特单线
        RTL: assign dout = din;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [din]  | high |
        """
        source = '''
module top(
    input wire [3:0] din,
    output wire [3:0] dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "dout = din 应有 1 个驱动源 (din)")
        self.assertIn('top.din', self._driver_ids(result),
            "dout 的驱动应包含 top.din")
        self.assertEqual(result.confidence, 'high')
    
    #----------------------------------------------------------------------
    # [错误处理]
    #----------------------------------------------------------------------
    
    def test_invalid_signal_name(self):
        """[Error] 无效信号名应返回 uncertain
        金标准:
        | 信号 | 置信度 |
        |------|--------|
        | invalid_@@@ | uncertain |
        """
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('invalid_@@@', 'top')
        
        self.assertEqual(len(result.drivers), 0,
            "无效信号名驱动数应为 0")
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_signal_in_invalid_module(self):
        """[Error] 无效模块名应返回 uncertain
        金标准:
        | 模块 | 置信度 |
        |------|--------|
        | invalid_module | uncertain |
        """
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'invalid_module')
        
        self.assertEqual(len(result.drivers), 0,
            "无效模块驱动数应为 0")
        self.assertEqual(result.confidence, 'uncertain')
    
    def test_empty_signal_name(self):
        """[Error] 空信号名不应崩溃
        金标准: 应返回 uncertain 而非崩溃
        """
        source = '''
module top(
    input wire din,
    output wire dout
);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        
        try:
            result = tracer.trace_signal('', 'top')
            self.assertEqual(len(result.drivers), 0,
                "空信号名驱动数应为 0")
            self.assertEqual(result.confidence, 'uncertain')
        except Exception as e:
            self.fail(f"Empty signal name caused crash: {e}")
    
    #----------------------------------------------------------------------
    # [压力测试]
    #----------------------------------------------------------------------
    
    def test_many_signals(self):
        """[Stress] 大量信号 (100个)
        金标准: w50 = d50，1 个驱动
        """
        source = 'module top('
        for i in range(100):
            source += f'input wire d{i},'
        source = source.rstrip(',') + ');'
        for i in range(100):
            source += f'wire w{i}; assign w{i} = d{i};'
        source += 'endmodule'
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('w50', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "w50 = d50 应有 1 个驱动源")
        self.assertIn('top.d50', self._driver_ids(result),
            "w50 的驱动应包含 top.d50")
        self.assertEqual(result.confidence, 'high')
    
    def test_deep_chain(self):
        """[Stress] 深链 (100 级)
        金标准: q0 <- w99 <- w98 <- ... <- w0 <- d0
        """
        source = 'module top(input wire d0, output wire q0);'
        for i in range(100):
            source += f'wire w{i}; assign w{i} = '
            if i == 0:
                source += 'd0;'
            else:
                source += f'w{i-1};'
        source += 'assign q0 = w99;endmodule'
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q0', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1,
            "深链应有至少 1 个驱动源")
        self.assertIn('top.w99', self._driver_ids(result),
            "q0 的驱动应包含最终驱动源 top.w99")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()


class TestBoundaryExtensive(unittest.TestCase):
    """扩展边界测试"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    def test_signal_without_module_prefix(self):
        """[Ext] 不带模块前缀查询
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | []     | uncertain |
        
        注意: [已知限制] 当前实现要求必须指定模块名
        """
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout')
        
        # [已知限制] 当前实现要求必须指定模块名
        self.assertEqual(len(result.drivers), 0,
            "[已知限制] 不带模块名查询暂返回 uncertain")
    
    def test_case_sensitive_signal(self):
        """[Ext] 大小写敏感
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | Din  | []     | uncertain |
        
        注意: [已知限制] 大小写敏感暂未完全支持
        """
        source = '''
module top(input wire Din, input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('Din', 'top')
        
        # [已知限制] 大小写敏感暂未完全支持
        self.assertEqual(len(result.drivers), 0,
            "[已知限制] 大小写敏感暂未完全支持")
    
    def test_underscore_in_name(self):
        """[Ext] 下划线信号名
        RTL: assign d_o = s_i;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | d_o  | [s_i]  | high |
        """
        source = '''
module top(input wire s_i, output wire d_o);
    assign d_o = s_i;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('d_o', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "d_o = s_i 应有 1 个驱动源")
        self.assertIn('top.s_i', self._driver_ids(result),
            "d_o 的驱动应包含 top.s_i")
        self.assertEqual(result.confidence, 'high')
    
    def test_dollar_in_name(self):
        """[Ext] 美元符信号名
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | []     | uncertain |
        
        注意: [已知限制] $data 暂未支持
        """
        source = '''
module top(input wire $data, output wire dout);
    assign dout = $data;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        # [已知限制] 美元符信号名暂未支持
        self.assertEqual(len(result.drivers), 0,
            "[已知限制] 美元符信号名暂未支持")
    
    def test_array_signal(self):
        """[Ext] 数组信号
        RTL: assign dout = data[0];
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | [data[0]] | high |
        """
        source = '''
module top(input wire [7:0] data [3:0], output wire [7:0] dout);
    assign dout = data[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "dout = data[0] 应有 1 个驱动源")
        self.assertIn('top.data[0]', self._driver_ids(result),
            "dout 的驱动应包含 top.data[0]")
        self.assertEqual(result.confidence, 'high')
    
    def test_parameterized_module(self):
        """[Ext] 参数化模块
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | dout | []     | uncertain |
        
        注意: [已知限制] 参数化模块暂未完全支持
        """
        source = '''
module #(
    parameter WIDTH = 8
) top(input wire [WIDTH-1:0] din, output wire [WIDTH-1:0] dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        # [已知限制] 参数化模块暂未完全支持
        self.assertEqual(len(result.drivers), 0,
            "[已知限制] 参数化模块暂未完全支持")
        self.assertEqual(result.confidence, 'uncertain',
            "[已知限制] 参数化模块暂未完全支持，置信度为 uncertain")
    
    def test_generate_for(self):
        """[Ext] generate for 块
        RTL: assign out = clk;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | out  | [clk]  | high |
        """
        source = '''
module top(input wire clk, output wire out);
    genvar i;
    generate for (i=0; i<1; i=i+1) begin
        assign out = clk;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "generate for 块中 out = clk 应有 1 个驱动源")
        self.assertIn('top.clk', self._driver_ids(result),
            "out 的驱动应包含 top.clk")
        self.assertEqual(result.confidence, 'high')
    
    def test_function(self):
        """[Ext] function 定义和调用
        RTL: assign y = add(a);
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | y    | [add, a] | high |
        
        注意: function 调用 add 和参数 a 都是驱动源
        """
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
        
        self.assertEqual(len(result.drivers), 2,
            "y = add(a) 应有 2 个驱动源 (add, a)")
        ids = self._driver_ids(result)
        self.assertIn('top.add', ids, "y 的驱动应包含 top.add")
        self.assertIn('top.a', ids, "y 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')
    
    def test_task(self):
        """[Ext] task 定义
        金标准: task 不影响信号追踪
        """
        source = '''
module top(input wire clk);
    task wait_clk;
        input clk;
        begin end
    endtask
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')
        
        self.assertIsNotNone(result,
            "task 不崩溃应返回结果")


if __name__ == '__main__':
    unittest.main()