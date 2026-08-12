# test_generate_enhanced.py - Generate 增强金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Generate 增强语法:
1. generate if/else 块内信号追踪
2. generate for 循环内信号追踪
3. generate case 信号追踪
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestGenerateEnhanced(unittest.TestCase):
    """Generate 增强测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_generate_if_else_signal_tracking(self):
        """[Golden] generate if/else 块内信号追踪 (Plan F1.3 2026-08-12 修复)

        RTL with runtime parameter:
        module top #(parameter COND = 1) (input a, b, output y);
            generate
                if (COND) begin : gen_true
                    assign y = a;
                end else begin : gen_false
                    assign y = b;
                end
            endgenerate
        endmodule

        预期:
        - COND=1 → 只 instantiate gen_true: a -> y 存在, b -> y 不存在
        - COND=0 → 只 instantiate gen_false: b -> y 存在, a -> y 不存在

        之前错误源码用 `if (1'b1)` (编译期常量), pyslang 正确 instantiate
        只 gen_true, gen_false.isUninstantiated=True. Plan F1 增 isUninstantiated
        filter (case30/31 依赖) 后, b -> y 不再出现 — 暴露了测试源码的逻辑错误.
        """
        source_template = '''module top #(parameter COND = 1) (input a, b, output y);
    generate
        if (COND) begin : gen_true
            assign y = a;
        end else begin : gen_false
            assign y = b;
        end
    endgenerate
endmodule'''

        # --- COND=1: 只 gen_true active ---
        source_true = source_template.replace('parameter COND = 1', 'parameter COND = 1')
        tracer = self._make_tracer(source_true)
        tracer.build_graph()
        edges = list(tracer.get_graph().edges())
        has_a_y = any('a' in edge[0] and 'y' in edge[1] for edge in edges)
        has_b_y = any('b' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertTrue(has_a_y, f"COND=1: a -> y not found in {edges}")
        self.assertFalse(has_b_y, f"COND=1: b -> y should NOT appear (gen_false uninstantiated), got {edges}")

        # --- COND=0: 只 gen_false active ---
        source_false = source_template.replace('parameter COND = 1', 'parameter COND = 0')
        tracer = self._make_tracer(source_false)
        tracer.build_graph()
        edges = list(tracer.get_graph().edges())
        has_a_y = any('a' in edge[0] and 'y' in edge[1] for edge in edges)
        has_b_y = any('b' in edge[0] and 'y' in edge[1] for edge in edges)
        self.assertFalse(has_a_y, f"COND=0: a -> y should NOT appear (gen_true uninstantiated), got {edges}")
        self.assertTrue(has_b_y, f"COND=0: b -> y not found in {edges}")

    def test_generate_for_signal_tracking(self):
        """[Golden] generate for 循环内信号追踪

        RTL:
        module top(input [7:0] data_in, output [7:0] data_out);
            genvar i;
            generate
                for (i = 0; i < 8; i = i + 1) begin : gen_loop
                    assign data_out[i] = data_in[7-i];
                end
            endgenerate
        endmodule

        预期:
        - data_in -> data_out 驱动关系
        """
        source = '''module top(input [7:0] data_in, output [7:0] data_out);
    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_loop
            assign data_out[i] = data_in[7-i];
        end
    endgenerate
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())

        # 验证: data_in -> data_out
        has_edge = any('data_in' in edge[0] and 'data_out' in edge[1] for edge in edges)
        self.assertTrue(has_edge, f"data_in -> data_out not found in {edges}")

if __name__ == '__main__':
    unittest.main()
