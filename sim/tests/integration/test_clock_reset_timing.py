#==============================================================================
# test_clock_reset_timing.py - Clock/Reset/Timing edge tests
#==============================================================================
"""
[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律18] 负面测试原则
[铁律20] 全面性原则

更新: 2026-05-10 增强弱断言，验证边类型和具体行为
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind, NodeKind


class TestClockEdge(unittest.TestCase):
    """CLOCK edge tests"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_clock_edge_posedge(self):
        """[金标准] Clock posedge edge
        
        金标准:
        RTL: always_ff @(posedge clk) q <= d;
        期望:
        - CLOCK 边: clk -> q
        """
        source = '''
module top(input clk, input d, output logic q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            f"应有CLOCK边: clk -> q，实际: {clock_edges}")
    
    def test_clock_edge_negedge(self):
        """[边界][金标准] Clock negedge edge
        
        金标准:
        RTL: always_ff @(negedge clk) q <= d;
        期望:
        - CLOCK 边: clk -> q (negedge 触发)
        """
        source = '''
module top(input clk, input d, output logic q);
    always_ff @(negedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 节点存在
        self.assertIn('top.clk', graph.nodes(), "clk节点应存在")
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言2: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            f"应有CLOCK边: clk -> q，实际: {clock_edges}")
    
    def test_clock_edge_both_edge(self):
        """[边界][金标准] Both clock edges (双沿触发)
        
        金标准:
        RTL: always_ff @(posedge clk or negedge clk) q <= d;
        期望:
        - CLOCK 边: clk -> q (任一沿触发)
        """
        source = '''
module top(input clk, input d, output logic q);
    always_ff @(posedge clk or negedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 节点存在
        self.assertIn('top.clk', graph.nodes(), "clk节点应存在")
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言2: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            f"应有CLOCK边: clk -> q，实际: {clock_edges}")


class TestResetEdge(unittest.TestCase):
    """RESET edge tests"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_async_reset_posedge(self):
        """[金标准] Async positive reset edge
        
        金标准:
        RTL: always_ff @(posedge clk or posedge rst) q <= 1'b0;
        期望:
        - CLOCK 边: clk -> q
        - RESET 边: rst -> q
        """
        source = '''
module top(input clk, input rst, output logic q);
    always_ff @(posedge clk or posedge rst) q <= 1'b0;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            f"应有CLOCK边: clk -> q，实际: {clock_edges}")
        
        # 强断言2: RESET 边存在
        reset_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.RESET]
        self.assertIn(('top.rst', 'top.q'), reset_edges,
            f"应有RESET边: rst -> q，实际: {reset_edges}")
    
    def test_async_reset_negedge(self):
        """[边界][金标准] Async negative reset (低有效复位)
        
        金标准:
        RTL: always_ff @(posedge clk or negedge rst_n) q <= 1'b0;
        期望:
        - CLOCK 边: clk -> q
        - RESET 边: rst_n -> q
        """
        source = '''
module top(input clk, input rst_n, output logic q);
    always_ff @(posedge clk or negedge rst_n) q <= 1'b0;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 节点存在
        self.assertIn('top.rst_n', graph.nodes(), "rst_n节点应存在")
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言2: RESET 边存在
        reset_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.RESET]
        self.assertIn(('top.rst_n', 'top.q'), reset_edges,
            f"应有RESET边: rst_n -> q，实际: {reset_edges}")
        
        # 强断言3: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            f"应有CLOCK边: clk -> q，实际: {clock_edges}")


class TestTimingControl(unittest.TestCase):
    """Timing control tests"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_delay_control(self):
        """[边界][金标准] #delay timing control
        
        金标准:
        RTL: always #5 q <= d;
        期望:
        - 不崩溃
        - 图构建成功
        - 注: 延时控制 (#5) 当前作为普通语句处理，不影响核心功能
        """
        source = '''
module top(input clk, input d, output logic q);
    always #5 q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 不崩溃
        self.assertIsNotNone(graph, "延时控制不应导致崩溃")
        
        # 强断言2: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
    
    def test_event_control(self):
        """[边界][金标准] @event timing control
        
        金标准:
        RTL: always @(posedge clk) q <= d;
        期望:
        - 不崩溃
        - 图构建成功
        - 事件控制被跳过（当前实现限制）
        """
        source = '''
module top(input clk, input d, output logic q);
    always @(posedge clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 不崩溃
        self.assertIsNotNone(graph, "事件控制不应导致崩溃")
        
        # 强断言2: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
    
    def test_wait_control(self):
        """[边界][金标准] wait control
        
        金标准:
        RTL: always wait(clk) q <= d;
        期望:
        - 不崩溃
        - 图构建成功
        - wait 控制被跳过（当前实现限制）
        """
        source = '''
module top(input clk, input d, output logic q);
    always wait(clk) q <= d;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 不崩溃
        self.assertIsNotNone(graph, "wait控制不应导致崩溃")
        
        # 强断言2: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")


class TestMultiClockDomain(unittest.TestCase):
    """Multi-clock domain tests"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_dual_clock_independent(self):
        """[金标准] Two independent clocks
        
        金标准:
        RTL:
          always_ff @(posedge clk1) q1 <= d1;
          always_ff @(posedge clk2) q2 <= d2;
        期望:
        - CLOCK 边: clk1 -> q1
        - CLOCK 边: clk2 -> q2
        - 两个独立时钟域
        """
        source = '''
module top(input clk1, clk2, input d1, d2, output logic q1, q2);
    always_ff @(posedge clk1) q1 <= d1;
    always_ff @(posedge clk2) q2 <= d2;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 所有节点存在
        self.assertIn('top.clk1', graph.nodes(), "clk1节点应存在")
        self.assertIn('top.clk2', graph.nodes(), "clk2节点应存在")
        self.assertIn('top.q1', graph.nodes(), "q1节点应存在")
        self.assertIn('top.q2', graph.nodes(), "q2节点应存在")
        
        # 强断言2: 两个独立 CLOCK 边
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk1', 'top.q1'), clock_edges,
            f"应有CLOCK边: clk1 -> q1，实际: {clock_edges}")
        self.assertIn(('top.clk2', 'top.q2'), clock_edges,
            f"应有CLOCK边: clk2 -> q2，实际: {clock_edges}")
        
        # 强断言3: 两个时钟域独立
        clk1_edges = [e for e in clock_edges if e[0] == 'top.clk1']
        clk2_edges = [e for e in clock_edges if e[0] == 'top.clk2']
        self.assertEqual(len(clk1_edges), 1, "clk1应有1条CLOCK边")
        self.assertEqual(len(clk2_edges), 1, "clk2应有1条CLOCK边")
    
    def test_clock_domain_cdc(self):
        """[边界][金标准] CDC crossing (跨时钟域)
        
        金标准:
        RTL:
          always_ff @(posedge clk1) sync <= d1;  // clk1 域
          always_ff @(posedge clk2) q <= sync;   // clk2 域
        期望:
        - CLOCK 边: clk1 -> sync (clk1 域)
        - CLOCK 边: clk2 -> q (clk2 域)
        - DRIVER 边: sync -> q (CDC 数据传递)
        - sync 作为 CDC 中继信号
        """
        source = '''
module top(input clk1, clk2, input d1, output logic q);
    logic sync;
    always_ff @(posedge clk1) sync <= d1;
    always_ff @(posedge clk2) q <= sync;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 强断言1: 所有节点存在
        self.assertIn('top.clk1', graph.nodes(), "clk1节点应存在")
        self.assertIn('top.clk2', graph.nodes(), "clk2节点应存在")
        self.assertIn('top.sync', graph.nodes(), "sync节点应存在")
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言2: 两个域的 CLOCK 边
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk1', 'top.sync'), clock_edges,
            f"应有CLOCK边: clk1 -> sync，实际: {clock_edges}")
        self.assertIn(('top.clk2', 'top.q'), clock_edges,
            f"应有CLOCK边: clk2 -> q，实际: {clock_edges}")
        
        # 强断言3: DRIVER 边: sync -> q (CDC 数据传递)
        driver_edges = [(src, dst) for src, dst in graph.edges()
                       if graph.get_edge(src, dst).kind == EdgeKind.DRIVER]
        self.assertIn(('top.sync', 'top.q'), driver_edges,
            f"应有DRIVER边: sync -> q，实际: {driver_edges}")


if __name__ == '__main__':
    unittest.main()
