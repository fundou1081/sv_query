#==============================================================================
# test_generate.py - generate 语句测试
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestGenerate(unittest.TestCase):
    """generate 语句测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_generate_for(self):
        """[Gen] generate for"""
        source = '''
module top(
    input wire clk,
    output wire [3:0] out
);
    genvar i;
    wire [3:0] tmp [0:3];
    generate
        for (i = 0; i < 4; i = i + 1) begin : GEN
            assign tmp[i] = clk;
        end
    endgenerate

    assign out = tmp[0];
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')

        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])

    def test_generate_if(self):
        """[Gen] generate if"""
        source = '''
module top(input wire cond, input wire a, output wire y);
    generate if (1'b1) begin : GEN
        assign y = a;
    endgenerate
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])

    def test_generate_case(self):
        """[Gen] generate case"""
        source = '''
module top(input [1:0] sel, input a, input b, output wire y);
    generate case (1'b1)
        2'b00: assign y = a;
        default: assign y = b;
    endgenerate
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])

    def test_generate_nested(self):
        """[Gen] 嵌套 generate"""
        source = '''
module top(input clk, input [1:0] sel, output wire y);
    genvar i;
    generate
        for (i = 0; i < 1; i = i + 1) begin : OUTER
            if (1'b1) begin : INNER
                assign y = clk;
            end
        end
    endgenerate
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])

    def test_generate_for_dynamic_bitselect(self):
        """[#8] generate-for 内动态位选必须产生 BIT_SELECT + DRIVER 边

        历史 bug: G2 计划 (06:33) 实测 generate-for 内 `acc[i]` 动态位选
        **不产生 BIT_SELECT 边** (节点 ID 是 'top.gen[0].acc[0]' 形式,
        regex 反推看不到)。#2 semantic API 修复了 BIT_SELECT 边, 但
        `acc[i] <= data_in` 的 DRIVER 边仍缺失 (generate always 块不被
        get_always_blocks 枚举 + genvar_ctx 不 substitute)。

        本测试断言三条:
        1. BIT_SELECT 边存在: acc[i] 展开后 acc[0..4] → acc
        2. DRIVER 边存在且 substitute: data_in → acc[0..3]
           (不是 data_in → acc[i])
        3. 无未 substitute 的 'acc[i]' 残留节点
        """
        source = '''
module top #(parameter N = 4) (input clk, input [3:0] data_in);
    logic [3:0] acc [0:N];
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen
            always_ff @(posedge clk) begin
                acc[i] <= data_in;
                acc[i+1] <= acc[i];
            end
        end
    endgenerate
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph(target_module='top')
        graph = tracer.get_graph()

        bit_select = []
        driver = []
        for u, v in graph.edges():
            te = graph.get_edge(u, v) if hasattr(graph, 'get_edge') else None
            if te is None:
                continue
            kd = str(getattr(te, 'kind', ''))
            if 'BIT_SELECT' in kd:
                bit_select.append((u, v))
            elif 'DRIVER' in kd:
                driver.append((u, v))

        # 1. BIT_SELECT: acc[0..4] → acc (≥4 条)
        self.assertGreaterEqual(len(bit_select), 4,
            f"generate-for 动态位选应有 BIT_SELECT 边, got {len(bit_select)}")
        # 2. DRIVER: data_in → acc[i] 应 substitute 成 acc[0..3], 不能有 acc[i] 残留
        data_in_drivers = [v for u, v in driver if u == 'top.data_in']
        self.assertGreaterEqual(len(data_in_drivers), 4,
            f"data_in 应驱动 acc[0..3], got {data_in_drivers}")
        self.assertNotIn('top.acc[i]', data_in_drivers,
            f"不应有未 substitute 的 acc[i] 残留: {data_in_drivers}")
        # 3. 节点: 无 'acc[i]' 残留
        node_ids = [n for n in graph.nodes() if 'acc' in n]
        self.assertNotIn('top.acc[i]', node_ids,
            f"不应有未 substitute 的 acc[i] 节点: {node_ids}")


if __name__ == '__main__':
    unittest.main()
