# test_covergroup_enhanced.py - 增强 Covergroup 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
增强 Covergroup 语法:
1. illegal_bins
2. ignore_bins
3. cross coverage
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestCovergroupEnhanced(unittest.TestCase):
    """增强 Covergroup 支持测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test': tree}))
    
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

if __name__ == '__main__':
    unittest.main()
