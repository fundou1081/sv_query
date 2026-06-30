#==============================================================================
# test_assign_chain.py - assign 连续赋值链追踪
# [金标准] din -> data -> dout 完整路径
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestAssignChain(unittest.TestCase):
    """assign 链追踪测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    #----------------------------------------------------------------------
    # [金标准] din -> data -> dout
    #----------------------------------------------------------------------

    def test_assign_to_assign_chain(self):
        """[Golden] assign -> assign 链"""
        # RTL:
        #   assign data = din;
        #   assign dout = data;
        # 金标准:
        #   din 无驱动
        #   data 驱动: din
        #   dout 驱动: data

        source = '''
module top(
    input wire din,
    output wire data,
    output wire dout
);
    assign data = din;
    assign dout = data;
endmodule'''

        tracer = self._make_tracer(source)

        # din 无驱动
        result = tracer.trace_signal('din', 'top')
        self.assertEqual(len(result.drivers), 0)

        # data 驱动: din
        result = tracer.trace_signal('data', 'top')
        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.din', driver_ids)

        # dout 驱动: data
        result = tracer.trace_signal('dout', 'top')
        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.data', driver_ids)

    def test_fanout_chain(self):
        """[Golden] 单驱动多负载 (扇出)"""
        # RTL:
        #   assign data = din;
        #   assign q1 = data;
        #   assign q2 = data;
        # 金标准:
        #   data 负载: [q1, q2]

        source = '''
module top(
    input wire din,
    output wire q1,
    output wire q2
);
    wire data;
    assign data = din;
    assign q1 = data;
    assign q2 = data;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('data', 'top')

        load_ids = [l.id for l in result.loads]
        self.assertIn('top.q1', load_ids)
        self.assertIn('top.q2', load_ids)

    def test_three_stage_chain(self):
        """[Golden] 三级链"""
        # RTL: a -> b -> c -> d
        source = '''
module top(
    input wire a,
    output wire d
);
    wire b, c;
    assign b = a;
    assign c = b;
    assign d = c;
endmodule'''

        tracer = self._make_tracer(source)

        # 追溯 d 的驱动
        result = tracer.trace_signal('d', 'top')
        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.c', driver_ids)

        # 继续追溯 c
        result = tracer.trace_signal('c', 'top')
        self.assertIn('top.b', [d.id for d in result.drivers])

        # 继续追溯 b
        result = tracer.trace_signal('b', 'top')
        self.assertIn('top.a', [d.id for d in result.drivers])


if __name__ == '__main__':
    unittest.main()
