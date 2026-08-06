"""
ExpressionTree — 从 pyslang 语法 AST 递归构建表达式树

pyslang 语法 AST 的表达式表示方式是扁平的 token 三元组:
  BinaryExpression.right = [left, operator, right, operator, ...]
  
例如 `(a * b) + c`:
  right = [ParenthesizedExpression(a*b), Plus, c]
  
ParenthesizedExpression.expression = [a, Star, b]

本模块将这种扁平的 token 序列递归解析为嵌套的 ExprNode 树。

用法:
    from trace.core.graph.viz.expression_tree import ExpressionTree
    
    tree = ExpressionTree.build(assign_node)
    # tree.root → ExprNode
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re as _re

from trace.core._pyslang_compat import SyntaxKind


# ── Constants ──

# Map pyslang operator token kinds to ExprNode op names
_OP_MAP = {
    # arithmetic
    "plus": "Add", "plusequals": "Add",
    "minus": "Subtract", "minusequals": "Subtract",
    "star": "Multiply", "starequals": "Multiply",
    "slash": "Divide", "slashequals": "Divide",
    "percent": "Modulo",
    # bitwise
    "and": "BinaryAnd", "or": "BinaryOr", "xor": "BinaryXor",
    "tilde": "BinaryNot",
    # shift
    "leftshift": "LeftShift", "rightshift": "RightShift",
    "lessless": "LogicalShiftLeft", "greatergreater": "LogicalShiftRight",
    # comparison
    "less": "LessThan", "greater": "GreaterThan",
    "lessthanequals": "LessThanEqual", "greaterthanequals": "GreaterThanEqual",
    "lessequal": "LessThanEqual", "greaterequal": "GreaterThanEqual",
    "doubleequals": "Equality", "exclamationequals": "Inequality",
    # logical
    "doubleand": "LogicalAnd", "doubleor": "LogicalOr",
    # unary
    "exclamation": "UnaryNot", "unaryprefixminus": "UnaryMinus",
    "unaryprefixplus": "UnaryPlus", "unaryprefixtilde": "UnaryNot",
    # ternary
    "question": "Ternary",
}

# Token kind names that are pure numbers or identifiers (not operators)
_IDENT_TYPE = {"Identifier", "IdentifierName", "IntegerLiteral", "RealLiteral",
               "StringLiteral", "TimeLiteral"}


@dataclass
class ExprNode:
    """表达式树节点"""
    op: str              # 操作类型: Add, Multiply, Const, SignalRef, Slice, Concat, Call
    label: str           # 显示标签: +, ×, 8'd128, a, [7:0], {}, add_sat
    children: list['ExprNode'] = field(default_factory=list)
    
    # Optional: width (for typed nodes)
    width: Optional[tuple[int, int]] = None
    
    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    def __repr__(self) -> str:
        if self.children:
            kids = ', '.join(repr(c) for c in self.children)
            return f"{self.op}({self.label} [{kids}])"
        return f"{self.op}({self.label})"


@dataclass  
class ExpressionTree:
    """完整的表达式树，根节点是顶层操作"""
    root: Optional[ExprNode] = None
    
    @staticmethod
    def build(assign_node) -> Optional[ExpressionTree]:
        """从 pyslang AssignmentExpression 节点构建表达式树
        
        assign_node 是 pyslang 的 SyntaxNode (kind=AssignmentExpression),
        有 .left (lhs) 和 .right (rhs token list)
        """
        rhs = getattr(assign_node, 'right', None)
        if rhs is None:
            return None
        
        # rhs is iterable: [left, op, right, op, ...] or single element
        tokens = list(rhs)
        if not tokens:
            return None
        
        root = ExpressionTree._parse_expr(tokens, 0, len(tokens))
        if root is None:
            return None
        return ExpressionTree(root=root)
    
    @staticmethod
    def _parse_expr(tokens: list, start: int, end: int) -> Optional[ExprNode]:
        """递归解析 tokens[start:end] 为 ExprNode 子树
        """
        if start >= end:
            return None
        
        # ── 0. Check for function call: [IdentifierName, ArgumentList] ──
        if end - start == 2:
            first_kind = str(getattr(tokens[start], 'kind', '')).lower()
            
            # Function call: IdentifierName/SystemName/FunctionName + ArgumentList
            is_name = any(k in first_kind for k in ('identifier', 'systemname', 'functionname', 'name'))
            if is_name and 'argumentlist' in str(getattr(tokens[1], 'kind', '')).lower():
                name = str(tokens[start]).strip()
                children = ExpressionTree._parse_arguments(tokens[1])
                return ExprNode(op="Call", label=name, children=children)
            
            # Unary prefix pattern: [operator, operand]
            op_kinds = {'exclamation', 'tilde', 'or', 'and', 'xor',
                        'minus', 'plus', 'unaryprefixminus', 'unaryprefixplus', 'unaryprefixtilde'}
            if any(ok in first_kind for ok in op_kinds):
                operand = ExpressionTree._parse_expr(tokens, start + 1, end)
                op_name = ExpressionTree._kind_to_op(str(getattr(tokens[start], 'kind', '')))
                label = ExpressionTree._kind_to_label(str(getattr(tokens[start], 'kind', '')))
                children = [operand] if operand else []
                # Reduce operators
                if op_name in ('BinaryOr', 'BinaryAnd', 'BinaryXor'):
                    op_name = 'Reduce' + op_name[6:]
                return ExprNode(op=op_name, label=label, children=children)
            
            # Bit select: [IdentifierName, ElementSelect]
            if 'identifier' in first_kind and 'elementselect' in str(getattr(tokens[1], 'kind', '')).lower():
                name = str(tokens[start]).strip()
                sel_text = str(tokens[1]).strip()
                return ExprNode(op="BitSelect", label=f"{name}{sel_text}", children=[
                    ExprNode(op="SignalRef", label=name)
                ])
        
        # ── 1. Check for concatenation (token list starts with OpenBrace) ──
        first_token = tokens[start] if start < end else None
        if first_token is not None and 'OpenBrace' in str(getattr(first_token, 'kind', '')):
            return ExpressionTree._build_concat_from_tokens(tokens, start, end)
        
        # ── 0.5. Check for ternary (ConditionalPredicate at position 0, ? at 1) ──
        if end - start >= 5:
            fkind = str(getattr(tokens[start], 'kind', ''))
            if 'Conditional' in fkind or 'Ternary' in fkind:
                # Find ? and : positions
                q_pos = -1
                c_pos = -1
                for i in range(start, end):
                    k = str(getattr(tokens[i], 'kind', ''))
                    if 'Question' in k:
                        q_pos = i
                    elif 'Colon' in k and q_pos >= 0:
                        c_pos = i
                        break
                if q_pos > start and c_pos > q_pos:
                    cond = ExpressionTree._parse_expr(tokens, start, q_pos)
                    true_val = ExpressionTree._parse_expr(tokens, q_pos + 1, c_pos)
                    false_val = ExpressionTree._parse_expr(tokens, c_pos + 1, end)
                    children = [c for c in [cond, true_val, false_val] if c is not None]
                    return ExprNode(op="Ternary", label="?:", children=children)
        
        # ── 1. If single token, unpack compound or return leaf ──
        if end - start == 1:
            token = tokens[start]
            kind = str(getattr(token, 'kind', ''))
            
            # IntegerVectorExpression / Literal tokens: never iterate, use _leaf directly.
            # (IntegerVectorExpression.__iter__ returns tokens like [8, 'd, 128]
            #  which breaks _parse_expr's operator detection.)
            if 'IntegerVector' in kind or 'VectorLiteral' in kind or 'IntegerLiteral' in kind or 'Literal' in kind:
                return ExpressionTree._leaf(token)
                inner = getattr(token, 'expression', None)
                if inner is not None:
                    inner_tokens = list(inner)
                    if inner_tokens:
                        return ExpressionTree._parse_expr(inner_tokens, 0, len(inner_tokens))
                return None
            
            # IntegerVectorExpression / Literal tokens: never iterate, use _leaf directly.
            # (IntegerVectorExpression.__iter__ returns tokens like [8, 'd, 128]
            #  which breaks _parse_expr's operator detection.)
            if 'IntegerVector' in kind or 'VectorLiteral' in kind or 'IntegerLiteral' in kind:
                return ExpressionTree._leaf(token)
            
            # Parenthesized expression → recurse into .expression
            if 'Parenthesized' in kind:
                inner = getattr(token, 'expression', None)
                if inner is not None:
                    inner_tokens = list(inner)
                    if inner_tokens:
                        return ExpressionTree._parse_expr(inner_tokens, 0, len(inner_tokens))
                return None
            
            # Compound expression node (AddExpression, MultiplyExpression, etc.)
            # These wrap sub-expressions and are iterable via __iter__.
            # Do NOT use .expression — only ParenthesizedExpression has .expression.
            if 'Expression' in kind and kind != 'AssignmentExpression':
                if hasattr(token, '__iter__') and not isinstance(token, str):
                    inner = list(token)
                    if inner:
                        return ExpressionTree._parse_expr(inner, 0, len(inner))
                # Fallback: try .expression for nodes that expose it
                inner_attr = getattr(token, 'expression', None)
                if inner_attr is not None and hasattr(inner_attr, '__iter__') and not isinstance(inner_attr, str):
                    inner_tokens = list(inner_attr)
                    if inner_tokens:
                        return ExpressionTree._parse_expr(inner_tokens, 0, len(inner_tokens))
                return ExpressionTree._leaf(token)
            
            # Concatenation → build from operands
            if 'Concatenation' in kind or 'OpenBrace' in kind:
                return ExpressionTree._build_concat_from_tokens(tokens, start, end)
            
            # Conditional/Ternary → build from condition/left/right
            if 'Conditional' in kind:
                return ExpressionTree._build_ternary(token)
            
            # Leaf
            return ExpressionTree._leaf(token)
        
        # ── 1. Find lowest-precedence operator ──
        # Walk [op0, op1, op2, ...] — every other position starting from 1 is an operator
        best_idx = -1
        best_prec = -1  # higher = lower priority, we want max
        
        for i in range(start + 1, end, 2):
            token = tokens[i]
            kind = str(getattr(token, 'kind', ''))
            prec = ExpressionTree._op_precedence(kind)
            if prec > best_prec:
                best_prec = prec
                best_idx = i
        
        if best_idx < 0 or best_idx <= start or best_idx >= end - 1:
            return ExpressionTree._leaf(tokens[start])
        
        # ── 2. Split at best_idx, recurse ──
        left = ExpressionTree._parse_expr(tokens, start, best_idx)
        right = ExpressionTree._parse_expr(tokens, best_idx + 1, end)
        
        if left is None and right is None:
            return None
        
        op_name = ExpressionTree._kind_to_op(str(getattr(tokens[best_idx], 'kind', '')))
        label = ExpressionTree._kind_to_label(str(getattr(tokens[best_idx], 'kind', '')))
        children = [c for c in [left, right] if c is not None]
        return ExprNode(op=op_name, label=label, children=children)
    
    @staticmethod
    def _build_ternary(node) -> Optional[ExprNode]:
        """Extract the predicate expression from ConditionalPredicate
        
        Structure: ConditionalPredicate → .conditions → [ConditionalPattern]
        ConditionalPattern is iterable → contains the predicate expression tokens
        
        Returns the predicate ExprNode directly (NOT wrapped in Ternary).
        The Ternary wrapper is created at the token level in _parse_expr.
        """
        conditions = getattr(node, 'conditions', None)
        if conditions is not None:
            for cond_node in conditions:
                if hasattr(cond_node, '__iter__') and not isinstance(cond_node, str):
                    cond_tokens = list(cond_node)
                    if cond_tokens:
                        return ExpressionTree._parse_expr(cond_tokens, 0, len(cond_tokens))
        return None
    
    @staticmethod
    def _parse_arguments(arg_list_node) -> list:
        """解析函数调用的参数列表，返回 ExprNode children
        
        ArgumentList 是 iterable: [OpenParenthesis, OrderedArgument, Comma, OrderedArgument, CloseParenthesis]
        每个 OrderedArgument 的 .expression 包含实际表达式 token
        """
        children = []
        try:
            raw = list(arg_list_node)
        except (TypeError, ValueError):
            return children
        
        for item in raw:
            kind = str(getattr(item, 'kind', ''))
            # Skip parens and commas
            if 'OpenParenthesis' in kind or 'CloseParenthesis' in kind or 'Comma' in kind:
                continue
            
            # OrderedArgument → get .expression
            text = str(item).strip()
            if 'OrderedArgument' in kind or 'Argument' in kind:
                expr = getattr(item, 'expression', None)
                if expr is not None:
                    if hasattr(expr, '__iter__') and not isinstance(expr, str):
                        try:
                            tokens = list(expr)
                            if tokens:
                                node = ExpressionTree._parse_expr(tokens, 0, len(tokens))
                                if node:
                                    children.append(node)
                        except (TypeError, ValueError):
                            pass
                    else:
                        leaf = ExpressionTree._leaf(expr)
                        if leaf:
                            children.append(leaf)
                else:
                    # Fallback: try _leaf on item directly
                    leaf = ExpressionTree._leaf(item)
                    if leaf:
                        children.append(leaf)
            else:
                # Direct expression token
                leaf = ExpressionTree._leaf(item)
                if leaf:
                    children.append(leaf)
        
        return children
    
    @staticmethod
    def _build_concat(node) -> ExprNode:
        """Build ExprNode from Concatenation node (has .operands)"""
        ops = getattr(node, 'operands', None) or getattr(node, 'expressions', None) or []
        children = []
        for op in ops:
            if hasattr(op, 'kind'):
                e = ExpressionTree._leaf(op)
                if e:
                    children.append(e)
        return ExprNode(op="Concat", label="{}", children=children)
    
    @staticmethod
    def _build_concat_from_tokens(tokens, start, end) -> ExprNode:
        """Build ExprNode from token-level concatenation: {, a, ,, b, }
        
        pyslang expands concatenations into flat tokens: [OpenBrace, expr, Comma, expr, CloseBrace]
        Skip OpenBrace, Comma, CloseBrace, collect only signal/const expressions.
        """
        children = []
        for i in range(start + 1, end - 1):  # skip { and }
            token = tokens[i]
            kind = str(getattr(token, 'kind', ''))
            if 'Comma' in kind or 'Comma' in str(token):
                continue
            e = ExpressionTree._leaf(token)
            if e:
                children.append(e)
        return ExprNode(op="Concat", label="{}", children=children)
    
    @staticmethod
    def _leaf(token) -> Optional[ExprNode]:
        """将单个 pyslang token 转为 ExprNode 叶子"""
        kind = str(getattr(token, 'kind', ''))
        text = str(token).strip()
        
        # Integer vector literal (e.g. 8'd128) — use source text for original representation
        if 'IntegerVector' in kind or 'VectorLiteral' in kind or 'IntegerLiteral' in kind or 'Literal' in kind:
            # str(token) gives the original text from pyslang
            label = text if text else '?'
            return ExprNode(op="Const", label=label)
        
        # Verilog literal constant
        if _re.match(r"\d+'[bdh]\w+", text):
            return ExprNode(op="Const", label=text)
        
        # Pure number (no base specifier)
        if _re.match(r'^\d+$', text):
            return ExprNode(op="Const", label=text)
        
        # Compound expression node (e.g. AddExpression, MultiplyExpression)
        # These are pyslang's synthesized nodes that wrap sub-expressions.
        # Recurse into their expression list.
        if 'Expression' in kind and kind != 'AssignmentExpression':
            inner = getattr(token, 'expression', None)
            if inner is not None:
                inner_tokens = list(inner) if hasattr(inner, '__iter__') and not isinstance(inner, str) else [inner]
                if inner_tokens:
                    return ExpressionTree._parse_expr(inner_tokens, 0, len(inner_tokens))
            return ExprNode(op="SignalRef", label=text)
        
        # Identifier/signal name
        if 'Identifier' in kind:
            return ExprNode(op="SignalRef", label=text)
        
        # Parenthesized expression — recurse into expression list
        if 'Parenthesized' in kind:
            inner = getattr(token, 'expression', None)
            if inner is not None:
                inner_tokens = list(inner)
                if inner_tokens:
                    return ExpressionTree._parse_expr(inner_tokens, 0, len(inner_tokens))
            return None
        
        # Concatenation
        if 'Concatenation' in kind:
            ops = getattr(token, 'operands', None) or getattr(token, 'expressions', None)
            children = []
            if ops:
                for op in ops:
                    e = ExpressionTree._leaf(op)
                    if e:
                        children.append(e)
            return ExprNode(op="Concat", label="{}", children=children)
        
        # Conditional/ternary — check multiple forms
        if 'Conditional' in kind or 'ConditionalPredicate' in kind:
            return ExpressionTree._build_ternary(token)
        
        # Catch-all: treat as signal or const
        # Check for constant-like text that didn't match Verilog literal pattern
        if text and _re.match(r'^\d+\'[bdh]', text):
            return ExprNode(op="Const", label=text)
        
        # Unknown token — try as signal ref
        return ExprNode(op="SignalRef", label=text)
        
        # Unknown — just return as signal ref
        return ExprNode(op="SignalRef", label=text)
    
    @staticmethod
    def _op_precedence(kind_str: str) -> int:
        """返回操作符优先级（数字越大越先合并/越低优先级）"""
        if not kind_str:
            return -1
        k = kind_str.lower().replace('tokenkind.', '').replace('syntaxkind.', '')
        if 'question' in k:
            return 1
        if 'colon' in k:
            return 1
        if 'doubleor' in k or 'oror' in k:
            return 2
        if 'doubleand' in k or 'andand' in k:
            return 3
        if k == 'or' or k == 'pipe':
            return 4
        if 'xor' in k:
            return 4
        if k == 'tilde':
            return 4  # unary bit-not: highest precedence
        if k == 'and' or k == 'ampersand':
            return 5
        if 'equals' in k or 'exclamation' in k:
            return 6
        if 'less' in k or 'greater' in k:
            return 6
        if 'shift' in k:
            return 7
        if 'plus' in k or 'minus' in k:
            return 8
        if k in ('star', 'slash', 'percent'):
            return 9
        if 'unary' in k:
            return 10
        return -1  # not an operator
    
    @staticmethod
    def _kind_to_op(kind_str: str) -> str:
        """pyslang token kind → ExprNode op name
        Match token kind name to _OP_MAP key.
        Token kinds from pyslang: TokenKind.DoubleAnd, TokenKind.DoubleOr,
        TokenKind.Exclamation, TokenKind.Tilde, TokenKind.Xor, etc.
        """
        lower = kind_str.lower().replace('tokenkind.', '').replace('syntaxkind.', '')
        if lower in _OP_MAP:
            return _OP_MAP[lower]
        for key, val in _OP_MAP.items():
            if key in lower:
                return val
        # Fallback: extract meaningful part
        return lower
    
    @staticmethod
    def _kind_to_label(kind_str: str) -> str:
        """pyslang token kind → 显示标签"""
        op_name = ExpressionTree._kind_to_op(kind_str)
        label_map = {
            "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
            "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
            "GreaterThan": ">", "LessThan": "<", "GreaterThanEqual": "≥",
            "LessThanEqual": "≤",
            "Equality": "=", "Inequality": "≠",
            "ArithmeticShiftRight": ">>>", "LogicalShiftRight": ">>",
            "ArithmeticShiftLeft": "<<<", "LogicalShiftLeft": "<<",
            "LogicalAnd": "&&", "LogicalOr": "||",
            "Ternary": "?:", "Concat": "{}", "Modulo": "%",
            "BinaryNot": "~", "UnaryNot": "!",
            "ReduceOr": "|", "ReduceAnd": "&", "ReduceXor": "^",
            "LeftShift": "<<", "RightShift": ">>",
        }
        return label_map.get(op_name, op_name)
    
    @staticmethod
    def _to_dict(node: ExprNode) -> dict:
        """Serialize ExprNode tree to JSON-safe dict for viz.meta storage."""
        return {
            "label": node.label,
            "op": node.op,
            "children": [ExpressionTree._to_dict(c) for c in node.children]
        }
        """Extract original source text from token's sourceRange (line/col based).
        
        Falls back to str(token).strip() if sourceRange is unavailable.
        """
        import re as _re2
        sr = getattr(token, 'sourceRange', None)
        if sr is None:
            return fallback
        
        start = getattr(sr, 'start', None)
        end = getattr(sr, 'end', None)
        if start is None or end is None:
            return fallback
        
        start_line = getattr(start, 'line', 1)
        start_col = getattr(start, 'column', 1)
        end_line = getattr(end, 'line', 1)
        end_col = getattr(end, 'column', 1)
        
        parent = getattr(token, 'parent', None)
        # Walk up to find the root SyntaxTree or source text
        # Use str(token) which pyslang gives the original text for tokens
        text = str(token).strip()
        if text and text != fallback:
            return text
        
        return fallback
