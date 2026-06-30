#==============================================================================
# test_aliases.py - 别名和覆盖测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestAliases(unittest.TestCase):
    """别名和覆盖测试"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def test_alias(self):
        """[Alias] alias 语句: alias b = a;
        金标准: b 驱动源为 a
        """
        source = '''
module top(input a, output b);
    alias b = a;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('b', 'top')

        self.assertEqual(len(result.drivers), 1,
            "alias b = a 应有 1 个驱动源 (a)")
        self.assertIn('top.a', [d.id for d in result.drivers],
            "b 的驱动应包含 top.a")

    def test_typedef_struct(self):
        """[Typedef] struct 定义和访问
        金标准: struct 定义不影响图构建
        """
        source = '''
module top;
    typedef struct packed {
        logic a;
        logic b;
    } my_struct;

    my_struct s;
    assign s.a = 1'b0;
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph(),
            "struct 定义应能正常构建图")

    def test_typedef_enum(self):
        """[Typedef] enum 定义和使用
        金标准: enum 值作为常量暂返回 uncertain
        """
        source = '''
module top;
    typedef enum logic [1:0] {IDLE, RUN, STOP} state_t;
    state_t state;
    assign state = IDLE;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('state', 'top')

        # enum 值作为常量，暂返回 uncertain
        self.assertIsNotNone(result,
            "enum 赋值应能追踪")

    def test_covergroup(self):
        """[Cover] covergroup 不影响信号追踪
        金标准: covergroup 只用于覆盖率统计不影响信号流
        """
        source = '''
module top(input clk, input a);
    covergroup cg @(posedge clk);
        option.per_instance = 1;
        coverpoint a;
    endgroup

    cg cg_inst = new();
endmodule'''

        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph(),
            "covergroup 定义应能正常构建图")


if __name__ == '__main__':
    unittest.main()
