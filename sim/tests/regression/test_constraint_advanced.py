# test_constraint_advanced.py - Constraint 语法缺口补充测试
# [iter_062 2026-08-29] 按 TEST_MAP 功能域缺口分析补充:
# 高优先级缺口: soft / dist :/ / randc / solve 多变量 / 嵌套 foreach / not inside
#
# 策略: 验证提取器**现有行为** (语法被 pyslang 接受 + 图构建不崩溃 + 基础节点
#       生成); soft 语义 (求解器优先级) / dist 权重类型区分是工具缺口
#       (constraint_visitor 只识别 ExpressionConstraint), 记录在
#       EXTRACTION_COVERAGE.md, 不在本文件断言失败.
"""
Constraint 高级语法覆盖 (iter_062 补充):
1. soft 约束
2. dist :/ 范围权重
3. randc 周期随机变量
4. solve 多变量顺序
5. 嵌套 foreach
6. not inside
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


class TestConstraintAdvanced(unittest.TestCase):
    """Constraint 高级语法支持测试"""

    def test_soft_constraint(self):
        """[Golden] soft 约束 — 求解器软约束 (优先级最低, 尽量满足)

        pyslang 接受 soft; 提取器将其归入 ExpressionConstraint (不区分
        soft/硬约束 — 工具缺口, 记录在 EXTRACTION_COVERAGE).
        本测试验证: 图构建不崩溃 + 约束块节点生成.
        """
        source = '''class packet;
    rand bit [7:0] len;
    rand bit [3:0] prio;
    constraint c_soft {
        soft len == 64;
        soft prio == 0;
        prio < len;
    }
endclass
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet.c_soft', nodes, "soft 约束块应生成节点")
        exprs = [n for n in nodes if 'c_soft::expr' in str(n)]
        self.assertGreaterEqual(len(exprs), 3, "soft 约束表达式应被提取")

    def test_dist_range_weight(self):
        """[Golden] dist 范围权重 :/ — 范围内值均分权重

        与 := 不同, :/ 表示权重在范围内均分. pyslang 接受; 提取器归入
        ExpressionConstraint (不区分 := 与 :/ — 工具缺口).
        """
        source = '''class packet;
    rand bit [3:0] val;
    constraint c_weighted {
        val dist { 0 := 5, [1:3] :/ 1, 15 := 2 };
    }
endclass
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet.c_weighted', nodes, "dist 约束块应生成节点")
        exprs = [n for n in nodes if 'c_weighted::expr' in str(n)]
        self.assertGreaterEqual(len(exprs), 1, "dist 表达式应被提取")

    def test_randc_variable(self):
        """[Golden] randc 周期随机变量 — CLASS_PROPERTY 节点"""
        source = '''class packet;
    randc bit [1:0] mode;
    rand bit [3:0] len;
    constraint c_cycle { mode != 2'd3; }
endclass
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet.mode', nodes, "randc 变量应生成 CLASS_PROPERTY 节点")
        self.assertIn('packet.len', nodes, "rand 变量应生成节点")

    def test_solve_multi_var(self):
        """[Golden] solve a, b before c, d — 多变量顺序约束"""
        source = '''class packet;
    rand bit [3:0] a, b, c, d;
    constraint c_order {
        solve a, b before c, d;
        a + b < c + d;
    }
endclass
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet.c_order', nodes, "solve 多变量约束块应生成节点")
        self.assertIn('packet.c_order::solve_0', nodes, "solve-before 应生成 solve_0 节点")
        self.assertIn('packet.c_order::expr_1', nodes, "算术表达式应生成 expr 节点")

    def test_nested_foreach(self):
        """[Golden] 嵌套 foreach — foreach (m[i]) foreach (m[i][j])"""
        source = '''class matrix;
    rand bit [3:0] m [2][3];
    constraint c_2d {
        foreach (m[i])
            foreach (m[i][j])
                m[i][j] < 4 * i + j;
    }
endclass
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('matrix.c_2d', nodes, "嵌套 foreach 约束块应生成节点")
        self.assertIn('matrix.c_2d::foreach_0', nodes, "foreach 应生成 foreach_0 节点")
        self.assertIn('matrix.i', nodes, "foreach 循环变量应生成节点")

    def test_not_inside(self):
        """[Golden] not inside — 取反集合约束"""
        source = '''class packet;
    rand bit [7:0] val;
    rand bit [3:0] lo, hi;
    constraint c_not_in {
        val not inside { [lo:hi] };
        lo < hi;
    }
endclass
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        self.assertIn('packet.c_not_in', nodes, "not inside 约束块应生成节点")
        # 工具缺口 (iter_062): not inside 的表达式节点不生成 (与 inside 形态不同),
        # 记录在 EXTRACTION_COVERAGE — 这里只验证块 + 变量节点.
        self.assertIn('packet.val', nodes)
        self.assertIn('packet.lo', nodes)

    def test_this_and_pkg_ref(self):
        """[Golden] 约束内显式 this. 引用 + 跨包类"""
        source = '''package my_pkg;
    class base;
        rand int x;
        constraint c { this.x < 100; }
    endclass
endpackage
module top; endmodule'''
        graph = _build_graph(source)
        nodes = list(graph.nodes())
        # 节点名不带包前缀 (提取器按类名命名)
        self.assertIn('base.c', nodes, "包内类约束块应生成节点")
        self.assertIn('base.c::expr_0', nodes, "this.x 表达式应被提取")
        self.assertIn('base.this.x', nodes, "显式 this. 引用生成独立节点")


if __name__ == '__main__':
    unittest.main(verbosity=2)
