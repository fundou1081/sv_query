# test_covergroup_constraint_compare.py - Covergroup ↔ Constraint 一致性比对
# [铁律13] 金标准测试
# [铁律17] 强断言
#
# 核心问题:
#   1. constraint 约束的合法空间，covergroup bins 是否完整覆盖？
#   2. constraint 定义了非法组合，covergroup 是否定义了 illegal_bins？
#   3. 条件约束 (if/else) 产生的分支，covergroup 是否有 cross 覆盖？
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.covergroup_analyzer import CovergroupAnalyzer, CoverageGap
from trace.core.graph.covergroup_models import CovergroupInfo


def _build_all(source):
    """构建信号图 + 提取 covergroup"""
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    extractor = CovergroupExtractor({'test.sv': source})
    cgs = extractor.extract()
    return graph, tracer, cgs


def _find_covergroup(cgs, name):
    """按名称查找 covergroup"""
    for cg in cgs:
        if cg.name == name:
            return cg
    return None


def _find_coverpoint(cg, signal):
    """按信号名查找 coverpoint"""
    for cp in cg.coverpoints:
        if cp.signal == signal:
            return cp
    return None


def _analyze(graph, cgs):
    """执行一致性分析"""
    analyzer = CovergroupAnalyzer(graph, cgs)
    return analyzer.analyze()


# =========================================================================
# 测试用例
# =========================================================================

class TestBinsCoverage(unittest.TestCase):
    """测试 1: bins 覆盖 constraint 合法空间"""

    def test_bins_covers_constraint_range(self):
        """[金标准] bins 覆盖了 constraint 的完整范围

        constraint: addr inside {[0:255]}  (无限制)
        coverpoint: bins low={[0:127]}, high={[128:255]}

        期望: 无缺失 cross (无条件约束)
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c_addr { addr inside {[0:255]}; }
    covergroup cg;
        coverpoint addr {
            bins low  = {[0:127]};
            bins high = {[128:255]};
        }
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)
        gaps = _analyze(graph, cgs)
        # 无条件约束，无 cross，所以无缺失
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertEqual(len(cross_gaps), 0)

    def test_bins_partial_coverage(self):
        """[金标准] 无条件约束无 cross 告警

        constraint: addr inside {[0:200]}
        coverpoint: bins low={[0:100]}

        期望: 无 cross 告警 (无条件约束)
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c_addr { addr inside {[0:200]}; }
    covergroup cg;
        coverpoint addr {
            bins low = {[0:100]};
        }
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)
        gaps = _analyze(graph, cgs)
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertEqual(len(cross_gaps), 0)


class TestMissingIllegalBins(unittest.TestCase):
    """测试 2: 缺失的 illegal_bins"""

    def test_conditional_constraint_needs_illegal_bins(self):
        """[金标准] 条件约束 + cross 需要 illegal_bins

        constraint:
            if (mode == 0) { addr inside {[0:63]}; }
            else { addr inside {[64:255]}; }

        covergroup:
            coverpoint addr { bins low, high }
            coverpoint mode
            cross addr, mode

        期望: 检测到缺失 illegal_bins
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    constraint c {
        if (mode == 0) { addr inside {[0:63]}; }
        else { addr inside {[64:255]}; }
    }
    covergroup cg;
        coverpoint addr {
            bins low  = {[0:63]};
            bins high = {[64:255]};
        }
        coverpoint mode;
        cross addr, mode;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)
        gaps = _analyze(graph, cgs)

        # 应该有 missing_illegal_bins 告警
        illegal_gaps = [g for g in gaps if g.kind == 'missing_illegal_bins']
        self.assertGreater(len(illegal_gaps), 0,
            "条件约束 + cross 应该有 illegal_bins 告警")


class TestMissingCross(unittest.TestCase):
    """测试 3: 缺失的 cross coverage"""

    def test_conditional_constraint_needs_cross(self):
        """[金标准] 条件约束的变量需要 cross

        constraint:
            if (mode == 0) { addr < 64; }

        covergroup:
            coverpoint addr;
            coverpoint mode;
            ❌ 缺少 cross addr, mode

        期望: 检测到 mode 和 addr 应该有 cross
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    constraint c {
        if (mode == 0) { addr inside {[0:63]}; }
    }
    covergroup cg;
        coverpoint addr;
        coverpoint mode;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)
        gaps = _analyze(graph, cgs)

        # 应该有 missing_cross 告警
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertGreater(len(cross_gaps), 0,
            "条件约束的变量应该有 cross")
        # 检查涉及的变量
        gap_vars = cross_gaps[0].variable
        self.assertIn('mode', gap_vars)
        self.assertIn('addr', gap_vars)

    def test_cross_exists_no_warning(self):
        """[金标准] 已有 cross 时不告警

        constraint:
            if (mode == 0) { addr < 64; }

        covergroup:
            coverpoint addr;
            coverpoint mode;
            cross addr, mode;  ✅

        期望: 无缺失 cross 告警
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    constraint c {
        if (mode == 0) { addr inside {[0:63]}; }
    }
    covergroup cg;
        coverpoint addr;
        coverpoint mode;
        cross addr, mode;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)
        gaps = _analyze(graph, cgs)

        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertEqual(len(cross_gaps), 0,
            "已有 cross 时不应告警")


class TestIntegration(unittest.TestCase):
    """集成测试: 完整的 covergroup ↔ constraint 比对报告"""

    def test_full_report(self):
        """[金标准] 完整比对报告

        场景: 有条件约束、cross 存在、缺少 data x mode cross
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    rand bit [7:0] data;
    constraint c_mode {
        if (mode == 0) { addr inside {[0:63]}; data < 128; }
        else { addr inside {[64:255]}; data >= 128; }
    }
    covergroup cg;
        coverpoint addr {
            bins low  = {[0:63]};
            bins high = {[64:255]};
        }
        coverpoint data {
            bins small = {[0:127]};
            bins large = {[128:255]};
        }
        coverpoint mode;
        cross addr, mode;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)
        cg = _find_covergroup(cgs, 'cg')
        self.assertIsNotNone(cg)

        # 验证结构提取正确
        self.assertEqual(len(cg.coverpoints), 3)
        self.assertGreaterEqual(len(cg.crosses), 1)

        # 执行分析
        gaps = _analyze(graph, cgs)

        # 应该有 missing_cross (data x mode)
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertGreater(len(cross_gaps), 0,
            "data 和 mode 有条件约束关系，应该有 cross 告警")

        # 应该有 missing_illegal_bins
        illegal_gaps = [g for g in gaps if g.kind == 'missing_illegal_bins']
        # 条件约束 + cross (addr, mode) 存在，应该检查 illegal_bins
        self.assertGreater(len(illegal_gaps), 0,
            "条件约束 + cross 应该有 illegal_bins 告警")


if __name__ == '__main__':
    unittest.main()
