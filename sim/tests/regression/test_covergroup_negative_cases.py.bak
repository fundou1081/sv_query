# test_covergroup_negative_cases.py - 反向测试用例
# [铁律13] 金标准测试
# [铁律18] 负面测试
#
# 证明系统能发现不合理的 covergroup 写法
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.covergroup_analyzer import CovergroupAnalyzer
from trace.core.graph.covergroup_models import CovergroupInfo


def _analyze(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    extractor = CovergroupExtractor({'test.sv': source})
    cgs = extractor.extract()
    analyzer = CovergroupAnalyzer(graph, cgs)
    gaps = analyzer.analyze()
    return cgs, gaps


def _has_gap(gaps, kind, keyword=None):
    """检查是否有指定类型的 gap"""
    for g in gaps:
        if g.kind == kind:
            if keyword is None or keyword in g.description:
                return True
    return False


# =========================================================================
# 场景 1: 条件约束未定义 cross
# =========================================================================

class TestMissingCrossDetection(unittest.TestCase):
    """检测条件约束缺少 cross 的情况"""

    def test_if_else_constraint_without_cross(self):
        """[反向] if/else 约束只 coverpoint 不 cross

        约束: if (mode == 0) { addr < 64 } else { addr >= 64 }
        covergroup: 只有 coverpoint addr 和 mode，没有 cross

        问题: mode 和 addr 存在依赖关系，单独覆盖无法验证组合
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
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        cgs, gaps = _analyze(source)
        self.assertTrue(_has_gap(gaps, 'missing_cross'),
            "应该检测到 mode 和 addr 缺少 cross")
        self.assertTrue(_has_gap(gaps, 'missing_cross', 'mode'),
            "应明确指出缺少 cross 的变量是 mode")

    def test_implication_without_cross(self):
        """[反向] implication 约束缺少 cross

        约束: mode == 1 -> { addr inside {[0:63]}; data < 128; }
        covergroup: 有 coverpoint 但无 cross

        问题: mode、addr、data 三者有依赖关系
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    rand bit [1:0] mode;
    constraint c {
        mode == 1 -> { addr inside {[0:63]}; data < 128; }
    }
    covergroup cg;
        coverpoint addr;
        coverpoint data;
        coverpoint mode;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        cgs, gaps = _analyze(source)
        self.assertTrue(_has_gap(gaps, 'missing_cross'),
            "implication 约束的变量应该建议 cross")


# =========================================================================
# 场景 2: 有条件约束 + cross 但缺少 illegal_bins
# =========================================================================

class TestMissingIllegalBinsDetection(unittest.TestCase):
    """检测缺少 illegal_bins 的情况"""

    def test_cross_without_illegal_bins(self):
        """[反向] 条件约束 + cross 存在但无 illegal_bins

        约束: if (mode == 0) { addr < 64 }
        covergroup: cross addr, mode 但无 illegal_bins

        问题: cross (mode==0, addr>=64) 是非法组合，应标记 illegal_bins
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
        cgs, gaps = _analyze(source)
        self.assertTrue(_has_gap(gaps, 'missing_illegal_bins'),
            "应该检测到缺少 illegal_bins")

    def test_three_way_constraint_missing_illegal(self):
        """[反向] 三路约束缺少 illegal_bins

        约束:
            if (mode == 0) { addr inside {[0:63]}; data < 128; }
            else { addr inside {[64:255]}; data >= 128; }
        covergroup: cross addr, mode 但无 illegal_bins

        问题: (mode==0, addr high, data large) 是非法组合
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    rand bit [1:0] mode;
    constraint c {
        if (mode == 0) { addr inside {[0:63]}; data inside {[0:127]}; }
        else { addr inside {[64:255]}; data inside {[128:255]}; }
    }
    covergroup cg;
        coverpoint addr { bins low = {[0:63]}; bins high = {[64:255]}; }
        coverpoint data { bins small = {[0:127]}; bins large = {[128:255]}; }
        coverpoint mode;
        cross addr, mode;
        cross data, mode;
        // 缺少: illegal_bins for (mode==0, addr high)
        // 缺少: illegal_bins for (mode==0, data large)
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        cgs, gaps = _analyze(source)
        self.assertTrue(_has_gap(gaps, 'missing_illegal_bins'),
            "三路约束应检测到缺少 illegal_bins")


# =========================================================================
# 场景 3: data 信号 bins 不合理
# =========================================================================

class TestDataBinsQuality(unittest.TestCase):
    """检测 data 信号 bins 不合理的情况"""

    def test_single_bin_coverage(self):
        """[反向] 8 位 data 信号只有 1 个 bin

        问题: 8 位信号有 256 个值，只有 1 个 bin 无法发现边界问题
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins all = {[0:255]};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs, _ = _analyze(source)
        cp = cgs[0].coverpoints[0]

        # 手动检查: 只有 1 个 bin
        self.assertEqual(len(cp.bins), 1,
            "8 位信号只有 1 个 bin，覆盖粒度不足")

    def test_no_extreme_values(self):
        """[反向] data 信号缺少极值 bin

        问题: 没有覆盖 0 和 255，可能漏掉边界 bug
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins low  = {[1:100]};
            bins high = {[101:254]};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs, _ = _analyze(source)
        cp = cgs[0].coverpoints[0]

        # 检查是否覆盖了极值
        has_zero = False
        has_max = False
        for b in cp.bins:
            if '0' in b.values and '1' not in b.values:
                has_zero = True
            if '255' in b.values:
                has_max = True

        self.assertFalse(has_zero, "没有覆盖 0 值")
        self.assertFalse(has_max, "没有覆盖 255 值")


# =========================================================================
# 场景 4: control 信号 bins 不合理
# =========================================================================

class TestControlBinsQuality(unittest.TestCase):
    """检测 control 信号 bins 不合理的情况"""

    def test_only_active_state(self):
        """[反向] valid 信号只覆盖了活跃状态

        问题: 没有覆盖 valid=0 的情况，无法验证非活跃路径
        """
        source = '''module top(input clk, logic valid);
    covergroup cg @(posedge clk);
        coverpoint valid {
            bins active = {1};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        cgs, _ = _analyze(source)
        cp = cgs[0].coverpoints[0]

        # 只有 1 个 bin
        self.assertEqual(len(cp.bins), 1)
        # 只覆盖了 1
        self.assertIn('1', cp.bins[0].values)


# =========================================================================
# 场景 5: 正向对照 - 合理的 covergroup 不应告警
# =========================================================================

class TestGoodCovergroupNoWarning(unittest.TestCase):
    """合理的 covergroup 不应产生告警"""

    def test_well_written_covergroup(self):
        """[正向对照] 写法合理的 covergroup

        - data: 多个 bins 覆盖全范围 + 极值
        - control: 活跃和非活跃
        - 条件约束: 有 cross
        - 有 illegal_bins

        期望: 无告警
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    rand bit [7:0] data;
    constraint c {
        if (mode == 0) { addr inside {[0:63]}; data inside {[0:127]}; }
        else { addr inside {[64:255]}; data inside {[128:255]}; }
    }
    covergroup cg;
        coverpoint addr {
            bins zero = {0};
            bins low  = {[1:63]};
            bins mid  = {[64:191]};
            bins high = {[192:254]};
            bins max  = {255};
        }
        coverpoint data {
            bins zero = {0};
            bins low  = {[1:127]};
            bins high = {[128:254]};
            bins max  = {255};
        }
        coverpoint mode {
            bins idle  = {0};
            bins busy  = {1};
            illegal_bins invalid = {2, 3};
        }
        cross addr, mode;
        cross data, mode;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        cgs, gaps = _analyze(source)

        # 不应有 missing_cross
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertEqual(len(cross_gaps), 0,
            f"写法合理不应有 missing_cross 告警: {[g.description for g in cross_gaps]}")

        # 不应有 missing_illegal_bins (mode 有 illegal_bins)
        illegal_gaps = [g for g in gaps if g.kind == 'missing_illegal_bins']
        self.assertEqual(len(illegal_gaps), 0,
            f"有 illegal_bins 不应告警: {[g.description for g in illegal_gaps]}")


# =========================================================================
# 场景 6: 复杂真实场景
# =========================================================================

class TestRealWorldScenarios(unittest.TestCase):
    """真实芯片验证中的典型问题"""

    def test_spi_mode_without_cross(self):
        """[反向] SPI 类接口: mode 和 data 有约束但无 cross

        类似 OpenTitan spi_item 的场景
        """
        source = '''class spi_item;
    rand bit [7:0] data;
    rand bit [1:0] mode;
    rand bit [2:0] num_lanes;

    constraint c_mode {
        if (mode == 0) { data inside {[0:63]}; }
        else { data inside {[64:255]}; }
    }
    constraint c_lanes {
        mode == 1 -> num_lanes inside {1, 2, 4};
    }
    covergroup cg;
        coverpoint data;
        coverpoint mode;
        coverpoint num_lanes;
        // 缺少: cross data, mode
        // 缺少: cross num_lanes, mode
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        cgs, gaps = _analyze(source)

        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertGreater(len(cross_gaps), 0,
            "SPI 类 item 的条件约束应建议 cross")

    def test_axi_burst_type_missing_cross(self):
        """[反向] AXI 类接口: burst_type 和 addr 有约束但无 cross

        约束: burst_type == WRAP -> addr aligned to burst_size
        """
        source = '''class axi_item;
    rand bit [31:0] addr;
    rand bit [1:0] burst_type;
    rand bit [3:0] burst_len;

    constraint c_wrap {
        burst_type == 2 -> { addr[3:0] == 0; }
    }
    constraint c_incr {
        burst_type == 1 -> { burst_len inside {[1:16]}; }
    }
    covergroup cg;
        coverpoint addr;
        coverpoint burst_type {
            bins fixed = {0};
            bins incr  = {1};
            bins wrap  = {2};
        }
        coverpoint burst_len;
        // 缺少: cross addr, burst_type
        // 缺少: cross burst_len, burst_type
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        cgs, gaps = _analyze(source)

        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        self.assertGreater(len(cross_gaps), 0,
            "AXI 类 item 的 burst_type 约束应建议 cross")


if __name__ == '__main__':
    unittest.main()
