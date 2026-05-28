# test_sva_coverage_analysis.py - SVA 覆盖分析测试
# [铁律13] 金标准测试
#
# Phase 3: 检查关键信号是否被 SVA 覆盖
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.graph.models import NodeKind
from trace.core.graph.sva_models import SVAGraph


def _build_all(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    sva_extractor = SVAExtractor({'test.sv': source})
    sva = sva_extractor.extract()
    return graph, sva, tracer


def _extract(source):
    extractor = SVAExtractor({'test.sv': source})
    return extractor.extract()


def _find_coverage_gaps(graph, sva):
    """找出有信号但没有 SVA 覆盖的端口/寄存器

    返回: list of uncovered signal names
    """
    # 收集 SVA 覆盖的信号
    sva_signals = set()
    for seq in sva.sequences.values():
        sva_signals.update(seq.signals)
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)

    # 收集 SVA 中的时钟信号（排除）
    clock_signals = set()
    for seq in sva.sequences.values():
        if seq.clock:
            clock_signals.add(seq.clock)
    for prop in sva.properties.values():
        if prop.clock:
            clock_signals.add(prop.clock)

    # 收集 graph 中的端口/寄存器
    uncovered = []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        if node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.REG, NodeKind.WIRE):
            signal_name = node_id.split('.')[-1]
            # 排除时钟信号
            if signal_name in clock_signals:
                continue
            if signal_name not in sva_signals:
                uncovered.append(signal_name)

    return uncovered


class TestSVACoverageAnalysis(unittest.TestCase):
    """SVA 覆盖分析"""

    def test_all_signals_covered(self):
        """[金标准] 所有信号都被 SVA 覆盖"""
        source = '''module top(input clk, input [7:0] a, output logic [7:0] b);
    always_ff @(posedge clk) b <= a;
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        self.assertNotIn('a', gaps)
        self.assertNotIn('b', gaps)

    def test_some_signals_uncovered(self):
        """[金标准] 部分信号没有 SVA 覆盖"""
        source = '''module top(input clk, input [7:0] a, b, output logic [7:0] c);
    always_ff @(posedge clk) c <= a + b;
    property p1;
        @(posedge clk) a |-> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        self.assertIn('b', gaps)

    def test_no_assertions(self):
        """[负面] 没有 SVA 时所有信号都是 gaps"""
        source = '''module top(input clk, input [7:0] a, output logic [7:0] b);
    always_ff @(posedge clk) b <= a;
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        self.assertTrue(len(gaps) > 0)

    def test_multiple_properties_cover_different_signals(self):
        """[金标准] 多个 property 覆盖不同信号"""
        source = '''module top(input clk, logic a, b, c, d);
    property p_ab;
        @(posedge clk) a |-> b;
    endproperty
    property p_cd;
        @(posedge clk) c |-> d;
    endproperty
    assert property (p_ab);
    assert property (p_cd);
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        self.assertNotIn('a', gaps)
        self.assertNotIn('b', gaps)
        self.assertNotIn('c', gaps)
        self.assertNotIn('d', gaps)

    def test_clock_excluded_from_gaps(self):
        """[负面] 时钟信号不应出现在 gaps 中"""
        source = '''module top(input clk, input [7:0] a);
    property p1;
        @(posedge clk) a;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        # clk 是时钟，不应出现在 gaps 中
        # （它不是数据信号）
        self.assertNotIn('clk', gaps)


class TestSVASignalRefAnalysis(unittest.TestCase):
    """SVA 信号引用分析"""

    def test_assertion_signals_completeness(self):
        """[金标准] assertion 信号完整性检查"""
        source = '''module top(input clk, input [7:0] addr, wdata, output logic [7:0] rdata);
    always_ff @(posedge clk) rdata <= addr;
    property p_wr;
        @(posedge clk) addr |-> wdata;
    endproperty
    property p_rd;
        @(posedge clk) addr |-> rdata;
    endproperty
    assert property (p_wr);
    assert property (p_rd);
endmodule'''
        graph, sva, _ = _build_all(source)

        # addr 应关联到两个 assertion
        refs = sva.signal_refs.get('addr', [])
        self.assertGreaterEqual(len(refs), 2)

    def test_coverage_ratio(self):
        """[金标准] 覆盖率计算"""
        source = '''module top(input clk, input [7:0] a, b, c, output logic [7:0] d);
    always_ff @(posedge clk) d <= a + b + c;
    property p1;
        @(posedge clk) a |-> d;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        # 统计 graph 中的数据信号数
        data_signals = []
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            if node is None:
                continue
            if node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.REG):
                signal_name = node_id.split('.')[-1]
                if signal_name not in ('clk',):
                    data_signals.append(signal_name)

        # 统计 SVA 覆盖的信号数
        sva_signals = set()
        for prop in sva.properties.values():
            sva_signals.update(prop.signals)

        # 计算覆盖率
        if data_signals:
            covered = len(sva_signals & set(data_signals))
            total = len(data_signals)
            ratio = covered / total
            # a 和 d 被覆盖，b 和 c 未覆盖
            self.assertLess(ratio, 1.0, "覆盖率应 < 100%")


class TestSVAGapReporting(unittest.TestCase):
    """SVA 覆盖缺口报告"""

    def test_report_format(self):
        """[金标准] 覆盖缺口报告格式"""
        source = '''module top(input clk, input [7:0] a, b, output logic [7:0] c);
    always_ff @(posedge clk) c <= a + b;
    property p1;
        @(posedge clk) a |-> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        # gaps 应该是字符串列表
        for gap in gaps:
            self.assertIsInstance(gap, str)

    def test_gap_report_includes_signal_info(self):
        """[金标准] 缺口报告包含信号信息"""
        source = '''module top(input clk, input [7:0] a, b, output logic [7:0] c);
    always_ff @(posedge clk) c <= a + b;
    property p1;
        @(posedge clk) a |-> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        gaps = _find_coverage_gaps(graph, sva)
        # b 应在 gaps 中
        self.assertIn('b', gaps)


if __name__ == '__main__':
    unittest.main()
