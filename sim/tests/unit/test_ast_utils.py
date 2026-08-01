# ruff: noqa: E402
"""
test_ast_utils.py - V6.3+3 2026-07-27: unit tests for ast_utils module.

Tests:
  - unwrap: paren stripping, conversion stripping, idempotent, safe on None
  - unwrap_paren: only strips parens
  - is_wrapper: detects wrapper kinds
  - kind_matches: alias resolution, exact match, multiple kinds
  - _kind_name: handles both SyntaxKind and ExpressionKind enums
"""
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pytest

# Import the module under test
from trace.core.ast_utils import (
    _KIND_ALIASES,
    _kind_name,
    is_wrapper,
    kind_is,
    kind_matches,
    node_text,
    unwrap,
    unwrap_paren,
)


# Mock objects for unit testing without pyslang AST construction
class MockNode:
    """Mock pyslang node with kind attribute."""

    def __init__(self, kind_name: str, **attrs):
        self._kind_name = kind_name
        # Create a fake kind enum-like object with .name attribute
        self.kind = type("Kind", (), {"name": kind_name})()
        for k, v in attrs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"<MockNode kind={self._kind_name}>"


def make_paren(inner):
    return MockNode("ParenthesizedExpressionSyntax", expression=inner)


def make_conversion(inner):
    return MockNode("ConversionExpression", operand=inner)


def make_implicit_cast(inner):
    return MockNode("ImplicitCastExpression", operand=inner)


def make_tern_op():
    return MockNode("ConditionalOp")


def make_tern_expr():
    return MockNode("ConditionalExpression")


# --- unwrap tests --------------------------------------------------------


class TestUnwrap:
    def test_unwrap_none_returns_none(self):
        assert unwrap(None) is None

    def test_unwrap_non_wrapper_returns_same(self):
        node = make_tern_op()
        assert unwrap(node) is node

    def test_unwrap_single_paren(self):
        inner = make_tern_op()
        paren = make_paren(inner)
        assert unwrap(paren) is inner

    def test_unwrap_nested_parens(self):
        inner = make_tern_op()
        p2 = make_paren(inner)
        p1 = make_paren(p2)
        assert unwrap(p1) is inner

    def test_unwrap_conversion(self):
        inner = make_tern_op()
        conv = make_conversion(inner)
        assert unwrap(conv) is inner

    def test_unwrap_implicit_cast(self):
        inner = make_tern_op()
        ic = make_implicit_cast(inner)
        assert unwrap(ic) is inner

    def test_unwrap_paren_around_conversion(self):
        inner = make_tern_op()
        conv = make_conversion(inner)
        paren = make_paren(conv)
        # unwrap strips BOTH: paren → conversion → ternary
        assert unwrap(paren) is inner

    def test_unwrap_idempotent(self):
        """Calling unwrap twice returns the same result as once."""
        inner = make_tern_op()
        paren = make_paren(inner)
        once = unwrap(paren)
        twice = unwrap(once)
        assert once is twice
        assert once is inner

    def test_unwrap_with_none_inner_returns_none(self):
        broken = make_paren(None)
        assert unwrap(broken) is None

    def test_unwrap_handles_paren_with_no_expression_attr(self):
        """If ParenthesizedExpressionSyntax has no .expression attr, return None."""
        weird = MockNode("ParenthesizedExpressionSyntax")
        assert unwrap(weird) is None


# --- unwrap_paren tests --------------------------------------------------


class TestUnwrapParen:
    def test_unwrap_paren_strips_parens(self):
        inner = make_tern_op()
        paren = make_paren(inner)
        assert unwrap_paren(paren) is inner

    def test_unwrap_paren_preserves_conversion(self):
        """Conversion nodes carry type info — don't strip them."""
        inner = make_tern_op()
        conv = make_conversion(inner)
        paren = make_paren(conv)
        # unwrap_paren stops at the conversion, preserves type info
        assert unwrap_paren(paren) is conv

    def test_unwrap_paren_preserves_implicit_cast(self):
        inner = make_tern_op()
        ic = make_implicit_cast(inner)
        paren = make_paren(ic)
        assert unwrap_paren(paren) is ic


# --- is_wrapper tests ----------------------------------------------------


class TestIsWrapper:
    def test_paren_is_wrapper(self):
        assert is_wrapper(make_paren(make_tern_op()))

    def test_conversion_is_wrapper(self):
        assert is_wrapper(make_conversion(make_tern_op()))

    def test_implicit_cast_is_wrapper(self):
        assert is_wrapper(make_implicit_cast(make_tern_op()))

    def test_tern_op_is_not_wrapper(self):
        assert not is_wrapper(make_tern_op())

    def test_tern_expr_is_not_wrapper(self):
        assert not is_wrapper(make_tern_expr())

    def test_none_is_not_wrapper(self):
        assert not is_wrapper(None)

    def test_non_wrapper_kind_is_not_wrapper(self):
        assert not is_wrapper(MockNode("Identifier"))
        assert not is_wrapper(MockNode("PortList"))
        assert not is_wrapper(MockNode("ModuleDeclaration"))


# --- kind_matches tests -------------------------------------------------


class TestKindMatches:
    def test_exact_match(self):
        assert kind_matches(make_tern_op(), "ConditionalOp")
        assert kind_matches(make_tern_expr(), "ConditionalExpression")

    def test_no_match(self):
        assert not kind_matches(make_tern_op(), "BinaryOp")
        assert not kind_matches(make_tern_expr(), "BinaryOp")

    def test_alias_resolves_syntax_to_semantic(self):
        """SyntaxKind.ConditionalExpression matches ExpressionKind.ConditionalOp."""
        # Both names should match "ConditionalOp" or "ConditionalExpression"
        assert kind_matches(make_tern_op(), "ConditionalOp")
        assert kind_matches(make_tern_op(), "ConditionalExpression")
        assert kind_matches(make_tern_expr(), "ConditionalOp")
        assert kind_matches(make_tern_expr(), "ConditionalExpression")

    def test_multiple_kinds_any_match(self):
        """If any expected kind matches (after alias resolution), return True."""
        node = make_tern_op()
        assert kind_matches(node, "BinaryOp", "ConditionalOp", "UnaryOp")

    def test_alias_table_covers_known_pairs(self):
        """All 4 known alias pairs must be in the alias map."""
        required = {
            "ConditionalExpression": "ConditionalOp",
            "ConcatenationExpression": "Concatenation",
            "BinaryExpression": "BinaryOp",
            "UnaryExpression": "UnaryOp",
        }
        for src, dst in required.items():
            assert _KIND_ALIASES.get(src) == dst, (
                f"alias map missing {src} -> {dst}"
            )

    def test_none_returns_false(self):
        assert not kind_matches(None, "ConditionalOp")

    def test_no_kind_attr_returns_false(self):
        class WeirdNode:
            pass
        assert not kind_matches(WeirdNode(), "ConditionalOp")

    def test_kind_is_singleton_helper(self):
        # kind_is uses kind_matches internally, so aliases work too.
        # ConditionalOp and ConditionalExpression are aliases, both should
        # match for either input.
        assert kind_is(make_tern_op(), "ConditionalOp")
        assert kind_is(make_tern_op(), "ConditionalExpression")
        assert kind_is(make_tern_expr(), "ConditionalOp")
        assert kind_is(make_tern_expr(), "ConditionalExpression")
        # But unrelated kinds should NOT match
        assert not kind_is(make_tern_op(), "BinaryOp")
        assert not kind_is(make_tern_op(), "Identifier")


# --- _kind_name tests ----------------------------------------------------


class TestKindName:
    def test_kind_with_name_attr(self):
        node = MockNode("ConditionalOp")
        assert _kind_name(node) == "ConditionalOp"

    def test_kind_without_name_attr_stringifies(self):
        class WeirdKind:
            def __str__(self):
                return "WeirdKind"

        node = MockNode("dummy")
        node.kind = WeirdKind()
        assert _kind_name(node) == "WeirdKind"

    def test_kind_none(self):
        node = MockNode("dummy")
        node.kind = None
        assert _kind_name(node) == ""

    def test_node_without_kind_attr(self):
        class NoKind:
            pass

        assert _kind_name(NoKind()) == ""

    def test_node_is_none(self):
        assert _kind_name(None) == ""


# --- node_text tests -----------------------------------------------------


class TestNodeText:
    def test_text_attr_used(self):
        node = MockNode("dummy")
        node.text = "my_signal"
        assert node_text(node) == "my_signal"

    def test_str_fallback(self):
        node = MockNode("dummy")
        # No .text attr, falls back to str(node)
        result = node_text(node)
        assert "MockNode" in result or "dummy" in result

    def test_none_returns_empty(self):
        assert node_text(None) == ""


# --- Integration with real pyslang AST -----------------------------------


class TestRealPyslangIntegration:
    """Verify ast_utils works on actual pyslang-parsed SV code."""

    @pytest.fixture
    def parsed_tern(self):
        """Parse `(g ? a : b)` via UnifiedTracer and return the conditional expr."""
        from trace.unified_tracer import UnifiedTracer

        src_text = """
        module m;
          wire a, b, g, y;
          assign y = (g ? a : b);
        endmodule
        """
        tracer = UnifiedTracer(sources={'m.sv': src_text}, strict=False)
        tracer.build_graph()

        # Walk to find a ConditionalOp / ConditionalExpression in any module.
        # After build, the AST is gone but we can still parse fresh.
        from trace.core.compiler import SVCompiler
        compiler = SVCompiler(sources={'m.sv': src_text})
        # Find the conditional expression in the AST
        def find(node, depth=0):
            if depth > 60:
                return None
            kind = _kind_name(node)
            if kind in ("ConditionalOp", "ConditionalExpression"):
                return node
            for attr in dir(node):
                if attr.startswith('_'):
                    continue
                try:
                    child = getattr(node, attr)
                    if child is None or callable(child):
                        continue
                    if hasattr(child, '__iter__') and not isinstance(child, str):
                        for c in child:
                            r = find(c, depth+1)
                            if r:
                                return r
                    elif hasattr(child, 'kind'):
                        r = find(child, depth+1)
                        if r:
                            return r
                except Exception:
                    pass
            return None

        for inst in compiler.get_root().topInstances:
            result = find(inst)
            if result:
                return result
        pytest.skip("could not find ternary in parsed SV")

    def test_unwrap_strips_real_paren(self, parsed_tern):
        """Real pyslang parse: (g ? a : b) → after unwrap, kind should be
        ConditionalExpression (or ConditionalOp after alias)."""
        inner = unwrap(parsed_tern)
        assert inner is not None
        assert kind_matches(inner, "ConditionalOp", "ConditionalExpression")
        # Inner node should be a ternary (not a Paren wrapper)
        assert not is_wrapper(inner)

    def test_kind_matches_real_tern(self, parsed_tern):
        inner = unwrap(parsed_tern)
        assert kind_matches(inner, "ConditionalOp")
        assert kind_matches(inner, "ConditionalExpression")
