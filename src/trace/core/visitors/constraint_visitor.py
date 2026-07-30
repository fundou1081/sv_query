# constraint_visitor.py
# [V6.9 2026-07-30] Recreated for semantic AST from class_graph_builder patterns.
# Original ConstraintVisitor deleted per 方豆 decision: "全面禁止 syntax+semantic
# visitor，统一用 pyslang native API". This version uses semantic_adapter.
#
# Exports ConstraintVisitor alias for backward-compatible test imports.

from trace.core.semantic_adapter import SemanticAdapter


class ConstraintVisitor:
    """[V6.9] Constraint 变量提取器（pyslang semantic AST）

    从 semantic AST 的 constraint 节点中提取所有引用变量名。

    Semantic AST 结构 (与 syntax tree 不同):
    - ConstraintBlock (.constraints → ConstraintList)
    - ConstraintList (.list → list of child constraints)
    - ConditionalConstraint (.predicate, .ifBody, .elseBody)
    - ImplicationConstraint (.predicate, .body)
    - ForeachConstraint (loop variables + body)
    - ExpressionConstraint (.expr → the actual expression)
    """

    def __init__(self, adapter: SemanticAdapter | None = None):
        self.adapter = adapter
        self.variables: list[str] = []

    def reset(self):
        self.variables = []

    def visit(self, node):
        """递归提取 constraint 语义节点的所有变量名"""
        if node is None:
            return

        kind_str = str(getattr(node, "kind", ""))

        # 1. ConditionalConstraint: if (predicate) ifBody else elseBody
        if "Conditional" in kind_str and "List" not in kind_str:
            predicate = getattr(node, "predicate", None)
            if_body = getattr(node, "ifBody", None)
            else_body = getattr(node, "elseBody", None)

            if predicate:
                pred_vars = self._extract_vars(predicate)
                self.variables.extend(pred_vars)
            self.visit(if_body)
            self.visit(else_body)
            return

        # 2. ImplicationConstraint: predicate → body
        if "Implication" in kind_str:
            predicate = getattr(node, "predicate", None)
            body = getattr(node, "body", None)
            if predicate:
                pred_vars = self._extract_vars(predicate)
                self.variables.extend(pred_vars)
            self.visit(body)
            return

        # 3. ForeachConstraint / LoopConstraint
        if "Foreach" in kind_str or "Loop" in kind_str:
            self._visit_foreach(node)
            return

        # 4. ConstraintList: iterate .list children
        if "ConstraintKind.List" in kind_str or "List" in kind_str:
            visited = set()
            # Priority: .list attribute (semantic AST)
            child_list = getattr(node, "list", None)
            if child_list and hasattr(child_list, "__iter__"):
                for child in child_list:
                    self.visit(child)
                    visited.add(id(child))
            # Fallback: .items (syntax tree compat)
            if hasattr(node, "items") and hasattr(node.items, "__iter__"):
                for child in node.items:
                    if id(child) not in visited:
                        self.visit(child)
            # Also try .constraints (ConstraintBlock compat)
            constraints = getattr(node, "constraints", None)
            if constraints and id(constraints) not in visited:
                self.visit(constraints)
            return

        # 5. ConstraintBlock: delegate to .constraints
        if "ConstraintBlock" in kind_str:
            constraints = getattr(node, "constraints", None)
            if constraints:
                self.visit(constraints)
            return

        # 6. ExpressionConstraint: extract .expr
        sigs = self._extract_vars(node)
        if sigs:
            self.variables.extend(sigs)

        # Also recurse generic .items / .constraints / .body for unseen structures
        for attr in ("items", "constraints", "body"):
            val = getattr(node, attr, None)
            if val is not None and hasattr(val, "__iter__") and not isinstance(val, str):
                for child in val:
                    self.visit(child)

    def _visit_foreach(self, node):
        """处理 ForeachConstraint: foreach (arr[i]) { body }
        
        semantic AST 结构:
        - .arrayRef → NamedValueExpression (.symbol.name = 数组名)
        - .loopDims → [LoopDim] (.loopVar.name = 循环变量名)  
        - .body → ExpressionConstraint
        """
        # 1. 提取数组名
        array_ref = getattr(node, "arrayRef", None)
        if array_ref:
            sym = getattr(array_ref, "symbol", None)
            if sym and hasattr(sym, "name"):
                self.variables.append(str(sym.name).strip())
        
        # 2. 提取循环变量
        loop_dims = getattr(node, "loopDims", None)
        if loop_dims and hasattr(loop_dims, "__iter__"):
            for dim in loop_dims:
                loop_var = getattr(dim, "loopVar", None)
                if loop_var and hasattr(loop_var, "name"):
                    self.variables.append(str(loop_var.name).strip())
        
        # 3. 递归处理 body
        body = getattr(node, "body", None)
        if body:
            self.visit(body)

    def _extract_vars(self, node) -> list[str]:
        """提取表达式中的变量名"""
        if self.adapter is None or node is None:
            return []

        kind_str = str(getattr(node, "kind", ""))

        # ExpressionConstraint: 提取 .expr
        if "ExpressionConstraint" in kind_str or "ConstraintKind.Expression" in kind_str:
            inner = getattr(node, "expr", None)
            if inner is not None:
                return self.adapter._extract_signals_from_expr(inner) or []
            return []

        # 直接表达式
        return self.adapter._extract_signals_from_expr(node) or []
