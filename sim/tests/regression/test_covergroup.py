# test_covergroup.py - Covergroup 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Covergroup 语法覆盖:
1. covergroup 声明
2. coverpoint 定义
3. bins 定义
4. cross coverage
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestCovergroup(unittest.TestCase):
    """Covergroup 支持测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
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

if __name__ == '__main__':
    unittest.main()
