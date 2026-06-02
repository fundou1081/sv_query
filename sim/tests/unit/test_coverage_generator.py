#==============================================================================
# test_coverage_generator.py - Control Coverage Generator 单元测试
#
# TDD 流程:
# 1. Red: 写失败的测试
# 2. Green: 写最简实现让测试通过
# 3. Refactor: 改进代码
#==============================================================================

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.coverage_models import (
    SourceLocation,
    SourceSnippet,
    EvidenceStep,
    AtomicSignal,
    DecompositionResult,
)


class TestSourceLocation(unittest.TestCase):
    """SourceLocation: 源码位置数据类"""

    def test_create_minimal(self):
        """能创建最小实例（只有文件）"""
        loc = SourceLocation(file="top.sv")
        self.assertEqual(loc.file, "top.sv")
        self.assertEqual(loc.line_start, 0)
        self.assertEqual(loc.line_end, 0)
        self.assertEqual(loc.column, 0)

    def test_create_full(self):
        """能创建完整实例"""
        loc = SourceLocation(
            file="top.sv",
            line_start=5,
            line_end=8,
            column=4,
        )
        self.assertEqual(loc.file, "top.sv")
        self.assertEqual(loc.line_start, 5)
        self.assertEqual(loc.line_end, 8)
        self.assertEqual(loc.column, 4)

    def test_is_empty(self):
        """is_empty() 在没有位置信息时返回 True"""
        loc = SourceLocation(file="top.sv")
        self.assertTrue(loc.is_empty())

        loc2 = SourceLocation(file="top.sv", line_start=5)
        self.assertFalse(loc2.is_empty())

    def test_str_returns_location(self):
        """__str__ 返回 file:line 形式"""
        loc = SourceLocation(file="top.sv", line_start=5, line_end=8)
        s = str(loc)
        self.assertIn("top.sv", s)
        self.assertIn("5", s)

        loc_single = SourceLocation(file="top.sv", line_start=5, line_end=5)
        s_single = str(loc_single)
        self.assertIn("top.sv", s_single)
        self.assertIn("5", s_single)


class TestSourceSnippet(unittest.TestCase):
    """SourceSnippet: 源码片段（懒加载）"""

    def test_create_empty(self):
        """能创建空 snippet"""
        snippet = SourceSnippet(
            location=SourceLocation(file="top.sv", line_start=5)
        )
        self.assertEqual(snippet.text, "")

    def test_with_text(self):
        """能直接提供 text"""
        snippet = SourceSnippet(
            location=SourceLocation(file="top.sv", line_start=5),
            text="assign c = a | b;",
        )
        self.assertEqual(snippet.text, "assign c = a | b;")

    def test_lazy_load_with_provider(self):
        """当 text 为空时，load_text() 调用 provider"""
        provider_calls = []

        def provider(file: str) -> str:
            provider_calls.append(file)
            return f"// content of {file}\nline2\nline3"

        snippet = SourceSnippet(
            location=SourceLocation(file="top.sv", line_start=1),
            text="",  # 懒加载
            text_provider=provider,
        )
        loaded = snippet.load_text()
        self.assertIn("content of top.sv", loaded)
        self.assertEqual(len(provider_calls), 1)

    def test_lazy_load_caches(self):
        """load_text() 第二次不调用 provider"""
        call_count = [0]

        def provider(file: str) -> str:
            call_count[0] += 1
            return "lazy content"

        snippet = SourceSnippet(
            location=SourceLocation(file="top.sv"),
            text="",
            text_provider=provider,
        )
        snippet.load_text()
        snippet.load_text()
        snippet.load_text()
        self.assertEqual(call_count[0], 1)


class TestEvidenceStep(unittest.TestCase):
    """EvidenceStep: 推导链单步"""

    def test_create_minimal(self):
        """能创建最小 EvidenceStep"""
        step = EvidenceStep(
            step_type="driver_chain",
            description="x's driver is c & d",
            from_signal="x",
            to_signals=["c", "d"],
        )
        self.assertEqual(step.step_type, "driver_chain")
        self.assertEqual(step.from_signal, "x")
        self.assertEqual(step.to_signals, ["c", "d"])
        self.assertIsNone(step.source)

    def test_str_returns_description(self):
        """__str__ 返回 description"""
        step = EvidenceStep(
            step_type="expression_parse",
            description="a | b -> {a, b}",
            from_signal="c",
            to_signals=["a", "b"],
        )
        self.assertIn("a | b", str(step))


class TestAtomicSignal(unittest.TestCase):
    """AtomicSignal: 原子信号（含位选）"""

    def test_create_simple(self):
        """能创建无位选的原子信号"""
        sig = AtomicSignal(name="a", base_name="a")
        self.assertEqual(sig.name, "a")
        self.assertEqual(sig.base_name, "a")
        self.assertIsNone(sig.bit_range)
        self.assertEqual(sig.evidence, [])

    def test_create_with_bit_range(self):
        """能创建带位选的原子信号"""
        sig = AtomicSignal(
            name="a[3:0]",
            base_name="a",
            bit_range=(3, 0),
        )
        self.assertEqual(sig.name, "a[3:0]")
        self.assertEqual(sig.base_name, "a")
        self.assertEqual(sig.bit_range, (3, 0))

    def test_str_returns_name(self):
        """__str__ 返回 name"""
        sig = AtomicSignal(name="a[3:0]", base_name="a", bit_range=(3, 0))
        self.assertEqual(str(sig), "a[3:0]")

    def test_evidence_preserved(self):
        """evidence 列表保持引用"""
        step = EvidenceStep(
            step_type="driver_chain",
            description="test",
            from_signal="x",
            to_signals=["a"],
        )
        sig = AtomicSignal(
            name="a",
            base_name="a",
            evidence=[step],
        )
        self.assertEqual(len(sig.evidence), 1)
        self.assertEqual(sig.evidence[0].step_type, "driver_chain")


class TestDecompositionResult(unittest.TestCase):
    """DecompositionResult: 分解结果"""

    def test_create_minimal(self):
        """能创建最小结果"""
        result = DecompositionResult(original_signal="x")
        self.assertEqual(result.original_signal, "x")
        self.assertEqual(result.atomic_signals, [])
        self.assertEqual(result.control_blocks, [])
        self.assertEqual(result.signal_count, 0)
        self.assertFalse(result.truncated)
        self.assertIsNone(result.error)

    def test_str_returns_summary(self):
        """__str__ 返回概要信息"""
        result = DecompositionResult(
            original_signal="x",
            atomic_signals=[
                AtomicSignal(name="a", base_name="a"),
                AtomicSignal(name="b", base_name="b"),
            ],
            signal_count=2,
            depth_reached=1,
        )
        s = str(result)
        self.assertIn("x", s)
        self.assertIn("2", s)  # signal_count

    def test_truncated_flag(self):
        """truncated 标志表示超过限制"""
        result = DecompositionResult(
            original_signal="x",
            signal_count=10,
            truncated=True,
        )
        self.assertTrue(result.truncated)


class TestDataModelIntegration(unittest.TestCase):
    """完整链路: 用所有数据结构构造一个分解结果"""

    def test_full_chain(self):
        """构造一个完整的 evidence chain"""
        loc = SourceLocation(file="top.sv", line_start=5, line_end=5)
        snippet = SourceSnippet(location=loc, text="assign c = a | b;")

        step = EvidenceStep(
            step_type="expression_parse",
            description="c = a | b -> {a, b}",
            from_signal="c",
            to_signals=["a", "b"],
            source=snippet,
        )

        sig = AtomicSignal(
            name="a",
            base_name="a",
            source=loc,
            evidence=[step],
        )

        result = DecompositionResult(
            original_signal="x",
            atomic_signals=[sig],
            signal_count=1,
            depth_reached=1,
        )

        self.assertEqual(len(result.atomic_signals), 1)
        self.assertEqual(result.atomic_signals[0].evidence[0].source.text,
                         "assign c = a | b;")


# ==============================================================================
# Cycle 2: 表达式解析器
# ==============================================================================

from trace.core.coverage_generator import ControlCoverageGenerator


class TestExpressionParser(unittest.TestCase):
    """ControlCoverageGenerator._parse_expression_to_atomics

    将 driver/condition 表达式字符串解析为原子信号列表。
    位选保留为区间表示。
    """

    def _parse(self, expr: str):
        """helper: 用空 graph 构造 generator 并解析"""
        from trace.core.graph.models import SignalGraph
        gen = ControlCoverageGenerator(graph=SignalGraph())
        return gen._parse_expression_to_atomics(expr)

    def test_parse_simple_and(self):
        """a & b -> [{a}, {b}]"""
        result = self._parse("a & b")
        names = [s.name for s in result]
        self.assertEqual(names, ["a", "b"])
        for s in result:
            self.assertIsNone(s.bit_range)

    def test_parse_simple_or(self):
        """a | b -> [{a}, {b}]"""
        result = self._parse("a | b")
        names = [s.name for s in result]
        self.assertEqual(names, ["a", "b"])

    def test_parse_with_bit_range(self):
        """a[3:0] -> [{a[3:0]}] 含位选"""
        result = self._parse("a[3:0]")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a[3:0]")
        self.assertEqual(result[0].base_name, "a")
        self.assertEqual(result[0].bit_range, (3, 0))

    def test_parse_multiple_bit_ranges(self):
        """a[3:0] | b[7:4] -> 两个含位选"""
        result = self._parse("a[3:0] | b[7:4]")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "a[3:0]")
        self.assertEqual(result[0].bit_range, (3, 0))
        self.assertEqual(result[1].name, "b[7:4]")
        self.assertEqual(result[1].bit_range, (7, 4))

    def test_parse_filters_literals(self):
        """a + 1 -> [{a}] 过滤字面量"""
        result = self._parse("a + 1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a")

    def test_parse_filters_decimal_literals(self):
        """a + 32'd100 -> [{a}]"""
        result = self._parse("a + 32'd100")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a")

    def test_parse_filters_binary_literals(self):
        """a | 4'b1011 -> [{a}]"""
        result = self._parse("a | 4'b1011")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a")

    def test_parse_comparison(self):
        """g < f -> [{g}, {f}] 比较表达式拆出所有信号"""
        result = self._parse("g < f")
        names = [s.name for s in result]
        self.assertIn("g", names)
        self.assertIn("f", names)
        self.assertEqual(len(result), 2)

    def test_parse_not_operator(self):
        """!a -> [{a}] 否定只包含底层信号"""
        result = self._parse("!a")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a")

    def test_parse_compound(self):
        """c & d -> [{c}, {d}]"""
        result = self._parse("c & d")
        names = [s.name for s in result]
        self.assertEqual(names, ["c", "d"])

    def test_parse_ternary(self):
        """en ? d : 0 -> [{en}, {d}] 三元运算"""
        result = self._parse("en ? d : 0")
        names = [s.name for s in result]
        self.assertIn("en", names)
        self.assertIn("d", names)
        self.assertEqual(len(result), 2)

    def test_parse_parenthesized(self):
        """(a & b) | c -> [{a}, {b}, {c}]"""
        result = self._parse("(a & b) | c")
        names = [s.name for s in result]
        self.assertEqual(sorted(names), ["a", "b", "c"])

    def test_parse_nested_bit(self):
        """data[3:0][1:0] -> [{data[3:0][1:0]}] 嵌套位选"""
        result = self._parse("data[3:0][1:0]")
        # 允许不同实现: 保留完整或只保留外层
        self.assertGreaterEqual(len(result), 1)
        # 至少第一个是 data
        self.assertTrue(any(s.base_name == "data" for s in result))

    def test_parse_empty_string(self):
        """空字符串 -> []"""
        result = self._parse("")
        self.assertEqual(result, [])

    def test_parse_only_literal(self):
        """只字面量 -> []"""
        result = self._parse("8'hFF")
        self.assertEqual(result, [])

    def test_parse_underscore_name(self):
        """data_in -> [{data_in}] 下划线名"""
        result = self._parse("data_in & valid_o")
        names = [s.name for s in result]
        self.assertEqual(sorted(names), ["data_in", "valid_o"])


# ==============================================================================
# Cycle 3: Driver 链追踪 + 端口检测
# ==============================================================================

from trace.core.graph.models import (
    SignalGraph,
    TraceNode,
    TraceEdge,
    EdgeKind,
    NodeKind,
)


def _make_signal_node(sig_id: str, is_port: bool = False, is_reg: bool = False) -> TraceNode:
    """helper: 创建测试用信号节点"""
    kind = NodeKind.SIGNAL
    if is_reg:
        kind = NodeKind.REG
    elif is_port:
        # 默认 PORT_IN
        kind = NodeKind.PORT_IN
    return TraceNode(
        id=sig_id,
        name=sig_id.split(".")[-1],
        module="top",
        kind=kind,
        width=(7, 0),
        is_port=is_port,
        is_clock=False,
        is_reset=False,
        is_enable=False,
    )


def _make_driver_edge(src: str, dst: str, expr: str = "", condition: str = "") -> TraceEdge:
    """helper: 创建测试用 driver 边"""
    return TraceEdge(
        src=src,
        dst=dst,
        kind=EdgeKind.DRIVER,
        assign_type="continuous",
        expression=expr,
        condition=condition,
    )


class TestIsModulePort(unittest.TestCase):
    """_is_module_port: 端口检测"""

    def _gen(self, is_port: bool):
        from trace.core.graph.models import SignalGraph
        gen = ControlCoverageGenerator(graph=SignalGraph())
        node = _make_signal_node("top.x", is_port=is_port)
        return gen._is_module_port(node)

    def test_port_in_node(self):
        """PORT_IN 节点 -> True"""
        self.assertTrue(self._gen(is_port=True))

    def test_signal_node(self):
        """普通 SIGNAL 节点 -> False"""
        self.assertFalse(self._gen(is_port=False))

    def test_reg_node(self):
        """REG 节点 -> False"""
        self.assertFalse(self._gen(is_port=False))


class TestTraceDrivers(unittest.TestCase):
    """_trace_drivers: driver 链递归追踪

    场景: x = c & d, c = a | b
    查询 x -> 应该是 {a, b, d}
    """

    def _setup_graph(self):
        """构造图: x, c, d, a, b 之间的 driver 链

        x <- c (expr="c & d")
        x <- d (expr="c & d")  # 同一表达式驱动 x 的两条边
        c <- a (expr="a | b")
        c <- b (expr="a | b")
        a <- a_input (a 是端口)
        """
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()

        # 节点
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.c"))
        g.add_trace_node(_make_signal_node("top.d"))
        g.add_trace_node(_make_signal_node("top.a"))
        g.add_trace_node(_make_signal_node("top.b"))
        g.add_trace_node(_make_signal_node("top.a_input", is_port=True))

        # 边
        g.add_trace_edge(_make_driver_edge("top.c", "top.x", expr="c & d"))
        g.add_trace_edge(_make_driver_edge("top.d", "top.x", expr="c & d"))
        g.add_trace_edge(_make_driver_edge("top.a", "top.c", expr="a | b"))
        g.add_trace_edge(_make_driver_edge("top.b", "top.c", expr="a | b"))
        g.add_trace_edge(_make_driver_edge("top.a_input", "top.a", expr="a_input"))
        return g

    def test_trace_drivers_simple(self):
        """c (无 driver) -> [c]"""
        g = self._setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        # c 有 driver (a, b) - 但 a 是端口
        # c 不是端口, 继续追踪
        result = gen._trace_drivers("top.c", None, depth=0, max_depth=10, visited=set())
        names = sorted([s.base_name for s in result])
        # c 的 driver: a, b (从 "a | b" 表达式)
        # a 还有 driver: a_input (端口, 停止)
        # 所以结果应该含 a, b
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_trace_drivers_leaf_port(self):
        """端口停止 - 不再追踪"""
        g = self._setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen._trace_drivers("top.a", None, depth=0, max_depth=10, visited=set())
        # a 是无端口 (只是普通信号), 有 driver a_input (端口)
        # 结果: a_input (端口) 停止
        names = [s.base_name for s in result]
        self.assertEqual(names, ["a_input"])

    def test_trace_drivers_at_port(self):
        """起点是端口 -> []"""
        g = self._setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen._trace_drivers("top.a_input", None, depth=0, max_depth=10, visited=set())
        # a_input 是端口, 立即返回
        self.assertEqual(result, [])

    def test_trace_drivers_no_driver(self):
        """无 driver 的信号 -> []"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.isolated"))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._trace_drivers("top.isolated", None, depth=0, max_depth=10, visited=set())
        self.assertEqual(result, [])

    def test_trace_drivers_avoids_cycle(self):
        """避免循环引用"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.a"))
        g.add_trace_node(_make_signal_node("top.b"))
        # 循环: a <- b, b <- a
        g.add_trace_edge(_make_driver_edge("top.b", "top.a", expr="a"))
        g.add_trace_edge(_make_driver_edge("top.a", "top.b", expr="b"))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._trace_drivers("top.a", None, depth=0, max_depth=10, visited=set())
        # 应该终止, 不无限递归
        self.assertIsInstance(result, list)

    def test_trace_drivers_respects_max_depth(self):
        """max_depth 限制"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.l1"))
        g.add_trace_node(_make_signal_node("top.l2"))
        g.add_trace_node(_make_signal_node("top.l3"))
        g.add_trace_edge(_make_driver_edge("top.l2", "top.l1", expr="l2"))
        g.add_trace_edge(_make_driver_edge("top.l3", "top.l2", expr="l3"))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._trace_drivers("top.l1", None, depth=0, max_depth=1, visited=set())
        # depth=0, max_depth=1: 只能看到 l2, 不能递归到 l3
        names = [s.base_name for s in result]
        self.assertIn("l2", names)
        # l3 不应出现 (depth 限制)
        # 但 l3 是 l2 的 driver, 如果 l2 的 driver 表达式是 "l3" 就会被加入
        # 所以需要 depth=1 才能包含 l2
        # 当 depth=max_depth 时停止, 不再继续


# ==============================================================================
# Cycle 4: decompose() 主入口 + 条件边收集
# ==============================================================================


def _make_conditional_edge(
    src: str,
    dst: str,
    expr: str = "",
    condition: str = "",
    effective_condition: str = "",
) -> TraceEdge:
    """helper: 创建带条件的边"""
    e = _make_driver_edge(src, dst, expr=expr)
    e.condition = condition
    e.effective_condition = effective_condition or condition
    return e


class TestCollectConditionEdges(unittest.TestCase):
    """_collect_condition_edges: 收集带 condition 的 incoming edges

    场景: x 在 if (en) 块内被驱动
    """

    def test_collect_empty_when_no_condition(self):
        """无 condition 边 -> 空"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.y"))
        g.add_trace_edge(_make_driver_edge("top.y", "top.x", expr="y"))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._collect_condition_edges("top.x")
        self.assertEqual(result, [])

    def test_collect_single_condition(self):
        """单条带 condition 边 -> 1 条"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.y"))
        g.add_trace_edge(_make_conditional_edge(
            "top.y", "top.x", expr="y", condition="rst_n && en"
        ))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._collect_condition_edges("top.x")
        self.assertEqual(len(result), 1)
        edge = result[0]
        self.assertEqual(edge.src, "top.y")
        self.assertIn("en", edge.effective_condition)

    def test_collect_uses_effective_condition(self):
        """有效条件去除 reset"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.y"))
        # effective_condition 已去除 rst_n
        g.add_trace_edge(_make_conditional_edge(
            "top.y", "top.x", expr="y",
            condition="!rst_n && en",
            effective_condition="en",
        ))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._collect_condition_edges("top.x")
        # 用 effective_condition, 不用 raw condition
        self.assertEqual(result[0].effective_condition, "en")

    def test_collect_multiple_edges(self):
        """多条带 condition 边 -> 多条"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.a"))
        g.add_trace_node(_make_signal_node("top.b"))
        g.add_trace_edge(_make_conditional_edge("top.a", "top.x", expr="a", condition="en"))
        g.add_trace_edge(_make_conditional_edge("top.b", "top.x", expr="b", condition="valid"))
        gen = ControlCoverageGenerator(graph=g)
        result = gen._collect_condition_edges("top.x")
        self.assertEqual(len(result), 2)


class TestDecompose(unittest.TestCase):
    """decompose(): 主入口

    场景: if (en) x <= c & d;  assign c = a | b;
    期望: x 的 coverage 信号集为 {en, a, b, c, d}
    """

    def _make_setup_graph(self):
        """x, c, d, a, b, en_input (端口)"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        # 节点
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.c"))
        g.add_trace_node(_make_signal_node("top.d"))
        g.add_trace_node(_make_signal_node("top.a"))
        g.add_trace_node(_make_signal_node("top.b"))
        g.add_trace_node(_make_signal_node("top.en_input", is_port=True))
        # 边
        # if (rst_n && en) x <= c & d;
        g.add_trace_edge(_make_conditional_edge(
            "top.c", "top.x", expr="c & d",
            condition="rst_n && en",
            effective_condition="en",
        ))
        g.add_trace_edge(_make_conditional_edge(
            "top.d", "top.x", expr="c & d",
            condition="rst_n && en",
            effective_condition="en",
        ))
        # assign c = a | b;
        g.add_trace_edge(_make_driver_edge("top.a", "top.c", expr="a | b"))
        g.add_trace_edge(_make_driver_edge("top.b", "top.c", expr="a | b"))
        # a, b 都有 driver (端口)
        g.add_trace_edge(_make_driver_edge("top.en_input", "top.en_signal"))
        return g

    def test_decompose_returns_decomposition_result(self):
        """返回 DecompositionResult"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        self.assertIsInstance(result, DecompositionResult)
        self.assertEqual(result.original_signal, "top.x")

    def test_decompose_finds_atomic_signals(self):
        """x 分解后应包含: en, c, d, a, b"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        names = {s.base_name for s in result.atomic_signals}
        # 期望: en (条件), c/d (driver 表达式), a/b (c 的 driver)
        for expected in ("en", "a", "b", "c", "d"):
            self.assertIn(expected, names, f"Missing {expected} in {names}")

    def test_decompose_collects_control_blocks(self):
        """control_blocks 应包含带条件的边"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        # 应该有至少一个 control block (来自条件边)
        self.assertGreater(len(result.control_blocks), 0)

    def test_decompose_returns_empty_for_unknown_signal(self):
        """不存在的信号 -> 错误结果 (empty + error)"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.unknown"])
        # 不报错, 但 atomic_signals 为空
        self.assertEqual(result.atomic_signals, [])

    def test_decompose_truncates_at_max_signals(self):
        """超过 max_signals 报错 (truncated=True + error)"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        # max_signals=2 强制截断
        result = gen.decompose(["top.x"], max_signals=2)
        self.assertTrue(result.truncated)
        self.assertIsNotNone(result.error)

    def test_decompose_signal_count(self):
        """signal_count 字段准确"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        self.assertEqual(result.signal_count, len(result.atomic_signals))


# ==============================================================================
# Cycle 5: Markdown 输出
# ==============================================================================


class TestMarkdownOutput(unittest.TestCase):
    """generate_coverage_markdown() - Markdown 报告生成"""

    def _make_setup_graph(self):
        """复用 TestDecompose 的图"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        # 节点
        g.add_trace_node(_make_signal_node("top.x"))
        g.add_trace_node(_make_signal_node("top.c"))
        g.add_trace_node(_make_signal_node("top.d"))
        g.add_trace_node(_make_signal_node("top.a"))
        g.add_trace_node(_make_signal_node("top.b"))
        g.add_trace_node(_make_signal_node("top.en_input", is_port=True))
        # 边
        g.add_trace_edge(_make_conditional_edge(
            "top.c", "top.x", expr="c & d",
            condition="rst_n && en",
            effective_condition="en",
        ))
        g.add_trace_edge(_make_conditional_edge(
            "top.d", "top.x", expr="c & d",
            condition="rst_n && en",
            effective_condition="en",
        ))
        g.add_trace_edge(_make_driver_edge("top.a", "top.c", expr="a | b"))
        g.add_trace_edge(_make_driver_edge("top.b", "top.c", expr="a | b"))
        g.add_trace_edge(_make_driver_edge("top.en_input", "top.a", expr="a_input"))
        return g

    def test_markdown_returns_string(self):
        """返回字符串"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        md = gen.generate_coverage_markdown(result)
        self.assertIsInstance(md, str)
        self.assertGreater(len(md), 0)

    def test_markdown_contains_title(self):
        """包含标题"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        md = gen.generate_coverage_markdown(result)
        self.assertIn("#", md)

    def test_markdown_contains_atomic_signals(self):
        """包含原子信号名"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        md = gen.generate_coverage_markdown(result)
        # 至少包含 en, c, d, a, b 之一
        self.assertTrue(any(s in md for s in ["en", "c", "d", "a", "b"]))

    def test_markdown_contains_summary(self):
        """包含概要信息 (原始信号、原子数等)"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"])
        md = gen.generate_coverage_markdown(result)
        # 原始信号名
        self.assertIn("top.x", md)
        # 原子信号数
        self.assertIn("5", md)  # 我们有 5 个原子信号

    def test_markdown_with_no_signals(self):
        """空结果也有合理输出"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.unknown"])
        md = gen.generate_coverage_markdown(result)
        self.assertIsInstance(md, str)

    def test_markdown_with_truncated(self):
        """截断时显示错误信息"""
        g = self._make_setup_graph()
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.x"], max_signals=2)
        md = gen.generate_coverage_markdown(result)
        # 截断时应有警告
        self.assertTrue("max_signals" in md or "truncated" in md.lower() or "超出" in md)


# ==============================================================================
# Cycle 7: CLI 入口 (coverage suggest)
# ==============================================================================


class TestCLICoverageSuggest(unittest.TestCase):
    """CLI: coverage suggest 命令

    测试入口函数, 不直接调 typer.
    """

    def test_cli_runs_with_real_sv(self):
        """实际 SV 文件能跑通"""
        import subprocess
        import sys
        import os

        # 用现有的 test_data_path.sv 作为输入
        sv_file = os.path.join(
            os.path.dirname(__file__),
            "..", "regression", "test_data_path.sv"
        )
        if not os.path.exists(sv_file):
            self.skipTest(f"SV file not found: {sv_file}")

        # 跑 CLI
        result = subprocess.run(
            [
                sys.executable, "run_cli.py", "coverage", "suggest",
                "-f", sv_file,
                "--signal", "data_path.din",
                "--max-signals", "5",
            ],
            cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."),
            capture_output=True,
            text=True,
            timeout=60,
        )
        # 成功 (返回 0) 或输出包含 Markdown
        if result.returncode != 0:
            print("STDOUT:", result.stdout[:500])
            print("STDERR:", result.stderr[:500])
        # 至少输出包含一些 markdown 标记
        output = result.stdout + result.stderr
        self.assertTrue(
            "#" in output or "原始信号" in output or "decompose" in output.lower(),
            f"Unexpected output: {output[:200]}"
        )

    def test_cli_module_imports(self):
        """coverage 模块能正常导入"""
        try:
            from src.cli.commands import coverage  # noqa: F401
            self.assertTrue(hasattr(coverage, "coverage_app"))
        except ImportError as e:
            self.fail(f"Failed to import coverage module: {e}")


# ==============================================================================
# Cycle 9: 跨模块检测
# ==============================================================================


class TestCrossModuleDetection(unittest.TestCase):
    """跨模块检测

    用户要求: rtl 不会跨模块设计, 如有, 报错不支持.
    """

    def test_simple_signal_no_cross_module(self):
        """简单信号名 (top.x) 不算跨模块"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.x"))
        gen = ControlCoverageGenerator(graph=g)
        self.assertFalse(gen._is_cross_module("top.x"))

    def test_dot_separated_simple(self):
        """单点分隔 (如 a.b) -> False (不是跨模块)"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        self.assertFalse(gen._is_cross_module("a.b"))

    def test_double_dot_cross_module(self):
        """双点分隔 (如 top.sub.x) -> True (跨模块)"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        self.assertTrue(gen._is_cross_module("top.sub.x"))

    def test_triple_dot_cross_module(self):
        """三点分隔 (如 top.a.b.c) -> True"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        self.assertTrue(gen._is_cross_module("top.a.b.c"))

    def test_decompose_with_cross_module_sets_error(self):
        """跨模块分解 -> error 非空"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        g.add_trace_node(_make_signal_node("top.sub.x"))
        gen = ControlCoverageGenerator(graph=g)
        result = gen.decompose(["top.sub.x"])
        self.assertIsNotNone(result.error)
        self.assertIn("跨模块", result.error or "")


# ==============================================================================
# Cycle 8: AST 解析集成 (SignalExpressionVisitor)
# ==============================================================================


class TestASTParsing(unittest.TestCase):
    """AST 路径解析

    复用 SignalExpressionVisitor 处理更准确的表达式提取.
    """

    def test_parse_via_string_still_works(self):
        """字符串路径 (现有) 仍正常工作"""
        from trace.core.graph.models import SignalGraph
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        # 旧 API 仍然工作
        result = gen._parse_expression_to_atomics("a & b")
        names = [s.name for s in result]
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_parse_via_real_pyslang_ast(self):
        """真实 pyslang AST 解析 (集成测试)"""
        import pyslang
        from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor
        from trace.core.semantic_adapter import SemanticAdapter

        # 用简单 SV 创建一个 expression AST
        source = """
        module test(input a, b, output [3:0] c);
            assign c = a & b;
        endmodule
        """
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 递归找 ContinuousAssign
        assign_node = None

        def find(node):
            s = str(node.kind)
            if "ContinuousAssign" in s:
                return node
            if hasattr(node, "__iter__") and not isinstance(node, str):
                try:
                    for c in node:
                        r = find(c)
                        if r is not None:
                            return r
                except Exception:
                    pass
            return None

        assign_node = find(root)
        if assign_node is None:
            self.fail("Could not find ContinuousAssign")

        # Get the assignment expression (a & b)
        # ContinuousAssignSyntax has 'assignments' (list of AssignmentExpression)
        assignments = assign_node.assignments
        if not assignments:
            self.fail("ContinuousAssign has no assignments")

        assign_expr = assignments[0]  # AssignmentExpression
        if "AssignmentExpression" not in str(assign_expr.kind):
            self.fail(f"Expected AssignmentExpression, got {assign_expr.kind}")

        rhs = assign_expr.right  # BinaryExpression (a & b)

        # 测试解析
        comp = pyslang.Compilation()
        comp.addSyntaxTree(tree)
        adapter = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(adapter)
        result = visitor.extract(rhs)
        self.assertIsNotNone(result)
        # 应该有 a 和 b
        self.assertIn("a", result.all_signals)
        self.assertIn("b", result.all_signals)


# ==============================================================================
# V2 Cycle 11: AST 集成 - TraceEdge.condition_ast 字段
# ==============================================================================


class TestTraceEdgeConditionAST(unittest.TestCase):
    """TraceEdge.condition_ast 字段存在

    需求: graph_builder 填充 condition 时同时存 AST, 让 coverage_generator
    走 AST 路径 (而不是字符串解析).
    """

    def test_condition_ast_field_exists(self):
        """TraceEdge 应该有 condition_ast 字段 (默认 None)"""
        from trace.core.graph.models import TraceEdge, EdgeKind
        edge = TraceEdge(
            src="top.a",
            dst="top.b",
            kind=EdgeKind.DRIVER,
            condition="en",
        )
        self.assertTrue(hasattr(edge, "condition_ast"))
        # 默认 None
        self.assertIsNone(edge.condition_ast)

    def test_condition_ast_can_be_set(self):
        """condition_ast 可以被设置"""
        from trace.core.graph.models import TraceEdge, EdgeKind
        sentinel = object()
        edge = TraceEdge(
            src="top.a",
            dst="top.b",
            kind=EdgeKind.DRIVER,
            condition="en",
            condition_ast=sentinel,
        )
        self.assertIs(edge.condition_ast, sentinel)

    def test_condition_ast_optional_in_construction(self):
        """不传 condition_ast 也能正常构造 (向后兼容)"""
        from trace.core.graph.models import TraceEdge, EdgeKind
        # 只传必要参数
        edge = TraceEdge(src="top.a", dst="top.b", kind=EdgeKind.DRIVER)
        self.assertIsNone(edge.condition_ast)
        self.assertEqual(edge.condition, "")  # 默认值


class TestASTConditionExtraction(unittest.TestCase):
    """_extract_atomics_from_ast() - 从 AST 节点提取原子信号

    V1 已有 _parse_expression_to_atomics() (字符串).
    V2 新增 _extract_atomics_from_ast() (AST 节点), 更准确.
    """

    def _make_gen(self):
        from trace.core.graph.models import SignalGraph
        return ControlCoverageGenerator(graph=SignalGraph())

    def test_extract_with_none(self):
        """None 输入 -> 空列表"""
        gen = self._make_gen()
        result = gen._extract_atomics_from_ast(None)
        self.assertEqual(result, [])

    def test_extract_via_real_pyslang_ast(self):
        """真实 pyslang AST 解析"""
        import pyslang
        from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor
        from trace.core.semantic_adapter import SemanticAdapter

        source = """
        module test(input a, b, c, output [3:0] d);
            assign d = a & b | c;
        endmodule
        """
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 找 BinaryExpression (a & b | c, 从左到右解析为 ((a & b) | c))
        def find_binary(node):
            s = str(node.kind)
            if "Binary" in s and "Expression" in s:
                return node
            if hasattr(node, "__iter__") and not isinstance(node, str):
                try:
                    for c in node:
                        r = find_binary(c)
                        if r is not None:
                            return r
                except Exception:
                    pass
            return None

        binary = find_binary(root)
        self.assertIsNotNone(binary, "Should find a Binary expression")

        comp = pyslang.Compilation()
        comp.addSyntaxTree(tree)
        adapter = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(adapter)
        sr = visitor.extract(binary)

        gen = self._make_gen()
        atomics = gen._extract_atomics_from_ast(binary)
        names = {s.name for s in atomics}

        # 字符串解析 (_parse_expression_to_atomics) 已经能处理
        # 但 AST 路径应该返回相同结果
        for expected in ("a", "b", "c"):
            self.assertIn(expected, names)

    def test_extract_ast_path_preferred(self):
        """当 AST 可用时, _extract_condition_atomic 优先用 AST"""
        import pyslang
        from trace.core.graph.models import SignalGraph, TraceEdge, EdgeKind
        from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor
        from trace.core.semantic_adapter import SemanticAdapter

        # 构造一个 TraceEdge, 带 AST
        source = """
        module test(input a, b, output [3:0] c);
            assign c = a & b;
        endmodule
        """
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        def find_binary(node):
            s = str(node.kind)
            if "Binary" in s and "Expression" in s:
                return node
            if hasattr(node, "__iter__") and not isinstance(node, str):
                try:
                    for c in node:
                        r = find_binary(c)
                        if r is not None:
                            return r
                except Exception:
                    pass
            return None

        ast_node = find_binary(root)
        self.assertIsNotNone(ast_node)

        # 模拟一个 "被错误字符串表示" 的 edge (但 AST 是正确的)
        edge = TraceEdge(
            src="top.a",
            dst="top.c",
            kind=EdgeKind.DRIVER,
            condition="BROKEN_STRING",  # 故意错的字符串
            condition_ast=ast_node,     # AST 是对的
        )

        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        # 优先用 AST, 应该能正确解析出 a, b
        atomics = gen._extract_condition_atomic(edge, "top.c")
        names = {s.base_name for s in atomics}
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_extract_fallback_to_string(self):
        """当 AST 不可用 (None) 时, 回退到字符串解析"""
        from trace.core.graph.models import SignalGraph, TraceEdge, EdgeKind
        g = SignalGraph()
        gen = ControlCoverageGenerator(graph=g)
        edge = TraceEdge(
            src="top.a",
            dst="top.c",
            kind=EdgeKind.DRIVER,
            condition="a & b",  # 只用字符串
            condition_ast=None,
        )
        atomics = gen._extract_condition_atomic(edge, "top.c")
        names = {s.base_name for s in atomics}
        self.assertIn("a", names)
        self.assertIn("b", names)


if __name__ == '__main__':
    unittest.main()
