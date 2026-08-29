# test_covergroup_advanced.py - Covergroup 语法缺口补充测试
# [iter_062 2026-08-29] 按 TEST_MAP 功能域缺口分析补充:
# 高优先级缺口: iff / wildcard bins / transition bins / 自动 bins /
#                default bin / 参数化 covergroup / sample() / 多事件
#
# 策略: 验证提取器**现有行为** (语法被 pyslang 接受 + 提取器不崩溃 +
#       基础字段正确); 深度语义 (wildcard/transition 类型识别) 是工具缺口,
#       记录在 EXTRACTION_COVERAGE.md 已知缺陷, 不在本文件断言失败.
"""
Covergroup 高级语法覆盖 (iter_062 补充):
1. coverpoint iff 条件
2. wildcard bins
3. transition bins
4. 自动 bins (bins foo[]) / default bin
5. 参数化 covergroup
6. 采样函数 sample()
7. 多采样事件 @(posedge clk, negedge clk)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_extractor import CovergroupExtractor


class TestCovergroupAdvanced(unittest.TestCase):
    """Covergroup 高级语法支持测试"""

    def _extract(self, source):
        ext = CovergroupExtractor({'test.sv': source})
        return ext.extract()

    def test_coverpoint_iff(self):
        """[Golden] coverpoint iff 条件

        coverpoint data iff (enable) — iff 是条件采样.

        预期: 提取器不崩溃, coverpoint 被提取 (iff 字段当前未建模, 见
        EXTRACTION_COVERAGE 已知缺陷 — 本测试只验证基础提取).
        """
        source = '''module top(input logic clk, input logic [7:0] data, input logic enable);
    covergroup cg @(posedge clk);
        coverpoint data iff (enable) {
            bins low = {[0:127]};
            bins high = {[128:255]};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1, "应提取 1 个 covergroup")
        cg = cgs[0]
        self.assertEqual(cg.name, 'cg')
        self.assertEqual(len(cg.coverpoints), 1)
        cp = cg.coverpoints[0]
        self.assertEqual(cp.signal, 'data')
        self.assertEqual(cp.iff, 'enable', "[iter_062] iff 条件应被提取")
        self.assertEqual(len(cp.bins), 2, "iff 不应影响 bins 提取")

    def test_cross_iff(self):
        """[Golden] cross 带 iff"""
        source = '''module top(input logic clk, input logic addr, mode, reset);
    covergroup cg @(posedge clk);
        coverpoint addr;
        coverpoint mode;
        cross addr, mode iff (reset == 0);
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1)
        cg = cgs[0]
        self.assertEqual(len(cg.crosses), 1, "cross 应被提取")
        self.assertEqual(sorted(cg.crosses[0].items), ['addr', 'mode'])
        self.assertEqual(cg.crosses[0].iff, 'reset == 0', "[iter_062] cross iff 应被提取")

    def test_wildcard_bins(self):
        """[Golden] wildcard bins — 通配符 ? 位

        wildcard bins read_op = {8'b0000_????} — 常见总线协议操作码覆盖.

        预期: bins 被提取 (values 保留通配符文本; wildcard 类型识别是工具
        缺口, 记录在 EXTRACTION_COVERAGE, 不在本测试断言).
        """
        source = '''module top(input logic clk, input logic [7:0] opcode);
    covergroup cg @(posedge clk);
        coverpoint opcode {
            wildcard bins read_op  = {8'b0000_????};
            wildcard bins write_op = {8'b0001_????};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1)
        cp = cgs[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 2, "wildcard bins 应被提取")
        types = {b.bin_type for b in cp.bins}
        self.assertEqual(types, {'wildcard'}, "[iter_062] wildcard 类型应被识别")
        values = {b.values for b in cp.bins}
        self.assertTrue(any("????" in v for v in values), "通配符值应保留")

    def test_transition_bins(self):
        """[Golden] transition bins — 状态迁移覆盖

        bins trans[] = (IDLE => READY => DONE) — 覆盖状态机迁移.

        预期: bins 被提取 (values 保留 => 文本; transition 类型识别是工具缺口).
        """
        source = '''module top(input logic clk, input logic [1:0] state);
    covergroup cg @(posedge clk);
        coverpoint state {
            bins idle_to_ready = (0 => 1);
            bins trans[] = (0 => 1 => 2);
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1)
        cp = cgs[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 2, "transition bins 应被提取")
        types = {b.bin_type for b in cp.bins}
        self.assertIn('transition', types, "[iter_062] transition 类型应被识别")
        values = {b.values for b in cp.bins}
        self.assertTrue(any("=>" in v for v in values), "transition 值应保留 =>")

    def test_auto_and_default_bins(self):
        """[Golden] 自动 bins (bins foo[]) + default bin"""
        source = '''module top(input logic clk, input logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low[] = {[0:63]};
            bins high[] = {[64:255]};
            bins others = default;
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1)
        cp = cgs[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 3, "自动 bins + default 应被提取")
        names = {b.name for b in cp.bins}
        self.assertEqual(names, {'low', 'high', 'others'})

    def test_parameterized_covergroup(self):
        """[Golden] 参数化 covergroup — #(int WIDTH = 8)

        pyslang 限制 (iter_062 实测):
        - 声明 `covergroup cg #(int WIDTH = 8)` 可解析
        - bins 内引用 covergroup 参数 (WIDTH'hFF) → 编译失败 (参数不解析)
        - 参数化实例化 `cg #(16) cg_inst = new()` → "not a generic class type"

        本测试验证**声明**可提取; 参数在 bins/实例化中的使用记录为 pyslang 限制.
        """
        source = '''module top(input logic clk, input logic [7:0] data);
    covergroup cg #(int WIDTH = 8) @(posedge clk);
        coverpoint data {
            bins zero = {0};
            bins max  = {255};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1, "参数化 covergroup 声明应被提取")
        self.assertEqual(cgs[0].name, 'cg')
        cp = cgs[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 2, "参数化 covergroup 的 bins 应被提取")

    def test_sample_function(self):
        """[Golden] 显式采样函数 — with function sample(...)"""
        source = '''module top(input logic clk, input logic [7:0] a, b);
    covergroup cg with function sample(bit [7:0] a, bit [7:0] b);
        coverpoint a { bins zero = {0}; bins max = {255}; }
        coverpoint b;
        cross a, b;
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1, "带 sample 的 covergroup 应被提取")
        cg = cgs[0]
        self.assertEqual(len(cg.coverpoints), 2)
        self.assertEqual(len(cg.crosses), 1)

    def test_multi_event_clocking(self):
        """[Golden] 多采样事件 — @(posedge clk1, negedge clk2)"""
        source = '''module top(input logic clk1, clk2, input logic [7:0] data);
    covergroup cg @(posedge clk1, negedge clk2);
        coverpoint data;
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1, "多事件 covergroup 应被提取")
        self.assertEqual(len(cgs[0].coverpoints), 1)

    def test_ignore_and_illegal_bins_combined(self):
        """[Golden] ignore_bins + illegal_bins 组合 (含通配符)"""
        source = '''module top(input logic clk, input logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins valid = {[0:127]};
            ignore_bins rsvd = {[128:191]};
            illegal_bins bad = {[192:255]};
            wildcard ignore_bins dont_care = {8'b1010_????};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs = self._extract(source)
        self.assertEqual(len(cgs), 1)
        cp = cgs[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 4, "ignore/illegal/wildcard bins 应被提取")
        kinds = {b.kind for b in cp.bins}
        self.assertIn('bins', kinds)


if __name__ == '__main__':
    unittest.main(verbosity=2)
