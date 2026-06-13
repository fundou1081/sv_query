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

import logging
from enum import Enum, auto
from typing import Any

from .base_visitor import BaseVisitor

logger = logging.getLogger(__name__)


class ItemType(Enum):
    """语句类型枚举

    [铁律27] 使用枚举定义有限集合，禁止硬编码字符串
    """

    STATEMENT = auto()  # 默认语句
    ASSIGNMENT = auto()  # 赋值语句 (=, <=)
    INVOCATION = auto()  # 函数/任务调用
    TIMING_CONTROL = auto()  # 时间控制 (@, #)
    CONDITIONAL = auto()  # 条件语句 (if/else)
    CASE = auto()  # case 语句
    LOOP = auto()  # for/while 循环
    BLOCK = auto()  # begin...end 块
    JUMP = auto()  # return/break/continue
    DISABLE = auto()  # disable

    WAIT_FORK = auto()  # wait fork
    WAIT_ORDER = auto()  # wait order
    RAND_CASE = auto()  # rand case
    RAND_SEQUENCE = auto()  # rand sequence
    VARIABLE_DECLARATION = auto()  # 变量声明
    EVENT_TRIGGER = auto()  # 事件触发
    IMMEDIATE_ASSERTION = auto()  # 即时断言
    CONCURRENT_ASSERTION = auto()  # 并发断言
    PROCEDURAL_ASSIGN = auto()  # force 语句
    PROCEDURAL_DEASSIGN = auto()  # release 语句
    DISABLE_FORK = auto()  # disable fork


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
        self._statements: list[tuple[Any, dict[str, str]]] = []
        self._ctx_stack: list[dict[str, str]] = [{}]
        self._visited: set[int] = set()

    @staticmethod
    def _safe_str(obj) -> str:
        """安全的 str() 调用，容忍非 utf-8 字节 (e.g. escape 序列)

        pyslang 的 Token/Syntax 节点在 str() 时会尝试 utf-8 解码,
        对于包含非 ASCII 字节的 escape 序列 (e.g. \\x80) 会抛 UnicodeDecodeError。
        这里捕获后返回 hex 表达, 避免中断整个 trace 流程。
        """
        if obj is None:
            return ""
        try:
            return str(obj)
        except (UnicodeDecodeError, TypeError):
            try:
                if hasattr(obj, 'rawText'):
                    raw = bytes(obj.rawText) if hasattr(obj.rawText, '__bytes__') else b''
                elif hasattr(obj, '__bytes__'):
                    raw = bytes(obj)
                else:
                    raw = b''
                return f"<id:0x{raw.hex()[:16]}>"
            except Exception:
                return "<id:non-utf8>"

    @property
    def current_ctx(self) -> dict[str, str]:
        """获取当前上下文"""
        return self._ctx_stack[-1] if self._ctx_stack else {}

    def _is_simple_expr_for_negation(self, expr) -> bool:
        """判断表达式是否为简单条件（可以直接求反，不需要括号）

        简单条件：
        - 简单标识符 (NamedValue/Identifier/Reference)
        - 简单取反 (!identifier)

        复杂条件（需要括号）：
        - 二元运算 (valid && sel)
        - 嵌套取反 (!(!rst_n))
        - 其他复杂表达式
        """
        if expr is None:
            return True  # 无条件默认为简单

        kind = getattr(expr, "kind", None)
        if not kind:
            return True
        kind_name = kind.name if hasattr(kind, "name") else str(kind)

        # 简单标识符
        if kind_name in ("NamedValue", "Identifier", "Reference"):
            return True

        # UnaryOp: 检查是否简单取反 !identifier
        if "UnaryOp" in kind_name:
            op = getattr(expr, "op", None)
            if not op or "Not" not in (op.name if hasattr(op, "name") else str(op)):
                return False  # 不是 ! 运算符
            operand = getattr(expr, "operand", None)
            if operand:
                operand_kind = getattr(operand, "kind", None)
                if operand_kind:
                    operand_name = operand_kind.name if hasattr(operand_kind, "name") else str(operand_kind)
                    # 只有 !identifier 是简单的
                    return operand_name in ("NamedValue", "Identifier", "Reference")
            return False

        # BinaryOp 等复杂表达式
        return False

    def _is_reset_condition(self, expr) -> bool:
        """判断表达式是否为 reset 条件

        Reset 条件：UnaryOp(!rst_n) 且 operand 是 NamedValue/Identifier 且名称包含 rst/reset
        """
        if expr is None:
            return False

        kind = getattr(expr, "kind", None)
        if not kind:
            return False
        kind_name = kind.name if hasattr(kind, "name") else str(kind)

        # UnaryOp: 检查是否 !rst 或 !reset
        if "UnaryOp" in kind_name:
            op = getattr(expr, "op", None)
            if not op or "Not" not in (op.name if hasattr(op, "name") else str(op)):
                return False
            operand = getattr(expr, "operand", None)
            if operand:
                # 获取 operand 的名称
                if hasattr(operand, "name"):
                    name = operand.name
                elif hasattr(operand, "text"):
                    name = operand.text
                else:
                    name = str(operand)
                # 检查名称是否包含 rst/reset
                name_lower = name.lower() if isinstance(name, str) else ""
                return "rst" in name_lower or "reset" in name_lower
        return False

    def _compute_effective_condition(self, cond_exprs: list) -> str:
        """从条件 AST 列表中提取 effective_condition

        规则：跳过 reset 条件（如 !rst_n），返回最后一个非 reset 条件的完整表达式

        对于 case item，会返回 case item 值（如 REQ），需要构造完整的比较表达式
        """
        # 找到最后一个非 reset 的表达式
        last_expr = None
        for expr in reversed(cond_exprs):
            if not self._is_reset_condition(expr):
                last_expr = expr
                break

        if last_expr is None:
            return ""

        # 获取 last_expr 的 kind
        kind = getattr(last_expr, "kind", None)
        kind_name = kind.name if hasattr(kind, "name") else str(kind) if kind else ""

        # 如果 last_expr 是一个 case item 值（如 NamedValue REQ），
        # 构造完整的比较表达式：selector == value
        if kind_name in ("NamedValue", "Identifier", "Reference", "IdentifierName"):
            # 获取 case selector（从当前上下文）
            selector = self.current_ctx.get("_case_selector", "")
            if selector:
                # 从 case item 条件值构造比较表达式
                # last_expr 的名称就是 case item 的值
                value_name = ""
                if hasattr(last_expr, "name"):
                    value_name = str(last_expr.name).strip()
                elif hasattr(last_expr, "text"):
                    value_name = self._safe_str(last_expr.text).strip()
                else:
                    value_name = self._safe_str(last_expr).strip()

                if value_name and value_name not in ("0", "1", "true", "false"):
                    return f"{selector} == {value_name}"

        return self._expr_to_string(last_expr)

    def collect(self, node, ctx: dict[str, str] = None) -> list[tuple[Any, dict[str, str], ItemType]]:
        """收集语句的入口方法

        Args:
            node: AST 节点
            ctx: 初始上下文

        Returns:
            List[(node, ctx, item_type)] 语句和上下文元组列表
            - node: AST 节点
            - ctx: 上下文字典
            - item_type: ItemType 枚举标记
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

        kind = getattr(node, "kind", None)
        if kind is None:
            self.generic_visit(node)
            return

        kind_name = kind.name if hasattr(kind, "name") else None

        # 过滤 TokenKind 和 Trivia
        kind_str = str(kind) if kind else ""
        if ".TokenKind." in kind_str or "Trivia" in kind_str:
            return

        # [FIX] StatementKind 别名映射 (Semantic AST naming -> visitor methods)
        # Conditional -> conditional_statement, Timed -> timed_statement, etc.
        semantic_alias_map = {
            "Conditional": "conditional_statement",
            "Timed": "timed_statement",
            "Case": "case_statement",
            "Block": "block_statement",
            "ExpressionStatement": "expression_statement",
            "ForLoop": "loop_statement",
            "WhileLoop": "loop_statement",
            "RepeatLoop": "loop_statement",
            "ForeachLoop": "loop_statement",
            "DoWhileLoop": "loop_statement",
            "ForeverLoop": "loop_statement",
            "Wait": "wait_statement",
            "Return": "jump_statement",
            "Break": "jump_statement",
            "Continue": "jump_statement",
            "Disable": "disable_statement",
            "Call": "invocation",  # CallExpression -> visit_invocation
        }

        # [铁律26] 分发到对应方法 (PascalCase -> snake_case 转换)
        if kind_name:
            import re

            # PascalCase -> snake_case: "Assignment" -> "visit_assignment"
            # But "ExpressionStatement" -> "expression_statement" (insert underscore before capitals)
            snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", kind_name).lower()
            method_name = f"visit_{snake_name}"
            if hasattr(self, method_name):
                getattr(self, method_name)(node)
                return

            # [FIX] 处理 SyntaxKind.XXXExpression -> visit_XXX 的映射
            # e.g., "NonblockingAssignmentExpression" -> "visit_nonblocking_assignment"
            if kind_name.endswith("Expression"):
                base_name = kind_name[:-10]  # Strip 'Expression'
                base_snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base_name).lower()
                method_name = f"visit_{base_snake}"
                if hasattr(self, method_name):
                    getattr(self, method_name)(node)
                    return

            # [FIX] SymbolKind 别名映射 (ProceduralBlock -> procedure_block)
            symbol_alias_map = {
                "ProceduralBlock": "procedure_block",
            }
            if kind_name in symbol_alias_map:
                alias = symbol_alias_map[kind_name]
                method_name = f"visit_{alias}"
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

        for attr in ["body", "statement", "statements", "items", "lhs", "rhs", "list"]:
            if hasattr(node, attr):
                child = getattr(node, attr)
                if child and hasattr(child, "__iter__") and not isinstance(child, str):
                    for item in child:
                        if item:
                            self.visit(item)
                elif child:
                    self.visit(child)

        self.depth -= 1

    def _add_statement(self, node, ctx: dict[str, str] = None, item_type: ItemType = ItemType.STATEMENT):
        """添加语句到收集列表

        Args:
            node: AST 节点
            ctx: 上下文字典 (默认使用 current_ctx)
            item_type: 语句类型标记 (ItemType 枚举)
        """
        if node is None:
            return

        effective_ctx = ctx.copy() if ctx else self.current_ctx.copy()
        self._statements.append((node, effective_ctx, item_type))

    def visit_empty_statement(self, node):
        """EmptyStatement: 空语句 ; 或 begin end

        不产生任何节点
        """
        pass

    def visit_variable_declaration(self, node):
        """VariableDeclaration: 变量声明 logic [7:0] data;

        记录变量声明
        """
        self._add_statement(node, item_type=ItemType.VARIABLE_DECLARATION)

    def visit_invalid_statement(self, node):
        """Invalid: 无效/错误的 AST 节点

        跳过不处理
        """
        pass

    def visit_event_trigger(self, node):
        """EventTrigger: -> event_name

        记录事件触发
        """
        self._add_statement(node, item_type=ItemType.EVENT_TRIGGER)

    def visit_immediate_assertion(self, node):
        """ImmediateAssertion: assert 表达式

        记录断言语句
        """
        self._add_statement(node, item_type=ItemType.IMMEDIATE_ASSERTION)

    def visit_concurrent_assertion(self, node):
        """ConcurrentAssertion: assert property(...), assume property(...)

        记录并发断言
        """
        self._add_statement(node, item_type=ItemType.CONCURRENT_ASSERTION)

    def visit_procedural_assign(self, node):
        """ProceduralAssign: force assignment

        记录 force 语句
        """
        self._add_statement(node, item_type=ItemType.PROCEDURAL_ASSIGN)

    def visit_procedural_deassign(self, node):
        """ProceduralDeassign: release assignment

        记录 release 语句
        """
        self._add_statement(node, item_type=ItemType.PROCEDURAL_DEASSIGN)

    def visit_procedural_checker(self, node):
        """ProceduralChecker: checker declaration

        记录 checker
        """
        pass  # 通常在块外定义

    def visit_disable_fork(self, node):
        """DisableFork: disable fork

        记录 disable fork
        """
        self._add_statement(node, item_type=ItemType.DISABLE_FORK)

    def visit_wait_fork(self, node):
        """WaitFork: wait fork

        记录 wait fork
        """
        self._add_statement(node, item_type=ItemType.WAIT_FORK)

    def visit_wait_order(self, node):
        """WaitOrder: wait order(...)

        记录 wait order
        """
        self._add_statement(node, item_type=ItemType.WAIT_ORDER)

    def visit_rand_case(self, node):
        """RandCase: rand case

        记录 rand case
        """
        self._add_statement(node, item_type=ItemType.RAND_CASE)

    def visit_rand_sequence(self, node):
        """RandSequence: rand sequence

        记录 rand sequence
        """
        self._add_statement(node, item_type=ItemType.RAND_SEQUENCE)

    def visit_pattern_case(self, node):
        """PatternCase: pattern case item

        使用通用的 case 处理
        """
        self.generic_visit(node)

    def visit_list(self, node):
        """List: 语句列表

        递归处理
        """
        self.generic_visit(node)

    # =========================================================================
    # [P1] 过程块 - always_ff / always_comb / always_latch / initial
    # =========================================================================

    def visit_initial_block(self, node):
        """InitialBlock: initial 块

        initial 块没有时钟域，条件为空
        """
        self._add_statement(node, item_type=ItemType.ASSIGNMENT)
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

    def visit_procedure_block(self, node):
        """AlwaysFF / AlwaysComb / AlwaysLatch 的统一入口

        根据 procedureKind 分发到具体方法
        """
        # [FIX] Semantic symbol 有 procedureKind 属性，不是 kind
        # kind 是 SymbolKind.ProceduralBlock，procedureKind 是 ProceduralBlockKind.AlwaysFF
        proc_kind = getattr(node, "procedureKind", None)
        if proc_kind:
            proc_kind_str = str(proc_kind)
        else:
            proc_kind_str = ""

        if "AlwaysFF" in proc_kind_str:
            self.visit_always_ff(node)
        elif "AlwaysComb" in proc_kind_str:
            self.visit_always_comb(node)
        elif "AlwaysLatch" in proc_kind_str:
            self.visit_always_latch(node)
        elif "Always" in proc_kind_str:
            # Verilog always @(posedge clk) - 同 always_ff 处理
            self.visit_always_ff(node)
        else:
            self.generic_visit(node)

    def visit_always_ff(self, node):
        """AlwaysFF: always_ff @(posedge clk) ... end

        提取时钟和复位信号
        """
        clock = self._extract_clock(node)
        reset = self._extract_reset(node)

        # 推入新上下文
        new_ctx = {"clock": clock, "reset": reset, "condition": ""}
        self._ctx_stack.append(new_ctx)

        # 进入 statement
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

        # 弹出上下文
        self._ctx_stack.pop()

    def visit_always_comb(self, node):
        """AlwaysComb: always_comb ... end

        无时钟域，组合逻辑
        """
        # 推入新上下文 (无时钟)
        new_ctx = {"clock": "", "reset": "", "condition": ""}
        self._ctx_stack.append(new_ctx)

        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

        self._ctx_stack.pop()

    def visit_always_latch(self, node):
        """AlwaysLatch: always_latch ... end

        无时钟域，锁存器
        """
        # 与 always_comb 类似
        new_ctx = {"clock": "", "reset": "", "condition": ""}
        self._ctx_stack.append(new_ctx)

        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

        self._ctx_stack.pop()

    def _extract_clock(self, node) -> str:
        """从 always_ff 提取时钟信号"""
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if not stmt:
            return ""

        # TimingControl 在 stmt.timing 或 stmt.timingControl
        tc = getattr(stmt, "timing", None) or getattr(stmt, "timingControl", None)
        if tc:
            return self._extract_clock_from_event_ctrl(tc)
        return ""

    def _extract_clock_from_event_ctrl(self, n) -> str:
        """从 TimingControl 提取时钟"""
        # EventList 有 events
        if hasattr(n, "events"):
            for evt in n.events:
                clock = self._extract_clock_from_event_ctrl(evt)
                if clock:
                    return clock
            return ""

        e = getattr(n, "expr", None)
        if not e:
            return ""

        i = getattr(e, "expr", None) or e

        def find_clock(expr):
            if expr is None:
                return ""

            # NamedValueExpression with symbol
            if hasattr(expr, "symbol"):
                sym = getattr(expr, "symbol", None)
                if sym:
                    try:
                        _name = sym.name
                    except (UnicodeDecodeError, TypeError, Exception):
                        _name = None
                    if _name:
                        return self._safe_str(_name).strip()

            if hasattr(expr, "left") and hasattr(expr, "right"):
                left_res = find_clock(expr.left)
                return left_res if left_res else find_clock(expr.right)

            edge_str = str(getattr(expr, "edge", ""))
            if "posedge" in edge_str.lower() or "PosEdge" in edge_str:
                ce = getattr(expr, "expr", None)
                if ce and hasattr(ce, "symbol"):
                    sym = getattr(ce, "symbol", None)
                    if sym:
                        try:
                            _name = sym.name
                        except (UnicodeDecodeError, TypeError, Exception):
                            _name = None
                        if _name:
                            return self._safe_str(_name).strip()
                return self._safe_str(ce).strip() if ce else ""

            return ""

        return find_clock(i)

    def _extract_reset(self, node) -> str:
        """从 always_ff 提取复位信号"""
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if not stmt:
            return ""

        tc = getattr(stmt, "timing", None) or getattr(stmt, "timingControl", None)
        if not tc:
            return ""

        # EventList
        if hasattr(tc, "events"):
            for evt in tc.events:
                reset = self._extract_reset_from_event(evt)
                if reset:
                    return reset
            return ""

        return ""

    def _extract_reset_from_event(self, n) -> str:
        """从 Event 提取复位信号

        规则:
        - negedge 且信号名包含 'rst'/'reset' -> 返回复位
        - posedge 且信号名包含 'rst'/'reset' -> 返回复位 (异步复位)
        - 其他信号名 -> 不返回 (可能是时钟)
        """
        e = getattr(n, "expr", None)
        if not e:
            return ""

        e = getattr(e, "expr", None) or e

        # 首先检查信号名是否像复位信号
        is_reset_signal = False
        signal_name = ""
        if hasattr(e, "symbol"):
            sym = getattr(e, "symbol", None)
            if sym:
                try:
                    _name = sym.name
                except (UnicodeDecodeError, TypeError, Exception):
                    _name = None
                if _name:
                    signal_name = self._safe_str(_name).strip()
                if "rst" in signal_name.lower() or "reset" in signal_name.lower():
                    is_reset_signal = True

        # 然后检查边沿
        edge_str = str(getattr(n, "edge", ""))
        is_negedge = "negedge" in edge_str.lower() or "NegEdge" in edge_str
        is_posedge = "posedge" in edge_str.lower() or "PosEdge" in edge_str

        # 如果信号名像复位，且边沿是 negedge 或 posedge，返回信号名
        if is_reset_signal and (is_negedge or is_posedge):
            return signal_name

        return ""

    # =========================================================================
    # [P1] 时序控制
    # =========================================================================

    def visit_timing_control(self, node):
        """TimingControl: @posedge clk 等

        提取时钟，进入 statement
        """
        self._add_statement(node, item_type=ItemType.ASSIGNMENT)
        tc = getattr(node, "timingControl", None)
        if tc:
            clock = self._extract_clock_from_event_ctrl(tc)
            new_ctx = {**self.current_ctx, "clock": clock}
            self._ctx_stack.append(new_ctx)

        stmt = getattr(node, "statement", None)
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
        self._add_statement(node, item_type=ItemType.TIMING_CONTROL)
        stmt = getattr(node, "stmt", None)
        if stmt:
            self.visit(stmt)

    # =========================================================================
    # [P1] 块语句
    # =========================================================================

    def visit_block_statement(self, node):
        """BlockStatement: begin...end 块

        进入 body
        """
        self._add_statement(node, item_type=ItemType.BLOCK)
        body = getattr(node, "body", None)
        if body:
            if hasattr(body, "kind") and not (hasattr(body, "__iter__") and not isinstance(body, str)):
                self.visit(body)
            elif hasattr(body, "__iter__") and not isinstance(body, str):
                for i in body:
                    self.visit(i)

    # =========================================================================
    # [P1] 条件语句
    # =========================================================================

    def visit_sequential_block(self, node):
        """begin...end 块"""
        self._add_statement(node, item_type=ItemType.BLOCK)
        self.generic_visit(node)

    def visit_case_statement(self, node):
        """CaseStatement: case/endcase

        处理所有分支，追踪条件上下文
        """
        self._add_statement(node, item_type=ItemType.CASE)

        # 获取 case selector (条件表达式)
        selector = self._get_case_selector(node)

        # [FIX] 保存 case selector 到上下文，供 _compute_effective_condition 使用
        # 先保留旧的 selector，退出时恢复
        self.current_ctx.get("_case_selector", "")
        self.current_ctx["_case_selector"] = selector

        # 获取 items
        items = getattr(node, "items", [])

        # [FIX] 始终优先使用 syntax items 获取 case item 条件
        # 语义 ItemGroup 没有 case item 条件信息 (0:, 1:, default:)
        # syntax items 有 StandardCaseItemSyntax.expressions 存储条件值
        syntax_items = None
        if hasattr(node, "syntax") and node.syntax and hasattr(node.syntax, "items"):
            syntax_items = node.syntax.items

        # 优先使用 syntax items（因为包含条件信息）
        use_syntax = syntax_items is not None and len(syntax_items) > 0

        process_items = syntax_items if use_syntax else items

        if process_items:
            for item in process_items:
                # 提取 case item 的条件值
                item_cond = self._get_case_item_condition(item, selector)

                # [BUG-FIX] 合并外层条件和 case item 条件
                # 外层条件 (如 !!rst_n) AND case item 条件 (如 state == REQ)
                parent_cond = self.current_ctx.get("condition", "")
                # [NEW] 从 parent_cond_exprs 中获取外层条件 AST 列表
                cond_exprs = list(self.current_ctx.get("_cond_exprs", []))
                # 获取 case item 的条件表达式 AST
                item_cond_expr = self._get_case_item_condition_ast(item)
                if item_cond_expr:
                    cond_exprs.append(item_cond_expr)
                if parent_cond:
                    # 组合条件: parent_cond && item_cond
                    combined_cond = f"{parent_cond} && {item_cond}"
                    new_ctx = {
                        **self.current_ctx,
                        "condition": combined_cond,
                        "_cond_exprs": cond_exprs,
                        "effective_condition": self._compute_effective_condition(cond_exprs),
                        # [P1 cycle 5] case 路径也存 condition_ast (V2.A.2 17a 遗漏)
                        "condition_ast": item_cond_expr,
                    }
                else:
                    new_ctx = {
                        **self.current_ctx,
                        "condition": item_cond,
                        "_cond_exprs": cond_exprs,
                        "effective_condition": self._compute_effective_condition(cond_exprs),
                        # [P1 cycle 5] case 路径也存 condition_ast
                        "condition_ast": item_cond_expr,
                    }

                self._ctx_stack.append(new_ctx)

                # 语义 AST: stmt 属性
                # 语法 AST: clause 属性
                stmt = getattr(item, "stmt", None) or getattr(item, "clause", None)
                if stmt:
                    self.visit(stmt)

                # 弹出上下文
                self._ctx_stack.pop()

    def _get_case_selector(self, node) -> str:
        """提取 case 语句的 selector 表达式字符串

        Returns:
            selector 字符串，如 "sel"
        """
        # 尝试语义 AST: stmt.expr
        expr = getattr(node, "expr", None)
        if expr:
            sel_str = self._expr_to_string(expr)
            if sel_str:
                return sel_str

        # 尝试语法 AST: syntax.expr
        syntax = getattr(node, "syntax", None)
        if syntax:
            expr = getattr(syntax, "expr", None)
            if expr:
                return self._safe_str(expr).strip()

        return "?"

    def _get_case_item_condition(self, item, selector: str) -> str:
        """提取 case item 的条件值

        Args:
            item: case item 节点
            selector: case selector 表达式字符串

        Returns:
            条件字符串，如 "sel == 0" 或 "sel == default"
        """
        # 检查是否是 default case
        item_kind = getattr(item, "kind", None)
        item_kind_name = item_kind.name if hasattr(item_kind, "name") else str(item_kind)

        if "Default" in item_kind_name:
            return f"{selector} == default"

        # StandardCaseItem: 从 expressions 获取条件值
        expressions = getattr(item, "expressions", None)
        if expressions:
            # expressions 可能是一个列表，提取值
            if hasattr(expressions, "__iter__") and not isinstance(expressions, str):
                expr_parts = []
                for expr in expressions:
                    expr_str = self._expr_to_string(expr)
                    if expr_str:
                        expr_parts.append(expr_str)
                if expr_parts:
                    return f"{selector} == {' || '.join(expr_parts)}"
            else:
                expr_str = self._expr_to_string(expressions)
                if expr_str:
                    return f"{selector} == {expr_str}"

        return f"{selector} == ?"

    def _get_case_item_condition_ast(self, item) -> Any | None:
        """提取 case item 的条件表达式 AST

        用于构建 _cond_exprs 列表

        Args:
            item: case item 节点

        Returns:
            条件表达式 AST 对象或 None
        """
        # 检查是否是 default case
        item_kind = getattr(item, "kind", None)
        item_kind_name = item_kind.name if hasattr(item_kind, "name") else str(item_kind)

        if "Default" in item_kind_name:
            return None  # default 不加入条件列表

        # StandardCaseItem: 从 expressions 获取条件 AST
        expressions = getattr(item, "expressions", None)
        if expressions:
            if hasattr(expressions, "__iter__") and not isinstance(expressions, str):
                # 多个条件值，返回第一个（通常 case 只有一个）
                for expr in expressions:
                    return expr
            else:
                return expressions
        return None

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
        # 提取条件
        cond = self._extract_condition(node)
        # 条件表达式：Semantic AST 有 conditions，Syntax AST 需要特殊处理
        cond_expr = None
        if hasattr(node, "conditions") and node.conditions:
            # Semantic AST: ConditionalStatement
            cond_expr = node.conditions[0].expr if len(node.conditions) > 0 else None
        elif hasattr(node, "predicate") and node.predicate:
            # Syntax AST: ConditionalStatementSyntax - 从 predicate 提取
            pred = node.predicate
            if hasattr(pred, "conditions"):
                cond_expr = pred.conditions[0].expr if len(pred.conditions) > 0 else None

        # ifTrue 分支
        ts = getattr(node, "ifTrue", None) or getattr(node, "statement", None)
        if ts:
            # Combine parent condition with current condition
            parent_cond = self.current_ctx.get("condition", "")
            if parent_cond:
                new_cond = parent_cond + " && " + cond if cond else parent_cond
            else:
                new_cond = cond
            # [NEW] 保存条件 AST 到 _cond_exprs 列表
            cond_exprs = list(self.current_ctx.get("_cond_exprs", []))
            if cond_expr:
                cond_exprs.append(cond_expr)
            # [NEW] 计算 effective_condition（最后一个非 reset 条件）
            effective_cond = self._compute_effective_condition(cond_exprs)
            new_ctx = {
                **self.current_ctx,
                "condition": new_cond,
                "_parent_cond_expr": cond_expr,
                "_cond_exprs": cond_exprs,
                "effective_condition": effective_cond,
                # [V2.A.2 cycle 17a] 把当前条件 AST 节点存入 ctx,
                # 供 graph_builder 填充到 TraceEdge.condition_ast
                "condition_ast": cond_expr,
            }
            self._ctx_stack.append(new_ctx)
            self.visit(ts)
            self._ctx_stack.pop()

        # ifFalse (else) 分支
        ec = getattr(node, "ifFalse", None) or getattr(node, "elseClause", None)
        if ec:
            ae = getattr(ec, "clause", None) or ec
            # [BUG-FIX] else-if chain: properly negate condition at semantic AST level
            # For "if (A) ... else if (B) ...": condition is (!A && B)
            # For "if (A) ... else ...": condition is (!A)
            # We use semantic AST to determine if parentheses are needed.

            def _is_simple_identifier(expr) -> bool:
                """判断表达式是否为简单标识符"""
                if expr is None:
                    return False
                kind = getattr(expr, "kind", None)
                if not kind:
                    return False
                kind_name = kind.name if hasattr(kind, "name") else str(kind)
                return kind_name in ("NamedValue", "Identifier", "Reference")

            def _is_simple_negation(expr) -> bool:
                """判断表达式是否为简单取反 (!identifier)

                简单取反：UnaryOp 且 operand 是 NamedValue/Identifier，不嵌套 UnaryOp
                """
                if expr is None:
                    return False
                kind = getattr(expr, "kind", None)
                if not kind:
                    return False
                kind_name = kind.name if hasattr(kind, "name") else str(kind)

                if "UnaryOp" in kind_name:
                    op = getattr(expr, "op", None)
                    if not op or "Not" not in (op.name if hasattr(op, "name") else str(op)):
                        return False
                    operand = getattr(expr, "operand", None)
                    if operand:
                        operand_kind = getattr(operand, "kind", None)
                        if operand_kind:
                            operand_name = operand_kind.name if hasattr(operand_kind, "name") else str(operand_kind)
                            return operand_name in ("NamedValue", "Identifier", "Reference")
                    return False
                return False

            # 获取条件表达式 (语义AST)
            cond_expr = None
            if hasattr(node, "conditions") and node.conditions:
                cond_expr = node.conditions[0].expr if len(node.conditions) > 0 else None
            elif hasattr(node, "predicate") and node.predicate:
                pred = node.predicate
                if hasattr(pred, "conditions"):
                    cond_expr = pred.conditions[0].expr if len(pred.conditions) > 0 else None

            if cond:
                if _is_simple_identifier(cond_expr):
                    # 简单标识符: sel -> !sel
                    neg_cond = "!" + cond
                elif _is_simple_negation(cond_expr):
                    # 简单取反: !rst_n -> !!rst_n
                    neg_cond = "!" + cond
                else:
                    # 复杂表达式需要括号: valid && sel -> !(valid && sel)
                    neg_cond = "!(" + cond + ")"
            else:
                neg_cond = ""

            parent_cond = self.current_ctx.get("condition", "")
            parent_cond_expr = self.current_ctx.get("_parent_cond_expr", None)
            if parent_cond:
                # 根据parent条件的语义结构决定是否需要括号
                # 简单条件（标识符、简单取反）直接加!，复杂条件需要括号
                if parent_cond_expr and self._is_simple_expr_for_negation(parent_cond_expr):
                    neg_parent = "!" + parent_cond
                else:
                    neg_parent = "!(" + parent_cond + ")"
                if neg_parent and neg_cond:
                    new_cond = neg_parent + " && " + neg_cond
                elif neg_parent:
                    new_cond = neg_parent
                else:
                    new_cond = neg_cond
            else:
                new_cond = neg_cond
            # [NEW] else 分支的条件是取反的，不加入 _cond_exprs（只记录 TRUE 路径的条件）
            new_ctx = {
                **self.current_ctx,
                "condition": new_cond,
                "_parent_cond_expr": cond_expr,
                # _cond_exprs 保持不变（else 分支是取反后的条件）
            }
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
                        expr = getattr(cond, "expr", None)
                        if expr:
                            syn = getattr(expr, "syntax", None)
                            if syn:
                                exprs.append(self._safe_str(syn))
                            else:
                                # Try to extract from semantic AST
                                expr_str = self._expr_to_string(expr)
                                if expr_str:
                                    exprs.append(expr_str)
                    return " && ".join(exprs) if exprs else self._safe_str(p)
                return self._safe_str(cs)
            return self._safe_str(p)

        # Semantic AST: conditions directly
        cs = getattr(n, "conditions", None)
        if cs:
            exprs = []
            for cond in cs:
                expr = getattr(cond, "expr", None)
                if expr:
                    expr_str = self._expr_to_string(expr)
                    if expr_str:
                        exprs.append(expr_str)
                    else:
                        exprs.append(self._safe_str(expr))
            return " && ".join(exprs) if exprs else ""

        return ""

    def _expr_to_string(self, expr) -> str:
        """将表达式转换为可读字符串

        优先使用 syntax 属性，其次尝试提取符号名
        """
        if expr is None:
            return ""

        # 优先使用 syntax (语法树)
        syn = getattr(expr, "syntax", None)
        if syn:
            try:
                s = self._safe_str(syn).strip()
                if s:
                    return s
            except (UnicodeDecodeError, TypeError):
                pass

        # LiteralExpressionSyntax: 提取字面量值
        # 例如 case (sel) 0: 中的 0, 1
        if hasattr(expr, "kind"):
            kind_name = expr.kind.name if hasattr(expr.kind, "name") else str(expr.kind)
            if "Literal" in kind_name:
                # 直接返回 expr 本身（LiteralExpressionSyntax 重载了 __str__）
                result = self._safe_str(expr).strip()
                if result:
                    return result
                # 尝试 literal 属性
                literal = getattr(expr, "literal", None)
                if literal:
                    return str(literal).strip()
                return ""

        # IntegerVectorExpressionSyntax: 提取进制数字如 2'b00
        # case (sel) 2'b00: 中的 2'b00
        if hasattr(expr, "kind"):
            kind_name = expr.kind.name if hasattr(expr.kind, "name") else str(expr.kind)
            if "IntegerVector" in kind_name:
                # 提取 size, base, value (都是 Token)
                size_tok = getattr(expr, "size", None)
                base_tok = getattr(expr, "base", None)
                value_tok = getattr(expr, "value", None)
                # 格式: size'bvalue, 例如 2'b00
                if size_tok is not None and base_tok is not None and value_tok is not None:
                    size_str = self._safe_str(size_tok).strip()
                    base_str = self._safe_str(base_tok).strip()
                    value_str = self._safe_str(value_tok).strip()
                    return f"{size_str}{base_str}{value_str}"
                # 直接返回 expr 本身
                result = self._safe_str(expr).strip()
                if result:
                    return result

        # UnaryOp: 提取操作数和操作符
        if hasattr(expr, "kind") and "UnaryOp" in str(expr.kind):
            op = getattr(expr, "op", None) or getattr(expr, "operator", None)
            operand = getattr(expr, "operand", None)
            if operand:
                operand_str = self._expr_to_string(operand)
                if operand_str:
                    # 将 UnaryOperator 枚举转换为标准符号
                    if hasattr(op, "name"):
                        op_name = op.name
                        if "Not" in op_name:
                            return f"!{operand_str}"
                        elif "Neg" in op_name:
                            return f"-{operand_str}"
                        elif "Pos" in op_name:
                            return f"+{operand_str}"
                    elif op:
                        op_str = str(op).strip()
                        if "Not" in op_str:
                            return f"!{operand_str}"
                        else:
                            return f"{op_str}{operand_str}"
                    return f"{operand_str}"
            return ""

        # NamedValueExpression: 提取符号名
        if hasattr(expr, "symbol"):
            sym = getattr(expr, "symbol", None)
            if sym:
                # 安全访问 .name (pyslang property 访问会触发 utf-8 解码)
                try:
                    name = sym.name
                except (UnicodeDecodeError, TypeError, Exception):
                    return "<id:non-utf8>"
                if name:
                    try:
                        return self._safe_str(name).strip()
                    except (UnicodeDecodeError, TypeError):
                        return "<id:non-utf8>"

        # IdentifierNameSyntax: 语法树节点 (嵌套 case 中的 selector)
        # 例如: case(valid) 中 valid 是 IdentifierNameSyntax，不是 NamedValueExpression
        kind = getattr(expr, "kind", None)
        if kind:
            kind_name = kind.name if hasattr(kind, "name") else str(kind)
            if "IdentifierName" in kind_name:
                return self._safe_str(expr).strip()

        # BinaryExpression: 递归处理左右操作数
        if hasattr(expr, "left") and hasattr(expr, "right"):
            left = self._expr_to_string(getattr(expr, "left", None))
            right = self._expr_to_string(getattr(expr, "right", None))
            op = getattr(expr, "op", None) or getattr(expr, "operator", None)
            if op:
                if hasattr(op, "name"):
                    op_name = op.name
                    # [FIX] 将操作符名称转换为标准符号
                    op_map = {
                        "Equality": "==",
                        "Inequality": "!=",
                        "LessThan": "<",
                        "LessEqual": "<=",
                        "GreaterThan": ">",
                        "GreaterEqual": ">=",
                        "LogicalAnd": "&&",
                        "LogicalOr": "||",
                        "BinaryAnd": "&",
                        "BinaryOr": "|",
                        "BinaryXor": "^",
                        "BinaryXnor": "~^",
                        "Add": "+",
                        "Subtract": "-",
                        "Multiply": "*",
                        "Divide": "/",
                        "Mod": "%",
                        "LogicalNot": "!",
                        "BitwiseNot": "~",
                        "Concat": "{}",
                    }
                    op_str = op_map.get(op_name, f" {op_name.lower().replace('_', ' ')} ")
                else:
                    op_str = f" {str(op).strip()} "
            else:
                op_str = " "
            return f"{left}{op_str}{right}"

        return ""

    def visit_else_clause(self, node):
        """ElseClause: else 分支

        进入 clause
        """
        self._add_statement(node, item_type=ItemType.CONDITIONAL)
        s = getattr(node, "clause", None)
        if s:
            self.visit(s)

    # =========================================================================
    # [P1] 表达式语句和赋值
    # =========================================================================

    def visit_expression_statement(self, node):
        """ExpressionStatement: 表达式语句

        对于语义 AST 节点，进入 expr；对于语法 AST 节点，只添加自身
        """
        self._add_statement(node, item_type=ItemType.STATEMENT)
        # 对于语义 AST 节点，递归进入 expr
        # 对于语法 AST 节点（ExpressionStatementSyntax），不递归
        kind = getattr(node, "kind", None)
        if kind is not None and hasattr(kind, "name") and "Syntax" not in str(kind):
            e = getattr(node, "expr", None)
            if e:
                self.visit(e)

    def visit_assignment(self, node):
        """Assignment: 赋值语句 (=, <=)

        收集赋值节点
        """
        self._add_statement(node, item_type=ItemType.ASSIGNMENT)

    def visit_invocation(self, node):
        """InvocationExpression: 函数/任务调用

        收集调用节点
        """
        self._add_statement(node, item_type=ItemType.INVOCATION)

    def visit_continuous_assignment(self, node):
        """assign 连续赋值"""
        self._add_statement(node, item_type=ItemType.LOOP)

    # =========================================================================
    # [P2] 循环语句
    # =========================================================================

    def visit_loop_statement(self, node):
        """LoopStatement: while/for/repeat

        进入 body/statement
        """
        self._add_statement(node, item_type=ItemType.BLOCK)
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

    # =========================================================================
    # [P2] 其他语句类型
    # =========================================================================

    def visit_nonblocking_assignment(self, node):
        """<= 非阻塞赋值"""
        self._add_statement(node, item_type=ItemType.BLOCK)

    def visit_blocking_assignment(self, node):
        """= 阻塞赋值"""
        self._add_statement(node, item_type=ItemType.JUMP)

    def visit_jump_statement(self, node):
        """JumpStatement: return/break/continue"""
        self._add_statement(node, item_type=ItemType.DISABLE)

    def visit_wait_statement(self, node):
        """WaitStatement: wait(condition)"""
        self._add_statement(node, item_type=ItemType.STATEMENT)
        self.generic_visit(node)

    def visit_event_control(self, node):
        """EventControl: @clk"""
        self._add_statement(node, item_type=ItemType.STATEMENT)
        stmt = getattr(node, "statement", None)
        if stmt:
            self.visit(stmt)

    def visit_disable_statement(self, node):
        """DisableStatement: disable name"""
        self._add_statement(node, item_type=ItemType.STATEMENT)

    def visit_procedural_timing_control(self, node):
        """ProceduralTimingControl: #delay"""
        self._add_statement(node, item_type=ItemType.STATEMENT)
        self.generic_visit(node)
