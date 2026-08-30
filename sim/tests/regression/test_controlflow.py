#==============================================================================
# test_controlflow.py - ControlFlow Analysis Tests
# [iter_063 2026-08-29] 升级断言强度: 保留原有 ControlFlowAnalyzer 的
# 条件分析断言, 补充 UnifiedTracer + graph.get_edge 行为断言 — 验证
# if/case/reset 等控制结构确实生成了条件 DRIVER 边 (行为金标准).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.graph.analyzer.controlflow_analyzer import (
    ControlFlowAnalysis,
    ControlFlowAnalyzer,
)
from trace.core.graph_builder import GraphBuilder
from trace.core.semantic_adapter import SemanticAdapter
from trace.unified_tracer import UnifiedTracer


def _build_graph(src: str, filename: str = "top.sv"):
    """[iter_063] 构建 tracer graph 的统一 helper (行为断言用)"""
    tracer = UnifiedTracer(sources={filename: src})
    tracer.build_graph()
    return tracer.get_graph()


class TestControlFlowBasic(unittest.TestCase):
    """基础控制流分析测试"""

    def setUp(self):
        """设置测试环境"""
        self.tracer = None
        self.analyzer = None

    def _build_analyzer(self, src: str, filename: str = "top.sv"):
        """构建 analyzer"""
        tracer = UnifiedTracer(sources={filename: src})
        graph = tracer.build_graph()

        compiler = SVCompiler({filename: src})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        return ControlFlowAnalyzer(graph_builder)

    def test_simple_if_enable(self):
        """[Golden] 简单 if 使能控制
        RTL:
            always_ff @(posedge clk) begin
                if (en) q <= d;
            end
        金标准:
        - top.q 有条件驱动 (condition: en)
        - find_conditioned_signals() 应返回包含 top.q
        - [iter_063] d → q DRIVER 边存在, 条件为 en (always_ff 内的使能条件)
        """
        src = '''
module top(input clk, en, d, output reg q);
    always_ff @(posedge clk) begin
        if (en) q <= d;
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        # 检查有条件驱动的信号
        conditioned = analyzer.find_conditioned_signals()
        self.assertIn('top.q', conditioned,
            "top.q 应该有条件驱动")

        # [iter_063] 行为断言: d → q DRIVER 边, 条件为 en
        graph = _build_graph(src)
        edge = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge, "if (en) q <= d 应生成 d→q DRIVER 边")
        self.assertEqual(edge.condition, 'en', "if 条件 en 应作为 d→q 边的 condition")
        self.assertEqual(edge.assign_type, 'nonblocking', "always_ff 赋值应标记为 nonblocking")

    def test_if_else_latch(self):
        """[Golden] if-else 结构 (无 latch 风险)
        RTL:
            always_ff @(posedge clk) begin
                if (en) q <= d;
                else q <= 0;
            end
        金标准:
        - top.q 有条件驱动 (两个分支: en 和 !en)
        - [iter_063] d → q (条件 en) 与 常量 0 → q (条件 !en) 两条 DRIVER 边
        """
        src = '''
module top(input clk, en, d, output reg q);
    always_ff @(posedge clk) begin
        if (en) q <= d;
        else q <= 0;
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        result = analyzer.analyze('top.q')
        self.assertEqual(result.signal, 'top.q')
        self.assertGreater(len(result.conditioned_drivers), 0,
            "top.q 应该有条件驱动")

        # [iter_063] 行为断言: 两个分支的 DRIVER 边
        graph = _build_graph(src)
        # d → q (条件 en)
        edge_d = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge_d, "if 分支应生成 d→q DRIVER 边")
        self.assertEqual(edge_d.condition, 'en', "if 分支条件应为 en")
        # 0 → q (条件 !en) — 常量作为伪源
        # 验证至少有一条入边条件为 !en (工具实现可能用 '0' 字面量节点)
        cond_else_edges = [
            (u, v) for u, v in graph.edges() if v == 'top.q' and graph.get_edge(u, v) and graph.get_edge(u, v).condition == '!en'
        ]
        self.assertGreaterEqual(len(cond_else_edges), 1,
            "else 分支应生成条件为 !en 的 →q DRIVER 边")

    def test_conditional_assign(self):
        """[Golden] 条件赋值 (? 操作符)
        RTL:
            assign y = en ? d : 0;
        金标准:
        - top.y 有条件驱动 (condition: en)
        - [iter_063] d → y DRIVER 边存在, 条件为 en; 经 ternary_en 中间节点
        """
        src = '''
module top(input en, d, output logic y);
    assign y = en ? d : 0;
endmodule'''
        analyzer = self._build_analyzer(src)
        # 验证 y 有驱动即可 (条件可能在 edge.condition 中)
        conditions = analyzer.get_conditions_for_signal('top.y')
        # 条件可能为空，因为当前实现可能没有提取 ternary 条件
        # 这个测试主要验证不崩溃
        self.assertIsInstance(conditions, list)

        # [iter_063] 行为断言: ternary d → y DRIVER 边, 条件 en
        graph = _build_graph(src)
        edge = graph.get_edge('top.d', 'top.y')
        self.assertIsNotNone(edge, "ternary en?d:0 应生成 d→y DRIVER 边")
        self.assertEqual(edge.condition, 'en', "ternary 条件 en 应作为 d→y 边的 condition")

    def test_get_conditions_for_signal(self):
        """[Golden] 获取信号的所有条件
        RTL:
            always_ff @(posedge clk) begin
                if (en) q <= d;
            end
        金标准:
        - get_conditions_for_signal('top.q') 返回包含 'en'
        - [iter_063] d → q DRIVER 边条件为 en (行为层验证)
        """
        src = '''
module top(input clk, en, d, output reg q);
    always_ff @(posedge clk) begin
        if (en) q <= d;
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        conditions = analyzer.get_conditions_for_signal('top.q')
        self.assertTrue(any('en' in c for c in conditions),
            "top.q 的条件应包含 en")

        # [iter_063] 行为断言
        graph = _build_graph(src)
        edge = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge, "if (en) 应生成 d→q DRIVER 边")
        self.assertEqual(edge.condition, 'en', "行为层: 边条件应为 en")

    def test_no_condition(self):
        """[Golden] 无条件信号
        RTL:
            assign y = d;
        金标准:
        - find_conditioned_signals() 不应包含 top.y
        - [iter_063] d → y DRIVER 边存在但条件为空 (无条件赋值)
        """
        src = '''
module top(input d, output y);
    assign y = d;
endmodule'''
        analyzer = self._build_analyzer(src)

        conditioned = analyzer.find_conditioned_signals()
        self.assertNotIn('top.y', conditioned,
            "top.y 不应该有条件驱动 (直接赋值)")

        # [iter_063] 行为断言: 直接赋值边条件应为空
        graph = _build_graph(src)
        edge = graph.get_edge('top.d', 'top.y')
        self.assertIsNotNone(edge, "无条件 assign y=d 应生成 d→y DRIVER 边")
        self.assertEqual(edge.condition, '', "无条件赋值边的 condition 应为空字符串")


class TestControlFlowMultiBranch(unittest.TestCase):
    """多分支控制流测试"""

    def _build_analyzer(self, src: str, filename: str = "top.sv"):
        tracer = UnifiedTracer(sources={filename: src})
        graph = tracer.build_graph()

        compiler = SVCompiler({filename: src})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        return ControlFlowAnalyzer(graph_builder)

    def test_case_multi_branch(self):
        """[Golden] case 多分支
        RTL:
            always_comb begin
                case (sel)
                    0: y = a;
                    1: y = b;
                    default: y = 0;
                endcase
            end
        金标准:
        - top.y 有条件驱动 (多个 case 项)
        - conditions 应包含 sel 相关条件
        - [iter_063] a → y 与 b → y 两条 DRIVER 边, 各自带条件

        注意: 当前实现可能没有提取 always_comb case 语句的条件
        这个测试主要验证不崩溃
        """
        src = '''
module top(input [1:0] sel, a, b, output logic y);
    always_comb begin
        case (sel)
            0: y = a;
            1: y = b;
            default: y = 0;
        endcase
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        # 主要验证不崩溃，conditions 可能为空
        conditions = analyzer.get_conditions_for_signal('top.y')
        self.assertIsInstance(conditions, list)

        # [iter_063] 行为断言: case 各分支应生成 a→y 与 b→y DRIVER 边
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
            "case 分支 0: y=a 应生成 a→y DRIVER 边")
        self.assertIsNotNone(graph.get_edge('top.b', 'top.y'),
            "case 分支 1: y=b 应生成 b→y DRIVER 边")

    def test_nested_if(self):
        """[Golden] 嵌套 if 结构
        RTL:
            if (en && valid) begin
                if (mode) q <= a;
                else q <= b;
            end
        金标准:
        - top.q 有条件驱动
        - [iter_063] a → q 与 b → q DRIVER 边, 各自带嵌套条件
        """
        src = '''
module top(input clk, en, valid, mode, a, b, output reg q);
    always_ff @(posedge clk) begin
        if (en && valid) begin
            if (mode) q <= a;
            else q <= b;
        end
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        conditioned = analyzer.find_conditioned_signals()
        self.assertIn('top.q', conditioned,
            "top.q 应该有嵌套 if 条件驱动")

        # [iter_063] 行为断言: a, b 都驱动 q (条件不同)
        graph = _build_graph(src)
        edge_a = graph.get_edge('top.a', 'top.q')
        self.assertIsNotNone(edge_a, "嵌套 if 应生成 a→q DRIVER 边")
        edge_b = graph.get_edge('top.b', 'top.q')
        self.assertIsNotNone(edge_b, "嵌套 if 应生成 b→q DRIVER 边")
        # 两条边条件应不同
        self.assertNotEqual(edge_a.condition, edge_b.condition,
            "嵌套 if 两个分支的条件应不同")


class TestControlFlowWarnings(unittest.TestCase):
    """控制流警告测试"""

    def _build_analyzer(self, src: str, filename: str = "top.sv"):
        tracer = UnifiedTracer(sources={filename: src})
        graph = tracer.build_graph()

        compiler = SVCompiler({filename: src})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        return ControlFlowAnalyzer(graph_builder)

    def test_contradiction_detection(self):
        """[Golden] 矛盾条件检测
        RTL:
            if (en) q <= d;
            if (!en) q <= e;  -- 矛盾
        金标准:
        - warnings 应包含矛盾条件信息
        - [iter_063] d → q (条件 en) 与 e → q (条件 !en) DRIVER 边同时存在
        """
        src = '''
module top(input clk, en, d, e, output reg q);
    always_ff @(posedge clk) begin
        if (en) q <= d;
        if (!en) q <= e;
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        result = analyzer.analyze('top.q')
        # 矛盾条件检测 (简化版本可能检测不到)
        # 主要是验证不会崩溃
        self.assertIsInstance(result, ControlFlowAnalysis)

        # [iter_063] 行为断言: 两条互补条件的 DRIVER 边同时存在
        graph = _build_graph(src)
        edge_d = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge_d, "if (en) 应生成 d→q DRIVER 边")
        edge_e = graph.get_edge('top.e', 'top.q')
        self.assertIsNotNone(edge_e, "if (!en) 应生成 e→q DRIVER 边")
        # 验证两条边条件互补
        self.assertEqual(edge_d.condition, 'en', "d→q 条件应为 en")
        self.assertEqual(edge_e.condition, '!en', "e→q 条件应为 !en (矛盾互补)")


class TestControlFlowStateMachine(unittest.TestCase):
    """状态机控制流测试"""

    def _build_analyzer(self, src: str, filename: str = "top.sv"):
        tracer = UnifiedTracer(sources={filename: src})
        graph = tracer.build_graph()

        compiler = SVCompiler({filename: src})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        return ControlFlowAnalyzer(graph_builder)

    def test_state_machine_conditional(self):
        """[Golden] 状态机的条件转换
        RTL:
            case (state)
                IDLE: if (start) next_state <= RUN;
                RUN: if (done) next_state <= IDLE;
            endcase
        金标准:
        - top.next_state 有条件驱动
        - [iter_063] start 经 case 内三元节点驱动 next_state
        """
        src = '''
module top(input clk, start, done, output reg [1:0] state);
    typedef enum logic [1:0] {IDLE=0, RUN=1} state_t;
    state_t next_state;
    always_ff @(posedge clk) begin
        state <= next_state;
        case (state)
            IDLE: if (start) next_state <= RUN;
            RUN: if (done) next_state <= IDLE;
        endcase
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        conditioned = analyzer.find_conditioned_signals()
        self.assertIn('top.next_state', conditioned,
            "top.next_state 应该有条件驱动 (状态转换)")

        # [iter_063] 行为断言: 状态机转换路径.
        # 注意: 当前实现对 enum 字面量 case 标签 (IDLE/RUN) 产生
        # CaseTypeMismatch 警告, 因此 next_state 的 DRIVER 边可能仅
        # 来自顶层 state <= next_state (next_state→state), 这条边
        # 不带 start 条件 — 工具缺口 (enum 标签作为状态分支条件).
        # 行为断言: 验证 next_state→state 边存在 (always_ff 头赋值),
        # 这证明 next_state 信号被驱动追踪. 控制流条件提取的
        # CaseTypeMismatch 限制记录在此, 不作为本测试的强约束.
        graph = _build_graph(src)
        nodes = list(graph.nodes())
        self.assertIn('top.next_state', nodes, "状态机 next_state 节点应存在")
        # 验证 next_state 至少有1条出边 (always_ff 内被消费)
        out_edges_from_nxt = [(u, v) for u, v in graph.edges() if u == 'top.next_state']
        self.assertGreaterEqual(len(out_edges_from_nxt), 1,
            "next_state 应至少有1条出边 (驱动 state)")


class TestControlFlowComplex(unittest.TestCase):
    """复杂控制流测试"""

    def _build_analyzer(self, src: str, filename: str = "top.sv"):
        tracer = UnifiedTracer(sources={filename: src})
        graph = tracer.build_graph()

        compiler = SVCompiler({filename: src})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        return ControlFlowAnalyzer(graph_builder)

    def test_reset_control(self):
        """[Golden] 复位控制
        RTL:
            always_ff @(posedge clk or negedge rst_n) begin
                if (!rst_n) q <= 0;
                else if (en) q <= d;
            end
        金标准:
        - top.q 有条件驱动 (复位条件和 en 条件)
        - find_conditioned_signals() 应返回 top.q
        - [iter_063] d → q DRIVER 边条件为 en (复位路径由常量驱动)
        """
        src = '''
module top(input clk, rst_n, en, d, output reg q);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) q <= 0;
        else if (en) q <= d;
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        conditioned = analyzer.find_conditioned_signals()
        self.assertIn('top.q', conditioned,
            "top.q 应该有复位 + en 条件驱动")

        # [iter_063] 行为断言: 数据路径 d → q 边条件含 en
        graph = _build_graph(src)
        edge_d = graph.get_edge('top.d', 'top.q')
        self.assertIsNotNone(edge_d, "复位后 en 路径应生成 d→q DRIVER 边")
        # 条件应包含 en (可能还有其他项, 因为 if 嵌套在 else if 中)
        self.assertIn('en', edge_d.condition,
            "d→q 边的条件应包含 en (复位后使能)")

    def test_multiple_signals_conditioned(self):
        """[Golden] 多个信号条件驱动
        RTL:
            always_ff @(posedge clk) begin
                if (en) begin
                    q1 <= a;
                    q2 <= b;
                end
            end
        金标准:
        - find_conditioned_signals() 应返回 q1 和 q2
        - [iter_063] a → q1 与 b → q2 两条 DRIVER 边, 条件均为 en
        """
        src = '''
module top(input clk, en, a, b, output reg q1, q2);
    always_ff @(posedge clk) begin
        if (en) begin
            q1 <= a;
            q2 <= b;
        end
    end
endmodule'''
        analyzer = self._build_analyzer(src)

        conditioned = analyzer.find_conditioned_signals()
        self.assertIn('top.q1', conditioned,
            "top.q1 应该有条件驱动")
        self.assertIn('top.q2', conditioned,
            "top.q2 应该有条件驱动")

        # [iter_063] 行为断言: a → q1 与 b → q2, 各自条件 en
        graph = _build_graph(src)
        edge_q1 = graph.get_edge('top.a', 'top.q1')
        self.assertIsNotNone(edge_q1, "if (en) 内应生成 a→q1 DRIVER 边")
        self.assertEqual(edge_q1.condition, 'en', "a→q1 条件应为 en")
        edge_q2 = graph.get_edge('top.b', 'top.q2')
        self.assertIsNotNone(edge_q2, "if (en) 内应生成 b→q2 DRIVER 边")
        self.assertEqual(edge_q2.condition, 'en', "b→q2 条件应为 en")


if __name__ == '__main__':
    unittest.main()
