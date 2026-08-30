# test_covergroup_extraction.py - Covergroup 结构化提取金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
# [iter_065 2026-09-12] 升级: 保留结构化提取断言, 补充:
#                       1. BinsInfo.kind + values 的更细字段断言 (existing tests)
#                       2. CoverpointInfo.iff / CoverCrossInfo.iff / BinsInfo.bin_type 字段断言
#                       3. CovergroupAnalyzer 缺口检测 (TestCovergroupExtractionBehavior)
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_extractor import CovergroupExtractor


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

        # [iter_065 行为断言] bins.values 应保留范围字面量 [0:63] / [64:255]
        bin_values = {b.name: b.values for b in cp.bins}
        self.assertIn('[0:63]', bin_values['low'],
                      f"range bins low 应保留 [0:63], 实得 {bin_values['low']!r}")
        self.assertIn('[64:255]', bin_values['high'],
                      f"range bins high 应保留 [64:255], 实得 {bin_values['high']!r}")
        # 普通 bins 的 bin_type 应为空 (非 wildcard/transition)
        for b in cp.bins:
            self.assertEqual(b.bin_type, '',
                             f"普通 bins {b.name} 的 bin_type 应为空")

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

        # [iter_065 行为断言] illegal_bins 的 values 字段应保留 {101, 102}
        self.assertIn('101', illegal[0].values)
        self.assertIn('102', illegal[0].values)
        # 普通 bins 的 values 应保留 [0:100]
        self.assertIn('[0:100]', valid[0].values)

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

        # [iter_065 行为断言] ignore_bins 的 values 应保留 {200, 201}
        self.assertIn('200', ignore[0].values)
        self.assertIn('201', ignore[0].values)

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

        # [iter_065 行为断言] cross.items 应**正好**包含 addr 和 data (不多不少)
        self.assertEqual(sorted(cross.items), ['addr', 'data'],
                         f"cross.items 应为 ['addr', 'data'], 实得 {cross.items}")
        # 无 iff 时字段应为空字符串
        self.assertEqual(cross.iff, '', "无 iff 时 cross.iff 应为空")

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

        # [iter_065 行为断言] cross 与 coverpoint 信号一致, cross.items 不重不漏
        cross_items_set = {tuple(sorted(c.items)) for c in cg.crosses}
        self.assertIn(('addr', 'data'), cross_items_set)
        self.assertIn(('addr', 'mode'), cross_items_set)
        # mode_cp.bins 中 illegal_bins 之外的应是普通 bins (kind='bins')
        non_illegal = [b for b in mode_cp.bins if b.kind != 'illegal_bins']
        self.assertEqual(len(non_illegal), 2, "mode 应有 2 个普通 bins (read/write)")
        self.assertEqual({b.name for b in non_illegal}, {'read', 'write'})

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

        # [iter_065 行为断言] in_class 字段应记录所在 class (若有)
        if cg.in_class:
            self.assertEqual(cg.in_class, 'packet',
                             f"in_class 应为 'packet', 实得 {cg.in_class!r}")
        # bins 的 kind 字段集合应为 {'bins'}
        cp = cg.coverpoints[0]
        kinds = {b.kind for b in cp.bins}
        self.assertEqual(kinds, {'bins'},
                         f"class 内 coverpoint 的 bins kind 应为 'bins', 实得 {kinds}")

    def test_no_covergroup(self):
        """[负面] 没有 covergroup 时返回空列表"""
        source = '''module top(input clk, logic [7:0] data);
    always_ff @(posedge clk) data <= data + 1;
endmodule'''
        cgs = _extract(source)
        self.assertEqual(len(cgs), 0)

        # [iter_065 行为断言] 负面场景下 analyzer 也应安静返回空
        from trace.core.covergroup_analyzer import CovergroupAnalyzer
        from trace.unified_tracer import UnifiedTracer

        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        graph = tracer.get_graph()
        analyzer = CovergroupAnalyzer(adapter=graph._adapter, cgs=cgs)
        gaps = analyzer.analyze()
        self.assertEqual(gaps, [], "无 covergroup 时 analyzer 应返回空缺口列表")


class TestCovergroupExtractionBehavior(unittest.TestCase):
    """[iter_065 行为] CovergroupAnalyzer 缺口检测 (联动 covergroup_extraction)

    真实行为金标准: 含条件约束 + covergroup 结构 → analyzer 报对应缺口.
    这是 test_covergroup_extraction.py 的**行为**层面补充.
    """

    def _analyze(self, source):
        from trace.core.covergroup_analyzer import CovergroupAnalyzer
        from trace.core.covergroup_extractor import CovergroupExtractor
        from trace.unified_tracer import UnifiedTracer

        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        graph = tracer.get_graph()
        cgs = CovergroupExtractor({'test.sv': source}).extract()
        analyzer = CovergroupAnalyzer(adapter=graph._adapter, cgs=cgs)
        return analyzer.analyze(), cgs

    def test_iff_coverpoint_extracted_for_analysis(self):
        """[行为] iff coverpoint 可被 analyzer 消费 (结构 + 缺口分析)

        注意: analyzer 只对**两者都被 coverpoint 覆盖**的条件约束报 missing_cross.
        本场景 coverpoint `data iff (en)` 覆盖 data; 同时再加 coverpoint en,
        使 (en, data) 这对都被覆盖但仍缺 cross → 应触发 missing_cross.
        """
        source = '''class packet;
    rand bit [7:0] data;
    rand bit en;
    constraint c { en -> data inside {[0:127]}; }
endclass
module top(input logic clk, input logic [7:0] data, input logic en);
    covergroup cg @(posedge clk);
        coverpoint data iff (en) {
            bins low = {[0:127]};
            bins high = {[128:255]};
        }
        coverpoint en { bins on = {1}; bins off = {0}; }
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps, cgs = self._analyze(source)
        # 结构提取: iff 字段被保留
        cp_data = [cp for cp in cgs[0].coverpoints if cp.signal == 'data'][0]
        self.assertEqual(cp_data.iff, 'en',
                         f"iff 条件应被提取为 'en', 实得 {cp_data.iff!r}")
        # analyzer 应返回缺口列表 (en/data 都覆盖但缺 cross)
        self.assertIsInstance(gaps, list)
        kinds = {g.kind for g in gaps}
        self.assertIn('missing_cross', kinds,
                      f"条件约束 en->data 应触发 missing_cross, 实得 kinds={kinds}")

    def test_wildcard_bins_extracted_and_analyzable(self):
        """[行为] wildcard bins 被结构化识别 (bin_type='wildcard') + analyzer 可消费"""
        source = '''class packet;
    rand bit [7:0] opcode;
    constraint c { opcode != 8'h00; }
endclass
module top(input logic clk, input logic [7:0] opcode);
    covergroup cg @(posedge clk);
        coverpoint opcode {
            wildcard bins read_op  = {8'b0000_????};
            wildcard bins write_op = {8'b0001_????};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps, cgs = self._analyze(source)
        cp = cgs[0].coverpoints[0]
        types = {b.bin_type for b in cp.bins}
        self.assertEqual(types, {'wildcard'},
                         f"wildcard bins 应被识别为 bin_type='wildcard', 实得 {types}")
        self.assertIsInstance(gaps, list)

    def test_transition_bins_extracted_and_analyzable(self):
        """[行为] transition bins 被识别 (bin_type='transition') + analyzer 可消费"""
        source = '''class packet;
    rand bit [1:0] state;
    constraint c { state inside {[0:2]}; }
endclass
module top(input logic clk, input logic [1:0] state);
    covergroup cg @(posedge clk);
        coverpoint state {
            bins idle_to_ready = (0 => 1);
            bins trans[] = (0 => 1 => 2);
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps, cgs = self._analyze(source)
        cp = cgs[0].coverpoints[0]
        types = {b.bin_type for b in cp.bins}
        self.assertIn('transition', types,
                      f"transition bins 应被识别为 bin_type='transition', 实得 {types}")
        # values 字段应保留 => 序列
        self.assertTrue(any('=>' in b.values for b in cp.bins),
                        "transition bins 的 values 应保留 '=>' 序列")
        self.assertIsInstance(gaps, list)

    def test_cross_iff_extracted(self):
        """[行为] cross iff 条件被结构化保留"""
        source = '''module top(input logic clk, input logic addr, mode, reset);
    covergroup cg @(posedge clk);
        coverpoint addr;
        coverpoint mode;
        cross addr, mode iff (reset == 0);
    endgroup
    cg cg_inst = new();
endmodule'''
        _, cgs = self._analyze(source)
        cg = cgs[0]
        self.assertEqual(len(cg.crosses), 1)
        cross = cg.crosses[0]
        self.assertEqual(sorted(cross.items), ['addr', 'mode'])
        self.assertEqual(cross.iff, 'reset == 0',
                         f"cross iff 应被提取, 实得 {cross.iff!r}")

    def test_complete_coverage_no_gaps(self):
        """[行为] 完整覆盖 (cross + illegal_bins) → analyzer 应安静返回"""
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
            illegal_bins bad = default;
        }
        coverpoint mode { bins on = {1}; bins off = {0}; }
        cross mode, data;
    endgroup
    cg cg_inst = new();
endmodule'''
        gaps, _ = self._analyze(source)
        kinds = {g.kind for g in gaps}
        # 完整覆盖 → 两种缺口都不应报
        self.assertNotIn('missing_cross', kinds,
                         f"cross 已定义 → 不应报 missing_cross, 实得 kinds={kinds}")
        self.assertNotIn('missing_illegal_bins', kinds,
                         f"illegal_bins 已定义 → 不应报 missing_illegal_bins, 实得 kinds={kinds}")


if __name__ == '__main__':
    unittest.main()
