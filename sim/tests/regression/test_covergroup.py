# test_covergroup.py - Covergroup 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_065 2026-09-12] 升级: 保留 AST 断言, 补充 CovergroupExtractor 结构化提取断言
#                       (CovergroupInfo.name/clock/coverpoints[].bins[].name/kind/values)
#                       + CovergroupAnalyzer 缺口检测 (有 constraint 的场景)
"""
Covergroup 语法覆盖:
1. covergroup 声明
2. coverpoint 定义
3. bins 定义
4. cross coverage
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


class TestCovergroup(unittest.TestCase):
    """Covergroup 支持测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_covergroup_declaration(self):
        """[Golden] covergroup 声明

        RTL:
        module top(input clk, logic [7:0] data);
            covergroup cg @(posedge clk);
                option.per_instance = 1;
                coverpoint data {
                    bins low = {0, 1, 2};
                    bins high = {253, 254, 255};
                }
            endgroup

            cg cg_inst = new();
        endmodule

        预期:
        - CovergroupDeclaration 存在
        - 名称为 cg
        - 包含 CoverageOption 和 Coverpoint
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        option.per_instance = 1;
        coverpoint data {
            bins low = {0, 1, 2};
            bins high = {253, 254, 255};
        }
    endgroup

    cg cg_inst = new();
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 CovergroupDeclaration
        cg_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.CovergroupDeclaration:
                cg_decl = m
                break

        self.assertIsNotNone(cg_decl, "CovergroupDeclaration not found")
        self.assertEqual(str(cg_decl.name).strip(), 'cg')

        # 检查 members
        cg_members = list(cg_decl.members)
        self.assertGreaterEqual(len(cg_members), 2, "Should have at least 2 members")

        # [iter_065 行为断言] CovergroupExtractor 结构化提取
        cgs = _extract(source)
        self.assertEqual(len(cgs), 1, "应提取 1 个 covergroup")
        cg_info = cgs[0]
        self.assertEqual(cg_info.name, 'cg', "结构化名称应匹配")
        self.assertIn('clk', cg_info.clock, "采样事件应包含 clk")
        self.assertEqual(len(cg_info.coverpoints), 1,
                         "应提取 1 个 coverpoint (option 不算 coverpoint)")
        cp_info = cg_info.coverpoints[0]
        self.assertEqual(cp_info.signal, 'data', "coverpoint 采样信号应为 data")
        # bins 结构化字段: name + kind
        bin_names = {b.name for b in cp_info.bins}
        self.assertEqual(bin_names, {'low', 'high'}, "bins 名称集合")
        for b in cp_info.bins:
            self.assertEqual(b.kind, 'bins', f"bins {b.name} 应为 'bins' 类型")

    def test_coverpoint(self):
        """[Golden] coverpoint 定义

        RTL:
        coverpoint data {
            bins low = {0, 1, 2};
            bins high = {253, 254, 255};
        }

        预期:
        - Coverpoint 存在
        - 包含 CoverageBins
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low = {0, 1, 2};
            bins high = {253, 254, 255};
        }
    endgroup
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        members = list(root.members)
        cg_decl = members[0]

        cg_members = list(cg_decl.members)

        # 查找 Coverpoint
        cp = None
        for m in cg_members:
            if m.kind == pyslang.SyntaxKind.Coverpoint:
                cp = m
                break

        self.assertIsNotNone(cp, "Coverpoint not found")

        # 检查 CoverageBins
        cp_members = list(cp.members)
        self.assertGreaterEqual(len(cp_members), 2, "Should have at least 2 bins")

        # [iter_065 行为断言] 结构化提取 + values 字段保留 set 字面量
        cgs = _extract(source)
        cp_info = cgs[0].coverpoints[0]
        self.assertEqual(cp_info.signal, 'data')
        self.assertEqual(len(cp_info.bins), 2)
        # values 应保留 bins 赋值的源文本 ({0, 1, 2} / {253, 254, 255})
        bin_values = {b.name: b.values for b in cp_info.bins}
        self.assertIn('0', bin_values['low'])
        self.assertIn('1', bin_values['low'])
        self.assertIn('2', bin_values['low'])
        self.assertIn('253', bin_values['high'])
        self.assertIn('254', bin_values['high'])
        self.assertIn('255', bin_values['high'])

    def test_coverage_bins(self):
        """[Golden] bins 定义

        RTL:
        bins low = {0, 1, 2};
        bins high = {253, 254, 255};

        预期:
        - CoverageBins 存在
        - 名称为 low, high
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low = {0, 1, 2};
            bins high = {253, 254, 255};
        }
    endgroup
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        members = list(root.members)
        cg_decl = members[0]
        cg_members = list(cg_decl.members)

        # 获取 Coverpoint
        cp = cg_members[0]
        cp_members = list(cp.members)

        # 检查 CoverageBins 名称
        bin_names = [str(m.name).strip() for m in cp_members if hasattr(m, 'name')]
        self.assertIn('low', bin_names)
        self.assertIn('high', bin_names)

        # [iter_065 行为断言] BinsInfo 结构化字段: kind + bin_type 默认值
        cgs = _extract(source)
        cp_info = cgs[0].coverpoints[0]
        self.assertEqual(len(cp_info.bins), 2)
        # 普通 bins 的 bin_type 字段应为空字符串 (普通 / wildcard / transition 之外的默认)
        for b in cp_info.bins:
            self.assertEqual(b.bin_type, '', f"普通 bins {b.name} 的 bin_type 应为空")
            self.assertEqual(b.kind, 'bins')


class TestCovergroupBehavior(unittest.TestCase):
    """[iter_065 行为] CovergroupAnalyzer 联动 — 缺口检测

    真实行为 = CovergroupExtractor 结构化提取 + CovergroupAnalyzer 覆盖缺口检测.
    参考 test_covergroup_advanced.py TestCovergroupBehavior 的范式.
    """

    def _analyze(self, source):
        """建图 + 提取 + 分析, 返回 CoverageGap 列表."""
        from trace.core.covergroup_analyzer import CovergroupAnalyzer

        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        graph = tracer.get_graph()
        cgs = CovergroupExtractor({'test.sv': source}).extract()
        analyzer = CovergroupAnalyzer(adapter=graph._adapter, cgs=cgs)
        return analyzer.analyze()

    def test_constraint_without_cross_yields_missing_cross(self):
        """[行为] 类内条件约束 (en -> data in [...]) 但 covergroup 缺 cross → 报 missing_cross

        Source 包含:
        - class packet 有 conditional constraint (en -> data inside {...})
        - covergroup 覆盖了 en/data 但**没有 cross**

        预期: analyzer 返回至少一个 missing_cross 缺口.
        """
        source = '''class packet;
    rand bit [7:0] data;
    rand bit en;
    constraint c { if (en) data inside {[0:127]}; }
endclass
module top(input logic clk, input logic [7:0] data, input logic en);
    covergroup cg @(posedge clk);
        coverpoint data { bins low = {[0:127]}; bins high = {[128:255]}; }
        coverpoint en   { bins on = {1}; bins off = {0}; }
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps = self._analyze(source)
        # 缺口应是 list, 包含至少一个 missing_cross (en/data 缺 cross)
        kinds = {g.kind for g in gaps}
        self.assertIn('missing_cross', kinds,
                      f"条件约束 en->data 应触发 missing_cross, 实得 kinds={kinds}")

    def test_no_constraint_yields_no_missing_cross(self):
        """[行为] 没有条件约束 → 不应报 missing_cross 缺口

        Source 是简单 covergroup (无 class / 无 constraint), analyzer 应安静返回.
        """
        source = '''module top(input logic clk, input logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data { bins low = {[0:127]}; bins high = {[128:255]}; }
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps = self._analyze(source)
        # 无条件约束 → 不应产生 missing_cross / missing_illegal_bins
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertEqual(cross_gaps, [],
                         f"无 constraint 时不应有 missing_cross, 实得 {cross_gaps}")


if __name__ == '__main__':
    unittest.main()
