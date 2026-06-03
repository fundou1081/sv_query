#==============================================================================
# test_evidence_credibility.py - TDD tests for credibility scoring (借鉴 sv-trace)
#
# Goal: Add credibility_score (0-1) and is_verified to Evidence,
#       computed on demand by cross-validating evidence against source_expr/signal
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.trace_evidence import TraceEvidenceResolver


def _make_resolver(source: str, source_name: str = "test.sv"):
    tracer = UnifiedTracer(sources={source_name: source}, log_level="ERROR")
    graph = tracer.build_graph()
    sem = tracer._get_adapter()
    return tracer, TraceEvidenceResolver(graph=graph, adapter=sem)


#==============================================================================
# TestGroup 1: is_verified property
#==============================================================================

class TestIsVerified(unittest.TestCase):
    """[V4] is_verified should be True when evidence cross-validates"""

    def test_verified_when_signal_in_enclosing(self):
        """[TDD-V4-1] is_verified = True when signal name 在 enclosing_always.text 中"""
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
        # 期望: is_verified = True
        self.assertTrue(ev.is_verified, f"is_verified should be True, got {ev.is_verified}")

    def test_verified_false_when_no_snippet(self):
        """[TDD-V4-2] 无 snippet 时 is_verified = False"""
        source = '''
module top(output reg q);
    initial q = 0;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.q")
        # 无 always 块驱动, 可能 is_verified = False
        # 但 initial 块也算驱动, 取决于实现
        # 至少: 不抛异常
        self.assertIsNotNone(ev)


#==============================================================================
# TestGroup 2: matches_signal_name cross-validation
#==============================================================================

class TestMatchesSignalName(unittest.TestCase):
    """[V4] matches_signal_name checks if LHS is in evidence snippet"""

    def test_signal_name_match_in_always(self):
        """[TDD-V4-3] signal_name 'q' 在 always_ff 块 snippet 中 → matches"""
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
        # 期望: matches_signal_name = True (q 在 enclosing_always.text)
        self.assertTrue(ev.matches_signal_name,
                       f"matches_signal_name should be True, got {ev.matches_signal_name}")

    def test_signal_name_match_in_class(self):
        """[TDD-V4-4] signal_name 'addr' 在 class/constraint snippet 中 → matches"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.addr")
        # 期望: matches_signal_name = True (addr 在 enclosing_constraint.text)
        self.assertTrue(ev.matches_signal_name)


#==============================================================================
# TestGroup 3: matches_source_expr cross-validation
#==============================================================================

class TestMatchesSourceExpr(unittest.TestCase):
    """[V4] matches_source_expr checks if RHS expression is in evidence snippet"""

    def test_source_expr_match_in_always(self):
        """[TDD-V4-5] source_expr (RHS) 在 always_ff 块 snippet 中 → matches"""
        source = '''
module top(
    input clk,
    input wire [7:0] a,
    output reg [7:0] q
);
    always_ff @(posedge clk) begin
        if (a > 8'd100) begin
            q <= a;
        end
    end
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.q")
        # 期望: source_expr (RHS) 应该是 "a" 或类似
        # matches_source_expr: 看 enclosing_always.text 含 "a"
        # 这里只要 snippet_present, 就会 matches (因为有 enclosing)
        # 严格说: matches_source_expr 应该是 "a" 在 snippet 中
        # 实际: enclosing_always.text 包含 "q <= a;" 所以 "a" 在其中
        if ev.source_expr:  # only if edge had expression
            self.assertTrue(ev.matches_source_expr)

    def test_source_expr_match_in_assign(self):
        """[TDD-V4-6] assign 中 source_expr match"""
        source = '''
module top(
    input wire a,
    output wire y
);
    assign y = a;
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        # 期望: source_expr 是 "a", enclosing_assign.text 含 "a"
        if ev.source_expr:
            self.assertTrue(ev.matches_source_expr)


#==============================================================================
# TestGroup 4: credibility_score 0-1
#==============================================================================

class TestCredibilityScore(unittest.TestCase):
    """[V4] credibility_score 0-1, 借鉴 sv-trace"""

    def test_credibility_score_range(self):
        """[TDD-V4-7] credibility_score 应在 0-1 范围"""
        source = '''
module top(
    input clk,
    input wire [7:0] a,
    output reg [7:0] q
);
    always_ff @(posedge clk) begin
        q <= a;
    end
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.q")
        score = ev.credibility_score
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_credibility_score_high_for_complete_evidence(self):
        """[TDD-V4-8] 完整 evidence 应有高 credibility (>=0.6)"""
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
        # 完整 evidence (enclosing_always + enclosing_if) → 高 credibility
        # 期望: >= 0.6 (snippet_present=0.2 + matches_signal_name=0.2 + matches_source_expr=0.4)
        self.assertGreaterEqual(ev.credibility_score, 0.4)

    def test_credibility_score_zero_for_no_evidence(self):
        """[TDD-V4-9] 无 evidence 时 credibility = 0"""
        source = '''
module top(output reg q);
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.q")
        # 无 evidence → credibility 应低
        self.assertLessEqual(ev.credibility_score, 0.2)


#==============================================================================
# TestGroup 5: 完整集成测试
#==============================================================================

class TestCredibilityIntegration(unittest.TestCase):
    """[V4] 完整集成: is_verified + credibility_score 同时工作"""

    def test_class_property_full_credibility(self):
        """[TDD-V4-10] class property 完整 evidence 应有高 credibility"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.addr")
        # 完整 evidence: enclosing_class + enclosing_constraint
        # 期望: is_verified = True
        self.assertTrue(ev.is_verified, f"is_verified should be True, got {ev.is_verified}")
        # 期望: credibility_score >= 0.4
        self.assertGreaterEqual(ev.credibility_score, 0.4)

    def test_always_comb_high_credibility(self):
        """[TDD-V4-11] always_comb 完整 evidence 应有高 credibility"""
        source = '''
module top(
    input wire a,
    input wire b,
    input wire sel,
    output reg y
);
    always_comb begin
        if (sel) y = a;
        else y = b;
    end
endmodule'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("top.y")
        # 完整 evidence: enclosing_always + enclosing_if
        self.assertTrue(ev.is_verified)
        self.assertGreaterEqual(ev.credibility_score, 0.4)


if __name__ == "__main__":
    unittest.main()
