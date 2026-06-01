# constraint_visitor.py - Constraint Visitor
# ==============================================================================
# [铁律15] Visitor 模式 - 每个 constraint 类型独立 visit 方法
# [铁律13] 金标准测试 - 每个方法有对应测试
# [铁律17] 强断言 - 方法返回具体节点/边，不是"不崩溃"
#
# ConstraintBlock.items[] 语法类型分发:
#   ExpressionConstraint     → visit_expression_constraint
#   ConditionalConstraint    → visit_conditional_constraint
#   ImplicationConstraint    → visit_implication_constraint
#   UniquenessConstraint     → visit_uniqueness_constraint
#   SolveBeforeConstraint    → visit_solve_before_constraint
#   ForeachConstraint        → visit_foreach_constraint
# ==============================================================================

from dataclasses import dataclass, field

from ..graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode
from .base_visitor import BaseVisitor


@dataclass
class ConstraintNodeResult:
    """Constraint 解析结果"""

    nodes: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    # 直接关联的 CLASS_PROPERTY（用于 CONSTRAINS 边建立）
    direct_variables: list[str] = field(default_factory=list)


class ConstraintVisitor(BaseVisitor):
    """[铁律15] Constraint Visitor - 每个语法类型独立方法

    设计原则:
    - 每个 constraint 类型一个 visit 方法
    - 无 if-elif 链，通过 kind 字符串分发
    - 方法返回 (nodes, edges, variables)，无副作用
    """

    def __init__(self):
        super().__init__()
        self.result_nodes: list[TraceNode] = []
        self.result_edges: list[TraceEdge] = []
        self.variables: list[str] = []  # 当前 constraint 直接引用的变量

    def reset(self) -> None:
        """重置收集器"""
        self.result_nodes = []
        self.result_edges = []
        self.variables = []

    def visit(self, node):
        """[铁律15] 主入口 - 分发到对应 visit 方法"""
        if node is None or self.depth > self.max_depth:
            return

        kind = getattr(node, "kind", None)
        if kind is None:
            return

        kind_str = str(kind)

        # [铁律15] 每个语法类型 → 独立方法，禁止 if-elif 链
        if "ExpressionConstraint" in kind_str:
            return self.visit_expression_constraint(node)
        if "ConditionalConstraint" in kind_str:
            return self.visit_conditional_constraint(node)
        if "ImplicationConstraint" in kind_str:
            return self.visit_implication_constraint(node)
        if "UniquenessConstraint" in kind_str:
            return self.visit_uniqueness_constraint(node)
        if "SolveBeforeConstraint" in kind_str:
            return self.visit_solve_before_constraint(node)
        if "ExpressionOrDist" in kind_str:
            return self.visit_dist_constraint(node)
        if "LoopConstraint" in kind_str:
            return self.visit_foreach_constraint(node)
        if "ElseConstraintClause" in kind_str:
            return self.visit_else_constraint_clause(node)

        # 默认: 递归进入子节点
        self.generic_visit(node)

    def _mk_node(
        self, node_id: str, kind: NodeKind, class_name: str, name: str = "", width: tuple[int, int] = (0, 0)
    ) -> TraceNode:
        """创建 TraceNode 辅助方法"""
        return TraceNode(
            id=node_id,
            name=name or node_id.split(".")[-1],
            module=class_name,
            kind=kind,
            width=width,
        )

    def _mk_edge(self, src: str, dst: str, kind: EdgeKind) -> TraceEdge:
        """创建 TraceEdge 辅助方法"""
        return TraceEdge(src=src, dst=dst, kind=kind)

    def _extract_identifier(self, expr) -> str:
        """从表达式提取标识符名称"""
        if expr is None:
            return ""
        kind = getattr(expr, "kind", None)
        if kind is None:
            return ""

        kind_str = str(kind)
        if "Identifier" in kind_str:
            return str(getattr(expr, "name", "") or getattr(expr, "text", "") or expr).strip()
        return ""

    def _extract_vars_from_expr(self, expr) -> list[str]:
        """递归提取表达式中的所有变量名"""
        vars = []
        if expr is None:
            return vars

        kind = getattr(expr, "kind", None)
        if kind is None:
            return vars

        kind_str = str(kind)

        # ScopedName (this.addr, range.min_addr)
        # 如果 left 是 this/super，只取 right；否则保留完整 dotted name
        if "ScopedName" in kind_str:
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)

            # 检查 left 是否是 this/super 关键字
            left_name = ""
            if left:
                left_ident = getattr(left, "identifier", None)
                if left_ident:
                    left_name = str(getattr(left_ident, "value", "")).strip()
                else:
                    left_name = str(getattr(left, "name", "") or "").strip()

            if left_name in ("this", "super", ""):
                # this.addr -> addr, 或无法解析 left -> 只取 right
                if right:
                    vars.extend(self._extract_vars_from_expr(right))
            else:
                # range.min_addr -> range.min_addr (保留完整路径)
                right_vars = self._extract_vars_from_expr(right) if right else []
                for rv in right_vars:
                    vars.append(f"{left_name}.{rv}")
            return vars

        # IdentifierSelectName (arr[i]): identifier + selectors
        # 必须放在 'Identifier' 检查之前，因为 IdentifierSelectName 也包含 'Identifier'
        if "IdentifierSelectName" in kind_str:
            ident = getattr(expr, "identifier", None)
            if ident and hasattr(ident, "value"):
                vars.append(str(ident.value).strip())
            # 递归提取 selectors 中的索引表达式
            selectors = getattr(expr, "selectors", None)
            if selectors and hasattr(selectors, "__iter__"):
                for sel in selectors:
                    vars.extend(self._extract_vars_from_expr(sel))
            return vars

        # Identifier - 叶子节点
        # 支持多种 Identifier 语法：IdentifierName,IdentifierTiming,ScopedName 等
        if "Identifier" in kind_str:
            # IdentifierNameSyntax: 有 identifier 属性
            ident = getattr(expr, "identifier", None)
            if ident and hasattr(ident, "value"):
                name = str(ident.value).strip()
            else:
                # 其他形式
                name = str(getattr(expr, "name", "") or getattr(expr, "text", "") or expr).strip()
            if name:
                vars.append(name)
            return vars

        # ElementSelect (arr[i] 中的索引选择器): selector 属性
        if "ElementSelect" in kind_str:
            selector = getattr(expr, "selector", None)
            if selector:
                vars.extend(self._extract_vars_from_expr(selector))
            return vars

        # BitSelect (arr[i] 中的索引): expr 属性
        if "BitSelect" in kind_str:
            bit_expr = getattr(expr, "expr", None)
            if bit_expr:
                vars.extend(self._extract_vars_from_expr(bit_expr))
            return vars

        # ConditionalPattern (三元表达式的条件部分: sel in sel ? a : b)
        if "ConditionalPattern" in kind_str:
            pattern_expr = getattr(expr, "expr", None)
            if pattern_expr:
                vars.extend(self._extract_vars_from_expr(pattern_expr))
            return vars

        # ConditionalPredicate (三元表达式条件的外层包装)
        if "ConditionalPredicate" in kind_str:
            conditions = getattr(expr, "conditions", None)
            if conditions and hasattr(conditions, "__iter__"):
                for c in conditions:
                    vars.extend(self._extract_vars_from_expr(c))
            return vars

        # 条件表达式: predicate (不是 condition), left (then), right (else)
        # pyslang ConditionalExpression 也有 left/right 属性，所以要优先检查
        if "ConditionalExpression" in kind_str:
            vars.extend(self._extract_vars_from_expr(getattr(expr, "predicate", None)))
            vars.extend(self._extract_vars_from_expr(getattr(expr, "left", None)))
            vars.extend(self._extract_vars_from_expr(getattr(expr, "right", None)))
            return vars

        # 二元表达式: left, right
        if hasattr(expr, "left") and hasattr(expr, "right"):
            vars.extend(self._extract_vars_from_expr(expr.left))
            vars.extend(self._extract_vars_from_expr(expr.right))
            return vars

        # ParenthesizedExpression: (expr) - 取 expression 属性
        if "ParenthesizedExpression" in kind_str:
            vars.extend(self._extract_vars_from_expr(getattr(expr, "expression", None)))
            return vars

        # 一元表达式: UnaryLogicalNotExpression (!a), NegationExpression (-a)
        # 属性是 operand，不是 left/right
        if hasattr(expr, "operand"):
            vars.extend(self._extract_vars_from_expr(expr.operand))
            return vars

        # Inside 表达式: x inside {[a:b]}
        # 提取 expr (x) 和 ranges 中的变量
        if "InsideExpression" in kind_str:
            vars.extend(self._extract_vars_from_expr(getattr(expr, "expr", None)))
            # 提取 ranges 中的变量
            # ranges 是 RangeListSyntax: [OpenBrace, SeparatedList, CloseBrace]
            # ValueRangeExpression 在 SeparatedList 中 (ranges[1])
            ranges = getattr(expr, "ranges", None)
            if ranges and hasattr(ranges, "__iter__"):
                # RangeListSyntax - extract the SeparatedList (index 1)
                items = list(ranges) if hasattr(ranges, "__iter__") else [ranges]
                for r in items:
                    r_kind = getattr(r, "kind", None)
                    if r_kind and "SeparatedList" in str(r_kind):
                        # Found the list containing ValueRangeExpression
                        for elem in r:
                            if hasattr(elem, "kind") and "ValueRangeExpression" in str(elem.kind):
                                vars.extend(self._extract_vars_from_expr(getattr(elem, "left", None)))
                                vars.extend(self._extract_vars_from_expr(getattr(elem, "right", None)))
            return vars

        # 递归进入子节点
        for attr in ["expr", "items"]:
            if hasattr(expr, attr):
                child = getattr(expr, attr)
                if child and hasattr(child, "__iter__") and not isinstance(child, str):
                    for item in child:
                        vars.extend(self._extract_vars_from_expr(item))
                elif child:
                    vars.extend(self._extract_vars_from_expr(child))

        return vars

    # =========================================================================
    # [铁律15] 每个 constraint 类型独立 visit 方法
    # =========================================================================

    def visit_expression_constraint(self, node) -> ConstraintNodeResult:
        """ExpressionConstraint: addr == 1 / addr inside {0,1,2}

        RTL: constraint c { addr inside {0, 1, 2}; }
        创建:
          - CONSTRAINT_EXPR 节点: c::expr_0
          - CONSTRAINS 边: c::expr_0 → 直接引用的 CLASS_PROPERTY
        """
        self.reset()
        self.generic_visit(node)

        # 提取约束表达式
        expr = getattr(node, "expr", None)
        if expr is None:
            return ConstraintNodeResult()

        # 收集表达式中引用的变量
        vars = self._extract_vars_from_expr(expr)
        self.variables = list(set(vars))  # 去重

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )

    def visit_conditional_constraint(self, node) -> ConstraintNodeResult:
        """ConditionalConstraint: if (cond) ... else ...

        RTL: constraint c { if (en) addr == 1; else addr == 2; }
        创建:
          - CONSTRAINT_IF 节点: c::if_branch (条件分支)
          - CONSTRAINT_EXPR 节点: c::if_branch::cons (consequent, addr == 1)
          - CONSTRAINT_ELSE 节点: c::if_branch::alt (alternate, addr == 2)
          - HAS_CONDITION 边: c::if_branch → 条件变量
          - HAS_CONSEQUENT 边: c::if_branch → c::if_branch::cons
          - HAS_ALTERNATE 边: c::if_branch → c::if_branch::alt
        """
        self.reset()

        condition = getattr(node, "condition", None)
        consequent = getattr(node, "constraints", None)  # consequent 在 constraints 属性
        else_clause = getattr(node, "elseClause", None)  # alternate 在 elseClause

        # 提取条件变量
        cond_vars = self._extract_vars_from_expr(condition)

        # 递归处理 consequent 和 alternate
        self.visit(consequent)
        self.visit(else_clause)

        # 结果变量是 if 和 else 分支的并集
        # cond_vars 需要累积，因为递归调用只更新 self.variables 为结果变量
        all_vars = list(set(cond_vars + self.variables))
        self.variables = all_vars

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=all_vars,
        )

    def visit_implication_constraint(self, node) -> ConstraintNodeResult:
        """ImplicationConstraint: (en) -> addr == 1

        RTL: constraint c { b1 == 5 -> b2 == 10; }
        创建:
          - CONSTRAINT_IMPLIES 节点: c::implies (左部条件)
          - CONSTRAINT_EXPR 节点: c::implies::result (右部结果)
          - HAS_CONSEQUENT 边: implies → result
          - CONSTRAINS 边: implies → 左部变量, result → 右部变量
        """
        self.reset()
        self.generic_visit(node)

        # 左部 (条件) 和 右部 (结果)
        left = getattr(node, "left", None)
        right = getattr(node, "constraints", None)

        left_vars = self._extract_vars_from_expr(left)
        right_vars = self._extract_vars_from_expr(right)

        self.variables = list(set(left_vars + right_vars))

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )

    def visit_uniqueness_constraint(self, node) -> ConstraintNodeResult:
        """UniquenessConstraint: unique {a, b, c}

        RTL: constraint c { unique {b1, b2, b3}; }
        创建:
          - CONSTRAINT_UNIQUE 节点: c::unique
          - HAS_MEMBER 边: c::unique → 每个成员 CLASS_PROPERTY
        """
        self.reset()

        # 收集 unique { ... } 中的变量
        # ranges[1] 是 SeparatedList 包含 {a, b, c} + commas
        vars = []
        ranges = getattr(node, "ranges", None)
        if ranges:
            for r in ranges:
                if hasattr(r, "kind"):
                    kind_str = str(r.kind)
                    # SeparatedList 包含 Identifier + Comma 交替
                    if "SeparatedList" in kind_str:
                        if hasattr(r, "__iter__"):
                            for elem in r:
                                if hasattr(elem, "kind"):
                                    elem_kind = str(elem.kind)
                                    if "Identifier" in elem_kind:
                                        ident = getattr(elem, "identifier", None)
                                        if ident and hasattr(ident, "value"):
                                            vars.append(str(ident.value).strip())

        self.variables = list(set(vars))

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )

    def visit_solve_before_constraint(self, node) -> ConstraintNodeResult:
        """SolveBeforeConstraint: solve A before B

        RTL: constraint c { solve b1 before b2; }
        创建:
          - CONSTRAINT_SOLVE 节点: c::solve
          - HAS_BEFORE 边: c::solve → before 变量
          - HAS_AFTER 边: c::solve → after 变量
        """
        self.reset()

        before_vars = []
        after_vars = []

        # solve a before b → beforeExpr=a, afterExpr=b
        # beforeExpr/afterExpr 是 SeparatedList，直接迭代取 IdentifierName
        before = getattr(node, "beforeExpr", None)
        after = getattr(node, "afterExpr", None)

        if before and hasattr(before, "__iter__"):
            for elem in before:
                if hasattr(elem, "kind") and "Identifier" in str(elem.kind):
                    ident = getattr(elem, "identifier", None)
                    if ident and hasattr(ident, "value"):
                        before_vars.append(str(ident.value).strip())

        if after and hasattr(after, "__iter__"):
            for elem in after:
                if hasattr(elem, "kind") and "Identifier" in str(elem.kind):
                    ident = getattr(elem, "identifier", None)
                    if ident and hasattr(ident, "value"):
                        after_vars.append(str(ident.value).strip())

        self.variables = list(set(before_vars + after_vars))

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )

    def visit_foreach_constraint(self, node) -> ConstraintNodeResult:
        """ForeachConstraint: foreach (arr[i]) arr[i] > 0

        RTL: constraint c { foreach (arr[i]) arr[i] > 0; }
        pyslang kind: SyntaxKind.LoopConstraint
        创建:
          - CONSTRAINT_FOREACH 节点: c::foreach
          - HAS_LOOP_VAR 边: c::foreach → arr
        """
        self.reset()

        # 提取 foreach (arr[i]) 中的数组名
        # pyslang: loopList 是 ForeachLoopListSyntax，包含:
        #   [0] OpenParen
        #   [1] IdentifierNameSyntax (arr)
        #   [2] OpenBracket
        #   [3] SeparatedList (索引变量 i)
        #   [4] CloseBracket
        #   [5] CloseParen
        vars = []
        loop_list = getattr(node, "loopList", None)
        if loop_list and hasattr(loop_list, "__iter__"):
            for elem in loop_list:
                elem_kind = str(getattr(elem, "kind", ""))
                if "IdentifierName" in elem_kind:
                    ident = getattr(elem, "identifier", None)
                    if ident and hasattr(ident, "value"):
                        vars.append(str(ident.value).strip())

        self.variables = list(set(vars))

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )

    def visit_dist_constraint(self, node) -> ConstraintNodeResult:
        """DistConstraint: b dist {3 := 1, 10 := 2}

        RTL: constraint c { b dist {3 := 1, 10 := 2}; }
        pyslang kind: SyntaxKind.ExpressionOrDist
        创建:
          - CONSTRAINT_DIST 节点: c::dist
          - CONSTRAINS 边: c::dist → 变量 b
        """
        self.reset()

        # ExpressionOrDist: expr=变量, distribution=DistConstraintList
        expr = getattr(node, "expr", None)
        dist = getattr(node, "distribution", None)

        # 提取变量 b
        if expr:
            self.variables.extend(self._extract_vars_from_expr(expr))

        # dist {3 := 1, 10 := 2} 中的 weight (:=) 不算变量
        # 只收集 left-side 的值 (这里是常数，不影响变量提取)
        # 如果 dist 中有变量引用，也需要提取
        if dist and hasattr(dist, "items"):
            items = dist.items
            if hasattr(items, "__iter__"):
                for item in items:
                    if hasattr(item, "left"):
                        self.variables.extend(self._extract_vars_from_expr(item.left))

        self.variables = list(set(self.variables))

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )

    def visit_else_constraint_clause(self, node) -> ConstraintNodeResult:
        """ElseConstraintClause: else { constraint_expr }

        RTL: constraint c { if (a) x == 1; else y == 2; }
        ElseConstraintClause.constraints 指向 else 分支的 ConstraintExpr
        """
        # 保存当前变量，因为 self.visit 会修改 self.variables
        saved_vars = list(self.variables)

        # 不 reset，直接进入 else 分支
        else_constraints = getattr(node, "constraints", None)
        if else_constraints:
            self.visit(else_constraints)

        # 合并: 之前累积的变量 + else 分支的变量
        all_vars = list(set(saved_vars + self.variables))
        self.variables = all_vars

        return ConstraintNodeResult(
            nodes=[],
            edges=[],
            direct_variables=self.variables,
        )


# [铁律11] Agent 调用示例
if __name__ == "__main__":
    import pyslang
    from pyslang import SyntaxKind

    # === 示例 ===
    source = """class packet;
    bit [7:0] addr;
    bit en;
    constraint c { if (en) addr == 1; else addr == 2; }
endclass"""
    tree = pyslang.SyntaxTree.fromText(source)
    cls = tree.root

    visitor = ConstraintVisitor()
    for item in cls.items:
        if item.kind == SyntaxKind.ConstraintDeclaration:
            for expr in item.block.items:
                visitor.visit(expr)
                print(f"Constraint expr: {expr.kind}")
                print(f"  Variables: {visitor.variables}")
                print(f"  Nodes: {len(visitor.result_nodes)}")
                print(f"  Edges: {len(visitor.result_edges)}")
