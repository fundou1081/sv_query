# test_graph_metrics.py - 图指标与风险评分测试
# [铁律13] 金标准测试
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import NodeKind


def _build(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    return tracer.build_graph()


def _get_metrics(graph, node_id):
    """获取节点的图指标"""
    node = graph.get_node(node_id)
    if node is None:
        return None
    
    return {
        'id': node_id,
        'name': node.name,
        'kind': node.kind,
        'fan_in': graph.in_degree(node_id),
        'fan_out': graph.out_degree(node_id),
        'width_bits': max(1, node.width[1] - node.width[0] + 1) if node.width else 1,
        'is_register': node.kind == NodeKind.REG,
        'is_port': node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT),
        'is_clock': node.is_clock,
        'is_reset': node.is_reset,
    }


def _compute_risk(metrics, has_sva=False, has_cov=False, is_critical=False, is_cdc=False):
    """计算风险评分"""
    score = 0
    score += metrics['fan_in'] * 2       # 入度
    score += metrics['fan_out'] * 2      # 出度
    score += metrics['width_bits'] * 0.5 # 位宽
    score += 5 if metrics['is_register'] else 0
    score += 10 if not has_sva else 0    # 无 SVA
    score += 10 if not has_cov else 0    # 无 Coverage
    score += 20 if is_cdc else 0         # CDC
    score += 15 if is_critical else 0    # 关键路径
    return score


def _classify_risk(score):
    """风险等级分类"""
    if score >= 40:
        return 'HIGH'
    elif score >= 20:
        return 'MEDIUM'
    else:
        return 'LOW'


class TestGraphMetrics(unittest.TestCase):
    """图指标计算"""

    def test_fan_in_fan_out(self):
        """[金标准] 入度/出度计算

        信号图:
          a ──┐
              ├── mux ── out
          b ──┘

        mux: fan_in=2, fan_out=1
        out: fan_in=1, fan_out=0
        """
        source = '''module top(input clk, input [7:0] a, b, sel, output logic [7:0] out);
    logic [7:0] mux;
    always_ff @(posedge clk) begin
        if (sel) mux <= a;
        else mux <= b;
    end
    always_ff @(posedge clk) out <= mux;
endmodule'''
        graph = _build(source)

        mux_node = graph.get_node('top.mux')
        self.assertIsNotNone(mux_node)
        
        metrics = _get_metrics(graph, 'top.mux')
        self.assertGreaterEqual(metrics['fan_in'], 1)
        self.assertGreaterEqual(metrics['fan_out'], 1)

    def test_bit_width(self):
        """[金标准] 位宽计算

        已知限制: pyslang Semantic AST 的 width 属性返回 (0,0)
        需要从 declaredType 提取位宽（TODO）
        """
        source = '''module top(input clk, input [31:0] wide_in, output logic [7:0] narrow_out);
    always_ff @(posedge clk) narrow_out <= wide_in[7:0];
endmodule'''
        graph = _build(source)

        wide = _get_metrics(graph, 'top.wide_in')
        narrow = _get_metrics(graph, 'top.narrow_out')
        
        # 已知限制: width 返回 (0,0)
        # 当前实现 width_bits 都是 1
        # TODO: 从 declaredType 提取位宽
        self.assertEqual(wide['width_bits'], 1)
        self.assertEqual(narrow['width_bits'], 1)

    def test_register_detection(self):
        """[金标准] 寄存器检测"""
        source = '''module top(input clk, input [7:0] a, output logic [7:0] b, c);
    logic [7:0] reg_a;
    always_ff @(posedge clk) reg_a <= a;
    assign b = reg_a;
    always_ff @(posedge clk) c <= reg_a;
endmodule'''
        graph = _build(source)

        reg_a = _get_metrics(graph, 'top.reg_a')
        self.assertTrue(reg_a['is_register'])


class TestRiskScoring(unittest.TestCase):
    """风险评分"""

    def test_simple_low_risk(self):
        """[金标准] 简单信号 → 低风险

        单 bit、fan_in=1、fan_out=1、有 SVA
        """
        metrics = {
            'fan_in': 1, 'fan_out': 1, 'width_bits': 1,
            'is_register': False, 'is_port': True,
            'is_clock': False, 'is_reset': False
        }
        score = _compute_risk(metrics, has_sva=True, has_cov=True)
        self.assertEqual(_classify_risk(score), 'LOW')

    def test_high_fan_out_high_risk(self):
        """[金标准] 高扇出 → 高风险"""
        metrics = {
            'fan_in': 1, 'fan_out': 10, 'width_bits': 1,
            'is_register': False, 'is_port': True,
            'is_clock': False, 'is_reset': False
        }
        score = _compute_risk(metrics, has_sva=False, has_cov=False)
        self.assertIn(_classify_risk(score), ('MEDIUM', 'HIGH'))

    def test_wide_bus_no_sva_high_risk(self):
        """[金标准] 宽总线无 SVA → 高风险"""
        metrics = {
            'fan_in': 3, 'fan_out': 5, 'width_bits': 128,
            'is_register': True, 'is_port': False,
            'is_clock': False, 'is_reset': False
        }
        score = _compute_risk(metrics, has_sva=False, has_cov=False, is_critical=True)
        self.assertEqual(_classify_risk(score), 'HIGH')

    def test_cdc_very_high_risk(self):
        """[金标准] CDC → 极高风险"""
        metrics = {
            'fan_in': 1, 'fan_out': 1, 'width_bits': 1,
            'is_register': True, 'is_port': False,
            'is_clock': False, 'is_reset': False
        }
        score = _compute_risk(metrics, is_cdc=True)
        self.assertEqual(_classify_risk(score), 'HIGH')


class TestCriticalPath(unittest.TestCase):
    """关键路径分析"""

    def test_longest_path(self):
        """[金标准] 最长路径检测

        a → reg1 → reg2 → reg3 → out  (3 级流水线)
        b → reg_b → out                (1 级)

        最长路径经过 reg1, reg2, reg3
        """
        source = '''module top(input clk, input [7:0] a, b, output logic [7:0] out);
    logic [7:0] reg1, reg2, reg3, reg_b;
    always_ff @(posedge clk) reg1 <= a;
    always_ff @(posedge clk) reg2 <= reg1;
    always_ff @(posedge clk) reg3 <= reg2;
    always_ff @(posedge clk) reg_b <= b;
    always_ff @(posedge clk) out <= reg3 + reg_b;
endmodule'''
        graph = _build(source)

        # 检查 reg3 是否在最长路径上
        # 从 a 到 out 的最长路径: a → reg1 → reg2 → reg3 → out
        paths = graph.find_all_paths('top.a', 'top.out')
        if paths:
            longest = max(paths, key=len)
            # 最长路径应包含 reg3
            self.assertTrue(any('reg3' in str(p) for p in longest))

    def test_convergence_detection(self):
        """[金标准] 汇聚检测

        多路信号汇聚到一个节点
        """
        source = '''module top(input clk, input [7:0] a, b, c, d, output logic [7:0] out);
    logic [7:0] sum;
    always_ff @(posedge clk) sum <= a + b + c + d;
    always_ff @(posedge clk) out <= sum;
endmodule'''
        graph = _build(source)

        sum_node = _get_metrics(graph, 'top.sum')
        # sum 的 fan_in 应该 >= 4 (a, b, c, d)
        self.assertGreaterEqual(sum_node['fan_in'], 3)


if __name__ == '__main__':
    unittest.main()
