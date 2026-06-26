"""[ADD 2026-06-26 A-PR1] pyslang binary-garbage safe attribute access.

解决 8GB 内存环境下 pyslang partial elaboration 触发的:
- UnicodeDecodeError: pyslang attribute 含非 utf-8 字节 (escape 序列, rawText 等)
- RuntimeError "mutex lock failed": pyslang 内部 pthread 死锁
- TypeError: str() 失败

替代 7+ 处重复的 try/except 模式 (semantic_adapter, class_graph_builder,
statement_collector_visitor, bit_select_handler, unified_tracer 等).

[为什么独立 module] SignalExpressionVisitor 等 1+ 个 class 都需要这些 helper,
放独立 module 避免循环 import (signal_expression_visitor 被多个 caller 引用).
"""

from typing import Any

MUTEX_ERROR_MARKER = "mutex"


def safe_node_attr(node: Any, attr: str, default: str = "") -> str:
    """[ADD 2026-06-26] 安全获取 AST 节点 attribute, 容错 UnicodeDecodeError / RuntimeError "mutex".

    替换 7+ 处重复的 try/except 模式:
        try:
            val = getattr(node, attr, default)
        except RuntimeError as e:
            if "mutex" not in str(e).lower():
                raise
            val = default

    用法:
        name = safe_node_attr(node, "name")
    """
    try:
        val = getattr(node, attr, default)
    except (RuntimeError, Exception):
        return default
    if val is None:
        return default
    try:
        return str(val).strip() if val else default
    except (UnicodeDecodeError, TypeError):
        return default


def safe_ident_str(ident: Any, default: str = "") -> str:
    """[ADD 2026-06-26] 安全提取 IdentifierName / NamedValue 的 .value string.

    替换 9+ 处 str(ident.value).strip() 模式:
        ident = getattr(node, "identifier", None)
        if ident:
            if hasattr(ident, "value"):
                base_name = str(ident.value).strip()  # ← 这里
            else:
                base_name = str(ident).strip()

    用法:
        name = safe_ident_str(ident)
    """
    if ident is None:
        return default
    try:
        raw = getattr(ident, "value", default) if not hasattr(ident, "value") else ident.value
        if raw is None:
            return default
        if not isinstance(raw, str):
            raw = str(raw)
        return raw.strip() if raw else default
    except (UnicodeDecodeError, TypeError):
        return default
