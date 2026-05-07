# base_visitor.py - Visitor 模式抽象基类
"""
[铁律15] Visitor 模式必须使用
每个语法类型对应独立的 visit_<type> 方法
"""
from abc import ABC, abstractmethod
from typing import List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from trace.core.graph_models import TraceNode

class BaseVisitor(ABC):
    """AST Visitor 抽象基类"""
    
    def __init__(self):
        self.statements: List = []
        self.depth: int = 0
        self.max_depth: int = 30
    
    @abstractmethod
    def visit(self, node):
        """主入口：分发到对应的 visit 方法"""
        raise NotImplementedError
    
    def generic_visit(self, node):
        """通用递归：进入子节点"""
        if node is None or self.depth > self.max_depth:
            return
        
        self.depth += 1
        
        for attr in ['body', 'statement', 'statements', 'items']:
            if hasattr(node, attr):
                child = getattr(node, attr)
                if child and hasattr(child, '__iter__') and not isinstance(child, str):
                    for item in child:
                        if item:
                            self.visit(item)
                elif child:
                    self.visit(child)
        
        self.depth -= 1
    
    # ========================================
    # [P2] 块语句 Visitors
    # ========================================
    
    def visit_always_block(self, node):
        """always_ff / always_comb / always_block"""
        self.generic_visit(node)
    
    def visit_sequential_block(self, node):
        """begin...end 块"""
        self.generic_visit(node)
    
    def visit_timing_control(self, node):
        """@posedge clk 等时序控制"""
        self.generic_visit(node)
    
    # ========================================
    # [P2] 循环语句 Visitors
    # ========================================
    
    def visit_loop_statement(self, node):
        """while / for / repeat 循环"""
        self.generic_visit(node)
    
    # ========================================
    # [P1] 条件语句 Visitors
    # ========================================
    
    def visit_case(self, node):
        """case / casex / casez"""
        self.generic_visit(node)
    
    def visit_if(self, node):
        """if-else 语句"""
        self.generic_visit(node)
    
    # ========================================
    # [P0] 赋值语句 Visitors
    # ========================================
    
    def visit_nonblocking_assignment(self, node):
        """<= 非阻塞赋值"""
        pass
    
    def visit_blocking_assignment(self, node):
        """= 阻塞赋值"""
        pass
    
    def visit_continuous_assignment(self, node):
        """assign 连续赋值"""
        pass
    
    def visit_expression_statement(self, node):
        """表达式语句"""
        self.generic_visit(node)
