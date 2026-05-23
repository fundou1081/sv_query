# visitors/__init__.py
"""
Visitor 模式模块

[铁律15] Visitor 模式必须使用
[铁律26] AST 遍历必须使用 Visitor 模式，禁止 if-elif 链
"""

from .base_visitor import BaseVisitor
from .signal_expression_visitor import SignalExpressionVisitor

__all__ = [
    'BaseVisitor',
    'SignalExpressionVisitor',
]