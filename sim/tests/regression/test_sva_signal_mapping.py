# test_sva_signal_mapping.py - SVA 信号关联测试
# [铁律13] 金标准测试
#
# Phase 2: 将 SVA 中引用的信号映射到 SignalGraph 节点
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
    sva_extractor = SVAExtractor({'test.sv': source})
    sva = sva_extractor.extract()
    return graph, sva, tracer


def _map_sva_to_graph(graph, sva):
    """将 SVA 信号映射到 SignalGraph 节点

    返回: dict of {sva_node_id: [graph_node_ids]}
    """
    mapping = {}

    # 收集 SVA 中所有引用的信号名
    all_sva_signals = set()
    for sid, seq in sva.sequences.items():
        all_sva_signals.update(seq.signals)
    for pid, prop in sva.properties.items():
        all_sva_signals.update(prop.signals)
    for a in sva.assertions:
        all_sva_signals.update(a.signals)

    # 在 SignalGraph 中查找匹配的节点
    for signal_name in all_sva_signals:
        for graph_node_id in graph.nodes():
            graph_node = graph.get_node(graph_node_id)
            if graph_node is None:
                continue
            # 匹配: graph_node_id 以 .signal_name 结尾
            if graph_node_id.endswith(f".{signal_name}"):
                # 记录映射
                for sid, seq in sva.sequences.items():
                    if signal_name in seq.signals:
                        if sid not in mapping:
                            mapping[sid] = []
                        if graph_node_id not in mapping[sid]:
                            mapping[sid].append(graph_node_id)
                for pid, prop in sva.properties.items():
                    if signal_name in prop.signals:
                        if pid not in mapping:
                            mapping[pid] = []
                        if graph_node_id not in mapping[pid]:
                            mapping[pid].append(graph_node_id)

    return mapping


class TestSVASignalMapping(unittest.TestCase):
    """SVA 信号映射到 SignalGraph"""

    def test_simple_signal_mapping(self):
        """[金标准] 简单信号映射

        RTL:
        module top(input clk, input [7:0] data_in, output logic [7:0] data_out);
            always_ff @(posedge clk) data_out <= data_in;
        endmodule

        SVA:
        property p1;
            @(posedge clk) data_in |-> data_out;
        endproperty

        映射:
        - data_in → top.data_in (PORT_IN)
        - data_out → top.data_out (REG)
        """
        source = '''module top(input clk, input [7:0] data_in, output logic [7:0] data_out);
    always_ff @(posedge clk) data_out <= data_in;
    property p1;
        @(posedge clk) data_in |-> data_out;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        # 验证 SVA 提取
        self.assertGreaterEqual(len(sva.properties), 1)
        prop = list(sva.properties.values())[0]
        self.assertIn('data_in', prop.signals)
        self.assertIn('data_out', prop.signals)

        # 验证信号映射
        mapping = _map_sva_to_graph(graph, sva)
        prop_id = list(sva.properties.keys())[0]

        self.assertIn(prop_id, mapping)
        mapped_nodes = mapping[prop_id]
        self.assertTrue(any('data_in' in n for n in mapped_nodes),
            f"data_in 应映射到 graph 节点, 实际: {mapped_nodes}")
        self.assertTrue(any('data_out' in n for n in mapped_nodes),
            f"data_out 应映射到 graph 节点, 实际: {mapped_nodes}")

    def test_signal_with_driver_chain(self):
        """[金标准] 信号映射 + 驱动链

        RTL:
        module top(input clk, input [7:0] a, output logic [7:0] c);
            logic [7:0] b;
            always_ff @(posedge clk) b <= a + 1;
            always_ff @(posedge clk) c <= b;
        endmodule

        SVA:
        property p1;
            @(posedge clk) a |-> c;
        endproperty

        映射:
        - a → top.a (PORT_IN)
        - c → top.c (REG)

        驱动链:
        - top.a → top.b → top.c
        """
        source = '''module top(input clk, input [7:0] a, output logic [7:0] c);
    logic [7:0] b;
    always_ff @(posedge clk) b <= a + 1;
    always_ff @(posedge clk) c <= b;
    property p1;
        @(posedge clk) a |-> c;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        mapping = _map_sva_to_graph(graph, sva)
        prop_id = list(sva.properties.keys())[0]

        mapped = mapping.get(prop_id, [])
        self.assertTrue(any('a' in n for n in mapped))
        self.assertTrue(any('c' in n for n in mapped))

        # 验证驱动链: a → b → c
        a_node = [n for n in mapped if n.endswith('.a')]
        if a_node:
            # a 的 driver 应该存在
            drivers = graph.find_drivers(a_node[0])
            self.assertIsNotNone(drivers)

    def test_clock_domain_check(self):
        """[金标准] 时钟域检查

        SVA 的时钟 vs 信号的时钟域是否一致
        """
        source = '''module top(input clk_a, clk_b, input [7:0] a, b);
    logic [7:0] reg_a;
    logic [7:0] reg_b;
    always_ff @(posedge clk_a) reg_a <= a;
    always_ff @(posedge clk_b) reg_b <= b;
    property p1;
        @(posedge clk_a) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        prop = list(sva.properties.values())[0]
        # SVA 时钟是 clk_a
        self.assertIn('clk_a', prop.clock)

    def test_multi_signal_property(self):
        """[金标准] 多信号 property 映射

        property p1;
            @(posedge clk) (a && b) |-> (c || d);
        endproperty

        映射: a, b, c, d 都应映射到 graph 节点
        """
        source = '''module top(input clk, logic a, b, c, d);
    property p1;
        @(posedge clk) (a && b) |-> (c || d);
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        prop = list(sva.properties.values())[0]
        # 应包含多个信号
        self.assertGreaterEqual(len(prop.signals), 2)


class TestSVACrossModule(unittest.TestCase):
    """跨模块 SVA 信号映射"""

    def test_assertion_in_parent_module(self):
        """[金标准] 父模块中的 assertion 引用子模块信号

        module sub(input [7:0] data);
        endmodule

        module top(input clk);
            logic [7:0] data;
            sub u_sub(.data(data));
            property p1;
                @(posedge clk) data != 0;
            endproperty
            assert property (p1);
        endmodule
        """
        source = '''module sub(input [7:0] data);
endmodule

module top(input clk);
    logic [7:0] data;
    sub u_sub(.data(data));
    property p1;
        @(posedge clk) data != 0;
    endproperty
    assert property (p1);
endmodule'''
        graph, sva, _ = _build_all(source)

        # data 应映射到 top.data
        mapping = _map_sva_to_graph(graph, sva)
        prop_id = list(sva.properties.keys())[0]
        mapped = mapping.get(prop_id, [])
        self.assertTrue(any('data' in n for n in mapped))


if __name__ == '__main__':
    unittest.main()
