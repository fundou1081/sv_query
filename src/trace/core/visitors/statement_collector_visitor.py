# statement_collector_visitor.py - 语句收集 Visitor (携带语义上下文)
"""
[铁律15] Visitor 模式
[铁律26] 必须使用 Visitor 模式，禁止 if-elif 链

职责:
1. 收集语句并携带语义上下文 (clock_domain, condition)
2. 处理 always_ff/always_comb/always_latch/initial 等过程块
3. 处理 case/if/while/for 等控制语句
4. 处理赋值和函数调用

对应 graph_builder.py 中的:
- _collect_stmts_with_context()
"""
from typing import List, Tuple, Dict, Any, Optional, Set
import logging

from .base_visitor import BaseVisitor

logger = logging.getLogger(__name__)


class StatementCollectorVisitor(BaseVisitor):
    """语句收集 Visitor - 携带语义上下文
    
    负责递归遍历 AST，收集语句节点并携带语义上下文。
    语义上下文包括:
    - clock: 时钟域 (来自 always_ff 的 @(posedge clk))
    - condition: 条件 (来自 if/case 等控制语句)
    - reset: 复位信号 (来自 @(posedge clk or negedge rst))
    
    使用方式:
        visitor = StatementCollectorVisitor(adapter)
        statements = visitor.collect(node)  # [(node, ctx), ...]
    """
    
    def __init__(self, adapter):
        """初始化
        
        Args:
            adapter: PyslangAdapter 实例，用于提取时钟、复位等信号
        """
        super().__init__()
        self.adapter = adapter
        self._statements: List[Tuple[Any, Dict[str, str]]] = []
        self._ctx_stack: List[Dict[str, str]] = [{}]
        self._visited: Set[int] = set()
    
    @property
    def current_ctx(self) -> Dict[str, str]:
        """获取当前上下文"""
        return self._ctx_stack[-1] if self._ctx_stack else {}
    
    def collect(self, node, ctx: Dict[str, str] = None) -> List[Tuple[Any, Dict[str, str]]]:
        """收集语句的入口方法
        
        Args:
            node: AST 节点
            ctx: 初始上下文
            
        Returns:
            [(node, ctx), ...] 语句和上下文元组列表
        """
        self._statements = []
        self._ctx_stack = [ctx.copy() if ctx else {}]
        self._visited = set()
        
        self.visit(node)
        
        result = self._statements
        self._statements = []
        return result
    
    def visit(self, node):
        """分发到对应的 visit 方法"""
        if node is None or self.depth > self.max_depth:
            return
        
        nid = id(node)
        if nid in self._visited:
            return
        self._visited.add(nid)
        
        kind = getattr(node, 'kind', None)
        if kind is None:
            self.generic_visit(node)
            return
        
        kind_name = kind.name if hasattr(kind, 'name') else None
        
        # 过滤 TokenKind 和 Trivia
        kind_str = str(kind) if kind else ""
        if ".TokenKind." in kind_str or "Trivia" in kind_str:
            return
        
        # [FIX] StatementKind 别名映射 (Semantic AST naming -> visitor methods)
        # Conditional -> conditional_statement, Timed -> timed_statement, etc.
        semantic_alias_map = {
            'Conditional': 'conditional_statement',
            'Timed': 'timed_statement',
            'Case': 'case_statement',
            'Block': 'block_statement',
            'ExpressionStatement': 'expression_statement',
            'ForLoop': 'loop_statement',
            'WhileLoop': 'loop_statement',
            'RepeatLoop': 'loop_statement',
            'ForeachLoop': 'loop_statement',
            'DoWhileLoop': 'loop_statement',
            'ForeverLoop': 'loop_statement',
            'Wait': 'wait_statement',
            'Return': 'jump_statement',
            'Break': 'jump_statement',
            'Continue': 'jump_statement',
            'Disable': 'disable_statement',
        }
        
        # 分发到对应方法
        if kind_name:
            method_name = f"visit_{kind_name}"
            if hasattr(self, method_name):
                getattr(self, method_name)(node)
                return
            # 尝试别名映射
            if kind_name in semantic_alias_map:
                alias = semantic_alias_map[kind_name]
                method_name = f"visit_{alias}"
                if hasattr(self, method_name):
                    getattr(self, method_name)(node)
                    return
        
        # 默认: 递归进入子节点
        self.generic_visit(node)
    
    def generic_visit(self, node):
        """通用递归：进入子节点"""
        if node is None or self.depth > self.max_depth:
            return
        
        self.depth += 1
        
        for attr in ['body', 'statement', 'statements', 'items', 'lhs', 'rhs']:
            if hasattr(node, attr):
                child = getattr(node, attr)
                if child and hasattr(child, '__iter__') and not isinstance(child, str):
                    for item in child:
                        if item:
                            self.visit(item)
                elif child:
                    self.visit(child)
        
        self.depth -= 1
    
    def _add_statement(self, node, ctx: Dict[str, str] = None):
        """添加语句到收集列表"""
        if node is None:
            return
        
        effective_ctx = ctx.copy() if ctx else self.current_ctx.copy()
        self._statements.append((node, effective_ctx))
    
    # =========================================================================
    # [P1] 过程块 - always_ff / always_comb / always_latch / initial
    # =========================================================================
    
    def visit_initial_block(self, node):
        """InitialBlock: initial 块
        
        initial 块没有时钟域，条件为空
        """
        self._add_statement(node)
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            self.visit(stmt)
    
    def visit_procedure_block(self, node):
        """AlwaysFF / AlwaysComb / AlwaysLatch 的统一入口
        
        根据 procedureKind 分发到具体方法
        """
        # [FIX] Semantic symbol 有 procedureKind 属性，不是 kind
        # kind 是 SymbolKind.ProceduralBlock，procedureKind 是 ProceduralBlockKind.AlwaysFF
        proc_kind = getattr(node, 'procedureKind', None)
        if proc_kind:
            proc_kind_str = str(proc_kind)
        else:
            proc_kind_str = ''
        
        if 'AlwaysFF' in proc_kind_str:
            self.visit_always_ff(node)
        elif 'AlwaysComb' in proc_kind_str:
            self.visit_always_comb(node)
        elif 'AlwaysLatch' in proc_kind_str:
            self.visit_always_latch(node)
        else:
            self.generic_visit(node)
    
    def visit_always_ff(self, node):
        """AlwaysFF: always_ff @(posedge clk) ... end
        
        提取时钟和复位信号
        """
        clock = self._extract_clock(node)
        reset = self._extract_reset(node)
        
        # 推入新上下文
        new_ctx = {
            "clock": clock,
            "reset": reset,
            "condition": ""
        }
        self._ctx_stack.append(new_ctx)
        
        # 进入 statement
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            self.visit(stmt)
        
        # 弹出上下文
        self._ctx_stack.pop()
    
    def visit_always_comb(self, node):
        """AlwaysComb: always_comb ... end
        
        无时钟域，组合逻辑
        """
        # 推入新上下文 (无时钟)
        new_ctx = {
            "clock": "",
            "reset": "",
            "condition": ""
        }
        self._ctx_stack.append(new_ctx)
        
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            self.visit(stmt)
        
        self._ctx_stack.pop()
    
    def visit_always_latch(self, node):
        """AlwaysLatch: always_latch ... end
        
        无时钟域，锁存器
        """
        # 与 always_comb 类似
        new_ctx = {
            "clock": "",
            "reset": "",
            "condition": ""
        }
        self._ctx_stack.append(new_ctx)
        
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            self.visit(stmt)
        
        self._ctx_stack.pop()
    
    def _extract_clock(self, node) -> str:
        """从 always_ff 提取时钟信号"""
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if not stmt:
            return ""
        
        # TimingControl 在 stmt.timing 或 stmt.timingControl
        tc = getattr(stmt, 'timing', None) or getattr(stmt, 'timingControl', None)
        if tc:
            return self._extract_clock_from_event_ctrl(tc)
        return ""
    
    def _extract_clock_from_event_ctrl(self, n) -> str:
        """从 TimingControl 提取时钟"""
        # EventList 有 events
        if hasattr(n, 'events'):
            for evt in n.events:
                clock = self._extract_clock_from_event_ctrl(evt)
                if clock:
                    return clock
            return ""
        
        e = getattr(n, 'expr', None)
        if not e:
            return ""
        
        i = getattr(e, 'expr', None) or e
        
        def find_clock(expr):
            if expr is None:
                return ""
            
            # NamedValueExpression with symbol
            if hasattr(expr, 'symbol'):
                sym = getattr(expr, 'symbol', None)
                if sym and hasattr(sym, 'name'):
                    return str(sym.name).strip()
            
            if hasattr(expr, 'left') and hasattr(expr, 'right'):
                l = find_clock(expr.left)
                return l if l else find_clock(expr.right)
            
            edge_str = str(getattr(expr, 'edge', ''))
            if 'posedge' in edge_str.lower() or 'PosEdge' in edge_str:
                ce = getattr(expr, 'expr', None)
                if ce and hasattr(ce, 'symbol'):
                    sym = getattr(ce, 'symbol', None)
                    if sym and hasattr(sym, 'name'):
                        return str(sym.name).strip()
                return str(ce).strip() if ce else ""
            
            return ""
        
        return find_clock(i)
    
    def _extract_reset(self, node) -> str:
        """从 always_ff 提取复位信号"""
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if not stmt:
            return ""
        
        tc = getattr(stmt, 'timing', None) or getattr(stmt, 'timingControl', None)
        if not tc:
            return ""
        
        # EventList
        if hasattr(tc, 'events'):
            for evt in tc.events:
                reset = self._extract_reset_from_event(evt)
                if reset:
                    return reset
            return ""
        
        return ""
    
    def _extract_reset_from_event(self, n) -> str:
        """从 Event 提取复位 (negedge)"""
        e = getattr(n, 'expr', None)
        if not e:
            return ""
        
        e = getattr(e, 'expr', None) or e
        
        edge_str = str(getattr(n, 'edge', ''))
        if 'negedge' in edge_str.lower() or 'NegEdge' in edge_str:
            if hasattr(e, 'symbol'):
                sym = getattr(e, 'symbol', None)
                if sym and hasattr(sym, 'name'):
                    return str(sym.name).strip()
            return str(e).strip() if e else ""
        
        return ""
    
    # =========================================================================
    # [P1] 时序控制
    # =========================================================================
    
    def visit_timing_control(self, node):
        """TimingControl: @posedge clk 等
        
        提取时钟，进入 statement
        """
        self._add_statement(node)
        tc = getattr(node, 'timingControl', None)
        if tc:
            clock = self._extract_clock_from_event_ctrl(tc)
            new_ctx = {**self.current_ctx, "clock": clock}
            self._ctx_stack.append(new_ctx)
        
        stmt = getattr(node, 'statement', None)
        if stmt:
            self.visit(stmt)
        
        if tc:
            self._ctx_stack.pop()
    
    def visit_Timed(self, node):
        """Timed: TimedStatement 的语义别名
        
        委托给 visit_timed_statement
        """
        # 不直接添加，而是委托给 timed_statement 处理
        self.visit_timed_statement(node)
    
    def visit_timed_statement(self, node):
        """TimedStatement: always @(*) wraps content
        
        进入 stmt
        """
        self._add_statement(node)
        stmt = getattr(node, 'stmt', None)
        if stmt:
            self.visit(stmt)
    
    # =========================================================================
    # [P1] 块语句
    # =========================================================================
    
    def visit_block_statement(self, node):
        """BlockStatement: begin...end 块
        
        进入 body
        """
        self._add_statement(node)
        body = getattr(node, 'body', None)
        if body:
            if hasattr(body, 'kind') and not (hasattr(body, '__iter__') and not isinstance(body, str)):
                self.visit(body)
            elif hasattr(body, '__iter__') and not isinstance(body, str):
                for i in body:
                    self.visit(i)
    
    # =========================================================================
    # [P1] 条件语句
    # =========================================================================
    

    def visit_sequential_block(self, node):
        """begin...end 块"""
        self._add_statement(node)
        self.generic_visit(node)

    def visit_case_statement(self, node):
        """CaseStatement: case/endcase
        
        处理所有分支，追踪条件上下文
        """
        self._add_statement(node)
        # 提取 case 条件
        case_cond = ""
        if hasattr(node, 'condition'):
            case_cond = str(node.condition)
        
        # 获取 items
        items = getattr(node, 'items', [])
        
        # 检查是否需要从 syntax 获取
        syntax_items = None
        if hasattr(node, 'syntax') and node.syntax and hasattr(node.syntax, 'items'):
            syntax_items = node.syntax.items
        
        process_items = items if items and not (len(items) == 1 and type(items[0]).__name__ == 'ItemGroup') else syntax_items
        
        if process_items:
            for item in process_items:
                stmt = getattr(item, 'stmt', None) or getattr(item, 'clause', None)
                if stmt:
                    self.visit(stmt)
    

    def visit_case(self, node):
        """case / casex / casez"""
        self.visit_case_statement(node)

    def visit_if(self, node):
        """if-else 语句"""
        self.visit_conditional_statement(node)

    def visit_conditional_statement(self, node):
        """ConditionalStatement: if/else
        
        处理 ifTrue/ifFalse，追踪条件
        """
        self._add_statement(node)
        # 提取条件
        cond = self._extract_condition(node)
        
        # ifTrue 分支
        ts = getattr(node, 'ifTrue', None) or getattr(node, 'statement', None)
        if ts:
            new_ctx = {**self.current_ctx, "condition": cond}
            self._ctx_stack.append(new_ctx)
            self.visit(ts)
            self._ctx_stack.pop()
        
        # ifFalse (else) 分支
        ec = getattr(node, 'ifFalse', None) or getattr(node, 'elseClause', None)
        if ec:
            ae = getattr(ec, 'clause', None) or ec
            neg_cond = "!" + cond if cond else ""
            new_ctx = {**self.current_ctx, "condition": neg_cond}
            self._ctx_stack.append(new_ctx)
            self.visit(ae)
            self._ctx_stack.pop()
    
    def _extract_condition(self, n) -> str:
        """从 if 语句提取条件表达式"""
        # predicate.conditions (syntax tree)
        p = getattr(n, "predicate", None)
        if p:
            cs = getattr(p, "conditions", None)
            if cs is not None:
                if isinstance(cs, (list, tuple)):
                    exprs = []
                    for cond in cs:
                        expr = getattr(cond, 'expr', None)
                        if expr:
                            syn = getattr(expr, 'syntax', None)
                            if syn:
                                exprs.append(str(syn))
                            else:
                                exprs.append(str(expr))
                    return ' && '.join(exprs) if exprs else str(p).strip()
                return str(cs).strip()
            return str(p).strip()
        
        # Semantic AST: conditions directly
        cs = getattr(n, "conditions", None)
        if cs:
            exprs = []
            for cond in cs:
                expr = getattr(cond, 'expr', None)
                if expr:
                    exprs.append(str(expr))
            return ' && '.join(exprs) if exprs else ""
        
        return ""
    
    def visit_else_clause(self, node):
        """ElseClause: else 分支
        
        进入 clause
        """
        self._add_statement(node)
        s = getattr(node, 'clause', None)
        if s:
            self.visit(s)
    
    # =========================================================================
    # [P1] 表达式语句和赋值
    # =========================================================================
    
    def visit_expression_statement(self, node):
        """ExpressionStatement: 表达式语句
        
        进入 expr
        """
        self._add_statement(node)
        e = getattr(node, 'expr', None)
        if e:
            self.visit(e)
    
    def visit_assignment(self, node):
        """Assignment: 赋值语句 (=, <=)
        
        收集赋值节点
        """
        self._add_statement(node, self.current_ctx)
    
    def visit_invocation(self, node):
        """InvocationExpression: 函数/任务调用
        
        收集调用节点
        """
        self._add_statement(node)
    
    def visit_continuous_assignment(self, node):
        """assign 连续赋值"""
        self._add_statement(node)
    
    # =========================================================================
    # [P2] 循环语句
    # =========================================================================
    
    def visit_loop_statement(self, node):
        """LoopStatement: while/for/repeat
        
        进入 body/statement
        """
        self._add_statement(node)
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            self.visit(stmt)
    
    # =========================================================================
    # [P2] 其他语句类型
    # =========================================================================
    

    def visit_nonblocking_assignment(self, node):
        """<= 非阻塞赋值"""
        self._add_statement(node)

    def visit_blocking_assignment(self, node):
        """= 阻塞赋值"""
        self._add_statement(node)

    def visit_jump_statement(self, node):
        """JumpStatement: return/break/continue"""
        self._add_statement(node)
    
    def visit_wait_statement(self, node):
        """WaitStatement: wait(condition)"""
        self._add_statement(node)
        self.generic_visit(node)
    
    def visit_event_control(self, node):
        """EventControl: @clk"""
        self._add_statement(node)
        stmt = getattr(node, 'statement', None)
        if stmt:
            self.visit(stmt)
    
    def visit_disable_statement(self, node):
        """DisableStatement: disable name"""
        self._add_statement(node)
    
    def visit_procedural_timing_control(self, node):
        """ProceduralTimingControl: #delay"""
        self._add_statement(node)
        self.generic_visit(node)