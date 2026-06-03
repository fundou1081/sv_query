#==============================================================================
# test_evidence_assign_comb.py - TDD tests for evidence support on assign
# and always_comb statements
#
# Goal: TraceEvidenceResolver should produce evidence for:
#   1. `assign y = expr;` (continuous assign, no if condition)
#   2. `always_comb y = expr;` (combinational always block)
#   3. `always_comb if (cond) y = expr;` (combinational with if)
#   4. `assign y = sel ? a : b;` (ternary expression - not a ConditionalStatement)
#
# Existing behavior:
#   - always_ff: works (enclosing_always populated, kind = AlwaysFFBlock)
#   - always_comb: enclosing_if populated, but enclosing_always is None
#     (current code only checks "AlwaysFF" in kind)
#   - assign: NO evidence at all (no condition_ast, no enclosing_*)
#
# This test file follows TDD: tests are written FIRST, then implementation
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.trace_evidence import TraceEvidenceResolver, Evidence


def _make_resolver(source: str, source_name: str = "test.sv"):
    """Helper: build tracer + resolver from source string"""
    tracer = UnifiedTracer(sources={source_name: source}, log_level="ERROR")
    graph = tracer.build_graph()
    sem = tracer._get_adapter()
    return tracer, TraceEvidenceResolver(graph=graph, adapter=sem)


#==============================================================================
# TestGroup 1: assign statement evidence
#==============================================================================

class TestAssignEvidence(unittest.TestCase):
    """TDD: assign 连续赋值应该能拿到 evidence"""

    def test_simple_assign_has_source_text(self):
        """[TDD-1] 简单 assign y = a; 应有 source_text"""
        source = '''
module top(
    input wire a,
    output wire y
);
    assign y = a;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        # 期望: source_text 不为空, 包含赋值行
        self.assertIsNotNone(ev.source_text)
        self.assertIn("y", ev.source_text)
        self.assertIn("a", ev.source_text)

    def test_simple_assign_has_source_location(self):
        """[TDD-2] 简单 assign 应有正确的 source_location (行号)"""
        source = '''
module top(
    input wire a,
    output wire y
);
    assign y = a;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        self.assertIsNotNone(ev.source_location)
        # 第 6 行 (在 module 内部, 0-indexed file 从 1 开始)
        # file line 6 = "    assign y = a;"
        self.assertEqual(ev.source_location.line_start, 6)
        self.assertEqual(ev.source_location.file, "test.sv")

    def test_simple_assign_has_enclosing_chain(self):
        """[TDD-3] 简单 assign 应有 enclosing_chain (至少包含 continuous assign 节点)"""
        source = '''
module top(
    input wire a,
    output wire y
);
    assign y = a;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        # enclosing_chain 不应为空 - 至少应能 walk 到 ContinuousAssign
        self.assertGreater(len(ev.enclosing_chain), 0,
                          "enclosing_chain should not be empty for assign statement")

    def test_ternary_assign_source_text(self):
        """[TDD-4] 三元 assign y = sel ? a : b; source_text 应含完整表达式"""
        source = '''
module top(
    input wire a,
    input wire b,
    input wire sel,
    output wire y
);
    assign y = sel ? a : b;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        self.assertIsNotNone(ev.source_text)
        # 期望 source_text 含 sel, a, b
        self.assertIn("sel", ev.source_text)
        self.assertIn("a", ev.source_text)
        self.assertIn("b", ev.source_text)

    def test_multi_assign_evidence(self):
        """[TDD-5] 多个 assign 链: c <= a, y <= c, 应能各自解析"""
        source = '''
module top(
    input wire a,
    output wire y
);
    wire c;
    assign c = a;
    assign y = c;
endmodule'''
        _, resolver = _make_resolver(source)
        # c 驱动
        ev_c = resolver.resolve("top.c")
        self.assertIsNotNone(ev_c.source_text)
        # y 驱动
        ev_y = resolver.resolve("top.y")
        self.assertIsNotNone(ev_y.source_text)


#==============================================================================
# TestGroup 2: always_comb evidence
#==============================================================================

class TestAlwaysCombEvidence(unittest.TestCase):
    """TDD: always_comb 应有完整 evidence (含 enclosing_always)"""

    def test_always_comb_simple_has_enclosing_always(self):
        """[TDD-6] always_comb y = a; 应有 enclosing_always 字段"""
        source = '''
module top(
    input wire a,
    output reg y
);
    always_comb y = a;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        # 期望: enclosing_always 不再是 None (修复 always_comb 捕获)
        self.assertIsNotNone(ev.enclosing_always,
                            "always_comb should populate enclosing_always")
        # text 应含 "always_comb"
        self.assertIn("always_comb", ev.enclosing_always.text)

    def test_always_comb_with_if_has_both(self):
        """[TDD-7] always_comb if (sel) y = a; 应有 enclosing_always AND enclosing_if"""
        source = '''
module top(
    input wire sel,
    input wire a,
    output reg y
);
    always_comb begin
        if (sel) y = a;
    end
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        # both should be populated
        self.assertIsNotNone(ev.enclosing_always)
        self.assertIn("always_comb", ev.enclosing_always.text)
        self.assertIsNotNone(ev.enclosing_if)
        self.assertIn("if", ev.enclosing_if.text)

    def test_always_comb_if_else_full(self):
        """[TDD-8] always_comb if/else y = a/b; 完整证据"""
        source = '''
module top(
    input wire sel,
    input wire a,
    input wire b,
    output reg y
);
    always_comb begin
        if (sel) y = a;
        else y = b;
    end
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        self.assertIsNotNone(ev.source_text)
        self.assertIn("y", ev.source_text)
        # enclosing_always should contain the always_comb block
        self.assertIsNotNone(ev.enclosing_always)
        self.assertIn("always_comb", ev.enclosing_always.text)
        # enclosing_if should contain the if-else
        self.assertIsNotNone(ev.enclosing_if)
        self.assertIn("if", ev.enclosing_if.text)


#==============================================================================
# TestGroup 3: always_ff 回归测试 (确保新实现不破坏现有 always_ff 行为)
#==============================================================================

class TestAlwaysFfRegression(unittest.TestCase):
    """回归测试: always_ff 行为应该保持不变"""

    def test_always_ff_still_works(self):
        """[REG-1] always_ff 行为不变: enclosing_always 仍是 always_ff 块"""
        source = '''
module top(
    input clk,
    input wire [7:0] a,
    output reg [7:0] q
);
    always_ff @(posedge clk) begin
        if (a > 8'd100) begin
            q <= 8'hFF;
        end
    end
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.q")
        self.assertIsNotNone(ev.enclosing_always)
        self.assertIn("always_ff", ev.enclosing_always.text)
        self.assertIsNotNone(ev.enclosing_if)
        self.assertIn("if", ev.enclosing_if.text)


#==============================================================================
# TestGroup 4: chain mode 回归 (assign/always_comb 的 chain 追溯)
#==============================================================================

class TestChainAssignComb(unittest.TestCase):
    """Chain 模式应能追溯 assign 和 always_comb 的 driver"""

    def test_chain_through_assign(self):
        """[CHAIN-1] chain 模式能跨 assign 链追溯"""
        source = '''
module top(
    input wire a,
    output wire y
);
    wire c;
    assign c = a;
    assign y = c;
endmodule'''
        _, resolver = _make_resolver(source)
        chain = resolver.resolve_chain("top.y")
        # 期望 chain 不为空
        self.assertGreater(len(chain), 0)
        # 第一个 evidence 应是 y 自身
        self.assertEqual(chain[0].signal, "top.y")
        # source_text 不应为 None (这是 assign 链的关键)
        self.assertIsNotNone(chain[0].source_text)

    def test_chain_through_always_comb(self):
        """[CHAIN-2] chain 模式能跨 always_comb 链追溯"""
        source = '''
module top(
    input wire a,
    input wire b,
    input wire sel,
    output reg y
);
    reg c;
    always_comb c = sel ? a : b;
    always_comb y = c;
endmodule'''
        _, resolver = _make_resolver(source)
        chain = resolver.resolve_chain("top.y")
        self.assertGreater(len(chain), 0)
        # 第一个 evidence 应是 y 自身
        self.assertEqual(chain[0].signal, "top.y")
        # source_text 应是 always_comb 块内的赋值
        self.assertIsNotNone(chain[0].source_text)


if __name__ == "__main__":
    unittest.main()
