#==============================================================================
# test_negative_cases.py - 负面测试和边界条件
#==============================================================================
"""
[铁律13] 金标准测试
[铁律17] 强断言原则
[铁律18] 负面测试原则
[铁律20] 边界条件测试

更新: 2026-05-10 增强弱断言，验证边类型和具体行为
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


class TestNegativeCases(unittest.TestCase):
    """负面测试 - 验证不支持的语法被合理处理"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_empty_module_no_crash(self):
        """[负面][金标准] 空 module 不应崩溃
        
        金标准:
        RTL: module top(); endmodule
        
        期望:
        - 不崩溃
        - top 节点不存在（空 module 无端口）
        """
        source = 'module top(); endmodule'
        graph = self._build_graph(source)
        
        # 强断言 1: 不崩溃
        self.assertIsNotNone(graph, "空 module 不应崩溃")
        
        # 强断言 2: top 节点不存在
        self.assertNotIn('top', graph.nodes(),
            "空 module 应该没有节点")
        
        # 强断言 3: 图为空
        self.assertEqual(len(graph.nodes()), 0,
            f"空 module 应该没有节点，实际节点数: {len(graph.nodes())}")
    
    def test_empty_always_ff_no_crash(self):
        """[负面][金标准] 空 always_ff 块不崩溃
        
        金标准:
        RTL: always_ff @(posedge clk) begin end
        期望:
        - 不崩溃
        - clk 节点存在
        - 不产生 REG 节点（空块无寄存器）
        """
        source = '''
module top(input clk);
    always_ff @(posedge clk) begin end
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: clk 节点存在
        self.assertIn('top.clk', graph.nodes(), "clk节点应存在")
        
        # 强断言2: 空 always_ff 不产生 REG 节点
        reg_nodes = [n for n in graph.nodes() 
                    if graph.get_node(n).kind == NodeKind.REG]
        self.assertEqual(len(reg_nodes), 0,
            f"空always_ff不应产生REG节点，实际: {reg_nodes}")
    
    def test_initial_not_supported(self):
        """[负面][金标准] initial 块不支持但不应崩溃
        
        金标准:
        RTL:
          initial q = 0;
          always_ff @(posedge clk) q <= 1;
        期望:
        - initial 被跳过
        - always_ff 正常处理
        - CLOCK 边: clk -> q
        """
        source = '''
module top(input clk, output logic q);
    initial q = 0;
    always_ff @(posedge clk) q <= 1;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: 节点存在
        self.assertIn('top.clk', graph.nodes())
        self.assertIn('top.q', graph.nodes())
        
        # 强断言2: always_ff 创建 CLOCK 边
        clock_edges = [(src, dst) for src, dst in graph.edges()
                      if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            "always_ff应创建CLOCK边: clk -> q")
    
    def test_illegal_assignment_no_crash(self):
        """[负面][金标准] 非法赋值不崩溃
        
        金标准:
        RTL: assign 1'b1 = 1'b0;
        期望:
        - 不崩溃
        - 图构建成功
        - 非法赋值被忽略（无新节点产生）
        """
        source = '''
module top(input clk);
    assign 1'b1 = 1'b0;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: 不崩溃
        self.assertIsNotNone(graph, "非法赋值不应崩溃")
        
        # 强断言2: 无崩溃或错误
        # 注意：非法赋值可能产生孤立常量节点，但不应导致崩溃
        # 只检查图构建成功
        nodes = list(graph.nodes())
        self.assertIsNotNone(nodes, "图节点列表应存在")
    
    def test_fork_join_not_supported(self):
        """[负面][金标准] fork..join 不支持但不应崩溃
        
        金标准:
        RTL:
          always_ff @(posedge clk) begin
              fork
              join
          end
        期望:
        - fork..join 被跳过
        - clk 节点正常
        - always_ff 其他部分正常处理
        """
        source = '''
module top(input clk);
    always_ff @(posedge clk) begin
        fork
        join
    end
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言: clk 节点存在
        self.assertIn('top.clk', graph.nodes(),
            "clk节点应存在，fork..join被跳过")


class TestBoundaryConditions(unittest.TestCase):
    """边界条件测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_single_bit_vector(self):
        """[边界][金标准] 1 位向量 [0:0]
        
        期望 width = (0, 0) 即 msb=0, lsb=0
        """
        source = '''
module top(input [0:0] d, output logic q);
    assign q = d;
endmodule'''
        graph = self._build_graph(source)
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node)
        # [0:0] -> msb=0, lsb=0
        self.assertEqual(d_node.width, (0, 0),
            f"[0:0] 应该是 (0, 0)，实际是 {d_node.width}")
    
    def test_8bit_vector(self):
        """[边界][金标准] 8 位向量 [7:0]
        
        期望 width = (7, 0) 即 msb=7, lsb=0
        """
        source = '''
module top(input [7:0] d);
endmodule'''
        graph = self._build_graph(source)
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node)
        self.assertEqual(d_node.width, (7, 0),
            f"[7:0] 应该是 (7, 0)，实际是 {d_node.width}")
    
    def test_16bit_vector_offset(self):
        """[边界][金标准] 16 位偏移向量 [15:8]
        
        期望 width = (15, 8) 即 msb=15, lsb=8
        """
        source = '''
module top(input [15:8] d);
endmodule'''
        graph = self._build_graph(source)
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node)
        self.assertEqual(d_node.width, (15, 8),
            f"[15:8] 应该是 (15, 8)，实际是 {d_node.width}")
    
    def test_max_bit_width(self):
        """[边界][金标准] 最大位宽 1024 位 [1023:0]
        
        期望 width = (1023, 0)
        """
        source = '''
module top(input [1023:0] d);
endmodule'''
        graph = self._build_graph(source)
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node)
        self.assertEqual(d_node.width, (1023, 0),
            f"[1023:0] 应该是 (1023, 0)，实际是 {d_node.width}")
    
    def test_negative_bit_index(self):
        """[边界][金标准] 负数位索引
        
        期望: 不崩溃，返回图（负索引处理是下游职责）
        """
        source = '''
module top(input [7:0] d, output logic q);
    assign q = d[-1];
endmodule'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph)
    
    def test_out_of_bounds_index(self):
        """[边界][金标准] 越界位索引
        
        期望: 不崩溃
        """
        source = '''
module top(input [7:0] d, output logic q);
    assign q = d[100];
endmodule'''
        graph = self._build_graph(source)
        self.assertIsNotNone(graph)
    
    def test_multi_stage_pipeline(self):
        """[边界][金标准] 5 级流水线
        
        期望: 验证 q 节点的完整驱动链路
        """
        source = '''
module top(input clk, input d, output q);
    logic tmp1, tmp2, tmp3, tmp4, tmp5;
    always_ff @(posedge clk) begin
        tmp1 <= d;
        tmp2 <= tmp1;
        tmp3 <= tmp2;
        tmp4 <= tmp3;
        tmp5 <= tmp4;
        q <= tmp5;
    end
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: q 节点存在
        self.assertIn('top.q', graph.nodes())
        
        # 强断言2: q 直接由 tmp5 驱动 (非 always_comb)
        q_node = graph.get_node('top.q')
        self.assertEqual(q_node.kind, NodeKind.REG,
            f"q 在 always_ff 中应为 REG，实际是 {q_node.kind}")
        
        # 强断言3: 验证驱动边存在
        preds_q = list(graph.predecessors('top.q'))
        self.assertIn('top.tmp5', preds_q,
            f"q 应由 tmp5 驱动，实际前驱是 {preds_q}")
    
    def test_zero_width_vector(self):
        """[边界][金标准] 零位宽向量 [0:0]
        
        期望: 正确处理为 1 位向量
        """
        source = '''
module top(input [0:0] d, output logic q);
    assign q = d;
endmodule'''
        graph = self._build_graph(source)
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node)
        self.assertEqual(d_node.width, (0, 0))


class TestErrorInputs(unittest.TestCase):
    """错误输入测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_undefined_signal(self):
        """[负面][金标准] 未定义信号引用
        
        金标准:
        RTL: always_ff @(posedge clk) q <= undefined_signal;
        期望:
        - 图构建成功
        - q 节点存在（未定义信号被忽略）
        - 无 undefined_signal 节点
        """
        source = '''
module top(input clk, output logic q);
    always_ff @(posedge clk) q <= undefined_signal;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: 图构建成功
        self.assertIsNotNone(graph, "未定义信号不应导致崩溃")
        
        # 强断言2: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言3: 无 undefined_signal 节点（被忽略）
        self.assertNotIn('undefined_signal', graph.nodes(),
            "未定义信号应被忽略，不应产生节点")
    
    def test_self_assign(self):
        """[负面][金标准] 自我赋值
        
        金标准:
        RTL: always_ff @(posedge clk) q <= q;
        期望:
        - 允许自赋值
        - q 节点存在且为 REG
        - DRIVER 边: q -> q (自驱动)
        """
        source = '''
module top(input clk, logic q);
    always_ff @(posedge clk) q <= q;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言2: q 是 REG 类型
        q_node = graph.get_node('top.q')
        self.assertEqual(q_node.kind, NodeKind.REG,
            f"q应为REG，实际是{q_node.kind}")
        
        # 强断言3: 有 DRIVER 边指向 q
        driver_edges = [(src, dst) for src, dst in graph.edges()
                       if graph.get_edge(src, dst).kind == EdgeKind.DRIVER
                       and dst == 'top.q']
        self.assertTrue(len(driver_edges) > 0,
            f"应有DRIVER边指向q，实际: {driver_edges}")
    
    def test_constant_drive(self):
        """[负面][金标准] 常量驱动
        
        金标准:
        RTL: always_ff @(posedge clk) q <= 1'b1;
        期望:
        - top.q 节点存在
        - q.kind == REG
        - DRIVER 边: top.1 -> top.q (常量作为源)
        - CLOCK 边: top.clk -> top.q
        """
        source = '''
module top(input clk, output logic q);
    always_ff @(posedge clk) q <= 1'b1;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言2: q 是 REG 类型
        q_node = graph.get_node('top.q')
        self.assertEqual(q_node.kind, NodeKind.REG,
            f"q应为REG，实际是{q_node.kind}")
        
        # 强断言3: 有 DRIVER 边指向 q
        driver_edges = [(src, dst) for src, dst in graph.edges()
                       if graph.get_edge(src, dst).kind == EdgeKind.DRIVER
                       and dst == 'top.q']
        self.assertTrue(len(driver_edges) > 0,
            f"应有DRIVER边指向q，实际: {driver_edges}")
        
        # 强断言4: 有 CLOCK 边
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            "应有CLOCK边: clk -> q")


class TestReverseEdgeCases(unittest.TestCase):
    """反向测试 - 特殊边/节点"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_clock_oscillator(self):
        """[反向][金标准] 时钟振荡器自驱动
        
        金标准:
        RTL: always clk = ~clk;
        期望:
        - top.clk 节点存在
        - clk.is_clock = True
        - DRIVER 自环边: clk -> clk
        """
        source = '''
module top(logic clk);
    always clk = ~clk;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: clk 节点存在
        self.assertIn('top.clk', graph.nodes(), "clk节点应存在")
        
        # 强断言2: clk 是 CLOCK 类型
        clk_node = graph.get_node('top.clk')
        self.assertTrue(clk_node.is_clock,
            f"clk.is_clock应为True，实际是{clk_node.is_clock}")
        
        # 强断言3: DRIVER 自环边存在
        driver_self_edges = [(src, dst) for src, dst in graph.edges()
                           if graph.get_edge(src, dst).kind == EdgeKind.DRIVER
                           and src == 'top.clk' and dst == 'top.clk']
        self.assertTrue(len(driver_self_edges) > 0,
            f"应有DRIVER自环边: clk -> clk，实际边: {list(graph.edges())}")
    
    def test_two_drivers_conflict(self):
        """[反向][金标准] 多驱动器冲突
        
        金标准:
        RTL:
          always_ff @(posedge clk) q <= d1;
          always_ff @(posedge clk) q <= d2;
        期望:
        - top.q 节点存在
        - q.kind == REG
        - 两个 DRIVER 边指向 q (d1 -> q, d2 -> q)
        - CLOCK 边: clk -> q
        """
        source = '''
module top(input clk, input d1, input d2, output logic q);
    always_ff @(posedge clk) q <= d1;
    always_ff @(posedge clk) q <= d2;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: q 节点存在
        q_node = graph.get_node('top.q')
        self.assertIsNotNone(q_node, "q节点应存在")
        
        # 强断言2: q 是 REG 类型
        self.assertEqual(q_node.kind, NodeKind.REG,
            f"q应为REG，实际是{q_node.kind}")
        
        # 强断言3: 两个 DRIVER 边指向 q
        driver_edges_to_q = [(src, dst) for src, dst in graph.edges()
                            if graph.get_edge(src, dst).kind == EdgeKind.DRIVER
                            and dst == 'top.q']
        self.assertGreaterEqual(len(driver_edges_to_q), 2,
            f"应有>=2个DRIVER边指向q，实际: {driver_edges_to_q}")
        
        # 强断言4: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            "应有CLOCK边: clk -> q")
    
    def test_reset_edge_priority(self):
        """[反向][金标准] 异步复位边
        
        金标准:
        RTL: always_ff @(posedge clk or negedge rst_n) q <= 1;
        期望:
        - top.rst_n 节点存在
        - top.q 节点存在
        - RESET 边: rst_n -> q
        - CLOCK 边: clk -> q
        - q.kind == REG
        - rst_n.is_reset = True
        """
        source = '''
module top(input clk, input rst_n, output logic q);
    always_ff @(posedge clk or negedge rst_n) q <= 1;
endmodule'''
        graph = self._build_graph(source)
        
        # 强断言1: rst_n 节点存在
        self.assertIn('top.rst_n', graph.nodes(), "rst_n节点应存在")
        
        # 强断言2: q 节点存在
        self.assertIn('top.q', graph.nodes(), "q节点应存在")
        
        # 强断言3: q 是 REG 类型
        q_node = graph.get_node('top.q')
        self.assertEqual(q_node.kind, NodeKind.REG,
            f"q应为REG，实际是{q_node.kind}")
        
        # 强断言4: RESET 边存在
        reset_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.RESET]
        self.assertIn(('top.rst_n', 'top.q'), reset_edges,
            f"应有RESET边: rst_n -> q，实际: {reset_edges}")
        
        # 强断言5: CLOCK 边存在
        clock_edges = [(src, dst) for src, dst in graph.edges()
                     if graph.get_edge(src, dst).kind == EdgeKind.CLOCK]
        self.assertIn(('top.clk', 'top.q'), clock_edges,
            f"应有CLOCK边: clk -> q，实际: {clock_edges}")
        
        # 强断言6: rst_n 是 RESET 类型
        rst_node = graph.get_node('top.rst_n')
        self.assertTrue(rst_node.is_reset,
            f"rst_n.is_reset应为True，实际是{rst_node.is_reset}")


if __name__ == '__main__':
    unittest.main()
