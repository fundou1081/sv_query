"""Safe accessors for pyslang objects.

pyslang property accessors (e.g. Token.value, Symbol.name, Symbol.hierarchicalPath)
can raise UnicodeDecodeError when the underlying buffer contains non-UTF-8 bytes
(e.g. SystemVerilog escape sequences with non-ASCII characters). These helpers
catch the error and return a placeholder, allowing trace/extraction to continue
instead of crashing the whole pipeline.
"""
from __future__ import annotations


def _safe_str(obj) -> str:
    """Safe str() that tolerates non-UTF-8 bytes in pyslang Tokens/Syntax.

    [FIX 2026-06-13] pyslang elaboration failure 可能返回含 null bytes / control chars
    的 str (内存垃圾). 过滤后返回纯可打印名或 <id:binary>.
    """
    if obj is None:
        return ""
    try:
        s = str(obj)
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
    # 过滤 null bytes + control chars (单文件模式 elaboration 失败时)
    if s and any(ord(c) < 0x20 for c in s):
        s = ''.join(c for c in s if 0x20 <= ord(c) < 0x7F)
        if not s.strip():
            return "<id:binary>"
    return s


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
