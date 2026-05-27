# test_covergroup_extraction.py - Covergroup 结构化提取金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.covergroup_models import (
    CovergroupInfo, CoverpointInfo, CoverCrossInfo, BinsInfo
)


def _extract(source):
    """便捷提取函数"""
    extractor = CovergroupExtractor({'test.sv': source})
    return extractor.extract()


class TestCovergroupExtraction(unittest.TestCase):
    """Covergroup 结构化提取"""

    def test_basic_covergroup(self):
        """[金标准] 基础 covergroup

        covergroup cg @(posedge clk);
            coverpoint data {
                bins low = {[0:63]};
                bins high = {[64:255]};
            }
        endgroup
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low = {[0:63]};
            bins high = {[64:255]};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = _extract(source)

        self.assertGreaterEqual(len(cgs), 1, "应找到 1 个 covergroup")
        cg = cgs[0]

        # 基本信息
        self.assertEqual(cg.name, 'cg')
        self.assertIn('clk', cg.clock)

        # coverpoint
        self.assertEqual(len(cg.coverpoints), 1)
        cp = cg.coverpoints[0]
        self.assertEqual(cp.signal, 'data')

        # bins
        self.assertEqual(len(cp.bins), 2)
        self.assertEqual(cp.bins[0].name, 'low')
        self.assertEqual(cp.bins[0].kind, 'bins')
        self.assertEqual(cp.bins[1].name, 'high')

    def test_illegal_bins(self):
        """[金标准] illegal_bins 提取

        coverpoint data {
            bins valid = {[0:100]};
            illegal_bins bad = {101, 102};
        }
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins valid = {[0:100]};
            illegal_bins bad = {101, 102};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = _extract(source)
        cp = cgs[0].coverpoints[0]

        illegal = [b for b in cp.bins if b.kind == 'illegal_bins']
        self.assertEqual(len(illegal), 1, "应有 1 个 illegal_bins")
        self.assertEqual(illegal[0].name, 'bad')

        valid = [b for b in cp.bins if b.kind == 'bins']
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].name, 'valid')

    def test_ignore_bins(self):
        """[金标准] ignore_bins 提取"""
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins valid = {[0:255]};
            ignore_bins skip = {200, 201};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = _extract(source)
        cp = cgs[0].coverpoints[0]

        ignore = [b for b in cp.bins if b.kind == 'ignore_bins']
        self.assertEqual(len(ignore), 1)
        self.assertEqual(ignore[0].name, 'skip')

    def test_cross_coverage(self):
        """[金标准] cross coverage 提取

        coverpoint addr;
        coverpoint data;
        cross addr, data;
        """
        source = '''module top(input clk, logic [7:0] addr, data);
    covergroup cg @(posedge clk);
        coverpoint addr;
        coverpoint data;
        cross addr, data;
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = _extract(source)
        cg = cgs[0]

        self.assertGreaterEqual(len(cg.crosses), 1, "应有 cross coverage")
        cross = cg.crosses[0]
        self.assertIn('addr', cross.items)
        self.assertIn('data', cross.items)

    def test_multiple_coverpoints(self):
        """[金标准] 多 coverpoint + bins + cross"""
        source = '''module top(input clk, logic [7:0] addr, data, mode);
    covergroup cg @(posedge clk);
        coverpoint addr {
            bins low  = {[0:63]};
            bins mid  = {[64:191]};
            bins high = {[192:255]};
        }
        coverpoint data {
            bins zero = {0};
            bins nonzero = {[1:255]};
        }
        coverpoint mode {
            bins read  = {0};
            bins write = {1};
            illegal_bins invalid = {2, 3};
        }
        cross addr, data;
        cross addr, mode;
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = _extract(source)
        cg = cgs[0]

        # 3 个 coverpoint
        self.assertEqual(len(cg.coverpoints), 3)

        # 2 个 cross
        self.assertEqual(len(cg.crosses), 2)

        # mode 有 illegal_bins
        mode_cp = [cp for cp in cg.coverpoints if cp.signal == 'mode'][0]
        illegal = [b for b in mode_cp.bins if b.kind == 'illegal_bins']
        self.assertEqual(len(illegal), 1)
        self.assertEqual(illegal[0].name, 'invalid')

        # addr 有 3 个 bins
        addr_cp = [cp for cp in cg.coverpoints if cp.signal == 'addr'][0]
        self.assertEqual(len(addr_cp.bins), 3)

    def test_covergroup_in_class(self):
        """[金标准] class 内的 covergroup"""
        source = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
        coverpoint addr {
            bins low = {[0:127]};
            bins high = {[128:255]};
        }
    endgroup
    function new();
        cg = new();
    endfunction
endclass
module top; endmodule'''
        cgs = _extract(source)

        self.assertGreaterEqual(len(cgs), 1, "应找到 class 内的 covergroup")
        cg = cgs[0]
        self.assertEqual(cg.name, 'cg')
        self.assertEqual(len(cg.coverpoints), 1)
        self.assertEqual(cg.coverpoints[0].signal, 'addr')

    def test_no_covergroup(self):
        """[负面] 没有 covergroup 时返回空列表"""
        source = '''module top(input clk, logic [7:0] data);
    always_ff @(posedge clk) data <= data + 1;
endmodule'''
        cgs = _extract(source)
        self.assertEqual(len(cgs), 0)


if __name__ == '__main__':
    unittest.main()
