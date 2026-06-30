#==============================================================================
# test_signal_tracer.py - SignalTracer 单元测试
# [铁律7] 金标准测试
# [铁律10] 置信度检查
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind


class TestSignalTracer(unittest.TestCase):
    """SignalTracer 单元测试"""

    def _make_tracer(self, source):
        """辅助: 创建 tracer"""
        return UnifiedTracer(sources={'test.sv': source})

    #----------------------------------------------------------------------
    # 金标准测试
    #----------------------------------------------------------------------

    def test_assign_continous_drivers(self):
        """[Golden] assign 连续赋值 - 驱动追踪"""
        # RTL: assign data = din;
        # 金标准: data 驱动 = din
        source = '''
module top(input wire din, output wire data);
    assign data = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data', 'top')

        # [铁律10] 置信度必须标注
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])

        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.din', driver_ids)

    def test_assign_continous_loads(self):
        """[Golden] assign 连续赋值 - 负载追踪"""
        # RTL: assign data = din;
        # 金标准: din 负载 = data
        source = '''
module top(input wire din, output wire data);
    assign data = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('din', 'top')

        load_ids = [l.id for l in result.loads]
        self.assertIn('top.data', load_ids)

    def test_input_port_is_driver_source(self):
        """[Golden] 输入端口是驱动源"""
        # RTL: 无驱动源
        # 金标准: 输入端口应该有驱动
        source = '''
module top(input wire din, output wire data);
    assign data = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('din', 'top')

        # din 是输入端口，驱动列表应为空（无上游）
        self.assertEqual(len(result.drivers), 0)

    def test_confidence_high_when_drivers_found(self):
        """[Golden] 有驱动时置信度为 high"""
        source = '''
module top(input wire din, output wire data);
    assign data = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data', 'top')

        self.assertEqual(result.confidence, 'high')

    def test_confidence_uncertain_when_no_drivers(self):
        """[Golden] 无驱动时置信度为 uncertain"""
        source = '''
module top(input wire din, output wire data);
    assign data = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('din', 'top')

        self.assertEqual(result.confidence, 'uncertain')

    def test_signal_chain_has_root(self):
        """[Golden] SignalChain 必须有 root"""
        source = '''
module top(input wire din, output wire data);
    assign data = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data', 'top')

        self.assertEqual(result.root, 'top.data')

    def test_multiple_signals(self):
        """[Golden] 多信号追踪"""
        source = '''
module top(input wire a, input wire b, output wire y);
    assign y = a & b;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')

        # y 被 a 和 b 驱动
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
