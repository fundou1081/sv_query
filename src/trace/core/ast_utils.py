"""Centralized AST operations — single source of truth for wrapper
unwrapping, kind matching, and node introspection.

[V6.3+3 2026-07-27] Replaces 6+ duplicated unwrap blocks scattered across
driver_extractor.py, visitors/expression_visitor.py, and
visitors/signal_expression_visitor.py.

Why this module exists:
- Before: each visitor wrote its own `if "Paren" in kind_str: ...` block.
  Result: when a new wrapper type (or a new alias between SyntaxKind and
  ExpressionKind) appeared, we had to find and fix all 6 sites, and we
  kept missing one (every mux-extraction bug we hit this week was a
  missing wrapper-unwrap at one of these sites).
- After: every site that needs an unwrapped expression calls
  `ast_utils.unwrap(node)` once. When we discover a new wrapper, we add
  it to `unwrap()` once and every site is fixed.

What this module does NOT do:
- AST mutation or construction (pyslang AST nodes are immutable in
  practice for our purposes; we don't synthesize new AST nodes).
- Type inference or width analysis (separate concern).
"""

from __future__ import annotations
from typing import Any


# ---------------------------------------------------------------------------
# Wrapper unwrap
# ---------------------------------------------------------------------------
#
# Pyslang wraps expressions in transparent wrappers that have no semantic
# effect on control flow. The most common is ParenthesizedExpressionSyntax
# (any time you write `(expr)` in SV source). Other wrappers include:
#   - ConversionExpression / ImplicitCastExpression: type conversion
#     (e.g. $signed(), $unsigned(), automatic int-to-bit conversion)
#   - ImplicitCastExpression: silent cast inserted by pyslang
#
# Every visitor that wants to look INSIDE an expression must first call
# unwrap() to strip these wrappers. Otherwise Paren-wrapped ternaries like
# `(sel ? a : b)` look like a single opaque node and the visitor falls
# back to "non-ternary" leaf extraction — losing all leaf signals.
#
# Idempotent: safe to call repeatedly on the same node.

# Set of kind names that represent transparent wrappers.
# We use a list (not set) for stable iteration order in error messages.
# pyslang's .kind.name drops the "Syntax" suffix in some versions and keeps
# it in others, so we list both forms.
_WRAPPER_KIND_NAMES = (
    "ParenthesizedExpressionSyntax",
    "ParenthesizedExpression",
    "ConversionExpression",
    "ImplicitCastExpression",
)


def _kind_name(node: Any) -> str:
    """Return the pyslang kind name as a string.

    pyslang exposes two parallel enum hierarchies:
      - SyntaxKind (syntax AST, e.g. "ConditionalExpression")
      - ExpressionKind (semantic AST, e.g. "ConditionalOp")
    Both kinds have a `.name` attribute (str enum) or stringify to a
    qualified form. This helper returns the short name in both cases.

    Examples:
        SyntaxKind.ConditionalExpression.name → "ConditionalExpression"
        ExpressionKind.ConditionalOp.name    → "ConditionalOp"
        str(SyntaxKind.X)                    → "SyntaxKind.X"
    """
    if node is None:
        return ""
    kind = getattr(node, "kind", None)
    if kind is None:
        return ""
    if hasattr(kind, "name"):
        return kind.name
    return str(kind)


def unwrap(node: Any) -> Any:
    """Strip transparent wrappers (Paren, Conversion, ImplicitCast).

    Returns the innermost non-wrapper node, or `node` itself if it's
    not a wrapper. Idempotent — safe to call repeatedly.

    Recognized wrappers:
      - ParenthesizedExpressionSyntax / ParenthesizedExpression → .expression
      - ConversionExpression         → unwrap to .operand
      - ImplicitCastExpression       → unwrap to .operand
    """
    if node is None:
        return None
    while True:
        name = _kind_name(node)
        if name in ("ParenthesizedExpressionSyntax", "ParenthesizedExpression"):
            node = getattr(node, "expression", None)
        elif name in ("ConversionExpression", "ImplicitCastExpression"):
            node = getattr(node, "operand", None)
        elif "Conversion" in name or "ImplicitCast" in name:
            # Future-proof: handle renamed enum values containing these substrings.
            node = getattr(node, "operand", None)
        else:
            return node
        if node is None:
            return None


def unwrap_paren(node: Any) -> Any:
    """Strip only ParenthesizedExpression wrappers.

    More conservative than `unwrap()` — does NOT unwrap Conversion or
    ImplicitCast, which carry type information that downstream code may
    need. Use this when you want to detect a Paren but preserve type info.
    """
    if node is None:
        return None
    while True:
        name = _kind_name(node)
        if name in ("ParenthesizedExpressionSyntax", "ParenthesizedExpression"):
            node = getattr(node, "expression", None)
        else:
            return node
        if node is None:
            return None


def is_wrapper(node: Any) -> bool:
    """True iff node is one of the transparent wrappers."""
    name = _kind_name(node)
    if name in _WRAPPER_KIND_NAMES:
        return True
    # Substring match for renamed enum values
    if "Conversion" in name or "ImplicitCast" in name:
        return True
    return False


# ---------------------------------------------------------------------------
# Kind matching
# ---------------------------------------------------------------------------
#
# Why alias map: pyslang has two parallel kind hierarchies (SyntaxKind for
# syntax AST, ExpressionKind for semantic AST). They use slightly different
# names for the same concept:
#   - SyntaxKind.ConditionalExpression  ↔  ExpressionKind.ConditionalOp
#   - SyntaxKind.ConcatenationExpression ↔  ExpressionKind.Concatenation
#   - SyntaxKind.BinaryExpression        ↔  ExpressionKind.BinaryOp
#   - SyntaxKind.UnaryExpression         ↔  ExpressionKind.UnaryOp
#
# Old code did `if "ConditionalOp" in kind_str:` which silently failed for
# syntax AST nodes (matched neither "ConditionalOp" nor "Op" substring of
# "ConditionalExpression"). `kind_matches()` resolves aliases first.

# Bidirectional aliases: a name can be canonical (right side) or alias
# (left side). Multiple aliases can map to the same canonical.
_KIND_ALIASES: dict[str, str] = {
    # syntax -> semantic
    "ConditionalExpression": "ConditionalOp",
    "ConcatenationExpression": "Concatenation",
    "BinaryExpression": "BinaryOp",
    "UnaryExpression": "UnaryOp",
    # semantic -> canonical (identity)
    "ConditionalOp": "ConditionalOp",
    "Concatenation": "Concatenation",
    "BinaryOp": "BinaryOp",
    "UnaryOp": "UnaryOp",
}


def kind_matches(node: Any, *expected_kinds: str) -> bool:
    """Check if node's kind matches any of the expected kinds.

    Replaces fragile `if "X" in str(kind):` substring checks.

    Examples:
        kind_matches(node, "ConditionalOp")  # True for either syntax or semantic
        kind_matches(node, "ConditionalOp", "ConditionalExpression")
        kind_matches(node, "PortList")       # exact name
    """
    if node is None:
        return False
    name = _kind_name(node)
    if not name:
        return False
    # Resolve alias: any name maps to its canonical form
    canonical = _KIND_ALIASES.get(name, name)
    for exp in expected_kinds:
        exp_canonical = _KIND_ALIASES.get(exp, exp)
        if canonical == exp_canonical:
            return True
    return False


def kind_is(node: Any, expected_kind: str) -> bool:
    """Single-kind version of kind_matches. Use when checking exactly one."""
    return kind_matches(node, expected_kind)


# ---------------------------------------------------------------------------
# Misc node introspection helpers
# ---------------------------------------------------------------------------


def node_text(node: Any) -> str:
    """Best-effort string representation of a node.

    Tries in order: node.text, _expr_to_string, str(node). Returns empty
    string on failure. Useful for condition stringification where we don't
    care about full AST — just want readable form.
    """
    if node is None:
        return ""
    for attr in ("text", "_text"):
        v = getattr(node, attr, None)
        if isinstance(v, str) and v:
            return v
    try:
        return str(node)
    except (UnicodeDecodeError, TypeError):
        return ""


def node_source_location(node: Any) -> tuple[str, int, int, int]:
    """Return (file, line, column, offset) for a node, or ("", 0, 0, 0)."""
    if node is None:
        return ("", 0, 0, 0)
    sr = getattr(node, "sourceRange", None)
    if sr is None:
        return ("", 0, 0, 0)
    # Caller is expected to have access to a SourceManager if they need
    # file/line resolution; this just returns whatever the node exposes.
    try:
        return (
            str(getattr(sr, "file", "") or ""),
            int(getattr(sr, "line", 0) or 0),
            int(getattr(sr, "column", 0) or 0),
            int(getattr(sr, "offset", 0) or 0),
        )
    except (AttributeError, TypeError):
        return ("", 0, 0, 0)