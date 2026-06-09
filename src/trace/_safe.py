"""Safe accessors for pyslang objects.

pyslang property accessors (e.g. Token.value, Symbol.name, Symbol.hierarchicalPath)
can raise UnicodeDecodeError when the underlying buffer contains non-UTF-8 bytes
(e.g. SystemVerilog escape sequences with non-ASCII characters). These helpers
catch the error and return a placeholder, allowing trace/extraction to continue
instead of crashing the whole pipeline.
"""
from __future__ import annotations


def _safe_str(obj) -> str:
    """Safe str() that tolerates non-UTF-8 bytes in pyslang Tokens/Syntax."""
    if obj is None:
        return ""
    try:
        return str(obj)
    except (UnicodeDecodeError, TypeError):
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


def _safe_attr(obj, name: str, default=None):
    """Safe getattr that tolerates non-UTF-8 pyslang property access.

    Equivalent to ``getattr(obj, name, default)`` but catches UnicodeDecodeError
    and other exceptions raised by pyslang property getters.
    """
    if obj is None:
        return default
    try:
        return getattr(obj, name)
    except (UnicodeDecodeError, TypeError, Exception):
        return default
