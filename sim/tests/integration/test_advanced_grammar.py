#==============================================================================
# test_advanced_grammar.py - 高级语法测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestForLoopExtraction(unittest.TestCase):
    """for 循环语法"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    def test_generate_for(self):
        """[For] generate for 块: assign out[i] = clk
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | out  | [clk]  | high |
        """
        source = '''
module top(input clk, output [3:0] out);
    genvar i;
    generate
        for (i=0; i<4; i=i+1) begin : g
            assign out[i] = clk;
        end
    endgenerate
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')

        self.assertEqual(len(result.drivers), 1,
            "generate for out[i] = clk 应有 1 个驱动源 (clk)")
        self.assertIn('top.clk', self._driver_ids(result),
            "out 的驱动应包含 top.clk")
        self.assertEqual(result.confidence, 'high')

    def test_for_loop_in_always(self):
        """[For] always 中的 for 循环
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [data] | high |
        """
        source = '''
module top(input clk, input [7:0] data, output logic [7:0] q);
    integer i;
    always_ff @(posedge clk) begin
        for (i = 0; i < 8; i = i + 1) begin
            q[i] <= data[i];
        end
    end
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 1,
            "always_ff q[i] <= data[i] 应有 1 个驱动源 (data)")
        self.assertIn('top.data', self._driver_ids(result),
            "q 的驱动应包含 top.data")
        self.assertEqual(result.confidence, 'high')


class TestProceduralTimingExtraction(unittest.TestCase):
    """过程时序"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def test_wait(self):
        """[Timing] wait 语句不影响图构建
        金标准: wait 语句只做延时，不产生驱动关系
        """
        source = '''
module top(input req);
    always wait(req);
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph(),
            "wait 语句应能正常构建图")

    def test_always_begin_end(self):
        """[Timing] always begin end 块
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | q    | [d]    | high |
        """
        source = '''
module top(input clk, input d, output logic q);
    always @(posedge clk) begin
        q <= d;
    end
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        self.assertEqual(len(result.drivers), 1,
            "always @(posedge clk) q <= d 应有 1 个驱动源 (d)")
        self.assertIn('top.d', [d.id for d in result.drivers],
            "q 的驱动应包含 top.d")
        self.assertEqual(result.confidence, 'high')


class TestClockingBlockExtraction(unittest.TestCase):
    """clocking block"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def test_clocking_block(self):
        """[CB] clocking block 定义不影响图构建
        金标准: clocking block 只做时序建模，不产生驱动关系
        """
        source = '''
module top(input clk);
    clocking cb @(posedge clk);
        input logic data;
        output logic enable;
    endclocking
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph(),
            "clocking block 应能正常构建图")


class TestSequencePropertyExtraction(unittest.TestCase):
    """sequence/property (assertion)"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def test_sequence(self):
        """[Seq] sequence 定义不影响图构建
        金标准: sequence 只做 assertion 建模，不产生驱动关系
        """
        source = '''
module top(logic req, logic ack);
    sequence s1;
        req |-> ##1 ack;
    endsequence
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph(),
            "sequence 定义应能正常构建图")

    def test_property(self):
        """[Prop] property 定义不影响图构建
        金标准: property 只做 assertion 建模，不产生驱动关系
        """
        source = '''
module top(logic req, logic ack);
    property p1;
        req |-> ##1 ack;
    endproperty
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph(),
            "property 定义应能正常构建图")


if __name__ == '__main__':
    unittest.main()
