# visitors/__init__.py
"""
Visitor 模式模块

[铁律15] Visitor 模式必须使用
[铁律26] AST 遍历必须使用 Visitor 模式，禁止 if-elif 链
"""

from .base_visitor import BaseVisitor
from .signal_expression_visitor import SignalExpressionVisitor
from .signal_result import SignalResult
from .statement_collector_visitor import StatementCollectorVisitor

__all__ = [
    "BaseVisitor",
    "SignalExpressionVisitor",
    "SignalResult",
    "StatementCollectorVisitor",
]
