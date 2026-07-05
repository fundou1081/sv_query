# statement_collector_visitor.py -      Visitor (       )
"""
[  15] Visitor   
[  26]      Visitor   ,   if-elif  

  :
1.              (clock_domain, condition)
2.    always_ff/always_comb/always_latch/initial     
3.    case/if/while/for      
4.          

   graph_builder.py   :
- _collect_stmts_with_context()
"""

import logging
from enum import Enum, auto
from typing import Any

from .base_visitor import BaseVisitor

logger = logging.getLogger(__name__)


class ItemType(Enum):
    """      

    [  27]           ,        
    """

    STATEMENT = auto()  #     
    ASSIGNMENT = auto()  #      (=, <=)
    INVOCATION = auto()  #   /    
    TIMING_CONTROL = auto()  #      (@, #)
    CONDITIONAL = auto()  #      (if/else)
    CASE = auto()  # case   
    LOOP = auto()  # for/while   
    BLOCK = auto()  # begin...end  
    JUMP = auto()  # return/break/continue
    DISABLE = auto()  # disable

    WAIT_FORK = auto()  # wait fork
    WAIT_ORDER = auto()  # wait order
    RAND_CASE = auto()  # rand case
    RAND_SEQUENCE = auto()  # rand sequence
    VARIABLE_DECLARATION = auto()  #     
    EVENT_TRIGGER = auto()  #     
    IMMEDIATE_ASSERTION = auto()  #     
    CONCURRENT_ASSERTION = auto()  #     
    PROCEDURAL_ASSIGN = auto()  # force   
    PROCEDURAL_DEASSIGN = auto()  # release   
    DISABLE_FORK = auto()  # disable fork


class StatementCollectorVisitor(BaseVisitor):
    """     Visitor -        

           AST,              .
           :
    - clock:     (   always_ff   @(posedge clk))
    - condition:    (   if/case      )
    - reset:      (   @(posedge clk or negedge rst))

        :
        visitor = StatementCollectorVisitor(adapter)
        statements = visitor.collect(node)  # [(node, ctx), ...]
    """

    def __init__(self, adapter):
        """   

        Args:
            adapter: PyslangAdapter   ,      ,     
        """
        super().__init__()
        self.adapter = adapter
        self._statements: list[tuple[Any, dict[str, str]]] = []
        self._ctx_stack: list[dict[str, str]] = [{}]
        self._visited: set[int] = set()

    @staticmethod
    def _safe_str(obj) -> str:
        """    str()   ,    utf-8    (e.g. escape   )

        pyslang   Token/Syntax     str()      utf-8   ,
              ASCII     escape    (e.g. \\x80)    UnicodeDecodeError.
                hex   ,        trace   .
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
        """       """
        return self._ctx_stack[-1] if self._ctx_stack else {}
    def _is_simple_expr_for_negation(self, expr) -> bool:
        """            (      ,     )

            :
        -       (NamedValue/Identifier/Reference)
        -      (!identifier)

            (    ):
        -      (valid && sel)
        -      (!(!rst_n))
        -        
        """
        if expr is None:
            return True  #         

        kind = getattr(expr, "kind", None)
        if not kind:
            return True
        kind_name = kind.name if hasattr(kind, "name") else str(kind)

        #      
        if kind_name in ("NamedValue", "Identifier", "Reference"):
            return True

        # UnaryOp:          !identifier
        if "UnaryOp" in kind_name:
            op = getattr(expr, "op", None)
            if not op or "Not" not in (op.name if hasattr(op, "name") else str(op)):
                return False  #    !    
            operand = getattr(expr, "operand", None)
            if operand:
                operand_kind = getattr(operand, "kind", None)
                if operand_kind:
                    operand_name = operand_kind.name if hasattr(operand_kind, "name") else str(operand_kind)
                    #    !identifier     
                    return operand_name in ("NamedValue", "Identifier", "Reference")
            return False

        # BinaryOp       
        return False

    def _is_reset_condition(self, expr) -> bool:
        """         reset   

        Reset   :UnaryOp(!rst_n)   operand   NamedValue/Identifier       rst/reset
        """
        if expr is None:
            return False

        kind = getattr(expr, "kind", None)
        if not kind:
            return False
        kind_name = kind.name if hasattr(kind, "name") else str(kind)

        # UnaryOp:      !rst   !reset
        if "UnaryOp" in kind_name:
            op = getattr(expr, "op", None)
            if not op or "Not" not in (op.name if hasattr(op, "name") else str(op)):
                return False
            operand = getattr(expr, "operand", None)
            if operand:
                #    operand    
                if hasattr(operand, "name"):
                    name = operand.name
                elif hasattr(operand, "text"):
                    name = operand.text
                else:
                    name = str(operand)
                #          rst/reset
                name_lower = name.lower() if isinstance(name, str) else ""
                return "rst" in name_lower or "reset" in name_lower
        return False

    def _compute_effective_condition(self, cond_exprs: list) -> str:
        """    AST       effective_condition

          :   reset   (  !rst_n),        reset         

           case item,    case item  (  REQ),            
        """
        #         reset     
        last_expr = None
        for expr in reversed(cond_exprs):
            if not self._is_reset_condition(expr):
                last_expr = expr
                break

        if last_expr is None:
            return ""

        #    last_expr   kind
        kind = getattr(last_expr, "kind", None)
        kind_name = kind.name if hasattr(kind, "name") else str(kind) if kind else ""

        #    last_expr     case item  (  NamedValue REQ),
        #           :selector == value
        if kind_name in ("NamedValue", "Identifier", "Reference", "IdentifierName"):
            #    case selector(      )
            selector = self.current_ctx.get("_case_selector", "")
            if selector:
                #   case item           
                # last_expr       case item   
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
        """         

        Args:
            node: AST   
            ctx:      

        Returns:
            List[(node, ctx, item_type)]           
            - node: AST   
            - ctx:      
            - item_type: ItemType     
        """
        self._statements = []
        self._ctx_stack = [ctx.copy() if ctx else {}]
        self._visited = set()

        self.visit(node)

        result = self._statements
        self._statements = []
        return result

    def visit(self, node: object) -> None:
        """       visit   """
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

        #    TokenKind   Trivia
        kind_str = str(kind) if kind else ""
        if ".TokenKind." in kind_str or "Trivia" in kind_str:
            return

        # [FIX] StatementKind      (Semantic AST naming -> visitor methods)
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

        # [  26]         (PascalCase -> snake_case   )
        if kind_name:
            import re

            # PascalCase -> snake_case: "Assignment" -> "visit_assignment"
            # But "ExpressionStatement" -> "expression_statement" (insert underscore before capitals)
            snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", kind_name).lower()
            method_name = f"visit_{snake_name}"
            if hasattr(self, method_name):
                getattr(self, method_name)(node)
                return

            # [FIX]    SyntaxKind.XXXExpression -> visit_XXX    
            # e.g., "NonblockingAssignmentExpression" -> "visit_nonblocking_assignment"
            if kind_name.endswith("Expression"):
                base_name = kind_name[:-10]  # Strip 'Expression'
                base_snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base_name).lower()
                method_name = f"visit_{base_snake}"
                if hasattr(self, method_name):
                    getattr(self, method_name)(node)
                    return

            # [FIX] SymbolKind      (ProceduralBlock -> procedure_block)
            symbol_alias_map = {
                "ProceduralBlock": "procedure_block",
            }
            if kind_name in symbol_alias_map:
                alias = symbol_alias_map[kind_name]
                method_name = f"visit_{alias}"
                if hasattr(self, method_name):
                    getattr(self, method_name)(node)
                    return
            #       
            if kind_name in semantic_alias_map:
                alias = semantic_alias_map[kind_name]
                method_name = f"visit_{alias}"
                if hasattr(self, method_name):
                    getattr(self, method_name)(node)
                    return

        #   :        
        self.generic_visit(node)

    def generic_visit(self, node: object) -> None:
        """    :     """
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
        """         

        Args:
            node: AST   
            ctx:       (     current_ctx)
            item_type:        (ItemType   )
        """
        if node is None:
            return

        effective_ctx = ctx.copy() if ctx else self.current_ctx.copy()
        self._statements.append((node, effective_ctx, item_type))

    def visit_empty_statement(self, node: object) -> None:
        """EmptyStatement:     ;   begin end

               
        """
        pass

    def visit_variable_declaration(self, node: object) -> None:
        """VariableDeclaration:      logic [7:0] data;

              
        """
        self._add_statement(node, item_type=ItemType.VARIABLE_DECLARATION)

    def visit_invalid_statement(self, node: object) -> None:
        """Invalid:   /    AST   

             
        """
        pass

    def visit_event_trigger(self, node: object) -> None:
        """EventTrigger: -> event_name

              
        """
        self._add_statement(node, item_type=ItemType.EVENT_TRIGGER)

    def visit_immediate_assertion(self, node: object) -> None:
        """ImmediateAssertion: assert    

              
        """
        self._add_statement(node, item_type=ItemType.IMMEDIATE_ASSERTION)

    def visit_concurrent_assertion(self, node: object) -> None:
        """ConcurrentAssertion: assert property(...), assume property(...)

              
        """
        self._add_statement(node, item_type=ItemType.CONCURRENT_ASSERTION)

    def visit_procedural_assign(self, node: object) -> None:
        """ProceduralAssign: force assignment

           force   
        """
        self._add_statement(node, item_type=ItemType.PROCEDURAL_ASSIGN)

    def visit_procedural_deassign(self, node: object) -> None:
        """ProceduralDeassign: release assignment

           release   
        """
        self._add_statement(node, item_type=ItemType.PROCEDURAL_DEASSIGN)

    def visit_procedural_checker(self, node: object) -> None:
        """ProceduralChecker: checker declaration

           checker
        """
        pass  #        

    def visit_disable_fork(self, node: object) -> None:
        """DisableFork: disable fork

           disable fork
        """
        self._add_statement(node, item_type=ItemType.DISABLE_FORK)

    def visit_wait_fork(self, node: object) -> None:
        """WaitFork: wait fork

           wait fork
        """
        self._add_statement(node, item_type=ItemType.WAIT_FORK)

    def visit_wait_order(self, node: object) -> None:
        """WaitOrder: wait order(...)

           wait order
        """
        self._add_statement(node, item_type=ItemType.WAIT_ORDER)

    def visit_rand_case(self, node: object) -> None:
        """RandCase: rand case

           rand case
        """
        self._add_statement(node, item_type=ItemType.RAND_CASE)

    def visit_rand_sequence(self, node: object) -> None:
        """RandSequence: rand sequence

           rand sequence
        """
        self._add_statement(node, item_type=ItemType.RAND_SEQUENCE)

    def visit_pattern_case(self, node: object) -> None:
        """PatternCase: pattern case item

              case   
        """
        self.generic_visit(node)

    def visit_list(self, node: object) -> None:
        """List:     

            
        """
        self.generic_visit(node)

    # =========================================================================
    # [P1]     - always_ff / always_comb / always_latch / initial
    # =========================================================================

    def visit_initial_block(self, node: object) -> None:
        """InitialBlock: initial  

        initial       ,    
        """
        self._add_statement(node, item_type=ItemType.ASSIGNMENT)
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

    def visit_procedure_block(self, node: object) -> None:
        """AlwaysFF / AlwaysComb / AlwaysLatch      

           procedureKind        
        """
        # [FIX] Semantic symbol   procedureKind   ,   kind
        # kind   SymbolKind.ProceduralBlock,procedureKind   ProceduralBlockKind.AlwaysFF
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
            # Verilog always @(posedge clk) -   always_ff   
            self.visit_always_ff(node)
        else:
            self.generic_visit(node)

    def visit_always_ff(self, node: object) -> None:
        """AlwaysFF: always_ff @(posedge clk) ... end

                 
        """
        # [FIX 2026-06-26] pyslang mutex lock failed in partial elaboration
        try:
            clock = self._extract_clock(node)
            reset = self._extract_reset(node)
            new_ctx = {"clock": clock, "reset": reset, "condition": ""}
            self._ctx_stack.append(new_ctx)
            stmt = getattr(node, "statement", None) or getattr(node, "body", None)
            if stmt:
                self.visit(stmt)
            self._ctx_stack.pop()
        except RuntimeError as e:
            if "mutex" in str(e).lower():
                # graceful degrade: pop ctx, skip node
                if self._ctx_stack and self._ctx_stack[-1].get("clock", "") == "":
                    # only pop if we pushed (heuristic)
                    pass
                return
            raise

    def visit_always_comb(self, node: object) -> None:
        """AlwaysComb: always_comb ... end

            ,    
        """
        #        (   )
        new_ctx = {"clock": "", "reset": "", "condition": ""}
        self._ctx_stack.append(new_ctx)

        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

        self._ctx_stack.pop()

    def visit_always_latch(self, node: object) -> None:
        """AlwaysLatch: always_latch ... end

            ,   
        """
        #   always_comb   
        new_ctx = {"clock": "", "reset": "", "condition": ""}
        self._ctx_stack.append(new_ctx)

        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

        self._ctx_stack.pop()

    def _extract_clock(self, node) -> str:
        """  always_ff       """
        # [FIX 2026-06-26] pyslang mutex lock failed in partial elaboration
        try:
            stmt = getattr(node, "statement", None) or getattr(node, "body", None)
            if not stmt:
                return ""
            tc = getattr(stmt, "timing", None) or getattr(stmt, "timingControl", None)
            if tc:
                return self._extract_clock_from_event_ctrl(tc)
            return ""
        except RuntimeError as e:
            if "mutex" in str(e).lower():
                return ""
            raise

    def _extract_clock_from_event_ctrl(self, n) -> str:
        """  TimingControl     """
        # EventList   events
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

        def find_clock(expr: object) -> str:
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
        """  always_ff       """
        # [FIX 2026-06-26] pyslang mutex lock failed in partial elaboration
        try:
            stmt = getattr(node, "statement", None) or getattr(node, "body", None)
            if not stmt:
                return ""
            tc = getattr(stmt, "timing", None) or getattr(stmt, "timingControl", None)
            if not tc:
                return ""
            if hasattr(tc, "events"):
                for evt in tc.events:
                    reset = self._extract_reset_from_event(evt)
                    if reset:
                        return reset
            return ""
        except RuntimeError as e:
            if "mutex" in str(e).lower():
                return ""
            raise

    def _extract_reset_from_event(self, n) -> str:
        """  Event       

          :
        - negedge        'rst'/'reset' ->     
        - posedge        'rst'/'reset' ->      (    )
        -       ->     (     )
        """
        e = getattr(n, "expr", None)
        if not e:
            return ""

        e = getattr(e, "expr", None) or e

        #               
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

        #       
        edge_str = str(getattr(n, "edge", ""))
        is_negedge = "negedge" in edge_str.lower() or "NegEdge" in edge_str
        is_posedge = "posedge" in edge_str.lower() or "PosEdge" in edge_str

        #         ,     negedge   posedge,     
        if is_reset_signal and (is_negedge or is_posedge):
            return signal_name

        return ""

    # =========================================================================
    # [P1]     
    # =========================================================================

    def visit_timing_control(self, node: object) -> None:
        """TimingControl: @posedge clk  

            ,   statement
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

    def visit_Timed(self, node: object) -> None:
        """Timed: TimedStatement      

            visit_timed_statement
        """
        #      ,      timed_statement   
        self.visit_timed_statement(node)

    def visit_timed_statement(self, node: object) -> None:
        """TimedStatement: always @(*) wraps content

           stmt
        """
        self._add_statement(node, item_type=ItemType.TIMING_CONTROL)
        stmt = getattr(node, "stmt", None)
        if stmt:
            self.visit(stmt)

    # =========================================================================
    # [P1]    
    # =========================================================================

    def visit_block_statement(self, node: object) -> None:
        """BlockStatement: begin...end  

           body
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
    # [P1]     
    # =========================================================================

    def visit_sequential_block(self, node: object) -> None:
        """begin...end  """
        self._add_statement(node, item_type=ItemType.BLOCK)
        self.generic_visit(node)

    def visit_case_statement(self, node: object) -> None:
        """CaseStatement: case/endcase

              ,       
        """
        self._add_statement(node, item_type=ItemType.CASE)

        #    case selector (     )
        selector = self._get_case_selector(node)

        # [FIX]    case selector     ,  _compute_effective_condition   
        #       selector,     
        self.current_ctx.get("_case_selector", "")
        self.current_ctx["_case_selector"] = selector

        #    items
        items = getattr(node, "items", [])

        # [FIX]        syntax items    case item   
        #    ItemGroup    case item      (0:, 1:, default:)
        # syntax items   StandardCaseItemSyntax.expressions      
        syntax_items = None
        if hasattr(node, "syntax") and node.syntax and hasattr(node.syntax, "items"):
            syntax_items = node.syntax.items

        #      syntax items(        )
        use_syntax = syntax_items is not None and len(syntax_items) > 0

        process_items = syntax_items if use_syntax else items

        if process_items:
            for item in process_items:
                #    case item     
                item_cond = self._get_case_item_condition(item, selector)

                # [BUG-FIX]         case item   
                #      (  !!rst_n) AND case item    (  state == REQ)
                parent_cond = self.current_ctx.get("condition", "")
                # [NEW]   parent_cond_exprs         AST   
                cond_exprs = list(self.current_ctx.get("_cond_exprs", []))
                #    case item        AST
                item_cond_expr = self._get_case_item_condition_ast(item)
                if item_cond_expr:
                    cond_exprs.append(item_cond_expr)
                if parent_cond:
                    #     : parent_cond && item_cond
                    combined_cond = f"{parent_cond} && {item_cond}"
                    new_ctx = {
                        **self.current_ctx,
                        "condition": combined_cond,
                        "_cond_exprs": cond_exprs,
                        "effective_condition": self._compute_effective_condition(cond_exprs),
                        # [P1 cycle 5] case      condition_ast (V2.A.2 17a   )
                        "condition_ast": item_cond_expr,
                    }
                else:
                    new_ctx = {
                        **self.current_ctx,
                        "condition": item_cond,
                        "_cond_exprs": cond_exprs,
                        "effective_condition": self._compute_effective_condition(cond_exprs),
                        # [P1 cycle 5] case      condition_ast
                        "condition_ast": item_cond_expr,
                    }

                self._ctx_stack.append(new_ctx)

                #    AST: stmt   
                #    AST: clause   
                stmt = getattr(item, "stmt", None) or getattr(item, "clause", None)
                if stmt:
                    self.visit(stmt)

                #      
                self._ctx_stack.pop()

    def _get_case_selector(self, node) -> str:
        """   case     selector       

        Returns:
            selector    ,  "sel"
        """
        #      AST: stmt.expr
        expr = getattr(node, "expr", None)
        if expr:
            sel_str = self._expr_to_string(expr)
            if sel_str:
                return sel_str

        #      AST: syntax.expr
        syntax = getattr(node, "syntax", None)
        if syntax:
            expr = getattr(syntax, "expr", None)
            if expr:
                return self._safe_str(expr).strip()

        return "?"

    def _get_case_item_condition(self, item, selector: str) -> str:
        """   case item     

        Args:
            item: case item   
            selector: case selector       

        Returns:
                 ,  "sel == 0"   "sel == default"
        """
        #       default case
        item_kind = getattr(item, "kind", None)
        item_kind_name = item_kind.name if hasattr(item_kind, "name") else str(item_kind)

        if "Default" in item_kind_name:
            return f"{selector} == default"

        # StandardCaseItem:   expressions      
        expressions = getattr(item, "expressions", None)
        if expressions:
            # expressions        ,   
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
        """   case item        AST

             _cond_exprs   

        Args:
            item: case item   

        Returns:
                  AST     None
        """
        #       default case
        item_kind = getattr(item, "kind", None)
        item_kind_name = item_kind.name if hasattr(item_kind, "name") else str(item_kind)

        if "Default" in item_kind_name:
            return None  # default        

        # StandardCaseItem:   expressions      AST
        expressions = getattr(item, "expressions", None)
        if expressions:
            if hasattr(expressions, "__iter__") and not isinstance(expressions, str):
                #      ,     (   case     )
                for expr in expressions:
                    return expr
            else:
                return expressions
        return None

    def visit_case(self, node: object) -> None:
        """case / casex / casez"""
        self.visit_case_statement(node)

    def visit_if(self, node: object) -> None:
        """if-else   """
        self.visit_conditional_statement(node)

    def visit_conditional_statement(self, node: object) -> None:
        """ConditionalStatement: if/else

        [REFACTOR 2026-07-05 v6] 源头方案最终版:
        走 pyslang syntax 树, 用 safe_str() 拿规范化字符串.
        维护 _path_neg_conj (else path 累积的 NOT cond list), 不用 _path_conj.

        关键 insight: ctx.cond 是 else 分支 push 的 neg path (joined with &&),
        inner if 进入时 read ctx.cond (NOT _path_conj):
        - if-true: ctx.cond + " && " + this_cond (累加)
        - if-false: 累加 this_cond 到 neg list, push joined neg list as new ctx.cond

        3 else-if 链 sel_a -> sel_b -> sel_c else:
        - in_a: sel_a
        - in_b: !sel_a && sel_b (外 else push "!sel_a", 内 TRUE 拼 " && sel_b")
        - in_c: !sel_a && !sel_b && sel_c (外 else "!sel_a", 内 else "!sel_a && !sel_b", innermost TRUE " && sel_c")
        - in_d (simple else): !sel_a && !sel_b && !sel_c
        """
        cond_expr = self._extract_cond_expr(node)
        cond = self._extract_condition(node)

        # 读 ctx.cond (else 分支 push 的 neg path) 和 _path_neg_conj (累加 neg list)
        ctx_cond = self.current_ctx.get("condition", "")
        path_neg_conj = list(self.current_ctx.get("_path_neg_conj", []))

        # ifTrue 分支: ctx_cond + " && " + cond (cond 含 || 时加括号)
        ts = getattr(node, "ifTrue", None) or getattr(node, "statement", None)
        if ts:
            cond_for_join = cond
            if cond and "||" in cond and "(" not in cond:
                cond_for_join = f"({cond})"
            if ctx_cond and cond_for_join:
                new_cond_str = ctx_cond + " && " + cond_for_join
            elif cond_for_join:
                new_cond_str = cond_for_join
            else:
                new_cond_str = ctx_cond

            cond_exprs = list(self.current_ctx.get("_cond_exprs", []))
            if cond_expr:
                cond_exprs.append(cond_expr)
            effective_cond = self._compute_effective_condition(cond_exprs)
            new_ctx = {
                **self.current_ctx,
                "condition": new_cond_str,
                "_parent_cond_expr": cond_expr,
                "_cond_exprs": cond_exprs,
                "effective_condition": effective_cond,
                "condition_ast": cond_expr,
            }
            self._ctx_stack.append(new_ctx)
            self.visit(ts)
            self._ctx_stack.pop()

        # ifFalse (else) 分支: 累加 !this_cond 到 path_neg_conj
        # 【v6 fix】!!! typo 防止: cond 是 !X 时, neg 应该 X (去掉 !), 不是 !!X
        # 【v6.2 fix】nested if + 5-way mux 都对:
        #   - path_neg_conj 初始为 [] (outer 没走 else)
        #     - inner else ctx.cond = current_ctx.cond && !cond (累加 outer path)
        #   - path_neg_conj 不为空 (outer 走了 else path)
        #     - inner else ctx.cond = joined_neg (current_ctx.cond 已包含 outer 的 neg)
        # 这区分了 nested if (outer 是 if-true path) 跟 else-if chain (outer 是 else path)
        ec = getattr(node, "ifFalse", None) or getattr(node, "elseClause", None)
        if ec:
            ae = getattr(ec, "clause", None) or ec
            if cond:
                # !this_cond: simple 用 !c, complex 用 !(c), 已经 !X 则 X (去 !)
                if cond.startswith("!"):
                    if cond.startswith("!(") and cond.endswith(")"):
                        neg_this = cond[2:-1]
                    else:
                        neg_this = cond[1:]
                elif "&&" in cond or "||" in cond:
                    neg_this = f"!({cond})"
                else:
                    neg_this = f"!{cond}"
                new_path_neg_conj = path_neg_conj + [neg_this]
                joined_neg = " && ".join(new_path_neg_conj)
                # 区分 nested if (path_neg_conj=[]) 跟 else-if chain (path_neg_conj 不空)
                if path_neg_conj:
                    # outer 走了 else path, current_ctx.cond 已包含 outer 的 neg
                    new_ctx_cond = joined_neg
                else:
                    # outer 走 if-true path, ctx.cond 应该累加 outer if-true path
                    if ctx_cond:
                        new_ctx_cond = f"{ctx_cond} && {neg_this}"
                    else:
                        new_ctx_cond = neg_this
                else_ctx = {**self.current_ctx, "condition": new_ctx_cond, "_path_neg_conj": new_path_neg_conj}
                self._visited.discard(id(ae))
                self._ctx_stack.append(else_ctx)
                if "ConditionalStatement" in type(ae).__name__:
                    self.visit_conditional_statement(ae)
                else:
                    self.visit(ae)
                self._ctx_stack.pop()
            else:
                self.visit(ae)


    def _extract_cond_expr(self, n):
        """Extract condition expression AST node."""
        if hasattr(n, "conditions") and n.conditions:
            # Semantic AST
            return n.conditions[0].expr if len(n.conditions) > 0 else None
        elif hasattr(n, "predicate") and n.predicate:
            # Syntax AST
            pred = n.predicate
            if hasattr(pred, "conditions") and pred.conditions:
                return pred.conditions[0].expr if len(pred.conditions) > 0 else None
        return None

    def _extract_condition(self, n) -> str:
        """  if          """
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
        """            

        Use syntax attr first
        """
        if expr is None:
            return ""

        #      syntax (   )
        syn = getattr(expr, "syntax", None)
        if syn:
            try:
                s = self._safe_str(syn).strip()
                if s:
                    return s
            except (UnicodeDecodeError, TypeError):
                pass

        # LiteralExpressionSyntax:       
        #    case (sel) 0:    0, 1
        if hasattr(expr, "kind"):
            kind_name = expr.kind.name if hasattr(expr.kind, "name") else str(expr.kind)
            if "Literal" in kind_name:
                #      expr   (LiteralExpressionSyntax     __str__)
                result = self._safe_str(expr).strip()
                if result:
                    return result
                #    literal   
                literal = getattr(expr, "literal", None)
                if literal:
                    return str(literal).strip()
                return ""

        # IntegerVectorExpressionSyntax:         2'b00
        # case (sel) 2'b00:    2'b00
        if hasattr(expr, "kind"):
            kind_name = expr.kind.name if hasattr(expr.kind, "name") else str(expr.kind)
            if "IntegerVector" in kind_name:
                #    size, base, value (   Token)
                size_tok = getattr(expr, "size", None)
                base_tok = getattr(expr, "base", None)
                value_tok = getattr(expr, "value", None)
                #   : size'bvalue,    2'b00
                if size_tok is not None and base_tok is not None and value_tok is not None:
                    size_str = self._safe_str(size_tok).strip()
                    base_str = self._safe_str(base_tok).strip()
                    value_str = self._safe_str(value_tok).strip()
                    return f"{size_str}{base_str}{value_str}"
                #      expr   
                result = self._safe_str(expr).strip()
                if result:
                    return result

        # UnaryOp:          
        if hasattr(expr, "kind") and "UnaryOp" in str(expr.kind):
            op = getattr(expr, "op", None) or getattr(expr, "operator", None)
            operand = getattr(expr, "operand", None)
            if operand:
                operand_str = self._expr_to_string(operand)
                if operand_str:
                    #   UnaryOperator          
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

        # NamedValueExpression:      
        if hasattr(expr, "symbol"):
            sym = getattr(expr, "symbol", None)
            if sym:
                #      .name (pyslang property       utf-8   )
                try:
                    name = sym.name
                except (UnicodeDecodeError, TypeError, Exception):
                    return "<id:non-utf8>"
                if name:
                    try:
                        return self._safe_str(name).strip()
                    except (UnicodeDecodeError, TypeError):
                        return "<id:non-utf8>"

        # IdentifierNameSyntax:       (   case    selector)
        #   : case(valid)   valid   IdentifierNameSyntax,   NamedValueExpression
        kind = getattr(expr, "kind", None)
        if kind:
            kind_name = kind.name if hasattr(kind, "name") else str(kind)
            if "IdentifierName" in kind_name:
                return self._safe_str(expr).strip()

        # BinaryExpression:          
        if hasattr(expr, "left") and hasattr(expr, "right"):
            left = self._expr_to_string(getattr(expr, "left", None))
            right = self._expr_to_string(getattr(expr, "right", None))
            op = getattr(expr, "op", None) or getattr(expr, "operator", None)
            if op:
                if hasattr(op, "name"):
                    op_name = op.name
                    # [FIX]              
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

    def visit_else_clause(self, node: object) -> None:
        """ElseClause: else   

           clause
        """
        self._add_statement(node, item_type=ItemType.CONDITIONAL)
        s = getattr(node, "clause", None)
        if s:
            self.visit(s)

    # =========================================================================
    # [P1]         
    # =========================================================================

    def visit_expression_statement(self, node: object) -> None:
        """ExpressionStatement:      

             AST   ,   expr;     AST   ,     
        """
        self._add_statement(node, item_type=ItemType.STATEMENT)
        #      AST   ,     expr
        #      AST   (ExpressionStatementSyntax),   
        kind = getattr(node, "kind", None)
        if kind is not None and hasattr(kind, "name") and "Syntax" not in str(kind):
            e = getattr(node, "expr", None)
            if e:
                self.visit(e)

    def visit_assignment(self, node: object) -> None:
        """Assignment:      (=, <=)

              
        """
        self._add_statement(node, item_type=ItemType.ASSIGNMENT)

    def visit_invocation(self, node: object) -> None:
        """InvocationExpression:   /    

              
        """
        self._add_statement(node, item_type=ItemType.INVOCATION)

    def visit_continuous_assignment(self, node: object) -> None:
        """assign     """
        self._add_statement(node, item_type=ItemType.LOOP)

    # =========================================================================
    # [P2]     
    # =========================================================================

    def visit_loop_statement(self, node: object) -> None:
        """LoopStatement: while/for/repeat

           body/statement
        """
        self._add_statement(node, item_type=ItemType.BLOCK)
        stmt = getattr(node, "statement", None) or getattr(node, "body", None)
        if stmt:
            self.visit(stmt)

    # =========================================================================
    # [P2]       
    # =========================================================================

    def visit_nonblocking_assignment(self, node: object) -> None:
        """<=      """
        self._add_statement(node, item_type=ItemType.BLOCK)

    def visit_blocking_assignment(self, node: object) -> None:
        """=     """
        self._add_statement(node, item_type=ItemType.JUMP)

    def visit_jump_statement(self, node: object) -> None:
        """JumpStatement: return/break/continue"""
        self._add_statement(node, item_type=ItemType.DISABLE)

    def visit_wait_statement(self, node: object) -> None:
        """WaitStatement: wait(condition)"""
        self._add_statement(node, item_type=ItemType.STATEMENT)
        self.generic_visit(node)

    def visit_event_control(self, node: object) -> None:
        """EventControl: @clk"""
        self._add_statement(node, item_type=ItemType.STATEMENT)
        stmt = getattr(node, "statement", None)
        if stmt:
            self.visit(stmt)

    def visit_disable_statement(self, node: object) -> None:
        """DisableStatement: disable name"""
        self._add_statement(node, item_type=ItemType.STATEMENT)

    def visit_procedural_timing_control(self, node: object) -> None:
        """ProceduralTimingControl: #delay"""
        self._add_statement(node, item_type=ItemType.STATEMENT)
        self.generic_visit(node)
