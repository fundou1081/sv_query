# visitors/__init__.py
"""
Visitor 模式模块 - semantic AST 工具

保留独立工具：
  - StatementCollectorVisitor: 语句收集器
  - ConstraintVisitor: constraint 分析
  - @on 装饰器: handler 注册

[V6.9 2026-07-29] 删除 syntax AST visitor 体系（SignalExpressionVisitor + 11 个多继承 visitor）。
信号提取统一用 semantic_adapter (pyslang native API)，不再用 pyslang syntax tree 回调。
"""

from .statement_collector_visitor import ItemType, StatementCollectorVisitor
from .constraint_visitor import ConstraintNodeResult, ConstraintVisitor

__all__ = [
    "ItemType",
    "StatementCollectorVisitor",
    "ConstraintNodeResult",
    "ConstraintVisitor",
]
