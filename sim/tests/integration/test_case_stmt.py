#==============================================================================
# test_case_stmt.py - case 语句测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestCaseStmt(unittest.TestCase):
    """case 语句测试"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_case_simple(self):
        """[Case] 基础 case: case (sel) 2'b00: q=a; 2'b01: q=b;
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a, b] | high |
        """
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    input wire b,
    output reg q
);
    always_comb case (sel)
        2'b00:   q = a;
        2'b01:   q = b;
    endcase
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 2,
            "case (sel) q=a/b 应有 2 个驱动源 (a, b)")
        ids = self._driver_ids(result)
        self.assertIn('top.a', ids, "q 的驱动应包含 top.a")
        self.assertIn('top.b', ids, "q 的驱动应包含 top.b")
        self.assertEqual(result.confidence, 'high')

    def test_casex(self):
        """[Case] casex (X作为无关位) 在 always_comb 中
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a]    | high |
        """
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    output reg q
);
    always_comb casex (sel)
        2'b00: q = a;
        2'bx1: q = a;
    endcase
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 1,
            "casex q = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "q 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')

    def test_casez(self):
        """[Case] casez (Z作为无关位) 在 always_comb 中
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a]    | high |
        """
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    output reg q
);
    always_comb casez (sel)
        2'b00: q = a;
        2'bz1: q = a;
    endcase
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 1,
            "casez q = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "q 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')

    def test_priority_case(self):
        """[Case] priority case
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a]    | high |
        """
        source = '''
module top(
    input wire [2:0] sel,
    input wire a,
    output reg q
);
    always_comb priority case (1'b1)
        sel[2]: q = a;
        sel[1]: q = a;
    endcase
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 1,
            "priority case q = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "q 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')

    def test_unique_case(self):
        """[Case] unique case
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [a]    | high |
        """
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    output reg q
);
    always_comb unique case (sel)
        2'b00: q = a;
        2'b01: q = a;
    endcase
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 1,
            "unique case q = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', self._driver_ids(result),
            "q 的驱动应包含 top.a")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
