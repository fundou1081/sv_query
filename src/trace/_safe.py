"""Safe accessors for pyslang objects — canonical module.

Pyslang property accessors (e.g. Token.value, Symbol.name, Symbol.hierarchicalPath)
can:
  1. raise UnicodeDecodeError when the underlying buffer contains non-UTF-8 bytes
     (e.g. SystemVerilog escape sequences with non-ASCII characters).
  2. return a str with embedded null bytes / control chars when elaboration fails
     (pyslang returns uninitialized memory which we get back as binary garbage).

These helpers normalize both failure modes so downstream code (graph builder,
DOT renderer, JSON output) never has to deal with corrupted strings.

Canonical functions (use these — others are deprecated):
  - safe_str(obj)        — convert any pyslang object to a clean Python str
  - clean_name(name)     — sanitize a string for use as an identifier (collapse
                            whitespace, replace control chars, return "" on
                            empty)
  - safe_attr(obj, n)    — safe getattr that catches pyslang property errors
"""
from __future__ import annotations

from typing import Any

# Sentinel returned when a name has no usable printable content.
_EMPTY = ""
_BINARY_PLACEHOLDER = "<id:binary>"


def _hex_placeholder(obj) -> str:
    """Best-effort <id:0x...> placeholder when str() fails."""
    try:
        if hasattr(obj, "rawText"):
            raw = bytes(obj.rawText) if hasattr(obj.rawText, "__bytes__") else b""
        elif hasattr(obj, "__bytes__"):
            raw = bytes(obj)
        else:
            raw = b""
        return f"<id:0x{raw.hex()[:16]}>"
    except Exception:
        return "<id:non-utf8>"


def safe_str(obj) -> str:
    """Convert any pyslang object to a clean Python str.

    Handles both failure modes of pyslang:
      1. str() raises UnicodeDecodeError / TypeError → hex placeholder
      2. str() returns str with null bytes / control chars → filter them
         out; if nothing printable remains, return <id:binary>.

    Returns:
        "" if obj is None; else a clean printable string or placeholder.
    """
    if obj is None:
        return _EMPTY
    try:
        s = str(obj)
    except (UnicodeDecodeError, TypeError):
        return _hex_placeholder(obj)
    return _sanitize(s)


def clean_name(name) -> str:
    """Normalize an identifier for graph/DOT/JSON use.

    Behavior:
      - None / empty → ""
      - non-str with __bytes__ → derive hex placeholder
      - filters control chars (< 0x20) and non-ASCII (> 0x7E)
      - collapses internal whitespace to single space
      - strips leading/trailing whitespace
      - returns "" if nothing printable remains (NOT a placeholder — caller
        decides whether to substitute a synthetic id)

    Use safe_str() if you want a placeholder for unsanitizable names; use
    clean_name() if you want to know "is this name usable?".
    """
    if not name:
        return _EMPTY
    try:
        s = str(name)
    except (UnicodeDecodeError, TypeError):
        return _EMPTY
    return _normalize_identifier(s)


def safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Safe getattr that tolerates non-UTF-8 pyslang property access.

    Equivalent to ``getattr(obj, name, default)`` but catches UnicodeDecodeError
    and other exceptions raised by pyslang property getters. The Exception
    catch is intentionally broad here because pyslang raises a variety of
    internal error types for bad identifiers, and getting None back is always
    a safer default than crashing the whole extraction.
    """
    if obj is None:
        return default
    try:
        return getattr(obj, name)
    except (UnicodeDecodeError, TypeError, Exception):
        return default


# ---- internals ----

def _sanitize(s: str) -> str:
    """Filter null bytes and control chars from a string.

    Used by safe_str() to clean pyslang elaboration-failure garbage.
    Returns <id:binary> if nothing printable remains.
    """
    if s and any(ord(c) < 0x20 for c in s):
        s = ''.join(c for c in s if 0x20 <= ord(c) < 0x7F)
        if not s.strip():
            return _BINARY_PLACEHOLDER
    return s


def _normalize_identifier(s: str) -> str:
    """Make s usable as a graph/DOT/JSON identifier.

    Filters control chars and non-ASCII; collapses whitespace. Does NOT
    substitute placeholders — returns "" if nothing remains, so the caller
    can decide what to do.
    """
    # Convert newlines/tabs to space FIRST, then drop other control chars and
    # non-ASCII. This preserves the "word break" semantics that newlines and
    # tabs represent in multi-line identifiers that pyslang sometimes flattens.
    s = ''.join(' ' if c in '\n\t' else c for c in s)
    s = ''.join(c for c in s if 0x20 <= ord(c) < 0x7F)
    s = " ".join(s.split()).strip()
    return s


# ---- backwards-compat shims (deprecated, will be removed) ----

# Older callers used leading-underscore names; keep thin aliases so existing
# imports don't break. New code should use the unprefixed names.
def _safe_str(obj) -> str:
    """DEPRECATED: use safe_str() instead."""
    return safe_str(obj)


def _safe_attr(obj, name: str, default=None):
    """DEPRECATED: use safe_attr() instead."""
    return safe_attr(obj, name, default)
