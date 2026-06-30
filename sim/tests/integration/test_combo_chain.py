#==============================================================================
# test_combo_chain.py - always_comb 阻塞赋值链追踪
# [P0] 优先级最高
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestComboChain(unittest.TestCase):
    """always_comb 阻塞赋值链测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    #----------------------------------------------------------------------
    # [金标准] always_comb 基本功能
    #----------------------------------------------------------------------

    def test_combo_basic(self):
        """[Golden] 基础 always_comb"""
        # RTL: always_comb q = a & b;
        # 金标准: q 驱动 = a & b (阻塞赋值)
        source = '''
module top(
    input wire a,
    input wire b,
    output reg q
);
    always_comb begin
        q = a & b;
    end
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        # 有驱动
        self.assertGreater(len(result.drivers), 0)

    def test_combo_simple_assign(self):
        """[Golden] 简单阻塞赋值"""
        # RTL: always_comb q = din;
        source = '''
module top(
    input wire din,
    output reg q
);
    always_comb q = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.din', driver_ids)

    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------

    def test_combo_empty_block(self):
        """[Boundary] 空 always_comb"""
        source = '''
module top(
    input wire din,
    output reg q
);
    always_comb begin
        // empty
    end
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')

        # 空块无驱动
        self.assertEqual(len(result.drivers), 0)

    def test_combo_multiple_stmts(self):
        """[Boundary] 多个阻塞赋值"""
        source = '''
module top(
    input wire a,
    input wire b,
    output reg y,
    output reg z
);
    always_comb begin
        y = a & b;
        z = a | b;
    end
endmodule'''

        tracer = self._make_tracer(source)

        result_y = tracer.trace_signal('y', 'top')
        result_z = tracer.trace_signal('z', 'top')

        self.assertIn('top.a', [d.id for d in result_y.drivers])
        self.assertIn('top.a', [d.id for d in result_z.drivers])

    #----------------------------------------------------------------------
    # [错误处理]
    #----------------------------------------------------------------------

    def test_combo_invalid_signal(self):
        """[Error] 不存在信号"""
        source = '''
module top(
    input wire din,
    output reg q
);
    always_comb q = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('invalid_signal', 'top')

        # 不存在信号应返回 uncertain
        self.assertEqual(result.confidence, 'uncertain')

    def test_combo_invalid_module(self):
        """[Error] 不存在模块"""
        source = '''
module top(
    input wire din,
    output reg q
);
    always_comb q = din;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'invalid_module')

        self.assertEqual(result.confidence, 'uncertain')


if __name__ == '__main__':
    unittest.main()
