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


if __name__ == '__main__':
    unittest.main()
