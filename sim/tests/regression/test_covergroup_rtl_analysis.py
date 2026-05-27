# test_covergroup_rtl_analysis.py - RTL Coverage 合理性分析
# [铁律13] 金标准测试
# [铁律17] 强断言
#
# 核心问题:
#   1. data 信号: bins 是否覆盖数值范围、极值、边界？
#   2. control 信号: bins 是否覆盖特殊值、cross？
#   3. 相关信号: 是否有建议的 cross 信号？
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.covergroup_analyzer import CovergroupAnalyzer, CoverageGap


def _build_all(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    extractor = CovergroupExtractor({'test.sv': source})
    cgs = extractor.extract()
    return graph, tracer, cgs


# =========================================================================
# 信号分类
# =========================================================================

SIGNAL_TYPE_DATA = "data"         # 多位宽、算术运算
SIGNAL_TYPE_CONTROL = "control"   # 1-4 位、条件判断
SIGNAL_TYPE_ADDR = "addr"         # 地址映射
SIGNAL_TYPE_STATUS = "status"     # 状态寄存器


def classify_signal(graph, signal_name):
    """根据信号的使用上下文分类

    启发式规则:
    - 名称含 addr → addr 类型
    - 名称含 data/val → data 类型
    - 名称含 ctrl/valid/ready/en → control 类型
    - 名称含 status/state → status 类型
    - 位宽 > 8 → data 类型
    - 位宽 <= 4 → control 类型
    """
    name_lower = signal_name.lower()

    if 'addr' in name_lower:
        return SIGNAL_TYPE_ADDR
    if any(k in name_lower for k in ['data', 'payload']):
        return SIGNAL_TYPE_DATA
    if any(k in name_lower for k in ['ctrl', 'valid', 'ready', 'en', 'mode']):
        return SIGNAL_TYPE_CONTROL
    if any(k in name_lower for k in ['status', 'state']):
        return SIGNAL_TYPE_STATUS

    # 根据位宽推断
    # 尝试多种节点 ID 格式
    node = graph.get_node(signal_name)
    if node is None:
        # 尝试 module.signal 格式
        for n in graph.nodes():
            if n.endswith(f".{signal_name}"):
                node = graph.get_node(n)
                break
    if node and hasattr(node, 'width'):
        width = node.width
        if isinstance(width, (tuple, list)) and len(width) >= 2:
            msb, lsb = width[0], width[1]
            try:
                bits = abs(int(msb) - int(lsb)) + 1
                if bits <= 4:
                    return SIGNAL_TYPE_CONTROL
                if bits > 8:
                    return SIGNAL_TYPE_DATA
            except (ValueError, TypeError):
                pass

    return SIGNAL_TYPE_DATA  # 默认


# =========================================================================
# 合理性检查
# =========================================================================

def check_data_bins合理性(cg, signal_name):
    """检查 data 类信号的 bins 是否合理

    data 信号应该有:
    - 数值范围分区 (多个 bins 覆盖整个范围)
    - 极值 bin (0, max)
    - 边界值 bin (边界附近)
    """
    cp = None
    for p in cg.coverpoints:
        if p.signal == signal_name:
            cp = p
            break

    if cp is None:
        return {'issues': [f"缺少 coverpoint: {signal_name}"]}

    issues = []
    bin_count = len(cp.bins)

    # 检查是否有足够的 bins 分区
    if bin_count < 2:
        issues.append(f"data 信号 {signal_name} 只有 {bin_count} 个 bins，建议至少 2 个范围分区")

    # 检查是否有极值 bin
    has_extreme = False
    for b in cp.bins:
        vals = b.values
        if '0' in vals or 'max' in vals.lower() or '255' in vals:
            has_extreme = True
            break
    if not has_extreme:
        issues.append(f"data 信号 {signal_name} 缺少极值 bin (0 或 max)")

    return {'issues': issues, 'bin_count': bin_count}


def check_control_bins合理性(cg, signal_name):
    """检查 control 类信号的 bins 是否合理

    control 信号应该有:
    - 特殊值 bin (0, max)
    - 活跃/非活跃 bin
    """
    cp = None
    for p in cg.coverpoints:
        if p.signal == signal_name:
            cp = p
            break

    if cp is None:
        return {'issues': [f"缺少 coverpoint: {signal_name}"]}

    issues = []
    bin_count = len(cp.bins)

    if bin_count < 2:
        issues.append(f"control 信号 {signal_name} 只有 {bin_count} 个 bins，建议覆盖活跃和非活跃状态")

    return {'issues': issues, 'bin_count': bin_count}


def suggest_cross_signals(graph, signal_name):
    """基于信号图建议需要 cross 的信号

    逻辑:
    - 找信号的 driver (谁驱动它)
    - 找信号的 load (它驱动谁)
    - 找同 constraint 中引用的其他信号
    """
    suggestions = []

    # 找同 constraint 中的其他信号
    from trace.core.graph.models import EdgeKind

    # 找信号所在的 constraint block
    constraint_blocks = set()
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge.kind == EdgeKind.CONSTRAINS and dst.endswith(f".{signal_name}"):
            # src 可能是 CONSTRAINT_BLOCK 或 CLASS
            node = graph.get_node(src)
            if node and 'CONSTRAINT' in str(node.kind):
                constraint_blocks.add(src)

    # 找同一 constraint block 引用的其他信号
    for block_id in constraint_blocks:
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge.kind == EdgeKind.CONSTRAINS and src == block_id:
                var_name = dst.split('.')[-1] if '.' in dst else dst
                if var_name != signal_name:
                    suggestions.append(var_name)

    return list(set(suggestions))


# =========================================================================
# 测试用例
# =========================================================================

class TestDataSignalAnalysis(unittest.TestCase):
    """data 信号合理性分析"""

    def test_data_signal_too_few_bins(self):
        """[金标准] data 信号 bins 太少

        signal: data [7:0]
        coverpoint: bins all = {[0:255]}  (只有 1 个 bin)

        期望: 告警 bins 太少
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins all = {[0:255]};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        graph, tracer, cgs = _build_all(source)
        cg = cgs[0]

        result = check_data_bins合理性(cg, 'data')
        self.assertGreater(len(result['issues']), 0,
            "data 信号只有 1 个 bin 应该告警")

    def test_data_signal_good_bins(self):
        """[金标准] data 信号 bins 合理

        signal: data [7:0]
        coverpoint: bins low, mid, high, zero, max

        期望: 无告警
        """
        source = '''module top(input clk, logic [7:0] data);
    covergroup cg @(posedge clk);
        coverpoint data {
            bins zero = {0};
            bins low  = {[1:63]};
            bins mid  = {[64:191]};
            bins high = {[192:254]};
            bins max  = {255};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        graph, tracer, cgs = _build_all(source)
        cg = cgs[0]

        result = check_data_bins合理性(cg, 'data')
        self.assertEqual(len(result['issues']), 0,
            f"合理的 bins 不应告警: {result['issues']}")
        self.assertGreaterEqual(result['bin_count'], 5)


class TestControlSignalAnalysis(unittest.TestCase):
    """control 信号合理性分析"""

    def test_control_signal_single_bin(self):
        """[金标准] control 信号只有 1 个 bin

        signal: valid [0:0]
        coverpoint: bins hit = {1}

        期望: 告警缺少非活跃状态
        """
        source = '''module top(input clk, logic valid);
    covergroup cg @(posedge clk);
        coverpoint valid {
            bins hit = {1};
        }
    endgroup
    cg cg_inst = new();
endmodule'''
        graph, tracer, cgs = _build_all(source)
        cg = cgs[0]

        result = check_control_bins合理性(cg, 'valid')
        self.assertGreater(len(result['issues']), 0,
            "control 信号只有 1 个 bin 应该告警")


class TestCrossSuggestion(unittest.TestCase):
    """相关信号建议"""

    def test_suggest_cross_from_constraint(self):
        """[金标准] 从 constraint 中建议 cross 信号

        constraint c { if (mode == 0) { addr < 64; } }

        查询 addr 的建议 cross 信号 → mode
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    constraint c {
        if (mode == 0) { addr inside {[0:63]}; }
    }
    covergroup cg;
        coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
endclass
module top; endmodule'''
        graph, tracer, cgs = _build_all(source)

        suggestions = suggest_cross_signals(graph, 'addr')
        self.assertIn('mode', suggestions,
            "addr 的 constraint 引用了 mode，应该建议 cross")


class TestSignalClassification(unittest.TestCase):
    """信号分类"""

    def test_classify_data_signal(self):
        """[金标准] data 信号分类"""
        source = '''module top(input clk, logic [7:0] data_in);
    covergroup cg @(posedge clk);
        coverpoint data_in;
    endgroup
    cg cg_inst = new();
endmodule'''
        graph, tracer, cgs = _build_all(source)
        sig_type = classify_signal(graph, 'data_in')
        self.assertEqual(sig_type, SIGNAL_TYPE_DATA)

    def test_classify_control_signal(self):
        """[金标准] control 信号分类"""
        source = '''module top(input clk, logic valid);
    covergroup cg @(posedge clk);
        coverpoint valid;
    endgroup
    cg cg_inst = new();
endmodule'''
        graph, tracer, cgs = _build_all(source)
        sig_type = classify_signal(graph, 'valid')
        self.assertEqual(sig_type, SIGNAL_TYPE_CONTROL)


if __name__ == '__main__':
    unittest.main()
