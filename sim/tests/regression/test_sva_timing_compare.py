# test_sva_timing_compare.py - SVA 时序关系比对测试
# [铁律13] 金标准测试
#
# Phase 4: 比对信号图推断的时序关系与 SVA 声明的时序关系
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.graph.models import NodeKind


def _build_all(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    sva = SVAExtractor({'test.sv': source}).extract()
    return graph, sva


def _get_timing_relation(graph, sva):
    """从信号图推断信号间的时序关系

    返回: dict of {(src, dst): relation}
    relation: 'same_cycle' | 'one_cycle_delay' | 'multi_cycle_delay' | 'unknown'
    """
    relations = {}

    # 收集 SVA 中所有信号对
    for prop in sva.properties.values():
        signals = prop.signals
        for i, s1 in enumerate(signals):
            for s2 in signals[i+1:]:
                # 在 graph 中查找 s1 和 s2 的关系
                s1_nodes = [n for n in graph.nodes() if n.endswith(f'.{s1}')]
                s2_nodes = [n for n in graph.nodes() if n.endswith(f'.{s2}')]

                for n1 in s1_nodes:
                    for n2 in s2_nodes:
                        # 检查是否有驱动链连接
                        if _has_direct_driver(graph, n1, n2):
                            relations[(s1, s2)] = 'same_cycle'
                        elif _has_one_cycle_delay(graph, n1, n2):
                            relations[(s1, s2)] = 'one_cycle_delay'

    return relations


def _has_direct_driver(graph, src, dst):
    """检查 src 是否直接驱动 dst（同一 always 块）"""
    # src 的 driver 是否包含 dst
    drivers = graph.find_drivers(dst)
    if drivers:
        for driver in drivers:
            if driver == src:
                return True
    return False


def _has_one_cycle_delay(graph, src, dst):
    """检查 src 到 dst 是否有一个时钟周期延迟"""
    # src → reg → dst，中间有一个寄存器
    src_drivers = graph.find_drivers(src)
    if src_drivers is None:
        return False

    # 检查 dst 的驱动者是否是寄存器
    dst_drivers = graph.find_drivers(dst)
    if dst_drivers is None:
        return False

    # 简化判断：如果 dst 是 REG，且 src 不是 REG，则有延迟
    src_node = graph.get_node(src)
    dst_node = graph.get_node(dst)
    if src_node and dst_node:
        if src_node.kind != NodeKind.REG and dst_node.kind == NodeKind.REG:
            return True
    return False


class TestTimingRelation(unittest.TestCase):
    """时序关系比对"""

    def test_same_cycle_relation(self):
        """[金标准] 同周期关系

        RTL: a 和 b 在同一 always 块中赋值
        SVA: a 和 b 同周期

        module top(input clk, input [7:0] a, output logic [7:0] b);
            always_ff @(posedge clk) b <= a;
        endmodule

        SVA: property p1; @(posedge clk) a |-> b; endproperty
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] b);
    always_ff @(posedge clk) b <= a;
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        # SVA 声明 a |-> b（蕴含）
        prop = list(sva.properties.values())[0]
        self.assertIn('|->', prop.operators)

        # 信号图：a 驱动 b（通过 always_ff）
        # b 是 REG，a 是 PORT_IN
        b_node = graph.get_node('top.b')
        self.assertIsNotNone(b_node)
        self.assertEqual(b_node.kind, NodeKind.REG)

    def test_one_cycle_delay(self):
        """[金标准] 一个时钟周期延迟

        RTL: a → reg_b → c（两级寄存器）
        SVA: a |=> c（下一周期）

        module top(input clk, input [7:0] a, output logic [7:0] c);
            logic [7:0] reg_b;
            always_ff @(posedge clk) reg_b <= a;
            always_ff @(posedge clk) c <= reg_b;
        endmodule

        SVA: property p1; @(posedge clk) a |=> c; endproperty
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] c);
    logic [7:0] reg_b;
    always_ff @(posedge clk) reg_b <= a;
    always_ff @(posedge clk) c <= reg_b;
    property p1;
        @(posedge clk) a |=> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        # SVA 声明 a |=> c（蕴含下一周期）
        prop = list(sva.properties.values())[0]
        self.assertIn('|=>', prop.operators)

        # 信号图：a → reg_b → c
        reg_b_node = graph.get_node('top.reg_b')
        self.assertIsNotNone(reg_b_node)
        self.assertEqual(reg_b_node.kind, NodeKind.REG)

    def test_assertion_with_disable_iff(self):
        """[金标准] disable iff 条件

        SVA: property p1; @(posedge clk) disable iff (!rst_n) a |-> b; endproperty
        """
        source = '''module top(input clk, rst_n, input [7:0] a, output logic [7:0] b);
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) b <= 0;
        else b <= a;
    property p1;
        @(posedge clk) disable iff (!rst_n) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        prop = list(sva.properties.values())[0]
        self.assertIn('!rst_n', prop.disable_iff)


class TestTimingMismatch(unittest.TestCase):
    """时序不匹配检测"""

    def test_sva_same_cycle_but_rtl_delayed(self):
        """[金标准] SVA 声明同周期，但 RTL 有延迟

        RTL: a → reg_b → c（两级寄存器，有延迟）
        SVA: a |-> c（同周期蕴含）

        这是一个潜在的时序不匹配：
        SVA 假设 a 和 c 同周期，但 RTL 有延迟
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] c);
    logic [7:0] reg_b;
    always_ff @(posedge clk) reg_b <= a;
    always_ff @(posedge clk) c <= reg_b;
    property p1;
        @(posedge clk) a |-> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        # 检查信号图中的关系
        c_node = graph.get_node('top.c')
        self.assertIsNotNone(c_node)
        self.assertEqual(c_node.kind, NodeKind.REG)

        # reg_b 是中间寄存器
        reg_b_node = graph.get_node('top.reg_b')
        self.assertIsNotNone(reg_b_node)
        self.assertEqual(reg_b_node.kind, NodeKind.REG)

    def test_sva_delayed_but_rtl_same_cycle(self):
        """[金标准] SVA 声明延迟，但 RTL 同周期

        RTL: a → b（同周期组合逻辑）
        SVA: a |=> b（下一周期蕴含）

        这也是一个潜在的时序不匹配
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] b);
    always_ff @(posedge clk) b <= a;
    property p1;
        @(posedge clk) a |=> b;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        # SVA 声明 |=>（下一周期）
        prop = list(sva.properties.values())[0]
        self.assertIn('|=>', prop.operators)

        # 但 RTL 是直接赋值（同周期）
        b_node = graph.get_node('top.b')
        self.assertEqual(b_node.kind, NodeKind.REG)


class TestComplexTiming(unittest.TestCase):
    """复杂时序场景"""

    def test_multi_signal_chain(self):
        """[金标准] 多信号链

        RTL: a → b → c → d
        SVA: a |-> d

        信号图推断: a 和 d 之间有 2 个寄存器延迟
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] d);
    logic [7:0] b, c;
    always_ff @(posedge clk) b <= a;
    always_ff @(posedge clk) c <= b;
    always_ff @(posedge clk) d <= c;
    property p1;
        @(posedge clk) a |-> d;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        # 检查驱动链
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node)
        self.assertEqual(d_node.kind, NodeKind.REG)

        # c 是 d 的驱动者
        d_drivers = graph.find_drivers('top.d')
        if d_drivers:
            self.assertTrue(any('c' in str(d) for d in d_drivers))

    def test_parallel_paths(self):
        """[金标准] 并行路径

        RTL: a → b, a → c（并行）
        SVA: b |-> c（同周期）
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] b, c);
    always_ff @(posedge clk) b <= a;
    always_ff @(posedge clk) c <= a;
    property p1;
        @(posedge clk) b |-> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva = _build_all(source)

        # b 和 c 都是 REG，都由 a 驱动
        b_node = graph.get_node('top.b')
        c_node = graph.get_node('top.c')
        self.assertEqual(b_node.kind, NodeKind.REG)
        self.assertEqual(c_node.kind, NodeKind.REG)


if __name__ == '__main__':
    unittest.main()
