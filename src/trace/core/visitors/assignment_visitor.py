# assignment_visitor.py - 赋值 Visitor
"""
[铁律15] Visitor 模式
处理: assign / <= / = 等赋值语句提取
"""

from typing import List

from .statement_visitor import StatementVisitor


class AssignmentVisitor(StatementVisitor):
    """赋值 Visitor - 负责提取赋值语句"""

    def __init__(self):
        super().__init__()
        self.assignments: List = []  # 收集到的赋值

    def visit_nonblocking_assignment(self, node):
        """<= 非阻塞赋值"""
        self.assignments.append(node)

    def visit_blocking_assignment(self, node):
        """= 阻塞赋值"""
        self.assignments.append(node)

    def visit_continuous_assignment(self, node):
        """assign 连续赋值"""
        self.assignments.append(node)

    def reset(self):
        """重置收集器"""
        self.assignments = []
