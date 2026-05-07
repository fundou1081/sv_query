# statement_visitor.py - 语句 Visitor
"""
[铁律15] Visitor 模式
处理: 循环、条件、块语句等
"""
from .base_visitor import BaseVisitor

class StatementVisitor(BaseVisitor):
    """语句 Visitor - 处理 while/for/case/if 等"""
    
    def __init__(self):
        super().__init__()
    
    def visit(self, node):
        """分发到对应的 visit 方法"""
        if node is None or self.depth > self.max_depth:
            return
        
        kind = getattr(node, 'kind', None)
        if kind is None:
            return
        
        kind_str = str(kind)
        
        # [P2] 循环语句
        if 'LoopStatement' in kind_str:
            return self.visit_loop_statement(node)
        
        # [P2] 块语句
        if 'SequentialBlock' in kind_str:
            return self.visit_sequential_block(node)
        
        if 'EventControl' in kind_str:
            return self.visit_timing_control(node)
        
        if 'AlwaysCombBlock' in kind_str or 'AlwaysBlock' in kind_str:
            return self.visit_always_block(node)
        
        # [P2] Class OOP
        if 'ClassDeclaration' in kind_str:
            return self.visit_class_declaration(node)
        
        if 'ClassProperty' in kind_str:
            return self.visit_class_property(node)
        
        # [P1] 条件语句
        if 'Case' in kind_str:
            return self.visit_case(node)
        
        if 'If' in kind_str:
            return self.visit_if(node)
        
        # [P0] 赋值语句
        if 'Nonblocking' in kind_str:
            return self.visit_nonblocking_assignment(node)
        
        if 'Blocking' in kind_str or 'AssignmentExpression' == kind_str:
            return self.visit_blocking_assignment(node)
        
        if 'ContinuousAssignment' in kind_str:
            return self.visit_continuous_assignment(node)
        
        if 'DataDeclaration' in kind_str:
            return self.visit_data_declaration(node)
        
        if 'ExpressionStatement' in kind_str:
            return self.visit_expression_statement(node)
        
        # 默认：递归进入子节点
        self.generic_visit(node)
    
    # ========================================
    # [P2] 块语句实现
    # ========================================
    
    def visit_always_block(self, node):
        """always_ff / always_comb / always_block"""
        # 进入 statement 属性
        if hasattr(node, 'statement'):
            self.visit(node.statement)
    
    def visit_sequential_block(self, node):
        """begin...end 块"""
        for attr in ['body', 'statements', 'items']:
            if hasattr(node, attr):
                block = getattr(node, attr)
                if block and hasattr(block, '__iter__') and not isinstance(block, str):
                    for item in block:
                        self.visit(item)
    
    def visit_timing_control(self, node):
        """@posedge clk 等时序控制"""
        if hasattr(node, 'statement'):
            self.visit(node.statement)
    
    # ========================================
    # [P2] 循环语句实现
    # ========================================
    
    def visit_loop_statement(self, node):
        """while / for / repeat 循环"""
        # 循环体在 statement 属性中
        if hasattr(node, 'statement'):
            self.visit(node.statement)
    
    # ========================================
    # [P1] 条件语句实现
    # ========================================
    
    def visit_case(self, node):
        """case 语句"""
        for item in getattr(node, 'items', []):
            if not item:
                continue
            stmt = getattr(item, 'clause', None) or getattr(item, 'statement', None)
            if stmt:
                self.visit(stmt)
    
    def visit_if(self, node):
        """if-else 语句"""
        # 递归处理所有分支
        self.generic_visit(node)
    
    # ========================================
    # [P0] 赋值语句实现 (子类负责具体逻辑)
    # ========================================
    
    def visit_nonblocking_assignment(self, node):
        """<= 非阻塞赋值 - 子类实现"""
        pass
    
    def visit_blocking_assignment(self, node):
        """= 阻塞赋值 - 子类实现"""
        pass
    
    def visit_continuous_assignment(self, node):
        """assign 连续赋值 - 子类实现"""
        pass
    
    def visit_expression_statement(self, node):
        """表达式语句"""
        self.generic_visit(node)
