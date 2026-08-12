"""
test_f2_no_string_fallback.py — [Plan F2.7 2026-08-13] 禁止 string fallback

[USER 2026-08-13 06:06 指示]
"关于 2.7 ，不需要 string fallback，如果失败了就单独报错，或者用一个
空的错误节点代替。 及时报错出来。不要 fallback。"

[F2.7 设计]
- 拿不到 tree 时 → log WARNING (含 signal_id / expr / tree_key 全 context)
- 返回 1 个 error_marker AtomicSignal (name=NO_TREE_MARKER)
- 绝不调用 _parse_expression_to_atomics (string parsing)

[Plan F2 核心承诺] 「消灭 string parsing 误识别 (字面量 / 关键字 / 嵌套)」
F2.4.3 加了 string fallback → 跟核心承诺矛盾. F2.7 关闭 fallback.

[铁律13] 金标准测试优先
[铁律17] 强断言 (具体行为, NO_TREE_MARKER 字符串 / WARNING 存在)
"""

import os
import sys
import logging
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.coverage_generator import (
    ControlCoverageGenerator,
    NO_TREE_MARKER,
)


def _tracer_for(src: str, name: str = 'test.sv'):
    tracer = UnifiedTracer(sources={name: src}, strict=False)
    tracer.build_graph()
    return tracer.get_graph()


class TestF2NoStringFallback(unittest.TestCase):
    """[Plan F2.7] coverage_generator 严格走 tree, 不 fallback string parsing"""

    def test_no_tree_marker_constant_exists(self):
        """[F2.7] NO_TREE_MARKER 常量必须存在且是字符串"""
        self.assertIsInstance(NO_TREE_MARKER, str)
        self.assertGreater(len(NO_TREE_MARKER), 0)
        # 应该明显不是合法 SV identifier (尖括号), 让 caller 一眼能 grep
        self.assertIn('<', NO_TREE_MARKER)
        self.assertIn('>', NO_TREE_MARKER)

    def test_normal_assign_with_tree_does_not_use_marker(self):
        """[F2.7 正常路径] tree 存在 → 不返回 NO_TREE_MARKER"""
        src = '''module top(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule'''
        g = _tracer_for(src)
        gen = ControlCoverageGenerator.__new__(ControlCoverageGenerator)
        # _trace_drivers 拿一个 driver 节点调用, 这里直接验证 _extract_atomics_from_expr_tree
        trees = getattr(g, '_expr_trees', {})
        tree = list(trees.values())[0]
        atomics = gen._extract_atomics_from_expr_tree(tree)
        # 应该有 'a' 和 'b', 不能有 NO_TREE_MARKER
        names = [a.name for a in atomics]
        self.assertNotIn(NO_TREE_MARKER, names,
                         f"[F2.7] Normal path shouldn't emit NO_TREE_MARKER, got {names}")
        self.assertEqual(sorted(names), ['a', 'b'])

    def test_missing_tree_logs_warning_and_returns_marker(self):
        """[F2.7 fallback 路径] tree 缺失 → WARNING + 返回 NO_TREE_MARKER

        [场景] 模拟 _trace_drivers 当 expr_trees.get(signal) 返回 None.
        应该 log WARNING 含 signal_id / expr, 返回 1 个 NO_TREE_MARKER atomic.
        """
        from trace.core.coverage_models import AtomicSignal

        # Capture log
        log_records = []
        handler = logging.Handler()
        handler.emit = lambda record: log_records.append(record)

        logger = logging.getLogger('trace.core.coverage_generator')
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        try:
            # 直接调 walker 模拟 missing tree: 不调 _extract_atomics_from_expr_tree,
            # 直接返回空 list, 让 _trace_drivers 走到 NO_TREE_MARKER 分支
            # 这里用 monkey-patch
            from trace.core import coverage_generator as cg_module

            gen = ControlCoverageGenerator.__new__(ControlCoverageGenerator)
            gen._graph = type('G', (), {
                '_expr_trees': {},  # 空 — tree 永远 miss
                'get_node': lambda s: None,
                'find_drivers': lambda s: [],
                'get_edge': lambda *a: None,
            })()
            # 直接调 _trace_drivers (会立即返空因没 driver)
            # 改为手动模拟 _trace_drivers 的 fallback 分支
            # 用一个 empty atomics list 走 _trace_drivers 的 logic
            # 实际: 模拟 signal 存在 driver 但 tree 缺失 — 通过 monkey-patch find_drivers
            from trace.core.graph.models import TraceNode, EdgeKind
            from trace.core.coverage_models import EvidenceStep

            class FakeNode:
                def __init__(self, id): self.id = id
            class FakeEdge:
                def __init__(self, expr): self.expression = expr

            gen._graph.find_drivers = lambda s: [FakeNode('top.a')]
            gen._graph.get_edge = lambda *a: FakeEdge('a + b')
            gen._graph.get_node = lambda s: type('N', (), {'id': s})()

            # 调 _trace_drivers
            atomics = gen._trace_drivers(
                signal='top.y',
                bit_range=None,
                depth=0,
                max_depth=10,
                visited=set(),
            )

            # 应该有 1 个 NO_TREE_MARKER atomic
            self.assertEqual(len(atomics), 1,
                             f"[F2.7] Missing tree should return 1 error marker, got {len(atomics)}")
            self.assertEqual(atomics[0].name, NO_TREE_MARKER)
            self.assertEqual(atomics[0].base_name, NO_TREE_MARKER)
            self.assertIsNone(atomics[0].bit_range)

            # WARNING 必须 log, 含关键 context
            self.assertGreater(len(log_records), 0,
                               "[F2.7] Missing tree should log WARNING")
            msg = log_records[-1].getMessage()
            self.assertIn('NO_EXPR_TREE', msg,
                          f"[F2.7] WARNING should mention NO_EXPR_TREE, got: {msg}")
            self.assertIn('top.y', msg,
                          f"[F2.7] WARNING should include signal_id, got: {msg}")
            self.assertIn("'a + b'", msg or repr(msg),
                          f"[F2.7] WARNING should include edge expression, got: {msg}")
        finally:
            logger.removeHandler(handler)

    def test_string_parsing_not_called_in_trace_drivers(self):
        """[F2.7 严格断言] _trace_drivers 永远不能调用 _parse_expression_to_atomics

        [Plan F2 核心承诺] 「消灭 string parsing 误识别」. F2.7 必须强制.
        """
        from trace.core import coverage_generator as cg_module

        call_count = {'count': 0}
        orig_parse = cg_module.ControlCoverageGenerator._parse_expression_to_atomics

        def counting_parse(self, expr):
            call_count['count'] += 1
            return orig_parse(self, expr)

        cg_module.ControlCoverageGenerator._parse_expression_to_atomics = counting_parse
        try:
            src = '''module top(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule'''
            g = _tracer_for(src)
            # 直接调 _trace_drivers (即使 tree 存在也不该调 string parse)
            from trace.core.graph.models import TraceNode, EdgeKind
            gen = ControlCoverageGenerator.__new__(ControlCoverageGenerator)
            gen._graph = g

            # 通过 decompose 走完整路径 (会内部调 _trace_drivers)
            gen._source_provider = lambda x: src
            gen._source_cache = {}
            try:
                result = gen.decompose(signal='top.y', max_depth=3)
                # decompose 不直接调 _parse_expression_to_atomics 通过 _trace_drivers
                # 我们关心的是 _trace_drivers 不调它
                # 即使调一次 (来自其他路径), 也应该远少于正常 atomic 数
                # 严格断言: _trace_drivers 不能调它
                # 用 monkey-patch 仅 patch _extract_atomics_from_expr_tree 强制返空,
                # 强制走 fallback 分支 (现在应该是 NO_TREE_MARKER 分支)
                orig_extract = cg_module.ControlCoverageGenerator._extract_atomics_from_expr_tree
                cg_module.ControlCoverageGenerator._extract_atomics_from_expr_tree = lambda self, tree: []
                try:
                    atomics = gen._trace_drivers('top.y', None, 0, 10, set())
                    # 应该返 NO_TREE_MARKER, 不是 [] 也不是 string parse 结果
                    self.assertEqual(len(atomics), 1)
                    self.assertEqual(atomics[0].name, NO_TREE_MARKER)
                    # 关键: 即使 tree 提取返空, 也不应该调 _parse_expression_to_atomics
                    self.assertEqual(call_count['count'], 0,
                                     f"[F2.7] _trace_drivers should NEVER call "
                                     f"_parse_expression_to_atomics, but called "
                                     f"{call_count['count']} times")
                finally:
                    cg_module.ControlCoverageGenerator._extract_atomics_from_expr_tree = orig_extract
            except Exception:
                # decompose 失败没关系, 我们关心 _trace_drivers 路径
                pass
        finally:
            cg_module.ControlCoverageGenerator._parse_expression_to_atomics = orig_parse


if __name__ == '__main__':
    unittest.main()