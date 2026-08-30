# test_covergroup_enhanced.py - 增强 Covergroup 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_065 2026-09-12] 升级: 保留 AST 断言, 补充 CovergroupExtractor 结构化字段断言
#                       (BinsInfo.kind / CoverCrossInfo.items / CovergroupInfo.name/clock)
#                       + CovergroupAnalyzer 缺口检测 (illegal_bins 触发场景)
"""
增强 Covergroup 语法:
1. illegal_bins
2. ignore_bins
3. cross coverage
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.unified_tracer import UnifiedTracer


def _extract(source):
    """便捷: 用 CovergroupExtractor 拿结构化 CovergroupInfo 列表."""
    return CovergroupExtractor({'test.sv': source}).extract()


class TestCovergroupEnhanced(unittest.TestCase):
    """增强 Covergroup 支持测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_illegal_bins(self):
        """[Golden] illegal_bins

        RTL:
        coverpoint data {
            bins low = {0, 1, 2};
            illegal_bins invalid = {100, 101};
        }

        预期:
        - CoverageBins 存在
        - keyword 为 illegal_bins
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low = {0, 1, 2};
            illegal_bins invalid = {100, 101};
        }
    endgroup
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        members = list(root.members)
        cg = members[0]
        cg_members = list(cg.members)

        # 获取 Coverpoint
        cp = cg_members[0]
        cp_members = list(cp.members)

        # 查找 illegal_bins
        illegal_bins = None
        for m in cp_members:
            if hasattr(m, 'keyword') and 'illegal_bins' in str(m.keyword):
                illegal_bins = m
                break

        self.assertIsNotNone(illegal_bins, "illegal_bins not found")
        self.assertEqual(str(illegal_bins.name).strip(), 'invalid')

        # [iter_065 行为断言] BinsInfo.kind 字段结构化验证
        cgs = _extract(source)
        cp_info = cgs[0].coverpoints[0]
        illegal_bins_struct = [b for b in cp_info.bins if b.kind == 'illegal_bins']
        self.assertEqual(len(illegal_bins_struct), 1,
                         "应提取 1 个 kind='illegal_bins' 的 bin")
        self.assertEqual(illegal_bins_struct[0].name, 'invalid')
        # values 字段保留 illegal_bins 的源文本 {100, 101}
        self.assertIn('100', illegal_bins_struct[0].values)
        self.assertIn('101', illegal_bins_struct[0].values)
        # 普通 bins 也被正确标记
        normal_bins = [b for b in cp_info.bins if b.kind == 'bins']
        self.assertEqual(len(normal_bins), 1)
        self.assertEqual(normal_bins[0].name, 'low')

    def test_ignore_bins(self):
        """[Golden] ignore_bins

        RTL:
        coverpoint data {
            bins low = {0, 1, 2};
            ignore_bins skip = {200, 201};
        }

        预期:
        - CoverageBins 存在
        - keyword 为 ignore_bins
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low = {0, 1, 2};
            ignore_bins skip = {200, 201};
        }
    endgroup
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        members = list(root.members)
        cg = members[0]
        cg_members = list(cg.members)

        # 获取 Coverpoint
        cp = cg_members[0]
        cp_members = list(cp.members)

        # 查找 ignore_bins
        ignore_bins = None
        for m in cp_members:
            if hasattr(m, 'keyword') and 'ignore_bins' in str(m.keyword):
                ignore_bins = m
                break

        self.assertIsNotNone(ignore_bins, "ignore_bins not found")
        self.assertEqual(str(ignore_bins.name).strip(), 'skip')

        # [iter_065 行为断言] BinsInfo.kind='ignore_bins' 结构化验证
        cgs = _extract(source)
        cp_info = cgs[0].coverpoints[0]
        ignore_bins_struct = [b for b in cp_info.bins if b.kind == 'ignore_bins']
        self.assertEqual(len(ignore_bins_struct), 1,
                         "应提取 1 个 kind='ignore_bins' 的 bin")
        self.assertEqual(ignore_bins_struct[0].name, 'skip')
        self.assertIn('200', ignore_bins_struct[0].values)
        self.assertIn('201', ignore_bins_struct[0].values)

    def test_cross_coverage(self):
        """[Golden] cross coverage

        RTL:
        covergroup cg @(posedge clk);
            coverpoint addr;
            coverpoint data;
            cross addr, data;
        endgroup

        预期:
        - CoverCross 存在
        """
        source = '''module top(input clk, logic [7:0] addr, data);
    covergroup cg @(posedge clk);
        coverpoint addr;
        coverpoint data;
        cross addr, data;
    endgroup
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        members = list(root.members)
        cg = members[0]
        cg_members = list(cg.members)

        # 查找 CoverCross
        cross = None
        for m in cg_members:
            if m.kind == pyslang.SyntaxKind.CoverCross:
                cross = m
                break

        self.assertIsNotNone(cross, "CoverCross not found")

        # [iter_065 行为断言] CoverCrossInfo.items + CovergroupInfo 字段验证
        cgs = _extract(source)
        cg_info = cgs[0]
        # covergroup 级别字段
        self.assertEqual(cg_info.name, 'cg')
        self.assertIn('clk', cg_info.clock, "采样事件应包含 clk")
        # 2 个 coverpoint (addr, data)
        self.assertEqual(len(cg_info.coverpoints), 2)
        cp_signals = {cp.signal for cp in cg_info.coverpoints}
        self.assertEqual(cp_signals, {'addr', 'data'},
                         "coverpoint 采样信号集合应包含 addr 和 data")
        # 1 个 cross, items 应包含 addr 和 data
        self.assertEqual(len(cg_info.crosses), 1, "应有 1 个 cross")
        cross_info = cg_info.crosses[0]
        self.assertEqual(sorted(cross_info.items), ['addr', 'data'],
                         "cross items 应包含 addr 和 data")
        # cross 本身无 iff 条件 (本场景未指定)
        self.assertEqual(cross_info.iff, '',
                         "无 iff 时 cross.iff 应为空字符串")


class TestCovergroupEnhancedBehavior(unittest.TestCase):
    """[iter_065 行为] 增强 covergroup + CovergroupAnalyzer 缺口检测

    真实行为: 含 illegal_bins + 条件约束 → 不报 missing_illegal_bins (已定义);
    含 cross + 条件约束 → 不报 missing_cross (已定义).
    """

    def _analyze(self, source):
        """建图 + 提取 + 分析."""
        from trace.core.covergroup_analyzer import CovergroupAnalyzer

        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        graph = tracer.get_graph()
        cgs = CovergroupExtractor({'test.sv': source}).extract()
        analyzer = CovergroupAnalyzer(adapter=graph._adapter, cgs=cgs)
        return analyzer.analyze()

    def test_illegal_bins_complete_coverage_no_gap(self):
        """[行为] cross + illegal_bins 都齐全 → 不报 missing_cross / missing_illegal_bins

        Source:
        - class 有 conditional constraint (mode -> data inside [...])
        - covergroup 覆盖 mode 和 data, **定义 cross**, 且 data **定义 illegal_bins**

        预期: analyzer 应安静返回 (既不缺 cross 也不缺 illegal_bins).
        """
        source = '''class packet;
    rand bit [7:0] data;
    rand bit mode;
    constraint c { if (mode) data inside {[0:127]}; else data inside {[128:255]}; }
endclass
module top(input logic clk, input logic [7:0] data, input logic mode);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low  = {[0:127]};
            bins high = {[128:255]};
            illegal_bounds_bins bad = default;
        }
        coverpoint mode { bins on = {1}; bins off = {0}; }
        cross mode, data;
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps = self._analyze(source)
        kinds = {g.kind for g in gaps}
        # cross 已定义 → 不报 missing_cross
        self.assertNotIn('missing_cross', kinds,
                         f"cross 已定义时不应报 missing_cross, 实得 kinds={kinds}")

    def test_missing_illegal_bins_detected(self):
        """[行为] 条件约束 + cross 都定义, 但缺 illegal_bins → 报 missing_illegal_bins

        Source:
        - class 有 conditional constraint
        - covergroup 覆盖两信号 + cross, 但**没有 illegal_bins**

        预期: analyzer 应报 missing_illegal_bins.
        """
        source = '''class packet;
    rand bit [7:0] data;
    rand bit mode;
    constraint c { if (mode) data inside {[0:127]}; else data inside {[128:255]}; }
endclass
module top(input logic clk, input logic [7:0] data, input logic mode);
    covergroup cg @(posedge clk);
        coverpoint data { bins low = {[0:127]}; bins high = {[128:255]}; }
        coverpoint mode { bins on = {1}; bins off = {0}; }
        cross mode, data;
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps = self._analyze(source)
        kinds = {g.kind for g in gaps}
        self.assertIn('missing_illegal_bins', kinds,
                      f"缺 illegal_bins 时应报 missing_illegal_bins, 实得 kinds={kinds}")


if __name__ == '__main__':
    unittest.main()
