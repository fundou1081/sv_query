# ==============================================================================
# subroutine_expander.py - 函数/任务展开器
# ==============================================================================
# [Subroutine Expansion] 专门处理函数/任务调用的展开

from dataclasses import dataclass, field
from ..._safe import _safe_attr, _safe_str
from typing import Any

from trace.core.graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode


@dataclass
class BranchInfo:
    """条件分支信息"""

    condition: Any  # 条件 AST 表达式
    condition_str: str  # 条件字符串,如 "sel==0"
    assignment: Any  # 赋值语句 AST (AssignmentExpression)
    assignment_lhs: str  # 赋值 LHS 变量名
    assignment_rhs: Any  # 赋值 RHS AST


@dataclass
class ExpansionResult:
    """展开结果"""

    edges: list[TraceEdge] = field(default_factory=list)
    nodes: list[TraceNode] = field(default_factory=list)
    branches: list[BranchInfo] = field(default_factory=list)  # 原始分支信息


@dataclass
class CallSiteInfo:
    """调用点信息"""

    invocation: Any  # InvocationExpression AST 节点
    call_name: str  # 被调用的函数/任务名
    call_args: list[str]  # 实参列表 [arg1, arg2, ...]
    named_args: dict[str, str]  # 命名实参 {name: signal}
    func_def: Any  # 函数定义 AST
    def_params: list[tuple]  # 形参列表 [(direction, name), ...]
    param_map: dict[str, str]  # 形参→实参映射 {def_param: call_arg}
    reverse_param_map: dict[str, str]  # 实参→形参映射 {call_arg: def_param}
    lhs_name: str | None  # 赋值目标信号名
    is_function: bool  # 是否为函数


class SubroutineExpander:
    """函数/任务展开器

    职责:
    1. 提取函数/任务内部的控制流分支(if/else/case)
    2. 参数替换(将形参替换为实参)
    3. 生成带条件的边

    与 GraphBuilder 协作:GraphBuilder 负责调用点分析和节点/边收集,
    SubroutineExpander 负责展开逻辑。
    """

    def __init__(self, adapter):
        """初始化展开器

        Args:
            adapter: SemanticAdapter 实例,用于访问 AST
        """
        self._adapter = adapter
        self._cond_formatter = None  # 延迟加载条件格式化器

    @property
    def cond_formatter(self) -> object:
        """延迟加载条件格式化器"""
        if self._cond_formatter is None:
            from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor

            self._cond_formatter = SignalExpressionVisitor(self._adapter)
        return self._cond_formatter

    def expand(self, call_site: CallSiteInfo, ctx: dict = None) -> ExpansionResult:
        """展开函数/任务调用

        Args:
            call_site: 调用点信息
            ctx: 上下文(条件、时钟等)

        Returns:
            ExpansionResult: 展开结果
        """
        if ctx is None:
            ctx = {}

        result = ExpansionResult()

        # 1. 获取函数体
        func_body = self._get_function_body(call_site.func_def)
        if func_body is None:
            return result

        # 2. 提取条件分支
        branches = self._extract_branches(func_body, call_site.func_def)
        result.branches = branches

        if not branches:
            # 没有条件分支,使用默认逻辑
            return self._expand_without_branches(call_site, ctx)

        # 3. 对每个分支进行参数替换并生成边
        for branch in branches:
            # 提取信号并映射:形参 → 实参
            signal_mapping = self._extract_signals_with_mapping(branch.assignment_rhs, call_site.param_map)

            # [FIX] 映射条件字符串中的形参到实参
            # branch.condition_str 是预计算的条件字符串(如 "s==0")
            # 需要将形参名(如 s)替换为实参名(如 sel)
            cond_str = self._map_condition_string(branch.condition_str, call_site.param_map)
            effective_cond = cond_str

            # 生成边:使用映射后的信号名
            for _orig_name, mapped_name in signal_mapping:
                edge = TraceEdge(
                    src=f"{call_site.lhs_name.split('.')[0] if '.' in call_site.lhs_name else 'top'}.{mapped_name}",
                    dst=call_site.lhs_name,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous",
                    clock_domain=ctx.get("clock", ""),
                    condition=cond_str,
                    effective_condition=effective_cond,
                )
                result.edges.append(edge)

            # [FIX] 如果没有提取到信号(常量表达式或无参数函数),添加函数返回值节点和边
            if not signal_mapping and not cond_str:
                func_return_id = (
                    f"{call_site.lhs_name.split('.')[0] if '.' in call_site.lhs_name else 'top'}.{call_site.call_name}"
                )
                result.nodes.append(
                    TraceNode(
                        id=func_return_id,
                        name=call_site.call_name,
                        module=call_site.lhs_name.split(".")[0] if "." in call_site.lhs_name else "top",
                        kind=NodeKind.SIGNAL,
                        width=(1, 0),
                    )
                )
                result.edges.append(
                    TraceEdge(
                        src=func_return_id,
                        dst=call_site.lhs_name,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        clock_domain=ctx.get("clock", ""),
                        condition="",
                        effective_condition="",
                    )
                )

        return result

    def _expand_without_branches(self, call_site: CallSiteInfo, ctx: dict) -> ExpansionResult:
        """处理没有条件分支的函数(简单函数)"""
        result = ExpansionResult()
        func_body = self._get_function_body(call_site.func_def)
        if func_body is None:
            return result

        # 提取返回值赋值
        func_name = call_site.call_name
        assignments = self._extract_assignments(func_body, func_name)

        for assignment in assignments:
            rhs = assignment.get("rhs")
            if rhs is None:
                continue

            # [FIX] 使用 _extract_signals_with_mapping 获取映射后的信号名
            signal_mapping = self._extract_signals_with_mapping(rhs, call_site.param_map)

            for _orig_name, mapped_name in signal_mapping:
                edge = TraceEdge(
                    src=f"{call_site.lhs_name.split('.')[0] if '.' in call_site.lhs_name else 'top'}.{mapped_name}",
                    dst=call_site.lhs_name,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous",
                    clock_domain=ctx.get("clock", ""),
                    condition=ctx.get("condition", ""),
                    effective_condition=ctx.get("effective_condition", ""),
                )
                result.edges.append(edge)

            # 如果没有提取到信号(可能是常量表达式),添加自环边表示函数返回值
            if not signal_mapping:
                func_return_id = (
                    f"{call_site.lhs_name.split('.')[0] if '.' in call_site.lhs_name else 'top'}.{call_site.call_name}"
                )
                result.nodes.append(
                    TraceNode(
                        id=func_return_id,
                        name=call_site.call_name,
                        module=call_site.lhs_name.split(".")[0] if "." in call_site.lhs_name else "top",
                        kind=NodeKind.SIGNAL,
                        width=(1, 0),
                    )
                )
                result.edges.append(
                    TraceEdge(
                        src=func_return_id,
                        dst=call_site.lhs_name,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        clock_domain=ctx.get("clock", ""),
                        condition=ctx.get("condition", ""),
                        effective_condition=ctx.get("effective_condition", ""),
                    )
                )

        return result

    def _get_function_body(self, func_def: Any) -> Any | None:
        """获取函数体 AST"""
        if func_def is None:
            return None
        return getattr(func_def, "body", None)

    def has_conditional_branches(self, func_def: Any) -> bool:
        """检查函数是否包含条件分支 (if/else/case) 或三元运算符

        Args:
            func_def: 函数定义 AST

        Returns:
            bool: True if function has conditional branches
        """
        if func_def is None:
            return False
        body = getattr(func_def, "body", None)
        if body is None:
            return False
        body_kind = str(getattr(body, "kind", ""))

        # ConditionalStatement: if/else
        # CaseStatement: case/covergroup
        if "Conditional" in body_kind or "Case" in body_kind:
            return True

        # Check for ternary operator in ExpressionStatement body
        # e.g., func = cond ? a : b;
        if "ExpressionStatement" in body_kind:
            expr = getattr(body, "expr", None)
            if expr and "Assignment" in str(getattr(expr, "kind", "")):
                rhs = getattr(expr, "right", None)
                if rhs and "ConditionalOp" in str(getattr(rhs, "kind", "")):
                    return True

        return False

    def _extract_branches(self, body: Any, func_def: Any) -> list[BranchInfo]:
        """提取函数体中的条件分支

        Args:
            body: 函数体 AST
            func_def: 函数定义 AST

        Returns:
            List[BranchInfo]: 条件分支列表
        """
        branches = []
        func_name = _safe_attr(func_def, "name", None)
        if func_name:
            func_name = str(func_name)

        # Check for ternary operator first
        # e.g., func = cond ? a : b;
        body_kind = str(getattr(body, "kind", ""))
        if "ExpressionStatement" in body_kind:
            expr = getattr(body, "expr", None)
            if expr and "Assignment" in str(getattr(expr, "kind", "")):
                rhs = getattr(expr, "right", None)
                if rhs and "ConditionalOp" in str(getattr(rhs, "kind", "")):
                    ternary_branches = self._extract_ternary_branches(expr, func_name)
                    if ternary_branches:
                        return ternary_branches

        self._collect_branches(body, func_name, branches)
        return branches

    def _extract_ternary_branches(self, assignment_expr: Any, func_name: str) -> list[BranchInfo]:
        """提取三元运算符的分支

        Args:
            assignment_expr: 赋值表达式 (lhs = cond ? ifTrue : ifFalse)
            func_name: 函数名

        Returns:
            List[BranchInfo]: 两个分支 (条件为真和条件为假)
        """
        branches = []
        rhs = getattr(assignment_expr, "right", None)
        if rhs is None:
            return branches

        # Extract condition, ifTrue, ifFalse from ConditionalOp
        # Semantic AST: conditions[0].expr is the condition
        conditions = getattr(rhs, "conditions", None)
        if conditions and len(conditions) > 0:
            cond_obj = conditions[0]
            cond_expr = getattr(cond_obj, "expr", None)
        else:
            cond_expr = None

        if_true = getattr(rhs, "left", None)
        if_false = getattr(rhs, "right", None)

        # Build condition string
        if cond_expr:
            cond_str = self._condition_to_string(cond_expr)
        else:
            cond_str = ""

        # ifTrue branch (condition is true)
        if if_true:
            branches.append(
                BranchInfo(
                    condition=cond_expr,
                    condition_str=cond_str,
                    assignment=None,
                    assignment_lhs=func_name,
                    assignment_rhs=if_true,
                )
            )

        # ifFalse branch (condition is false, negate the condition)
        if if_false:
            neg_cond_str = f"!({cond_str})" if cond_str else "!()"
            branches.append(
                BranchInfo(
                    condition=cond_expr,
                    condition_str=neg_cond_str,
                    assignment=None,
                    assignment_lhs=func_name,
                    assignment_rhs=if_false,
                )
            )

        return branches

    def _collect_branches(
        self,
        stmt: Any,
        func_name: str,
        branches: list[BranchInfo],
        parent_condition: Any = None,
        in_else: bool = False,
        case_expr: Any = None,
    ):
        """递归收集条件分支

        Args:
            stmt: 语句 AST
            func_name: 函数名
            branches: 输出的分支列表
            parent_condition: 父级条件(用于嵌套 if)
            in_else: 是否在 else 分支中
            case_expr: case 语句的表达式 (用于构建 case 值比较)
        """
        if stmt is None:
            return

        stmt_kind = str(getattr(stmt, "kind", ""))

        # CaseStatement: case (...) ... endcase
        if "Case" in stmt_kind and "Statement" in stmt_kind:
            # 获取 case 表达式
            stmt_case_expr = getattr(stmt, "expr", None)
            self._collect_case_branches(stmt, func_name, branches, parent_condition, in_else, stmt_case_expr)
            return

        # ConditionalStatement: if (...) ... else ...
        if "Conditional" in stmt_kind and "Statement" in stmt_kind:
            # 获取条件表达式
            cond_expr = self._get_condition_expr(stmt)

            # ifTrue 分支
            if_true = getattr(stmt, "ifTrue", None) or getattr(stmt, "statement", None)
            if if_true:
                self._collect_branches(if_true, func_name, branches, cond_expr, in_else=False, case_expr=case_expr)

            # ifFalse 分支 - 需要取反条件
            if_false = getattr(stmt, "ifFalse", None)
            if if_false:
                self._collect_branches(if_false, func_name, branches, cond_expr, in_else=True, case_expr=case_expr)
            return

        # ReturnStatement: return x;
        if "Return" in stmt_kind and "Statement" in stmt_kind:
            # Semantic AST: ReturnStatement.expr, Syntax AST: ReturnStatement.value
            return_expr = getattr(stmt, "expr", None) or _safe_attr(stmt, "value", None)
            if return_expr:
                # 构建条件字符串
                if parent_condition is not None:
                    if isinstance(parent_condition, str):
                        cond_str = parent_condition
                    else:
                        cond_str = self._condition_to_string(parent_condition)
                    if in_else:
                        cond_str = f"!({cond_str})"
                else:
                    cond_str = ""
                branch = BranchInfo(
                    condition=parent_condition,
                    condition_str=cond_str,
                    assignment=None,  # Return 语句没有 assignment 对象
                    assignment_lhs=func_name,
                    assignment_rhs=return_expr,
                )
                branches.append(branch)
            return

        # SequentialBlock: begin...end
        if "SequentialBlock" in stmt_kind:
            items = getattr(stmt, "items", None)
            if items:
                for item in items:
                    self._collect_branches(item, func_name, branches, parent_condition, in_else, case_expr)
            return

        # StatementList
        if "List" in stmt_kind and "Statement" in stmt_kind:
            stmt_list = getattr(stmt, "list", None)
            if stmt_list:
                for s in stmt_list:
                    self._collect_branches(s, func_name, branches, parent_condition, in_else, case_expr)
            return

        # ExpressionStatement: 查找函数名赋值
        if "ExpressionStatement" in stmt_kind:
            expr = getattr(stmt, "expr", None)
            if expr and "Assignment" in str(getattr(expr, "kind", "")):
                lhs = getattr(expr, "left", None)
                if lhs:
                    lhs_name = self._get_name(lhs)
                    # 检查是否是函数名赋值
                    if lhs_name == func_name:
                        rhs = getattr(expr, "right", None)
                        if rhs:
                            # 构建条件字符串:如果是 else 分支则取反
                            if parent_condition is not None:
                                if isinstance(parent_condition, str):
                                    cond_str = parent_condition
                                else:
                                    cond_str = self._condition_to_string(parent_condition)
                                if in_else:
                                    cond_str = f"!({cond_str})"
                            else:
                                cond_str = ""
                            branch = BranchInfo(
                                condition=parent_condition,
                                condition_str=cond_str,
                                assignment=expr,
                                assignment_lhs=lhs_name,
                                assignment_rhs=rhs,
                            )
                            branches.append(branch)
            return

        # BlockStatement
        if "Block" in stmt_kind and "Statement" in stmt_kind:
            body = getattr(stmt, "body", None)
            if body:
                stmt_list = getattr(body, "list", None) or list(body) if hasattr(body, "__iter__") else [body]
                for s in stmt_list:
                    self._collect_branches(s, func_name, branches, parent_condition, in_else, case_expr)
            return

        # ForLoop/WhileLoop - 简化处理,只遍历 body
        if "ForLoop" in stmt_kind or "WhileLoop" in stmt_kind:
            loop_body = getattr(stmt, "body", None)
            if loop_body:
                self._collect_branches(loop_body, func_name, branches, parent_condition, in_else, case_expr)
            return

    def _collect_case_branches(
        self,
        stmt: Any,
        func_name: str,
        branches: list[BranchInfo],
        parent_condition: Any = None,
        in_else: bool = False,
        case_expr: Any = None,
    ):
        """收集 case 语句的分支

        CaseStatement structure:
        - .items: list of ItemGroup for non-default cases
        - .defaultCase: direct statement for default case (if present)

        ItemGroup has:
        - .expressions: list of case values (can be multiple for '0, 1:')
        - .stmt: the statement to execute
        """
        # Get case expression if not provided
        if case_expr is None:
            case_expr = getattr(stmt, "expr", None)

        # Convert case expression to string for building comparisons
        case_expr_str = ""
        if case_expr:
            try:
                case_expr_str = self.cond_formatter._expr_to_string(case_expr)
            except Exception:
                case_expr_str = "?"

        # Process regular case items
        items = getattr(stmt, "items", None)
        if items:
            for item in items:
                # Get case values (patterns)
                expressions = getattr(item, "expressions", None) or []

                # Get the statement body
                case_stmt = getattr(item, "stmt", None)
                if case_stmt is None:
                    continue

                # For case items with multiple values (e.g., 0, 1:), we still use the
                # same statement - the condition covers all values
                if expressions:
                    # Build condition string for this case item
                    # For multiple values, we join them with OR
                    case_conds = []
                    for expr in expressions:
                        val_str = self._case_value_to_string(expr)
                        case_conds.append(val_str)

                    if len(case_conds) == 1:
                        combined_cond = f"{case_expr_str}=={case_conds[0]}"
                    else:
                        # Multiple values: s==0 || s==1
                        combined_cond = " || ".join(f"{case_expr_str}=={v}" for v in case_conds)

                    # Recursively collect from the case statement
                    self._collect_branches(case_stmt, func_name, branches, combined_cond, in_else, case_expr)

        # Process default case
        default_stmt = getattr(stmt, "defaultCase", None)
        if default_stmt:
            self._collect_branches(default_stmt, func_name, branches, "default", in_else, case_expr)

    def _case_value_to_string(self, expr: Any) -> str:
        """将 case 值表达式转换为字符串"""
        import re

        if expr is None:
            return "default"

        kind = str(getattr(expr, "kind", ""))

        # Conversion type (e.g., 32'd0) - extract constant
        if "Conversion" in kind:
            try:
                const_val = getattr(expr, "constant", None)
                if const_val is not None:
                    # constant is like '32'd0', extract the numeric value
                    const_str = str(const_val)
                    if "'" in const_str:
                        # Format: WIDTH'BASEvalue, e.g., 32'd0
                        parts = const_str.split("'")
                        if len(parts) >= 2:
                            val_with_base = parts[-1]  # e.g., 'd0'
                            # Remove leading base chars (d, h, b, o)
                            numeric_val = re.sub(r"^[dhboDHBO]+", "", val_with_base)
                            return numeric_val
                    return const_str
            except Exception:
                pass

        # Literal values
        if "Literal" in kind or "Integer" in kind:
            try:
                val = _safe_attr(expr, "value", None)
                if val is not None:
                    return str(val)
            except Exception:
                pass
            try:
                val = getattr(expr, "constant", None)
                if val is not None:
                    const_str = str(val)
                    if "'" in const_str:
                        parts = const_str.split("'")
                        if len(parts) >= 2:
                            val_with_base = parts[-1]
                            numeric_val = re.sub(r"^[dhboDHBO]+", "", val_with_base)
                            return numeric_val
                    return const_str
            except Exception:
                pass

        # Default keyword
        if "Default" in kind:
            return "default"

        # NamedValue (identifier)
        if "NamedValue" in kind:
            try:
                sym = getattr(expr, "symbol", None)
                if sym:
                    name = _safe_attr(sym, "name", None)
                    if name:
                        return str(name)
            except Exception:
                pass

        # Fallback
        return self._condition_to_string(expr)

    def _map_condition_string(self, cond_str: str, param_map: dict[str, str]) -> str:
        """将条件字符串中的形参替换为实参

        Args:
            cond_str: 条件字符串,如 "s==0" 或 "default"
            param_map: {形参名: 实参名}

        Returns:
            str: 替换后的条件字符串,如 "sel==0"
        """
        if not cond_str or cond_str == "default" or not param_map:
            return cond_str

        result = cond_str
        # 替换形参名为实参名
        # 形参名按长度降序排列,避免部分匹配(如 s 优先于 sel_before)
        for def_param, call_arg in sorted(param_map.items(), key=lambda x: -len(x[0])):
            if def_param in result:
                result = result.replace(def_param, call_arg)
        return result

    def _get_condition_expr(self, stmt: Any) -> Any | None:
        """从条件语句提取条件表达式"""
        # Semantic AST: ConditionalStatement.conditions[0].expr
        if hasattr(stmt, "conditions") and stmt.conditions:
            return stmt.conditions[0].expr if len(stmt.conditions) > 0 else None

        # Syntax AST: ConditionalStatementSyntax.predicate.conditions
        if hasattr(stmt, "predicate") and stmt.predicate:
            pred = stmt.predicate
            if hasattr(pred, "conditions"):
                return pred.conditions[0].expr if len(pred.conditions) > 0 else None
            # 也可能是直接的表达式
            return pred

        return None

    def _negate_condition(self, cond: Any) -> Any:
        """取反条件表达式

        由于 pyslang AST 是只读的,我们不能动态创建 UnaryOp 节点。
        因此这个方法返回 None,实际的取反通过字符串拼接实现。
        """
        # pyslang AST is immutable, cannot create new nodes
        # Negation will be handled via condition_str string concatenation
        return None

    def _get_name(self, node: Any) -> str | None:
        """获取节点的名称"""
        if node is None:
            return None

        kind = str(getattr(node, "kind", ""))

        if "NamedValue" in kind or "Identifier" in kind:
            sym = getattr(node, "symbol", None)
            if sym:
                return _safe_attr(sym, "name", None) or str(getattr(sym, "def", ""))
            # 尝试直接获取 name
            name = _safe_attr(node, "name", None)
            if name:
                return str(name)

        # 回退
        return str(node) if node else None

    def _build_condition_str(self, base_cond: Any, is_negated: bool) -> str:
        """构建条件字符串

        Args:
            base_cond: 基础条件 AST 或字符串
            is_negated: 是否取反

        Returns:
            条件字符串
        """
        if base_cond is None:
            return "" if not is_negated else "!()"

        if isinstance(base_cond, str):
            cond_str = base_cond
        else:
            cond_str = self._condition_to_string(base_cond)

        if is_negated:
            return f"!({cond_str})"
        return cond_str

    def _replace_params(self, expr: Any, param_map: dict[str, str]) -> Any:
        """将表达式中的形参替换为实参

        由于 pyslang AST 是只读的,我们不能直接替换 AST 节点。
        这个方法返回原始表达式,但会记录替换映射供后续使用。

        Args:
            expr: AST 表达式
            param_map: {形参名: 实参名}

        Returns:
            原始表达式(不可变)
        """
        # pyslang AST is immutable - cannot create new nodes
        # Return original expression; signal replacement is done at string level
        return expr

    def _extract_signals_with_mapping(self, expr: Any, param_map: dict[str, str]) -> list[tuple[str, str]]:
        """从表达式提取信号名列表(带映射信息)

        Args:
            expr: AST 表达式
            param_map: {形参名: 实参名}

        Returns:
            List[Tuple[signal_name, mapped_name]]
        """
        if expr is None:
            return []

        # 使用 SignalExpressionVisitor.get_all_signals 提取信号
        try:
            all_signals = self.cond_formatter.get_all_signals(expr)
        except Exception:
            all_signals = []

        # 映射形参到实参,过滤无效信号名(常量字面量等)
        result = []
        for sig in all_signals:
            # [FIX] 过滤无效信号名:
            # 1. 空信号
            # 2. 以数字开头 (如 8'd255)
            # 3. 包含引号 (如 '0, '1)
            # 4. 花括号开始 (如 {a, b})
            if not sig or not sig[0].isalpha() or "'" in sig or sig.startswith("{"):
                continue
            mapped = param_map.get(sig, sig)
            result.append((sig, mapped))

        return result

    def _condition_to_string(self, cond: Any) -> str:
        """将条件表达式转换为字符串"""
        if cond is None:
            return ""

        # 使用 SignalExpressionVisitor 的格式化逻辑
        try:
            return self.cond_formatter._expr_to_string(cond)
        except Exception:
            # 回退:简单字符串化
            return str(cond)

    def _compute_effective_condition_string(self, cond: Any) -> str:
        """计算有效条件字符串"""
        if cond is None:
            return ""
        return self._condition_to_string(cond)

    def _extract_assignments(self, body: Any, func_name: str) -> list[dict]:
        """提取函数体内的赋值语句"""
        assignments = []

        def collect(stmt: object) -> None:
            if stmt is None:
                return

            stmt_kind = str(getattr(stmt, "kind", ""))

            if "ExpressionStatement" in stmt_kind:
                expr = getattr(stmt, "expr", None)
                if expr and "Assignment" in str(getattr(expr, "kind", "")):
                    lhs = getattr(expr, "left", None)
                    if lhs:
                        lhs_name = self._get_name(lhs)
                        if lhs_name == func_name:
                            assignments.append({"lhs": lhs, "lhs_name": lhs_name, "rhs": getattr(expr, "right", None)})
                return

            if "SequentialBlock" in stmt_kind:
                items = getattr(stmt, "items", None)
                if items:
                    for item in items:
                        collect(item)
                return

            if "Block" in stmt_kind and "Statement" in stmt_kind:
                body = getattr(stmt, "body", None)
                if body:
                    stmt_list = getattr(body, "list", None) or list(body) if hasattr(body, "__iter__") else [body]
                    for s in stmt_list:
                        collect(s)
                return

            if "List" in stmt_kind and "Statement" in stmt_kind:
                stmt_list = getattr(stmt, "list", None)
                if stmt_list:
                    for s in stmt_list:
                        collect(s)
                return

            if "Conditional" in stmt_kind and "Statement" in stmt_kind:
                if_true = getattr(stmt, "ifTrue", None) or getattr(stmt, "statement", None)
                if if_true:
                    collect(if_true)
                if_false = getattr(stmt, "ifFalse", None)
                if if_false:
                    collect(if_false)
                return

        collect(body)
        return assignments


class ParameterReplacer:
    """参数替换 Visitor"""

    def __init__(self, param_map: dict[str, str]):
        self.param_map = param_map
        self._cache = {}  # 缓存避免重复处理

    def visit(self, node: Any) -> Any:
        """访问 AST 节点"""
        if node is None:
            return None

        node_id = id(node)
        if node_id in self._cache:
            return self._cache[node_id]

        kind = str(getattr(node, "kind", ""))

        # NamedValue - 检查是否需要替换
        if "NamedValue" in kind:
            sym = getattr(node, "symbol", None)
            if sym:
                name = _safe_attr(sym, "name", None)
                if name and name in self.param_map:
                    # 替换为实参
                    replacement = self._create_named_value(self.param_map[name], node)
                    self._cache[node_id] = replacement
                    return replacement

        # 递归遍历子节点
        for attr_name in dir(node):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(node, attr_name)
                if isinstance(attr, (list, tuple)):
                    new_list = []
                    changed = False
                    for item in attr:
                        if hasattr(item, "kind"):
                            new_item = self.visit(item)
                            if new_item is not item:
                                changed = True
                            new_list.append(new_item)
                        else:
                            new_list.append(item)
                    if changed:
                        setattr(node, attr_name, new_list)
                elif hasattr(attr, "kind"):
                    new_attr = self.visit(attr)
                    if new_attr is not attr:
                        setattr(node, attr_name, new_attr)
            except Exception:
                pass

        self._cache[node_id] = node
        return node

    def _create_named_value(self, name: str, ref_node: Any) -> Any:
        """创建 NamedValue 节点"""
        from trace.core._pyslang_compat import NamedValueExpression, ValueDriver  # [Stage 6] v10/v11 兼容

        try:
            # 尝试创建语义 AST 节点
            driver = ValueDriver()
            return NamedValueExpression(name=name, symbol=driver)
        except Exception:
            # 回退:返回原始节点
            return ref_node
