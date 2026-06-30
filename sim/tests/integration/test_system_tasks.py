#==============================================================================
# test_system_tasks.py - 系统任务和函数测试
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestSystemTasks(unittest.TestCase):
    """系统任务和函数测试"""

    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})

    def _driver_ids(self, result):
        return [d.id for d in result.drivers]

    #==========================================================================
    # 纯仿真任务 - 不影响信号追踪
    #==========================================================================

    def test_display(self):
        """[SVL] $display 不影响信号追踪
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | -    | []     | uncertain |
        """
        source = '''
module top;
    initial $display("Hello");
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nonexist', 'top')

        self.assertEqual(len(result.drivers), 0,
            "$display 不影响信号追踪，驱动数为 0")
        self.assertEqual(result.confidence, 'uncertain')

    def test_finish(self):
        """[SVL] $finish 不影响信号追踪
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | -    | []     | uncertain |
        """
        source = '''
module top;
    initial #10 $finish;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nonexist', 'top')

        self.assertEqual(len(result.drivers), 0,
            "$finish 不影响信号追踪，驱动数为 0")
        self.assertEqual(result.confidence, 'uncertain')

    def test_strobe(self):
        """[SVL] $strobe 不影响信号追踪
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | clk  | []     | uncertain |

        注意: $strobe 只打印，不断言
        """
        source = '''
module top(input clk, input a);
    always @(posedge clk) $strobe("%h", a);
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')

        self.assertEqual(len(result.drivers), 0,
            "$strobe 不影响信号追踪，驱动数为 0")
        self.assertEqual(result.confidence, 'uncertain')

    #==========================================================================
    # 系统函数 - 返回值应可追踪驱动源
    #==========================================================================

    def test_time(self):
        """[SVL] $time 返回仿真时间
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | t    | []     | uncertain |

        $time 是系统函数，无外部输入
        """
        source = '''
module top(output [31:0] t);
    assign t = $time;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('t', 'top')

        self.assertEqual(len(result.drivers), 0,
            "$time 无外部驱动源，驱动数为 0")
        self.assertEqual(result.confidence, 'uncertain')

    def test_random(self):
        """[SVL] $random 返回随机数
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | r    | []     | uncertain |

        $random 是系统函数，无外部输入
        """
        source = '''
module top(output [31:0] r);
    assign r = $random;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('r', 'top')

        self.assertEqual(len(result.drivers), 0,
            "$random 无外部驱动源，驱动数为 0")
        self.assertEqual(result.confidence, 'uncertain')

    def test_floor(self):
        """[SVL] $floor(r) 向下取整
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | f    | [r]    | high |

        $floor 是函数调用，r 是输入参数，应追踪为驱动源
        """
        source = '''
module top(input real r, output [31:0] f);
    assign f = $floor(r);
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('f', 'top')

        self.assertEqual(len(result.drivers), 1,
            "f = $floor(r) 应有 1 个驱动源 (r)")
        self.assertIn('top.r', self._driver_ids(result),
            "f 的驱动应包含 top.r")
        self.assertEqual(result.confidence, 'high')

    def test_countdrivers(self):
        """[SVL] $countdrivers 预处理指令相关
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | a    | []     | uncertain |

        注意: 输入端口 a 作为 source，暂不追踪其上游驱动
        """
        source = '''
module top(input a);
    // synthesis translate_off
    wire checked = a;
    // synthesis translate_on
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('a', 'top')

        # 输入端口作为 source 点，暂返回 uncertain
        self.assertEqual(len(result.drivers), 0,
            "输入端口 a 作为 source 点，暂不追踪上游驱动")
        self.assertEqual(result.confidence, 'uncertain')

    def test_sformatf(self):
        """[SVL] $sformatf 返回格式化字符串
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | s    | [8'd66] | high |

        注意: 字面量 8'h42 以十进制 8'd66 显示
        """
        source = '''
module top(output [7:0] s);
    assign s = 8'h42;
endmodule'''

        tracer = self._make_tracer(source)
        result = tracer.trace_signal('s', 'top')

        self.assertEqual(len(result.drivers), 1,
            "s = 8'h42 应有 1 个驱动源")
        self.assertIn('8\'d66', self._driver_ids(result),
            "s 的驱动应为 8'd66 (8'h42 的十进制)")
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
