# test_module_synth_advanced.py - Module 可综合语法缺口补充测试
# [iter_062 2026-08-29] 按 TEST_MAP 功能域缺口分析 (module 域) 补充:
# 高优先级缺口: signed 类型与算术移位 / 复合赋值 / enum 状态机 case /
#               2D packed 数组 / defparam 参数覆盖 / 数组写索引
#
# 语法均已被 pyslang + 图构建接受 (iter_062 probe); 数组索引 DRIVER 边是
# 工具缺口 (EXTRACTION_COVERAGE #20), 相关测试只断言节点并记录.
"""
Module 可综合语法覆盖 (iter_062 补充):
1. signed 算术 + 算术移位 (>>> / <<<) + $signed
2. 复合赋值 (+= 等)
3. enum 类型 case 状态机
4. 2D packed 数组索引
5. defparam 参数覆盖 (与命名 override 双路径)
6. 数组写索引 mem[idx] <= data
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


def _build_graph(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    tracer.build_graph()
    return tracer.get_graph()


class TestModuleSynthesizable(unittest.TestCase):
    """可综合 RTL 语法支持测试"""

    def test_signed_arithmetic_shift(self):
        """[Golden] signed 类型 + 算术移位 >>> / <<<

        算术右移保留符号位, 与逻辑右移 >> 语义不同 — 现代 RTL 常见.
        """
        source = '''module top(input logic clk, input signed [7:0] a, b,
                   output logic signed [15:0] y, output logic [7:0] y2);
    assign y = a >>> 2;
    assign y2 = a <<< b;
endmodule'''
        graph = _build_graph(source)
        self.assertIn('top.a', list(graph.nodes()))
        self.assertIn('top.b', list(graph.nodes()))
        self.assertIn('top.y', list(graph.nodes()))
        edge = graph.get_edge('top.a', 'top.y')
        self.assertIsNotNone(edge, "算术右移应生成 a→y DRIVER 边")

    def test_compound_assign(self):
        """[Golden] 复合赋值 += 在 always_ff 内 (状态机计数器常见)"""
        source = '''module top(input logic clk, input logic [7:0] a,
                   output logic [7:0] cnt, output logic [7:0] cnt2);
    always_ff @(posedge clk) cnt += a;
    always_ff @(posedge clk) cnt2 <= cnt2 - 8'd1;
endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.cnt', nodes)
        self.assertIn('top.a', nodes)
        self.assertIn('top.cnt2', nodes, "递减复合赋值目标应存在")
        edge = graph.get_edge('top.a', 'top.cnt')
        self.assertIsNotNone(edge, "复合赋值 += 应生成 a→cnt DRIVER 边")

    def test_enum_case_state_machine(self):
        """[Golden] enum 类型 case 状态机 — typedef enum + case 分支

        状态机是 RTL 核心模式; enum 成员 (IDLE/RUN/DONE) 用于 case 标签.
        """
        source = '''typedef enum logic [1:0] {IDLE=0, RUN=1, DONE=2} state_t;
module top(input logic clk, input logic start,
           output logic [1:0] state);
    state_t cur, nxt;
    always_ff @(posedge clk) begin
        case (cur)
            IDLE: nxt = start ? RUN : IDLE;
            RUN:  nxt = DONE;
            DONE: nxt = IDLE;
        endcase
        state <= nxt;
    end
endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.cur', nodes, "enum 状态变量应生成节点")
        self.assertIn('top.nxt', nodes)
        self.assertIn('top.start', nodes)
        self.assertIn('top.nxt.ternary_start', nodes, "case 内三元应生成节点")
        # start 经三元节点驱动 nxt (start → ternary_start → nxt)
        edge = graph.get_edge('top.start', 'top.nxt.ternary_start')
        self.assertIsNotNone(edge, "case 内 start 应驱动 ternary 节点")
        edge2 = graph.get_edge('top.nxt.ternary_start', 'top.nxt')
        self.assertIsNotNone(edge2, "ternary 应驱动 nxt")

    def test_2d_packed_array(self):
        """[Golden] packed 2D 数组 — input [1:0][3:0] packed2d

        工具缺口 (iter_062): packed2d[0] 行访问不生成 DRIVER 边
        (数组索引边界, EXTRACTION_COVERAGE #20) — 只断言节点存在.
        """
        source = '''module top(input logic [1:0][3:0] packed2d, output logic [3:0] y);
    assign y = packed2d[0];
endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.packed2d', nodes, "2D packed 数组应生成节点")
        self.assertIn('top.y', nodes)

    def test_defparam_override(self):
        """[Golden] defparam 参数覆盖 + 命名 override 双路径

        defparam 是 Verilog-2001 旧语法, 生产 RTL (OpenTitan/pulp) 仍用.
        """
        source = '''module sub #(parameter W = 8) (input logic [W-1:0] d, output logic [W-1:0] q);
    assign q = d;
endmodule
module top;
    logic [31:0] d, q;
    sub u1(.d(d), .q(q));
    sub #(.W(16)) u2();
    defparam u1.W = 32;
endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.u1', nodes, "defparam 目标实例应存在")
        self.assertIn('top.u2', nodes, "命名 override 实例应存在")
        self.assertIn('sub.d', nodes, "参数化子模块端口应被提取")

    def test_array_write_index(self):
        """[Golden] 数组写索引 mem[idx] <= data — always_ff 动态索引写入

        工具缺口 (iter_062): mem[idx] <= data 写索引不生成 DRIVER 边
        (数组 LHS 索引写, EXTRACTION_COVERAGE #20) — 只断言节点存在.
        """
        source = '''module top(input logic clk, input logic [3:0] idx,
                   input logic [7:0] data, output logic [7:0] mem [0:15]);
    always_ff @(posedge clk)
        mem[idx] <= data;
endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.idx', nodes)
        self.assertIn('top.data', nodes)
        self.assertIn('top.mem', nodes, "数组应生成节点")

    def test_signed_cast(self):
        """[Golden] $signed / $unsigned 类型转换"""
        source = '''module top(input logic [7:0] a, b, output logic signed [15:0] y);
    assign y = a * $signed(b);
endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('top.a', nodes)
        self.assertIn('top.b', nodes)
        self.assertIn('top.y', nodes)
        edge = graph.get_edge('top.b', 'top.y')
        self.assertIsNotNone(edge, "$signed 转换乘法应生成 b→y DRIVER 边")


if __name__ == '__main__':
    unittest.main(verbosity=2)
