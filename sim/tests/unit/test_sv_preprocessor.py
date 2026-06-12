"""Test SV Preprocessor (Req-20)

[Req-20 2026-06-12] 用户洞察: "应该把宏替换后再用语义解析"

preprocessor 跨文件展开 `MACRO → literal value, 让 pyslang 避开 TooFewArguments.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
SRC_DIR = str(REPO_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest

from trace.core.sv_preprocessor import (
    preprocess_macros,
    _resolve_macro_recursive,
    _strip_comment,
)


# ----------------------------------------------------------------------------
# 单元测试: _strip_comment
# ----------------------------------------------------------------------------

class TestStripComment:
    def test_no_comment(self):
        assert _strip_comment("4") == "4"

    def test_trailing_comment(self):
        assert _strip_comment("4 // Must be power of 2") == "4"

    def test_only_comment(self):
        assert _strip_comment("// comment") == ""

    def test_multiple_spaces(self):
        assert _strip_comment("  4  // x") == "4"


# ----------------------------------------------------------------------------
# 单元测试: _resolve_macro_recursive
# ----------------------------------------------------------------------------

class TestResolveMacro:
    def test_simple_literal(self):
        macros = {"FOO": "4"}
        assert _resolve_macro_recursive("FOO", macros) == "4"

    def test_indirect(self):
        macros = {"USER_X": "8", "X": "`USER_X"}
        assert _resolve_macro_recursive("X", macros) == "8"

    def test_double_indirect(self):
        macros = {"A": "2", "B": "`A", "C": "`B"}
        assert _resolve_macro_recursive("C", macros) == "2"

    def test_undefined_returns_none(self):
        assert _resolve_macro_recursive("NOPE", {"X": "4"}) is None

    def test_circular_returns_none(self):
        macros = {"A": "`B", "B": "`A"}
        # 任意一个返回 None (visited set 保护)
        assert _resolve_macro_recursive("A", macros) is None

    def test_strip_comment_in_value(self):
        macros = {"X": "4 // inline comment"}
        assert _resolve_macro_recursive("X", macros) == "4"

    def test_expression_with_macro(self):
        macros = {"A": "2", "B": "`A + 6"}
        assert _resolve_macro_recursive("B", macros) == "2 + 6"


# ----------------------------------------------------------------------------
# 集成测试: preprocess_macros
# ----------------------------------------------------------------------------

class TestPreprocessMacros:
    def test_simple_replace(self):
        sources = {
            "a.sv": "`define FOO 4\nlogic [`FOO - 1 : 0] x;\n"
        }
        out = preprocess_macros(sources)
        # `define 行不变
        assert "`define FOO 4" in out["a.sv"]
        # 引用被替换
        assert "logic [4 - 1 : 0] x;" in out["a.sv"]
        # 原文不变
        assert "`FOO - 1" in sources["a.sv"]

    def test_cross_file(self):
        """[核心场景] NaplesPU 痛点: DCACHE_WAY 在 npu_defines 定义, coherence:49 引用"""
        sources = {
            "a.sv": "`define USER_DCACHE_WAY 4\n`define DCACHE_WAY `USER_DCACHE_WAY\n",
            "b.sv": "typedef logic [$clog2(`DCACHE_WAY) - 1 : 0] idx_t;\n",
        }
        out = preprocess_macros(sources)
        # b.sv 里 `DCACHE_WAY → 4
        assert "typedef logic [$clog2(4) - 1 : 0] idx_t;" in out["b.sv"]
        # a.sv 里 `define 行保留
        assert "`define DCACHE_WAY `USER_DCACHE_WAY" in out["a.sv"]
        # a.sv 里没有引用, 所以没替换 (对的不变)

    def test_define_line_not_replaced(self):
        """`define 行的右侧不应被替换 (避免无限递归)"""
        sources = {
            "a.sv": "`define A `B\n`define B 4\nlogic [`A - 1 : 0] x;\n"
        }
        out = preprocess_macros(sources)
        # define 行保留原样
        assert "`define A `B" in out["a.sv"]
        assert "`define B 4" in out["a.sv"]
        # 引用替换
        assert "logic [4 - 1 : 0] x;" in out["a.sv"]

    def test_no_recursion_on_undefined(self):
        """未定义的 `XXX 不应崩溃"""
        sources = {
            "a.sv": "logic x = `UNDEFINED_MACRO;\n"
        }
        out = preprocess_macros(sources)
        # 保持原样 (因为 macro 不在 all_macros 里)
        assert "logic x = `UNDEFINED_MACRO;" in out["a.sv"]

    def test_word_boundary_protection(self):
        """`FOO 不能匹配 `FOOBAR"""
        sources = {
            "a.sv": "`define FOO 4\nlogic [4-1:0] x;\nlogic y = `FOOBAR;  // 注意没有 FOO 这个标识符"
        }
        # 先简化 - 不加 FOOOBAR 测试, 因为不属于 NaplesPU 实际场景
        sources = {
            "a.sv": "`define FOO 4\nlogic x = `FOO;\nlogic y = `FOOBAR;\n"
        }
        out = preprocess_macros(sources)
        # FOO 替换
        assert "logic x = 4;" in out["a.sv"]
        # FOOBAR 不替换 (无 \b 边界保护的话会错)
        assert "logic y = `FOOBAR;" in out["a.sv"]

    def test_naplespu_real_case(self):
        """NaplesPU coherence:49 真实场景"""
        sources = {
            "npu_user_defines.sv": "`define USER_DCACHE_WAY              4\n",
            "npu_defines.sv": "`define DCACHE_WAY              `USER_DCACHE_WAY\n",
            "npu_coherence_defines.sv": "typedef logic [$clog2(`DCACHE_WAY)   - 1 : 0] dcache_way_idx_t;\n",
        }
        out = preprocess_macros(sources)
        # coherence 里 `DCACHE_WAY 展开成 4
        assert "typedef logic [$clog2(4)   - 1 : 0] dcache_way_idx_t;" in out["npu_coherence_defines.sv"]
        # define 行不变
        assert "`define DCACHE_WAY              `USER_DCACHE_WAY" in out["npu_defines.sv"]


# ----------------------------------------------------------------------------
# 集成测试: UnifiedTracer preprocess_macros flag
# ----------------------------------------------------------------------------

class TestUnifiedTracerPreprocess:
    def test_preprocess_disabled_keeps_orig(self):
        """--no-preprocess 保留原始 source"""
        from trace.unified_tracer import UnifiedTracer
        sources = {
            "a.sv": "`define FOO 4\nlogic [`FOO-1:0] x;\n"
        }
        t = UnifiedTracer(sources=sources, log_level="ERROR", strict=False, preprocess_macros=False)
        # 检查 _sources 没被改
        assert "`FOO-1" in t.sources["a.sv"]
        assert t._preprocessed is False

    def test_preprocess_enabled_replaces(self):
        """默认 preprocess_macros=True, source 会被替换"""
        from trace.unified_tracer import UnifiedTracer
        sources = {
            "a.sv": "`define FOO 4\nlogic [`FOO-1:0] x;\n"
        }
        t = UnifiedTracer(sources=sources, log_level="ERROR", strict=False, preprocess_macros=True)
        # 触发 preprocess
        t._ensure_preprocessed()
        # source 被替换
        assert "logic [4-1:0] x;" in t.sources["a.sv"]
        assert t._preprocessed is True

    def test_idempotent(self):
        """连续调用 _ensure_preprocessed 不会重复替换"""
        from trace.unified_tracer import UnifiedTracer
        sources = {
            "a.sv": "`define FOO 4\nlogic [`FOO-1:0] x;\n"
        }
        t = UnifiedTracer(sources=sources, log_level="ERROR", strict=False, preprocess_macros=True)
        t._ensure_preprocessed()
        first = t.sources["a.sv"]
        t._ensure_preprocessed()
        assert t.sources["a.sv"] == first  # 不变


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
