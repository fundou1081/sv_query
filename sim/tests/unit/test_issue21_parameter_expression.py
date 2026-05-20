#==============================================================================
# test_issue21_parameter_expression.py - Issue 21: 参数表达式未展开
#==============================================================================
# [铁律7] 金标准测试
#
# Issue 21: 参数表达式未展开
#   现象: 节点名包含 ADDR_WIDTH-1
#   期望: 节点名应该是已展开的值 (如 in[2], 因为 ADDR_WIDTH=3)
#
# 根因: 节点创建时使用原始信号名,未替换参数引用
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestIssue21ParameterExpression(unittest.TestCase):
    """Issue 21: 参数表达式未展开"""

    def _make_tracer(self, source):
        """辅助: 创建 tracer"""
        return UnifiedTracer(sources={'test.sv': source}, log_level='ERROR')

    #----------------------------------------------------------------------
    # 金标准测试
    #----------------------------------------------------------------------

    def test_parameter_expression_in_node_name(self):
        """[Golden] 参数表达式应在节点名中展开
        
        源: input wire [ADDR_WIDTH-1:0] in (ADDR_WIDTH=3)
        当前: dual_clock_fifo.in[ADDR_WIDTH-1]
        期望: dual_clock_fifo.in[2] 或 dual_clock_fifo.in (带有正确的位宽信息)
        
        验证: 节点名不应包含未展开的参数名 ADDR_WIDTH
        """
        source = '''
module dual_clock_fifo #(
    parameter ADDR_WIDTH = 3
)(
    input wire clk,
    input wire [ADDR_WIDTH-1:0] in,
    output reg [ADDR_WIDTH-1:0] out
);
endmodule
'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()

        node_ids = [nid for nid in graph.nodes()]
        
        # 检查是否有节点名包含 ADDR_WIDTH (未展开)
        for nid in node_ids:
            self.assertNotIn(
                'ADDR_WIDTH',
                nid,
                f"节点名不应包含未展开的参数 ADDR_WIDTH: {nid}"
            )

    def test_parameter_expression_in_internal_signal(self):
        """[Golden] 内部信号的参数位宽表达式应展开
        
        内部信号 reg [ADDR_WIDTH-1:0] wr_addr (ADDR_WIDTH=3)
        当前: dual_clock_fifo.wr_addr[ADDR_WIDTH-1] (在函数返回值中)
        期望: dual_clock_fifo.wr_addr (带有位宽信息) 或 wr_addr[2]
        
        注意: 此测试验证参数表达式不应出现在节点名中
        函数返回值节点创建是另一个问题，此处只检查参数表达式展开
        """
        source = '''
module dual_clock_fifo #(
    parameter ADDR_WIDTH = 3
)(
    input wire clk
);
reg [ADDR_WIDTH-1:0] wr_addr;

function [ADDR_WIDTH-1:0] gray_conv;
input [ADDR_WIDTH-1:0] in;
begin
    gray_conv = {in[ADDR_WIDTH-1], in[ADDR_WIDTH-2:0] ^ in[ADDR_WIDTH-1:1]};
end
endfunction
endmodule
'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()

        node_ids = [nid for nid in graph.nodes()]
        
        # 内部信号 wr_addr 应该存在
        self.assertIn('dual_clock_fifo.wr_addr', node_ids)
        
        # 检查是否有节点名包含未展开的 ADDR_WIDTH
        for nid in node_ids:
            self.assertNotIn(
                'ADDR_WIDTH',
                nid,
                f"节点名不应包含未展开的参数 ADDR_WIDTH: {nid}"
            )

    def test_parameter_expression_in_function_bit_select(self):
        """[Golden] 函数内位选择表达式参数应展开
        
        函数返回值灰Conv = {in[ADDR_WIDTH-1], ...} (ADDR_WIDTH=3)
        期望: in[2] 而非 in[ADDR_WIDTH-1]
        
        验证位宽提取时参数被正确解析
        """
        source = '''
module dual_clock_fifo #(
    parameter ADDR_WIDTH = 3
)(
    input wire clk
);
function [ADDR_WIDTH-1:0] gray_conv;
input [ADDR_WIDTH-1:0] in;
begin
    gray_conv = in[ADDR_WIDTH-1];
end
endfunction
endmodule
'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()

        node_ids = [nid for nid in graph.nodes()]
        
        # 检查是否有节点名包含未展开的 ADDR_WIDTH
        for nid in node_ids:
            self.assertNotIn(
                'ADDR_WIDTH',
                nid,
                f"节点名不应包含未展开的参数 ADDR_WIDTH: {nid}"
            )


if __name__ == '__main__':
    unittest.main()