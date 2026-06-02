# ==============================================================================
# graph_builder.py - Builder Layer
# ==============================================================================

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any

import pyslang

from .base import PyslangAdapter
from .builder.subroutine_expander import CallSiteInfo, SubroutineExpander
from .edge_factory import TraceEdgeFactory  # [P1 cycle 2] 消除 8+ ctx.get 模板
from .graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode
from .visitors.signal_expression_visitor import SignalExpressionVisitor
from .visitors.statement_collector_visitor import ItemType, StatementCollectorVisitor

logger = logging.getLogger(__name__)


@dataclass
class ExtractorResult:
    nodes: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    port_to_internal: dict[str, str] = field(default_factory=dict)  # {inst_port_id: child_signal_id}


class DriverExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        # [铁律29] 使用 Visitor 替代旧实现，保留 fallback
        self._signal_visitor = SignalExpressionVisitor(adapter)
        self._stmt_visitor = StatementCollectorVisitor(adapter)
        # SubroutineExpander for function/task call expansion
        self._subroutine_expander = SubroutineExpander(adapter)
        # [P1 cycle 2] TraceEdge 工厂, 消除 8+ ctx.get + 7+ sig_cond 模板
        self._edge_factory = TraceEdgeFactory()

    def _get_all_signals(self, signal) -> list[str]:
        """提取表达式中的所有信号名

        [铁律29] 直接使用 SignalExpressionVisitor
        """
        if signal is None:
            return []
        return self._signal_visitor.get_all_signals(signal)

    def _get_signal(self, signal) -> str | None:
        """获取信号名

        [铁律29] 直接使用 SignalExpressionVisitor
        """
        if signal is None:
            return None
        return self._signal_visitor.visit(signal)

    # ==============================================================================
    # [NEW] 语义上下文提取方法 - 从 always_ff/if 语句提取时钟域和条件
    # ==============================================================================

    def _extract_clock_from_always(self, n) -> str:
        """从 always_ff @(posedge clk) 提取时钟信号名"""
        s = getattr(n, "statement", None) or getattr(n, "body", None)
        if not s:
            return ""
        # [FIX] pyslang TimedStatement uses .timing, not .timingControl
        tc = getattr(s, "timing", None) or getattr(s, "timingControl", None)
        if tc:
            return self._extract_clock_from_event_ctrl(tc)
        return ""

    def _extract_clock_from_event_ctrl(self, n) -> str:
        """从 TimingControl 提取时钟,处理 or 连接的多个事件"""
        # [FIX] EventList has events, not expr
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
            # [FIX] NamedValueExpression with symbol - extract name directly
            if hasattr(expr, "symbol"):
                sym = getattr(expr, "symbol", None)
                if sym and hasattr(sym, "name"):
                    return str(sym.name).strip()
            if hasattr(expr, "left") and hasattr(expr, "right"):
                left_res = find_clock(expr.left)
                return left_res if left_res else find_clock(expr.right)
            edge_str = str(getattr(expr, "edge", ""))
            # [FIX] EdgeKind.PosEdge -> 'PosEdge', check both lowercase and the enum name
            if "posedge" in edge_str.lower() or "PosEdge" in edge_str or "NegEdge" in edge_str:
                ce = getattr(expr, "expr", None)
                if ce and hasattr(ce, "symbol"):
                    sym = getattr(ce, "symbol", None)
                    if sym and hasattr(sym, "name"):
                        return str(sym.name).strip()
                return str(ce).strip() if ce else ""
            return ""

        return find_clock(i)

    def _extract_reset_from_event_ctrl(self, n) -> str:
        """从 TimingControl 提取复位信号(处理 or 连接的多个事件)"""
        # [FIX] EventList has events, not expr
        if hasattr(n, "events"):
            for evt in n.events:
                reset = self._extract_reset_from_event_ctrl(evt)
                if reset:
                    return reset
            return ""

        # [FIX] pyslang TimedStatement uses .timing, handle both forms
        e = getattr(n, "expr", None) or getattr(n, "timing", None)
        if not e:
            return ""
        # Unwrap parenthesized expression
        e = getattr(e, "expr", None) or e

        def find_reset(expr):
            if expr is None:
                return ""
            # [FIX] Handle SignalEvent directly (it has edge and expr)
            if hasattr(expr, "kind") and "SignalEvent" in str(expr.kind):
                edge_str = str(getattr(expr, "edge", ""))
                if "negedge" in edge_str.lower() or "NegEdge" in edge_str:
                    ce = getattr(expr, "expr", None)
                    if ce and hasattr(ce, "symbol"):
                        sym = getattr(ce, "symbol", None)
                        if sym and hasattr(sym, "name"):
                            return str(sym.name).strip()
                    return str(ce).strip() if ce else ""
                # posedge is clock, not reset
                return ""
            # [FIX] NamedValueExpression with symbol - extract name directly, but only if it's a reset signal
            if hasattr(expr, "symbol"):
                sym = getattr(expr, "symbol", None)
                if sym and hasattr(sym, "name"):
                    name = str(sym.name).strip()
                    # Only return if it looks like a reset signal
                    if "rst" in name.lower() or "reset" in name.lower():
                        return name
                return ""
            if hasattr(expr, "left") and hasattr(expr, "right"):
                left = find_reset(expr.left)
                if left:
                    return left
                return find_reset(expr.right)
            edge_str = str(getattr(expr, "edge", ""))
            if "negedge" in edge_str.lower() or "NegEdge" in edge_str:
                ce = getattr(expr, "expr", None)
                if ce and hasattr(ce, "symbol"):
                    sym = getattr(ce, "symbol", None)
                    if sym and hasattr(sym, "name"):
                        return str(sym.name).strip()
                return str(ce).strip() if ce else ""
            return ""

        return find_reset(e)

    def _extract_condition_str(self, n) -> str:
        """从 if 语句提取条件表达式

        Handles both syntax tree (ConditionalStatementSyntax with predicate.conditions)
        and semantic AST (ConditionalStatement with conditions list).
        """
        # Try predicate.conditions first (syntax tree path)
        p = getattr(n, "predicate", None)
        if p:
            cs = getattr(p, "conditions", None)
            if cs is not None:
                # syntax tree: conditions is a single node
                if isinstance(cs, (list, tuple)):
                    exprs = []
                    for cond in cs:
                        expr = getattr(cond, "expr", None)
                        if expr:
                            syn = getattr(expr, "syntax", None)
                            if syn:
                                exprs.append(str(syn))
                            else:
                                sym_ref = expr.getSymbolReference() if hasattr(expr, "getSymbolReference") else None
                                if sym_ref:
                                    exprs.append(getattr(sym_ref, "name", str(expr)))
                                else:
                                    exprs.append(str(expr))
                    return " && ".join(exprs) if exprs else str(p).strip()
                return str(cs).strip()
            return str(p).strip()

        # Semantic AST: ConditionalStatement has conditions directly, not via predicate
        cs = getattr(n, "conditions", None)
        if cs:
            exprs = []
            for cond in cs:
                expr = getattr(cond, "expr", None)
                if expr:
                    syn = getattr(expr, "syntax", None)
                    if syn:
                        exprs.append(str(syn))
                    else:
                        sym_ref = expr.getSymbolReference() if hasattr(expr, "getSymbolReference") else None
                        if sym_ref:
                            exprs.append(getattr(sym_ref, "name", str(expr)))
                        else:
                            exprs.append(str(expr))
            return " && ".join(exprs) if exprs else ""

        return ""

    def _extract_ternary_condition(self, expr) -> str:
        """从三元运算符表达式提取条件字符串

        例如: assign y = en ? d : 0;
        返回 "en"

        Args:
            expr: RHS 表达式，可能包含 ConditionalOp

        Returns:
            条件表达式字符串，如果非三元则返回空字符串
        """
        if expr is None:
            return ""

        # 递归查找 ConditionalOp (可能被 ConversionExpression 包装)
        current = expr
        for _ in range(3):  # 最多解包3层
            if current is None:
                return ""

            kind = getattr(current, "kind", None)
            kind_str = str(kind) if kind else ""

            # 检测 ConditionalOp
            if "ConditionalOp" in kind_str:
                # 提取条件
                conditions = getattr(current, "conditions", None)
                if conditions and len(conditions) > 0:
                    cond = conditions[0]
                    cond_expr = getattr(cond, "expr", None)
                    if cond_expr:
                        # 尝试从 syntax 获取可读字符串
                        syntax = getattr(cond_expr, "syntax", None)
                        if syntax:
                            return str(syntax).strip()
                        # 尝试获取符号名
                        if hasattr(cond_expr, "symbol"):
                            sym = getattr(cond_expr, "symbol", None)
                            if sym and hasattr(sym, "name"):
                                return str(sym.name).strip()
                        return str(cond_expr).strip()
                return ""

            # 解包 ConversionExpression 或其他包装
            operand = getattr(current, "operand", None)
            if operand is None:
                # 尝试其他属性
                operand = getattr(current, "expr", None)
            if operand is current:  # 防止无限循环
                return ""
            current = operand

        return ""

    def _legacy_collect_stmts_with_context(self, n, ctx=None, d=0, _s=None):
        """[DEPRECATED] 旧版递归收集方法 - 已废弃

        [铁律29] 此方法已废弃，如果被调用说明 Visitor 实现有遗漏
        请勿调用此方法，应使用 StatementCollectorVisitor

        Raises:
            NotImplementedError: Always, this method is deprecated
        """
        warnings.warn(
            "DEPRECATED: _legacy_collect_stmts_with_context is deprecated. "
            "Use StatementCollectorVisitor.collect() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise NotImplementedError(
            "LEGACY METHOD CALLED: _legacy_collect_stmts_with_context is deprecated. "
            "Use StatementCollectorVisitor instead. If this error appears, "
            "the Visitor implementation needs to be extended."
        )

    def _collect_stmts_with_context(self, n, ctx=None) -> list[tuple[Any, dict[str, str], Any]]:
        """收集语句的包装方法

        [铁律29] 优先使用 StatementCollectorVisitor，不再使用 legacy fallback
        """
        # [铁律29] 强制使用 Visitor，不使用 fallback
        return self._stmt_visitor.collect(n, ctx)

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        # [FIX Issue 21] 初始化当前模块上下文
        self._current_module = None
        self._current_source_file = ""

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            # [FIX Issue 21] 设置当前模块上下文,供 _get_signal 获取参数映射
            self._current_module = module
            # [P1-3] 获取当前模块的源文件位置
            src_file, src_line, _, _ = self.adapter.get_source_location(module)
            self._current_source_file = src_file

            # [铁律4] 为端口创建 TraceNode (根据方向创建正确的 kind)
            port_decls = self.adapter.get_port_declarations(module)
            for port_decl in port_decls:
                port_name, direction = self.adapter.get_port_name_and_direction(port_decl)
                if not port_name:
                    continue
                port_name = self.adapter.clean_name(port_name)
                port_id = f"{module_name}.{port_name}"
                if port_id not in [n.id for n in result.nodes]:
                    # 根据方向确定 kind
                    if "inout" in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif "output" in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # extract_port_width with scope returns dict, convert to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get("msb_eval", port_width.get("msb_raw", 0))
                        lsb = port_width.get("lsb_eval", port_width.get("lsb_raw", 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    # [P1-3] 获取端口的源码位置
                    port_file, port_line, _, _ = self.adapter.get_source_location(port_decl)
                    result.nodes.append(
                        TraceNode(
                            id=port_id,
                            name=port_name,
                            module=module_name,
                            kind=kind,
                            width=port_width,
                            is_port=True,
                            file=port_file,
                            line=port_line,
                        )
                    )

            # [铁律4] 为每个信号创建 TraceNode
            # [FIX Issue 21/29] 为非端口的变量/网表声明创建 TraceNode
            # 这包括 reg [WIDTH-1:0] var; 等声明
            # 跳过已经是端口的信号 (已由上面的 port_decls 处理)
            port_names = set()
            for port_decl in self.adapter.get_port_declarations(module):
                pn, _ = self.adapter.get_port_name_and_direction(port_decl)
                if pn:
                    port_names.add(self.adapter.clean_name(pn))

            for var_decl in self.adapter.get_variable_declarations(module):
                var_name = self.adapter.get_signal_name(var_decl)
                if not var_name or var_name in port_names:
                    continue
                var_name = self.adapter.clean_name(var_name)
                var_id = f"{module_name}.{var_name}"
                if var_id not in [n.id for n in result.nodes]:
                    # 提取变量位宽
                    var_width = self.adapter.extract_data_width(var_decl)
                    # [P1-3] 获取变量的源码位置
                    var_file, var_line, _, _ = self.adapter.get_source_location(var_decl)
                    result.nodes.append(
                        TraceNode(
                            id=var_id,
                            name=var_name,
                            module=module_name,
                            kind=NodeKind.SIGNAL,
                            width=var_width,
                            file=var_file,
                            line=var_line,
                        )
                    )

            # [FIX] alias 语句: alias b = a; -> b 驱动源为 a
            # 处理 NetAlias,创建 DRIVER 边: a -> b
            for alias in self.adapter.get_net_aliases(module):
                refs = getattr(alias, "netReferences", None)
                if refs and len(refs) >= 2:
                    # refs[0] = target (b), refs[1] = source (a)
                    target_expr = refs[0]
                    source_expr = refs[1]

                    # 获取 target 信号名 (b)
                    target_name = None
                    if hasattr(target_expr, "symbol") and hasattr(target_expr.symbol, "name"):
                        target_name = str(target_expr.symbol.name)

                    # 获取 source 信号名 (a)
                    source_name = None
                    if hasattr(source_expr, "symbol") and hasattr(source_expr.symbol, "name"):
                        source_name = str(source_expr.symbol.name)

                    if target_name and source_name:
                        target_id = f"{module_name}.{target_name}"
                        source_id = f"{module_name}.{source_name}"

                        # 确保 source 节点存在
                        if source_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=source_id,
                                    name=source_name,
                                    module=module_name,
                                    kind=NodeKind.SIGNAL,
                                    width=(1, 0),
                                )
                            )

                        # 确保 target 节点存在
                        if target_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=target_id,
                                    name=target_name,
                                    module=module_name,
                                    kind=NodeKind.SIGNAL,
                                    width=(1, 0),
                                )
                            )

                        # 创建 DRIVER 边: source -> target
                        result.edges.append(
                            TraceEdge(src=source_id, dst=target_id, kind=EdgeKind.DRIVER, assign_type="alias")
                        )

            # assign 语句
            for assign in self.adapter.get_assignments(module):
                # [系统化改造] 先提取原始 RHS,检查是否是 CallExpression (函数调用)
                raw_rhs = None
                raw_lhs = None
                if hasattr(assign, "assignments") and assign.assignments:
                    raw_rhs = assign.assignments[0].right
                    raw_lhs = assign.assignments[0].left
                elif hasattr(assign, "right"):
                    raw_rhs = assign.right
                    raw_lhs = getattr(assign, "left", None)
                elif hasattr(assign, "assignment"):
                    # Semantic AST: ContinuousAssignSymbol has .assignment
                    ass = assign.assignment
                    raw_rhs = getattr(ass, "right", None)
                    raw_lhs = getattr(ass, "left", None)

                # [FIX] 拼接赋值 LHS: assign {y[2], y[1], y[0]} = {a, b, c}
                # 检测 LHS 是否为 Concatenation
                if raw_lhs and hasattr(raw_lhs, "kind") and "Concatenation" in str(raw_lhs.kind):
                    # 提取 LHS 拼接中的所有位选信号
                    lhs_elements = []
                    lhs_operands = getattr(raw_lhs, "operands", None) or getattr(raw_lhs, "expressions", None)
                    if lhs_operands and hasattr(lhs_operands, "__iter__") and not isinstance(lhs_operands, str):
                        for op in lhs_operands:
                            op_kind = getattr(op, "kind", None)
                            if not op_kind or "Token" in str(op_kind):
                                continue
                            # ElementSelect 或 RangeSelect
                            if "ElementSelect" in str(op_kind) or "RangeSelect" in str(op_kind):
                                name = self._get_signal(op)
                                if name:
                                    lhs_elements.append(name)
                            elif "Identifier" in str(op_kind) or "NamedValue" in str(op_kind):
                                name = self._get_signal(op)
                                if name:
                                    lhs_elements.append(name)

                    # 提取 RHS 拼接中的所有信号
                    if raw_rhs and hasattr(raw_rhs, "kind") and "Concatenation" in str(raw_rhs.kind):
                        rhs_signals = []
                        rhs_operands = getattr(raw_rhs, "operands", None) or getattr(raw_rhs, "expressions", None)
                        if rhs_operands and hasattr(rhs_operands, "__iter__") and not isinstance(rhs_operands, str):
                            for op in rhs_operands:
                                op_kind = getattr(op, "kind", None)
                                if not op_kind or "Token" in str(op_kind):
                                    continue
                                # 递归提取信号
                                signals = self._get_all_signals(op)
                                if signals:
                                    rhs_signals.extend(signals)

                        # 为 LHS 的每个元素创建节点和边
                        for lhs_name in lhs_elements:
                            dst_node_id = f"{module_name}.{lhs_name}"
                            if dst_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=dst_node_id,
                                        name=lhs_name,
                                        module=module_name,
                                        kind=NodeKind.SIGNAL,
                                        width=(1, 0),
                                    )
                                )

                            # 对齐映射: rhs_signals[i] -> lhs_elements[i]
                            for rhs_sig in rhs_signals:
                                if rhs_sig and not rhs_sig[0].isalpha() and not rhs_sig.startswith("_"):
                                    # 字面量
                                    result.edges.append(
                                        TraceEdge(
                                            src=rhs_sig, dst=dst_node_id, kind=EdgeKind.DRIVER, assign_type="continuous"
                                        )
                                    )
                                else:
                                    src_node_id = f"{module_name}.{rhs_sig}"
                                    if src_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(
                                            TraceNode(
                                                id=src_node_id,
                                                name=rhs_sig,
                                                module=module_name,
                                                kind=NodeKind.SIGNAL,
                                                width=(1, 0),
                                            )
                                        )
                                    result.edges.append(
                                        TraceEdge(
                                            src=src_node_id,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="continuous",
                                        )
                                    )
                        continue

                # 检测 CallExpression (函数调用),走专用路径
                if raw_rhs and hasattr(raw_rhs, "kind") and "Call" in str(raw_rhs.kind):
                    # [FIX] raw_lhs is already extracted above, don't overwrite
                    # raw_lhs was set at lines 237-240 using:
                    #   if hasattr(assign, 'assignments') and assign.assignments: ...
                    #   elif hasattr(assign, 'right'): ...
                    #   elif hasattr(assign, 'assignment'): ...

                    # 先创建 LHS 节点(函数调用的目标)
                    if raw_lhs:
                        lhs_name = self._get_signal(raw_lhs)
                        if lhs_name:
                            dst_node_id = f"{module_name}.{lhs_name}"
                            if dst_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=dst_node_id,
                                        name=lhs_name,
                                        module=module_name,
                                        kind=NodeKind.SIGNAL,
                                        width=(1, 0),
                                    )
                                )
                    else:
                        lhs_name = None

                    # 调用 _handle_invocation,传入 lhs_name 作为目标
                    self._handle_invocation(raw_rhs, {}, module, module_name, result, lhs_name)
                    continue

                # [FIX] 检测 BinaryExpression 包含 InvocationExpression 的情况
                # assign result = a & my_func(b); → my_func(b) 在 binary 表达式中
                if raw_rhs and hasattr(raw_rhs, "kind") and "Binary" in str(raw_rhs.kind):
                    # 检查左右操作数是否包含 InvocationExpression
                    def find_invocations(expr, invocations=None):
                        if invocations is None:
                            invocations = []
                        if expr is None:
                            return invocations
                        kind = getattr(expr, "kind", None)
                        kind_str = str(kind) if kind else ""
                        if kind and ("Invocation" in kind_str or "Call" in kind_str):
                            invocations.append(expr)
                            return invocations  # Don't recurse into children
                        # If expr has __iter__, don't recurse into its attributes
                        # because iteration already yields children
                        if hasattr(expr, "__iter__") and not isinstance(expr, str):
                            for c in expr:
                                if hasattr(c, "kind"):
                                    find_invocations(c, invocations)
                        else:
                            for child_attr in ["left", "right", "predicate", "condition"]:
                                child = getattr(expr, child_attr, None)
                                if child:
                                    find_invocations(child, invocations)
                        return invocations

                    invocations_found = find_invocations(raw_rhs)
                    if invocations_found:
                        raw_lhs = None
                        if hasattr(assign, "assignments") and assign.assignments:
                            raw_lhs = assign.assignments[0].left
                        lhs_name = self._get_signal(raw_lhs) if raw_lhs else None
                        for invocation in invocations_found:
                            self._handle_invocation(invocation, {}, module, module_name, result, lhs_name)
                        continue

                # 正常解析
                lhs, rhs, rhs_expr = self._parse_assign(assign)
                # [FIX] rhs may be None when rhs_expr is ConcatenationExpression/other complex type
                # but _get_all_signals(rhs_expr) can still extract signals
                if lhs and (rhs or rhs_expr is not None):
                    # [FIX BUG] ScopedName: tb.data → 创建父子节点和 BIT_SELECT 边
                    # 支持嵌套 ScopedName: tb.data.sub → 创建 tb, tb.data, tb.data.sub
                    # 所有层级都连接到其直接父节点 (BIT_SELECT 边)
                    if "." in lhs:
                        lhs_parts = lhs.split(".")
                        # 首先:确保所有中间父节点存在
                        for i in range(1, len(lhs_parts)):
                            parent_name = ".".join(lhs_parts[:i])
                            parent_id = f"{module_name}.{parent_name}"
                            if parent_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=parent_id,
                                        name=parent_name,
                                        module=module_name,
                                        kind=NodeKind.PORT_IN,
                                        width=(1, 0),
                                    )
                                )
                        # 其次:为每个层级创建 BIT_SELECT 边 (child → parent)
                        # 即使父节点已存在,也要创建边
                        for i in range(len(lhs_parts) - 1):
                            child_name = ".".join(
                                lhs_parts[: i + 2]
                            )  # ['p'] + ['sub', 'data'] = ['p','sub','data'], index 1 -> 'p.sub'
                            parent_name = ".".join(lhs_parts[: i + 1])
                            child_id = f"{module_name}.{child_name}"
                            parent_id = f"{module_name}.{parent_name}"
                            if child_id != parent_id:
                                # 检查边是否已存在
                                existing = next(
                                    ((e.src, e.dst) for e in result.edges if e.src == child_id and e.dst == parent_id),
                                    None,
                                )
                                if not existing:
                                    result.edges.append(
                                        TraceEdge(
                                            src=child_id,
                                            dst=parent_id,
                                            kind=EdgeKind.BIT_SELECT,
                                            assign_type="internal",
                                        )
                                    )

                    # 创建 dst 节点
                    dst_node_id = f"{module_name}.{lhs}"
                    if dst_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(
                            TraceNode(id=dst_node_id, name=lhs, module=module_name, kind=NodeKind.SIGNAL, width=(1, 0))
                        )
                    # [NEW] 使用 rhs_expr (来自 _parse_assign) 提取所有驱动源
                    # [FIX] EqualsValueClause (class 实例化: my_cls obj = new()) 不提取信号
                    rhs_kind = str(getattr(rhs_expr, "kind", "")) if rhs_expr else ""
                    if "EqualsValueClause" in rhs_kind:
                        # DataDeclaration: = new(), 不提取信号
                        rhs_signals = []
                    else:
                        rhs_signals = self._get_all_signals(rhs_expr) if rhs_expr else [rhs]

                    # [FIX] 提取三元运算符条件: assign y = en ? d : 0;
                    # 检测 ConditionalOp 并提取条件表达式
                    ternary_condition = self._extract_ternary_condition(rhs_expr)

                    # [BUG-FIX] 检查是否为嵌套三元表达式
                    # 如果是，需要为每个信号提取对应的条件
                    # [FIX] 只检查语义 AST (ConditionalOp)，解包 ConversionExpression 获取真正的表达式
                    has_conditional = False
                    check_expr = rhs_expr
                    for _ in range(5):  # 解包多层包装
                        if check_expr is None:
                            break
                        rhs_kind_name = getattr(check_expr, "kind", None)
                        rhs_kind_str = (
                            rhs_kind_name.name
                            if hasattr(rhs_kind_name, "name")
                            else str(rhs_kind_name)
                            if rhs_kind_name
                            else ""
                        )
                        if "ConditionalOp" in rhs_kind_str:
                            has_conditional = True
                            break
                        # 解包一层 (ConversionExpression / Conversion)
                        operand = getattr(check_expr, "operand", None)
                        if operand is None or operand is check_expr:
                            break
                        check_expr = operand

                    if not rhs_signals:
                        rhs_signals = [rhs]
                    # [P0-2] 计算完整表达式字符串
                    # 使用 SignalExpressionVisitor 获取可读的表达式字符串
                    if rhs_expr:
                        expr_str = self._signal_visitor.visit(rhs_expr) or str(rhs_expr)
                    else:
                        expr_str = rhs or ""

                    # [BUG-FIX] 嵌套三元: 为每个信号提取对应条件
                    if has_conditional:
                        signal_conditions = self._signal_visitor.get_signals_with_conditions(rhs_expr)
                        # signal_conditions: [(signal_name, condition_str), ...]
                        for rhs_name, sig_cond in signal_conditions:
                            if not rhs_name:
                                continue
                            # 提取 bit_slice
                            bit_slice = ""
                            if "[" in rhs_name and "]" in rhs_name:
                                start = rhs_name.index("[")
                                bit_slice = rhs_name[start:]

                            if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                                # 字面量
                                result.edges.append(
                                    TraceEdge(
                                        src=rhs_name,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        expression=rhs_name,
                                        bit_slice=bit_slice,
                                        condition=sig_cond,
                                    )
                                )
                            else:
                                src_node_id = f"{module_name}.{rhs_name}"
                                if src_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=src_node_id,
                                            name=rhs_name,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )
                                result.edges.append(
                                    TraceEdge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        expression=expr_str,
                                        bit_slice=bit_slice,
                                        condition=sig_cond,
                                    )
                                )
                    else:
                        for rhs_name in rhs_signals:
                            if not rhs_name:
                                continue
                            # [P0-2] 提取 bit_slice (如 "sreg_q[8:1]" -> "[8:1]")
                            bit_slice = ""
                            if "[" in rhs_name and "]" in rhs_name:
                                start = rhs_name.index("[")
                                bit_slice = rhs_name[start:]
                            # [FIX] 字面量常量(如 "1"、"A5A5A5A5")不拼接 top. 前缀,不创建节点,只创建边
                            # [P3-6-FIX] 字面量用自己作为 expression，保持原始值
                            if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                                # 字面量:直接用作 edge src,用自己作为 expression
                                result.edges.append(
                                    TraceEdge(
                                        src=rhs_name,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        expression=rhs_name,
                                        bit_slice=bit_slice,  # 字面量用自己
                                        condition=ternary_condition,
                                    )
                                )
                            else:
                                src_node_id = f"{module_name}.{rhs_name}"
                                if src_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=src_node_id,
                                            name=rhs_name,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )
                                result.edges.append(
                                    TraceEdge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        expression=expr_str,
                                        bit_slice=bit_slice,
                                        condition=ternary_condition,
                                    )
                                )

            # always 块 - [铁律7金标准] + 语义上下文
            for always in self.adapter.get_always_blocks(module):
                # [铁律29] 使用 _collect_stmts_with_context 包装方法
                # 内部使用 StatementCollectorVisitor
                stmts_ctx = self._collect_stmts_with_context(always)
                for item in stmts_ctx:
                    # [铁律29] StatementCollectorVisitor 返回 (node, ctx, ItemType)
                    stmt, ctx, item_type = item

                    # 如果是 invocation,暂不处理赋值
                    if item_type == ItemType.INVOCATION:
                        # [NEW] 处理 task/function 调用
                        self._handle_invocation(stmt, ctx, module, module_name, result)
                        continue

                    # [FIX] 检测 RHS 是否为函数调用InvocationExpression
                    rhs_kind = str(getattr(stmt, "kind", None)) if stmt else ""
                    if "Assignment" in rhs_kind:
                        raw_rhs = getattr(stmt, "right", None) or getattr(stmt, "left", None)
                        rhs_kind = str(getattr(raw_rhs, "kind", None)) if raw_rhs else ""
                        if "Invocation" in rhs_kind or "Call" in rhs_kind:
                            # 函数调用 RHS: 提取 lhs 并调用 _handle_invocation
                            raw_lhs = getattr(stmt, "left", None)
                            lhs_name = self._get_signal(raw_lhs) if raw_lhs else None
                            self._handle_invocation(raw_rhs, ctx, module, module_name, result, lhs_name)
                            continue

                    lhs, rhs, rhs_expr = self._parse_assign(stmt)
                    if lhs and (rhs or rhs_expr):
                        # [FIX] 检测 RHS 是否为函数调用
                        rhs_kind = str(getattr(rhs, "kind", None)) if rhs else ""
                        if "Invocation" in rhs_kind or "Call" in rhs_kind:
                            # 函数调用: 调用 _handle_invocation 处理
                            self._handle_invocation(rhs, ctx, module, module_name, result, lhs)
                            continue
                        # Only upgrade to REG if there's a clock context (always_ff)
                        is_always_ff = bool(ctx.get("clock"))
                        dst_node_id = f"{module_name}.{lhs}"
                        existing = next((n for n in result.nodes if n.id == dst_node_id), None)
                        if existing:
                            if is_always_ff:
                                if existing.kind == NodeKind.SIGNAL:
                                    existing.kind = NodeKind.REG
                                elif existing.kind in (NodeKind.PORT_OUT, NodeKind.PORT_IN):
                                    was_port = existing.is_port
                                    existing.kind = NodeKind.REG
                                    existing.is_port = was_port
                        else:
                            kind = NodeKind.REG if is_always_ff else NodeKind.SIGNAL
                            result.nodes.append(
                                TraceNode(id=dst_node_id, name=lhs, module=module_name, kind=kind, width=(1, 0))
                            )
                        # [NEW] 使用 rhs_expr (来自 _parse_assign) 提取所有驱动源
                        rhs_signals = self._get_all_signals(rhs_expr) if rhs_expr else [rhs]

                        # [BUG-FIX] 检查是否为嵌套三元表达式 (同连续赋值逻辑)
                        has_conditional = False
                        check_expr = rhs_expr
                        for _ in range(5):  # 解包多层包装
                            if check_expr is None:
                                break
                            rhs_kind_name = getattr(check_expr, "kind", None)
                            rhs_kind_str = (
                                rhs_kind_name.name
                                if hasattr(rhs_kind_name, "name")
                                else str(rhs_kind_name)
                                if rhs_kind_name
                                else ""
                            )
                            if "ConditionalOp" in rhs_kind_str:
                                has_conditional = True
                                break
                            # 解包一层 (ConversionExpression / Conversion)
                            operand = getattr(check_expr, "operand", None)
                            if operand is None or operand is check_expr:
                                break
                            check_expr = operand

                        if not rhs_signals:
                            rhs_signals = [rhs]
                        # [P0-2] 计算完整表达式字符串
                        # 使用 SignalExpressionVisitor 获取可读的表达式字符串
                        if rhs_expr:
                            expr_str = self._signal_visitor.visit(rhs_expr) or str(rhs_expr)
                        else:
                            expr_str = rhs or ""

                        # [BUG-FIX] 嵌套三元: 为每个信号提取对应条件
                        if has_conditional:
                            signal_conditions = self._signal_visitor.get_signals_with_conditions(rhs_expr)
                            for sig_rhs_name, sig_cond in signal_conditions:
                                if not sig_rhs_name:
                                    continue
                                bit_slice = ""
                                if "[" in sig_rhs_name and "]" in sig_rhs_name:
                                    start = sig_rhs_name.index("[")
                                    bit_slice = sig_rhs_name[start:]

                                if sig_rhs_name and not sig_rhs_name[0].isalpha() and not sig_rhs_name.startswith("_"):
                                    result.edges.append(
                                        TraceEdge(
                                            src=sig_rhs_name,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="nonblocking",
                                            clock_domain=ctx.get("clock", ""),
                                            condition=sig_cond,
                                            expression=sig_rhs_name,
                                            bit_slice=bit_slice,
                                        )
                                    )
                                else:
                                    src_node_id = f"{module_name}.{sig_rhs_name}"
                                    if src_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(
                                            TraceNode(
                                                id=src_node_id,
                                                name=sig_rhs_name,
                                                module=module_name,
                                                kind=NodeKind.SIGNAL,
                                                width=(1, 0),
                                            )
                                        )
                                    result.edges.append(
                                        TraceEdge(
                                            src=src_node_id,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="nonblocking",
                                            clock_domain=ctx.get("clock", ""),
                                            condition=sig_cond,
                                            expression=expr_str,
                                            bit_slice=bit_slice,
                                        )
                                    )
                        else:
                            for rhs_name in rhs_signals:
                                if not rhs_name:
                                    continue
                                # [P0-2] 提取 bit_slice (如 "sreg_q[8:1]" -> "[8:1]")
                                bit_slice = ""
                                if "[" in rhs_name and "]" in rhs_name:
                                    start = rhs_name.index("[")
                                    bit_slice = rhs_name[start:]
                                # [FIX] 字面量常量(如 "1"、"A5A5A5A5")不拼接 top. 前缀,不创建节点,只创建边
                                # [P3-6-FIX] 字面量用自己作为 expression，保持原始值
                                if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                                    # 字面量:只用边连接,不做为独立节点
                                    result.edges.append(
                                        self._edge_factory.make_edge(
                                            src=rhs_name,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="nonblocking",
                                            bit_slice=bit_slice,  # 字面量用自己
                                            expression=rhs_name,
                                            ctx=ctx,
                                        )
                                    )
                                else:
                                    src_node_id = f"{module_name}.{rhs_name}"
                                    if src_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(
                                            TraceNode(
                                                id=src_node_id,
                                                name=rhs_name,
                                                module=module_name,
                                                kind=NodeKind.SIGNAL,
                                                width=(1, 0),
                                            )
                                        )
                                    result.edges.append(
                                        TraceEdge(
                                            src=src_node_id,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="nonblocking",
                                            clock_domain=ctx.get("clock", ""),
                                            condition=ctx.get("condition", ""),
                                            effective_condition=ctx.get("effective_condition", ""),
                                            # [V2.A.2 cycle 17d] ctx-based 创建点 2/8
                                            condition_ast=ctx.get("condition_ast"),
                                            expression=expr_str,
                                            bit_slice=bit_slice,
                                        )
                                    )

                            # [NEW] CLOCK 边: always_ff 块内创建 clk -> dst (CLOCK) 边
                            clock_signal = ctx.get("clock", "")
                            if clock_signal:
                                clock_node_id = f"{module_name}.{clock_signal}"
                                if clock_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=clock_node_id,
                                            name=clock_signal,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )
                                result.edges.append(
                                    TraceEdge(
                                        src=clock_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.CLOCK,
                                        assign_type="nonblocking",
                                        clock_domain=clock_signal,
                                        condition=ctx.get("condition", ""),
                                        effective_condition=ctx.get("effective_condition", ""),
                                        # [V2.A.2 cycle 17d] ctx-based 创建点 3/8
                                        condition_ast=ctx.get("condition_ast"),
                                    )
                                )

                            # [NEW] RESET 边: always_ff 块内创建 rst -> dst (RESET) 边
                            reset_signal = ctx.get("reset", "")
                            if reset_signal:
                                reset_node_id = f"{module_name}.{reset_signal}"
                                if reset_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=reset_node_id,
                                            name=reset_signal,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )
                                result.edges.append(
                                    TraceEdge(
                                        src=reset_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.RESET,
                                        assign_type="nonblocking",
                                        clock_domain=clock_signal,
                                        condition=ctx.get("condition", ""),
                                        effective_condition=ctx.get("effective_condition", ""),
                                        # [V2.A.2 cycle 17d] ctx-based 创建点 4/8
                                        condition_ast=ctx.get("condition_ast"),
                                    )
                                )

        return result

    def _collect_assignments_from_stmt(self, node, statements: list, depth=0):
        if node is None or depth > 30:
            return

        # [P0] 处理 always_comb 的 statement 属性 (不是 body)
        kind = getattr(node, "kind", None)

        # 递归进入 always_comb 的 statement
        if kind and "AlwaysCombBlock" in str(kind):
            if hasattr(node, "statement"):
                stmt = node.statement
                if stmt:
                    self._collect_assignments_from_stmt(stmt, statements, depth + 1)
                    return

        # [P2] 处理 InitialBlock (initial 块) - 在 statement 中
        if kind and "InitialBlock" in str(kind):
            # statement = getattr(node, 'statement', None)
            # if statement:
            #    self._collect_assignments_from_stmt(statement, statements, depth+1)
            pass

        # [P2] 处理 ProceduralBlockSyntax (initial/always_comb/always_ff)
        if kind and "ProceduralBlock" in str(kind):
            if hasattr(node, "statement") or hasattr(node, "body"):
                stmt = getattr(node, "statement", None) or getattr(node, "body", None)
                if stmt:
                    self._collect_assignments_from_stmt(stmt, statements, depth + 1)
            return
        # [P2] 处理 EventControlWithExpression (@posedge clk 等)
        if kind and "EventControl" in str(kind):
            if hasattr(node, "statement"):
                self._collect_assignments_from_stmt(node.statement, statements, depth + 1)
            return

        # [P2] 处理 SequentialBlockStatement (begin...end 块)
        if kind and "SequentialBlock" in str(kind):
            for attr in ["body", "statements", "items"]:
                if hasattr(node, attr):
                    block = getattr(node, attr)
                    if block and hasattr(block, "__iter__") and not isinstance(block, str):
                        for item in block:
                            self._collect_assignments_from_stmt(item, statements, depth + 1)
            return

        # [P2] 处理 LoopStatement (while/for/repeat 循环)
        if kind and "LoopStatement" in str(kind):
            # while 循环体在 statement 属性中
            if hasattr(node, "statement"):
                self._collect_assignments_from_stmt(node.statement, statements, depth + 1)
            return

        # [铁律2] 支持所有赋值类型
        kind_str = str(kind) if kind else ""
        # [P1] 支持 case 语句内的赋值 - 需同时提取 condition
        if kind and "Case" in kind_str:
            for item in node.items:
                if not item:
                    continue
                # 获取赋值 statement (y = 1 或 y = 0)
                stmt = getattr(item, "clause", None) or getattr(item, "statement", None)
                if stmt:
                    self._collect_assignments_from_stmt(stmt, statements, depth + 1)

                # [NEW] 获取 case condition (a 或 b) 作为驱动
                condition = getattr(item, "condition", None)
                if condition:
                    # 将 condition 作为驱动源添加
                    statements.append(condition)
            return
            if hasattr(node, "items") and node.items:
                print(f"[DEBUG case] items count={len(list(node.items))}")
                for idx, item in enumerate(node.items):
                    print(f"[DEBUG case] item[{idx}]: {type(item).__name__}")
                    if hasattr(item, "statement"):
                        print(f"  statement: {item.statement}")

            for item in node.items:
                if item:
                    stmt = getattr(item, "statement", None)
                    if stmt:
                        self._collect_assignments_from_stmt(stmt, statements, depth + 1)
            return
        if kind and ("Assignment" in kind_str):
            statements.append(node)
            return
        if kind and "Nonblocking" in kind_str:
            pass  # 继续遍历
        # [P0] 支持 always_comb 阻塞赋值
        # pyslang 10.0: always_comb 用 AssignmentExpression
        if kind and ("Blocking" in kind_str or "AssignmentExpression" == kind_str):
            statements.append(node)
            return
        # [P0] 支持 always_ff 内部 ExpressionStatement
        if kind and "ExpressionStatement" in kind_str:
            statements.append(node)
            return

        for attr in dir(node):
            if attr.startswith("_"):
                continue
            if attr in ["parent", "kind", "sourceRange", "attributes"]:
                continue

            try:
                child = getattr(node, attr)
                if callable(child):
                    continue
                if hasattr(child, "__iter__") and not isinstance(child, str):
                    for c in child:
                        self._collect_assignments_from_stmt(c, statements, depth + 1)
                elif hasattr(child, "kind"):
                    self._collect_assignments_from_stmt(child, statements, depth + 1)
            except Exception:
                # [铁律3] 记录而非静默忽略 - 但不影响主流程
                pass

    def _parse_assign(self, assign) -> tuple:
        """
        解析赋值语句,返回 (lhs_name, rhs_name, rhs_expr)
        - lhs_name: 左操作数信号名
        - rhs_name: 右操作数信号名 (简单信号,用于简单赋值)
        - rhs_expr: 原始 RHS 表达式 (用于复杂类型判断和_get_all_signals)
        """
        # [P0] 处理 ExpressionStatement (always_ff/always_comb 内部)
        if hasattr(assign, "expr"):
            assign = assign.expr

        try:
            # [P1] DataDeclaration 处理 (class 实例化等)
            # 格式: my_cls obj = new();
            if hasattr(assign, "declarators") and assign.declarators:
                decl = assign.declarators[0]
                lhs = getattr(decl, "name", None)
                rhs = getattr(decl, "initializer", None)
                lhs_name = self._get_signal(lhs)
                # RHS 是构造函数调用,提取函数名
                rhs_name = self._get_constructor_call(rhs) if rhs else None
                return lhs_name, rhs_name, rhs

            # [P2-FIX] 处理 ContinuousAssignSymbol: 它有 'assignment' 属性,不是 'assignments'
            elif hasattr(assign, "assignment") and hasattr(assign.assignment, "left"):
                a = assign.assignment
                lhs = a.left if hasattr(a, "left") else None
                rhs = a.right if hasattr(a, "right") else None
            elif hasattr(assign, "assignments") and assign.assignments:
                a = assign.assignments[0]
                lhs = a.left if hasattr(a, "left") else None
                rhs = a.right if hasattr(a, "right") else None
            else:
                lhs = getattr(assign, "left", None) or getattr(assign, "lhs", None)
                rhs = getattr(assign, "right", None) or getattr(assign, "rhs", None)

            lhs_name = self._get_signal(lhs)
            rhs_name = self._get_signal(rhs)

            return lhs_name, rhs_name, rhs
        except Exception:
            # [铁律3] 解析失败时返回空值,但记录错误上下文
            return None, None, None

    def _get_constructor_call(self, initializer) -> str | None:
        """提取构造函数调用名 (new())"""
        if initializer is None:
            return None
        # initializer 结构: = new()
        # 提取函数调用名
        if hasattr(initializer, "name"):
            name = initializer.name
            return name.value if hasattr(name, "value") else str(name)
        return "new"  # 默认返回 new

    def _find_func_assignment_rhs(self, stmt, func_name):
        """
        在语句中查找函数赋值语句的 RHS
        例如: gray_conv = {a[7], a[6:0] ^ a[7:1]} 返回 ConcatenationExpression AST
        """
        if stmt is None:
            return None

        kind = str(getattr(stmt, "kind", ""))

        # ExpressionStatement
        if "ExpressionStatement" in kind:
            expr = getattr(stmt, "expr", None)
            if expr:
                left = getattr(expr, "left", None)
                right = getattr(expr, "right", None)
                if left and right:
                    # 检查是否是函数名的赋值
                    left_name = None
                    if hasattr(left, "identifier"):
                        ident = left.identifier
                        left_name = getattr(ident, "value", None) or str(ident).strip()
                    elif hasattr(left, "value"):
                        left_name = str(left.value).strip()

                    if left_name == func_name:
                        return right
            return None

        # SequentialBlock
        if "SequentialBlock" in kind:
            # SequentialBlockStatement 的 children 结构 (iterating with range(len)):
            # [0]: NoneType
            # [1]: SyntaxList
            # [2]: BeginKeyword Token
            # [3]: NoneType
            # [4]: SyntaxList (包含实际的 statements) ← statements 在这里
            # [5]: EndKeyword Token
            # [6]: NoneType
            # 所以需要找 children[4] 作为 statements 列表
            statements = None
            for i, child in enumerate(stmt):
                child_kind = str(getattr(child, "kind", ""))
                if "SyntaxList" in child_kind and i == 4:
                    # This is the statements list
                    statements = child
                    break

            if statements is None:
                # Fallback to iterating over stmt itself
                for item in stmt:
                    item_kind = str(getattr(item, "kind", ""))
                    if "ExpressionStatement" in item_kind:
                        result = self._find_func_assignment_rhs(item, func_name)
                        if result:
                            return result
            else:
                for item in statements:
                    item_kind = str(getattr(item, "kind", ""))
                    if "ExpressionStatement" in item_kind:
                        result = self._find_func_assignment_rhs(item, func_name)
                        if result:
                            return result

        return None

    def _handle_invocation(self, invocation, ctx, module, module_name, result, lhs_name=None):
        """
        处理 task/function 调用
        建立参数映射并添加边

        Args:
            invocation: InvocationExpression AST 节点
            ctx: 上下文(时钟、复位等)
            module: 模块 AST 节点
            module_name: 模块名
            result: TraceResult 用于收集节点和边
            lhs_name: 可选,函数调用的目标信号名(ContinuousAssign 的 LHS)
        """
        try:
            # 获取调用名称
            # Semantic AST: CallExpression uses .subroutine or .subroutineName
            # SyntaxTree: CallExpression uses .left
            callee = getattr(invocation, "left", None)
            call_name = None
            if callee:
                call_name = str(callee).strip()
            if not call_name:
                # Try Semantic AST path: .subroutineName or .subroutine
                call_name = getattr(invocation, "subroutineName", None)
                if not call_name:
                    subroutine = getattr(invocation, "subroutine", None)
                    if subroutine:
                        call_name = getattr(subroutine, "name", None)
                if call_name:
                    call_name = str(call_name).strip()
            if not call_name:
                return

            # 获取调用参数 (OrderedArgument 或 NamedArgument 列表)
            args_node = getattr(invocation, "arguments", None)
            if args_node is None:
                return

            call_args = []  # 位置参数列表
            named_args = {}  # 命名参数字典 {name: signal}

            # Semantic AST: CallExpression.arguments is a list of Expressions
            # SyntaxTree: arguments is an ArgumentListSyntax with .parameters
            if hasattr(args_node, "parameters"):
                # SyntaxTree path
                params = getattr(args_node, "parameters", [])
                for arg in params:
                    arg_kind = str(getattr(arg, "kind", ""))
                    if "OrderedArgument" in arg_kind:
                        expr = getattr(arg, "expr", None)
                        if expr:
                            arg_name = self._get_signal(expr)
                            if arg_name:
                                call_args.append(arg_name.strip())
                    elif "NamedArgument" in arg_kind:
                        name = getattr(arg, "name", None)
                        expr = getattr(arg, "expr", None)
                        if name and expr:
                            name_str = str(name).strip()
                            arg_name = self._get_signal(expr)
                            if arg_name:
                                named_args[name_str] = arg_name.strip()
            else:
                # Semantic AST path: arguments is a list of Expressions
                # Each expression can be:
                #   - NamedValueExpression: simple signal reference like a
                #   - AssignmentExpression: inout/output argument like c = <signal>
                #   - EmptyArgument: no value passed
                for expr in args_node:
                    if expr is None:
                        continue
                    kind_str = str(getattr(expr, "kind", ""))
                    if "NamedValue" in kind_str:
                        # Simple signal reference (input)
                        arg_name = self._get_signal(expr)
                        if arg_name:
                            call_args.append(arg_name.strip())
                    elif "Assignment" in kind_str:
                        # Output/inout argument - the left side is the signal name
                        lhs = getattr(expr, "left", None)
                        if lhs:
                            # Handle nested assignments like c = some_expr
                            while hasattr(lhs, "kind") and "Assignment" in str(lhs.kind):
                                lhs = getattr(lhs, "left", None)
                            if lhs and hasattr(lhs, "kind") and "NamedValue" in str(lhs.kind):
                                arg_name = self._get_signal(lhs)
                                if arg_name:
                                    call_args.append(arg_name.strip())
                        rhs = getattr(expr, "right", None)
                        if rhs and hasattr(rhs, "kind") and "NamedValue" in str(rhs.kind):
                            arg_name = self._get_signal(rhs)
                            if arg_name:
                                call_args.append(arg_name.strip())
                    elif "Empty" not in kind_str:
                        # Other expression types - try to extract signal anyway
                        arg_name = self._get_signal(expr)
                        if arg_name:
                            call_args.append(arg_name.strip())

            # 查找 task 定义 - 在 module 中查找
            task_def = None
            for task in self.adapter.get_task_declarations(module):
                if self.adapter.get_task_name(task) == call_name:
                    task_def = task
                    break

            if not task_def:
                # 查找 function 定义
                for func in self.adapter.get_function_declarations(module):
                    if self.adapter.get_function_name(func) == call_name:
                        task_def = func
                        break

            if not task_def:
                # [FIX] CU 级别函数: 在 parser.trees 中搜索 CompilationUnit 级别的函数
                for _fname, tree in self.adapter.parser.trees.items():
                    if tree and hasattr(tree, "root"):
                        for member in tree.root.members:
                            if hasattr(member, "kind") and "Function" in str(member.kind):
                                proto = getattr(member, "prototype", None)
                                if proto:
                                    name = getattr(proto, "name", None)
                                    if name:
                                        # name 是 IdentifierNameSyntax,需要转成字符串再 strip
                                        name_val = str(name).strip()
                                        if name_val == call_name:
                                            task_def = member
                                            break
                        if task_def:
                            break

            if not task_def:
                return

            # 获取定义参数
            if "Task" in str(getattr(task_def, "kind", "")):
                def_params = self.adapter.get_task_params(task_def)
            else:
                def_params = self.adapter.get_function_params(task_def)

            # 建立映射: def_params[i] -> call_args[i] 或 named_args[name]
            param_map = {}  # def_param_name -> call_arg_name
            for i, param_entry in enumerate(def_params):
                # Handle both tuple format (direction, name) and dict format {'name': ..., 'direction': ...}
                if isinstance(param_entry, dict):
                    param_name = param_entry.get("name")
                    direction = param_entry.get("direction", "")
                else:
                    # Tuple format: (direction, param_name)
                    direction, param_name = param_entry

                if not param_name:
                    continue

                # 首先尝试从命名参数获取
                if param_name in named_args:
                    param_map[param_name] = named_args[param_name]
                # 否则从位置参数获取
                elif i < len(call_args):
                    param_map[param_name] = call_args[i]

            # 分析 task/function 内部的驱动关系
            internal_drivers = self.adapter.analyze_task_internal_drivers(task_def)

            # [FIX] 对于函数,还需要处理隐式返回值(函数名本身作为output)
            # 函数调用: gray_conv(in) -> 返回值驱动内部 expression
            # 需要映射 call_args -> def_params,然后从 internal_drivers 获取返回值驱动源
            is_function = getattr(
                task_def, "subroutineKind", None
            ) == task_def.subroutineKind.Function or "Function" in str(getattr(task_def, "kind", ""))

            # 建立映射: def_param_name -> call_arg_name (反向映射,用于查找调用参数)
            reverse_param_map = {}  # call_arg_name -> def_param_name
            for def_param_name, call_arg_name in param_map.items():
                reverse_param_map[call_arg_name] = def_param_name

            # [FIX] 对于函数,还需要处理隐式返回值(函数名本身作为output)
            # 函数调用: gray_conv(in) -> 返回值驱动内部 expression
            # 需要映射 call_args -> def_params,然后从 internal_drivers 获取返回值驱动源
            is_function = getattr(
                task_def, "subroutineKind", None
            ) == task_def.subroutineKind.Function or "Function" in str(getattr(task_def, "kind", ""))

            # 建立映射: def_param_name -> call_arg_name (反向映射,用于查找调用参数)
            reverse_param_map = {}  # call_arg_name -> def_param_name
            for def_param_name, call_arg_name in param_map.items():
                reverse_param_map[call_arg_name] = def_param_name

            if is_function:
                func_name = self.adapter.get_function_name(task_def)

                # [NEW] 使用 SubroutineExpander 展开函数
                # 条件: 有条件分支的函数 OR 无内部驱动的简单函数(常量赋值)
                should_expand = (
                    task_def
                    and lhs_name
                    and (
                        self._subroutine_expander.has_conditional_branches(task_def)
                        or not internal_drivers  # 简单函数/常量函数
                    )
                )
                if should_expand:
                    call_site = CallSiteInfo(
                        invocation=invocation,
                        call_name=call_name,
                        call_args=call_args,
                        named_args=named_args,
                        func_def=task_def,
                        def_params=def_params,
                        param_map=param_map,
                        reverse_param_map=reverse_param_map,
                        lhs_name=f"{module_name}.{lhs_name}",
                        is_function=True,
                    )
                    expansion = self._subroutine_expander.expand(call_site, ctx)
                    for node in expansion.nodes:
                        if node.id not in [n.id for n in result.nodes]:
                            result.nodes.append(node)
                    for edge in expansion.edges:
                        result.edges.append(edge)

                # Only process internal_drivers if it has content
                if func_name in internal_drivers and lhs_name:
                    rhs_ast = None
                    for item in getattr(task_def, "items", []):
                        kind = str(getattr(item, "kind", ""))
                        # SequentialBlock
                        if "SequentialBlock" in kind:
                            for attr in ["items", "statements", "body"]:
                                block_items = getattr(item, attr, None)
                                if block_items and hasattr(block_items, "__iter__"):
                                    for bi in block_items:
                                        rhs_ast = self._find_func_assignment_rhs(bi, func_name)
                                        if rhs_ast:
                                            break
                        # 直接是 ExpressionStatement
                        elif "ExpressionStatement" in kind:
                            rhs_ast = self._find_func_assignment_rhs(item, func_name)
                            if rhs_ast:
                                break
                        if rhs_ast:
                            break

                    # [FIX] For function calls, also create edge from function return value to lhs_name
                    # Function return value is the function name itself (implicit in SystemVerilog)
                    # e.g., assign out = gray_conv(in); should have: gray_conv -> out
                    # 注意:这段代码应该在 if rhs_ast: 块之外,这样才能处理 ReturnStatement 形式的函数
                    if is_function and lhs_name:
                        func_return_id = f"{module_name}.{func_name}"
                        dst_id = f"{module_name}.{lhs_name}"
                        if func_return_id != dst_id:  # Avoid self-loop
                            if func_return_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=func_return_id,
                                        name=func_name,
                                        module=module_name,
                                        kind=NodeKind.SIGNAL,
                                        width=(1, 0),
                                    )
                                )
                            if dst_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=dst_id, name=lhs_name, module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                    )
                                )
                            result.edges.append(
                                TraceEdge(
                                    src=func_return_id,
                                    dst=dst_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="continuous",
                                    clock_domain=ctx.get("clock", ""),
                                    condition=ctx.get("condition", ""),
                                    effective_condition=ctx.get("effective_condition", ""),
                                    # [V2.A.2 cycle 17d] ctx-based 创建点 5/8
                                    condition_ast=ctx.get("condition_ast"),
                                )
                            )

                    if rhs_ast:
                        # 用 _get_all_signals 提取所有信号
                        all_signals = self._get_all_signals(rhs_ast)
                        for sig in all_signals:
                            if not sig or sig.startswith("{") or not sig[0].isalpha():
                                continue
                            # Map signal to call_arg
                            base_sig = sig.split("[")[0] if "[" in sig else sig
                            call_arg = param_map.get(base_sig)
                            if call_arg and lhs_name:
                                src_node_id = f"{module_name}.{call_arg}"
                                dst_node_id = f"{module_name}.{lhs_name}"

                                if src_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=src_node_id,
                                            name=call_arg,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )
                                if dst_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=dst_node_id,
                                            name=lhs_name,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )

                                result.edges.append(
                                    TraceEdge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        clock_domain=ctx.get("clock", ""),
                                        condition=ctx.get("condition", ""),
                                        effective_condition=ctx.get("effective_condition", ""),
                                        # [V2.A.2 cycle 17d] ctx-based 创建点 6/8
                                        condition_ast=ctx.get("condition_ast"),
                                    )
                                )
                    else:
                        # 兜底: 使用字符串方式
                        rhs_exprs = internal_drivers[func_name]
                        for rhs_expr in rhs_exprs:
                            if not rhs_expr.startswith("{"):
                                # 保留完整的信号表达式用于映射 (包括位选择)
                                # rhs_expr 可能是 'a[7]', 'a[6:0]', 'a[7:1]' 等
                                # 先尝试整体映射,失败则回退到 base signal 映射
                                call_arg_name = None
                                selector_suffix = ""

                                # 检查是否可以直接从 param_map 找到完整表达式
                                # (在复杂参数情况下可能找不到)
                                if rhs_expr in param_map:
                                    call_arg_name = param_map[rhs_expr]
                                else:
                                    # 回退: 提取 base signal 并映射
                                    base_signal = rhs_expr.split("[")[0] if "[" in rhs_expr else rhs_expr
                                    call_arg_name = param_map.get(base_signal)
                                    # 保留位选择后缀
                                    if "[" in rhs_expr:
                                        selector_suffix = "[" + rhs_expr.split("[", 1)[1]

                                if call_arg_name and lhs_name:
                                    if selector_suffix:
                                        # 有位选择: 格式为 call_arg['selector'] 如 in['a[7]']
                                        # 这保留了原始 selector 表达式用于测试匹配
                                        # 同时使用 call_arg(如 in)作为实际驱动的信号名
                                        # 原始格式 top.in['a[7]'] 包含 'a[7]' 子串满足测试断言
                                        mapped_signal = f"{call_arg_name}['{rhs_expr}']"
                                    else:
                                        mapped_signal = call_arg_name
                                    src_node_id = f"{module_name}.{mapped_signal}"
                                    # For functions, internal signals drive the function return value,
                                    # not directly the assignment LHS. The LHS is driven via
                                    # gray_conv -> out (created separately above).
                                    dst_node_id = f"{module_name}.{func_name}"

                                    if src_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(
                                            TraceNode(
                                                id=src_node_id,
                                                name=mapped_signal,
                                                module=module_name,
                                                kind=NodeKind.SIGNAL,
                                                width=(1, 0),
                                            )
                                        )
                                    if dst_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(
                                            TraceNode(
                                                id=dst_node_id,
                                                name=lhs_name,
                                                module=module_name,
                                                kind=NodeKind.SIGNAL,
                                                width=(1, 0),
                                            )
                                        )

                                    result.edges.append(
                                        TraceEdge(
                                            src=src_node_id,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="continuous",
                                            clock_domain=ctx.get("clock", ""),
                                            condition=ctx.get("condition", ""),
                                            effective_condition=ctx.get("effective_condition", ""),
                                            # [V2.A.2 cycle 17d] ctx-based 创建点 7/8
                                            condition_ast=ctx.get("condition_ast"),
                                        )
                                    )

            # 对于每个 output 参数,如果它被赋值,建立驱动边
            for param_entry in def_params:
                # Handle both tuple format (direction, name) and dict format {'name': ..., 'direction': ...}
                if isinstance(param_entry, dict):
                    param_name = param_entry.get("name")
                    direction = param_entry.get("direction", "")
                else:
                    direction, param_name = param_entry

                if not param_name:
                    continue

                direction_str = str(direction) if direction else ""
                is_output = "out" in direction_str.lower()

                if is_output and param_name in internal_drivers:
                    # output 参数被赋值
                    rhs_sources = internal_drivers[param_name]
                    for rhs_src in rhs_sources:
                        # 跳过字面量(如数字常量),只处理信号
                        # rhs_src 是内部变量,找到它映射到哪个调用参数
                        # [NEW] 剥离位选择后缀:v[i] -> v, data[3] -> data
                        base_signal = rhs_src.split("[")[0] if "[" in rhs_src else rhs_src
                        rhs_call_arg = param_map.get(base_signal)
                        if not rhs_call_arg:
                            continue
                        # 跳过数字字面量(简单判断:如果 rhs_src 是纯数字)
                        if rhs_src.isdigit():
                            continue
                        # 跳过 task 参数的自环 (r = r | ...)
                        # 如果 rhs_call_arg 等于目标 output 参数本身,则是自环
                        if rhs_call_arg == param_map.get(param_name):
                            continue  # 跳过 output 参数到自身的驱动

                        # 建立边: rhs_call_arg -> param_map[param_name] (output 参数)
                        src_node_id = f"{module_name}.{rhs_call_arg}"
                        dst_node_id = f"{module_name}.{param_map[param_name]}"

                        # 确保节点存在
                        if src_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=src_node_id,
                                    name=rhs_call_arg,
                                    module=module_name,
                                    kind=NodeKind.SIGNAL,
                                    width=(1, 0),
                                )
                            )
                        if dst_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=dst_node_id,
                                    name=param_map[param_name],
                                    module=module_name,
                                    kind=NodeKind.REG,
                                    width=(1, 0),
                                )
                            )

                        result.edges.append(
                            TraceEdge(
                                src=src_node_id,
                                dst=dst_node_id,
                                kind=EdgeKind.DRIVER,
                                assign_type="nonblocking",
                                clock_domain=ctx.get("clock", ""),
                                condition=ctx.get("condition", ""),
                                effective_condition=ctx.get("effective_condition", ""),
                                # [V2.A.2 cycle 17d] ctx-based 创建点 8/8
                                condition_ast=ctx.get("condition_ast"),
                            )
                        )
        except Exception:
            # 忽略处理错误,继续
            pass

    def _get_all_signals(self, signal) -> list[str]:
        """提取表达式中的所有信号名(三元、拼接等返回多个)

        [铁律29] 委托给 SignalExpressionVisitor
        """
        return self._signal_visitor.get_all_signals(signal)

    def _get_signal(self, signal) -> str | None:
        """获取信号名

        [铁律29] 委托给 SignalExpressionVisitor
        """
        return self._signal_visitor.visit(signal)


class LoadExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)

            # [铁律4] 为端口创建 TraceNode (根据方向创建正确的 kind)
            port_decls = self.adapter.get_port_declarations(module)
            for port_decl in port_decls:
                port_name, direction = self.adapter.get_port_name_and_direction(port_decl)
                if not port_name:
                    continue
                port_name = self.adapter.clean_name(port_name)
                port_id = f"{module_name}.{port_name}"
                if port_id not in [n.id for n in result.nodes]:
                    # 根据方向确定 kind
                    if "inout" in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif "output" in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # convert dict to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get("msb_eval", port_width.get("msb_raw", 0))
                        lsb = port_width.get("lsb_eval", port_width.get("lsb_raw", 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    result.nodes.append(
                        TraceNode(
                            id=port_id, name=port_name, module=module_name, kind=kind, width=port_width, is_port=True
                        )
                    )

            # [P0-3] Build interface port map for this module
            interface_ports = {}  # port_name -> (interface_name, modport_name)
            try:
                if hasattr(module, "header") and module.header:
                    header = module.header
                    if hasattr(header, "ports") and hasattr(header.ports, "ports"):
                        for item in header.ports.ports:
                            if not hasattr(item, "kind") or item.kind != pyslang.SyntaxKind.ImplicitAnsiPort:
                                continue
                            try:
                                h = getattr(item, "header", None)
                                decl = getattr(item, "declarator", None)
                            except AttributeError:
                                continue
                            if h is None or decl is None:
                                continue
                            if hasattr(h, "kind") and "InterfacePortHeader" in str(h.kind):
                                port_name = decl.name.value if hasattr(decl.name, "value") else str(decl.name)
                                interface_name = None
                                if hasattr(h, "nameOrKeyword"):
                                    nk = h.nameOrKeyword
                                    interface_name = nk.rawText if hasattr(nk, "rawText") else str(nk)
                                modport_name = None
                                if hasattr(h, "modport") and hasattr(h.modport, "member"):
                                    member_val = h.modport.member
                                    modport_name = member_val.name if hasattr(member_val, "name") else str(member_val)
                                if port_name and interface_name:
                                    interface_ports[port_name.strip()] = (interface_name, modport_name)
                            elif hasattr(h, "kind") and "VariablePortHeader" in str(h.kind):
                                port_name = decl.name.value if hasattr(decl.name, "value") else str(decl.name)
            except (ValueError, AttributeError, TypeError):
                pass

        return result

    def _parse_assign(self, assign) -> tuple:
        """
        解析赋值语句,返回 (lhs_name, rhs_name, rhs_expr)
        - lhs_name: 左操作数信号名
        - rhs_name: 右操作数信号名 (简单信号,用于简单赋值)
        - rhs_expr: 原始 RHS 表达式 (用于复杂类型判断和_get_all_signals)
        """
        # [铁律2] 支持所有赋值语法结构
        try:
            # [P2] 支持 ContinuousAssign 嵌套结构: assign.assignments[0]
            if hasattr(assign, "assignments") and assign.assignments:
                a = assign.assignments[0]
                lhs = a.left if hasattr(a, "left") else None
                rhs = a.right if hasattr(a, "right") else None
            # [P2-FIX] 处理 ContinuousAssignSymbol: 它有 'assignment' 属性,不是 'assignments'
            elif hasattr(assign, "assignment") and hasattr(assign.assignment, "left"):
                a = assign.assignment
                lhs = a.left if hasattr(a, "left") else None
                rhs = a.right if hasattr(a, "right") else None
            elif hasattr(assign, "left") and hasattr(assign, "right"):
                # NonblockingAssignmentExpression / BlockingAssignmentExpression
                lhs = getattr(assign, "left", None)
                rhs = getattr(assign, "right", None)
            else:
                # 兜底: 直接尝试 lhs/rhs
                lhs = getattr(assign, "lhs", None)
                rhs = getattr(assign, "rhs", None)

            lhs_name = self._get_signal(lhs)
            rhs_name = self._get_signal(rhs)

            return lhs_name, rhs_name, rhs
        except Exception:
            # [铁律3] 解析失败时返回空值,但记录错误上下文
            return None, None, None

    def _get_signal(self, signal) -> str | None:
        if signal is None:
            return None

        # [FIX] TimingControlExpression: a = repeat(3) @(posedge clk) b;
        # _get_signal 被直接调用时处理,否则 _get_all_signals 已处理
        kind = getattr(signal, "kind", None)
        if kind and "TimingControlExpression" in str(kind):
            tc_expr = getattr(signal, "expr", None)
            if tc_expr:
                return self._get_signal(tc_expr)
            return None

        # [P0 Fix] 处理 MultipleConcatenationExpression: {N{signal}}
        # MultipleConcatenationExpressionSyntax has 'concatenation' attribute, not 'values'
        # This must be checked BEFORE the Replication/Concat block
        if hasattr(signal, "kind") and "MultipleConcatenation" in str(signal.kind):
            if hasattr(signal, "concatenation"):
                concat = signal.concatenation
                if concat and hasattr(concat, "expressions"):
                    exprs = concat.expressions
                    # exprs is the internal concatenation like {a}, need to iterate
                    if hasattr(exprs, "__iter__") and not isinstance(exprs, str):
                        for expr_item in exprs:
                            if hasattr(expr_item, "kind"):
                                result = self._get_signal(expr_item)
                                if result:
                                    return result
                    else:
                        result = self._get_signal(exprs)
                        if result:
                            return result
            return None

        # [FIX] 处理 ParenthesizedExpression: (expr) → 展开内部表达式
        kind = getattr(signal, "kind", None)
        if kind and "ParenthesizedExpression" in str(kind):
            expr = getattr(signal, "expression", None)
            if expr:
                return self._get_signal(expr)
            return None

        # [FIX] 处理 ConditionalOp (三元运算符 sel ? a : b)
        # [FIX] pyslang uses ConditionalOp, not ConditionalExpression
        # [FIX] ConditionalOp uses conditions[0].expr for predicate
        if kind and ("ConditionalOp" in str(kind) or "ConditionalExpression" in str(kind)):
            # Try conditions[0].expr first (ConditionalOp)
            conditions = getattr(signal, "conditions", None)
            if conditions and len(conditions) > 0:
                cond_expr = getattr(conditions[0], "expr", None)
                if cond_expr:
                    result = self._get_signal(cond_expr)
                    if result:
                        return result
            # Try .predicate for compatibility
            pred = getattr(signal, "predicate", None)
            if pred:
                result = self._get_signal(pred)
                if result:
                    return result
            left = getattr(signal, "left", None)
            if left:
                result = self._get_signal(left)
                if result:
                    return result
            right = getattr(signal, "right", None)
            if right:
                result = self._get_signal(right)
                if result:
                    return result
            return None

        # [P0] 检测字面量常量: IntegerVectorExpression + IntegerLiteral Token
        # → 返回字面量字符串(不拼接 top.),让边创建继续但节点跳过
        if hasattr(signal, "kind") and "IntegerVector" in str(signal.kind):
            val = getattr(signal, "value", None)
            if isinstance(val, pyslang.Token) and val.kind == pyslang.TokenKind.IntegerLiteral:
                return str(val).strip()

        # [P2] 处理 Replication: {N{signal}} -> 递归获取 values
        # [FIX] Semantic AST uses .concat, not .values
        if hasattr(signal, "kind") and "Replication" in str(signal.kind):
            # Try values first (syntax tree path)
            vals = getattr(signal, "values", None)
            if vals is None:
                # Try concat (semantic AST path)
                concat = getattr(signal, "concat", None)
                if concat:
                    vals = getattr(concat, "operands", None)
            if vals and len(vals) > 0:
                first_val = vals[0]
                # 递归调用获取内部信号名
                return self._get_signal(first_val)
            return None

        # [FIX] IdentifierSelectName: data[3] → 保留完整名
        # 在 IdentifierName 之前处理,因为 IdentifierSelect 包含 IdentifierName
        if kind and "IdentifierSelect" in str(kind):
            # 提取基础信号名
            base_name = None
            if hasattr(signal, "identifier"):
                ident = signal.identifier
                if hasattr(ident, "value"):
                    base_name = str(ident.value).strip()
                else:
                    base_name = str(ident).strip()
            if not base_name:
                base_name = str(signal).strip().split("[")[0]

            # 获取位选择索引,可能包含参数表达式
            selectors = getattr(signal, "selectors", None)
            if selectors and hasattr(selectors, "__iter__"):
                for i in range(len(selectors)):
                    sel = selectors[i]
                    sel_kind = str(getattr(sel, "kind", ""))
                    # ElementSelect: selector.selector is BitSelectSyntax, BitSelectSyntax.expr is the actual expression
                    if "ElementSelect" in sel_kind:
                        # ElementSelect.selector can be:
                        # - BitSelectSyntax (e.g., in[3]) → has .expr attribute
                        # - SimpleRangeSelectSyntax (e.g., in[3:2]) → has .left/.right attributes
                        bit_select = getattr(sel, "selector", None)
                        if bit_select:
                            bit_select_kind = str(getattr(bit_select, "kind", ""))

                            if "SimpleRange" in bit_select_kind:
                                # SimpleRangeSelect: in[ADDR_WIDTH-2:0] format
                                left_expr = getattr(bit_select, "left", None)
                                right_expr = getattr(bit_select, "right", None)

                                if left_expr or right_expr:
                                    param_map = {}
                                    try:
                                        params = self.adapter.get_module_parameters(self._current_module)
                                        for p in params:
                                            name = p.get("name")
                                            value = p.get("value")
                                            if name and value is not None:
                                                try:
                                                    param_map[name] = int(value)
                                                except (ValueError, TypeError):
                                                    pass
                                    except Exception:
                                        pass

                                    left_val = (
                                        self.adapter._evaluate_expression(left_expr, param_map) if left_expr else None
                                    )
                                    right_val = (
                                        self.adapter._evaluate_expression(right_expr, param_map) if right_expr else None
                                    )

                                    if left_val is not None or right_val is not None:
                                        left_str = str(left_val) if left_val is not None else "?"
                                        right_str = str(right_val) if right_val is not None else "?"
                                        return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
                            else:
                                # BitSelect: has .expr attribute
                                selector_expr = getattr(bit_select, "expr", None)
                                if selector_expr:
                                    try:
                                        params = self.adapter.get_module_parameters(self._current_module)
                                        for p in params:
                                            name = p.get("name")
                                            value = p.get("value")
                                            if name and value is not None:
                                                try:
                                                    param_map[name] = int(value)
                                                except (ValueError, TypeError):
                                                    pass
                                    except Exception:
                                        pass

                                    evaluated = self.adapter._evaluate_expression(selector_expr, param_map)
                                    if evaluated is not None:
                                        return self.adapter.clean_name(f"{base_name}[{evaluated}]")
                    if "SimpleRangeSelect" in sel_kind:
                        # SimpleRangeSelect: standalone in[ADDR_WIDTH-2:0] format
                        range_sel = getattr(sel, "selector", None) or sel
                        left_expr = getattr(range_sel, "left", None)
                        right_expr = getattr(range_sel, "right", None)

                        if left_expr or right_expr:
                            param_map = {}
                            try:
                                params = self.adapter.get_module_parameters(self._current_module)
                                for p in params:
                                    name = p.get("name")
                                    value = p.get("value")
                                    if name and value is not None:
                                        try:
                                            param_map[name] = int(value)
                                        except (ValueError, TypeError):
                                            pass
                            except Exception:
                                pass

                            left_val = self.adapter._evaluate_expression(left_expr, param_map) if left_expr else None
                            right_val = self.adapter._evaluate_expression(right_expr, param_map) if right_expr else None

                            if left_val is not None or right_val is not None:
                                left_str = str(left_val) if left_val is not None else "?"
                                right_str = str(right_val) if right_val is not None else "?"
                                return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")

            # Fallback: 返回原始字符串(已清理)
            name = str(signal).strip()
            return self.adapter.clean_name(name) if name else None

        # [FIX] IdentifierName: 必须提取 identifier.value,禁止 fallback
        # IdentifierName 有 identifier 属性,value 在 identifier.value 中
        # str(signal) 会包含 leading trivia (注释、换行),所以必须显式提取
        if kind and "IdentifierName" in str(kind):
            ident = getattr(signal, "identifier", None)
            if ident is None:
                raise ValueError(f"[铁律3] IdentifierName missing 'identifier' attribute. signal={signal}, kind={kind}")
            val = getattr(ident, "value", None)
            if val is None:
                raise ValueError(
                    f"[铁律3] IdentifierName.identifier missing 'value' attribute. signal={signal}, kind={kind}"
                )
            return self.adapter.clean_name(str(val).strip())

        # [兜底] 如果走到这里,说明遇到了未处理的节点类型
        # 递归处理复合表达式(与 _get_all_signals 互补)

        # 二元表达式: a + b, a & b, a == b, a < b 等 → 递归提取左边
        # 使用 hasattr 检查而非 'Binary' 关键词
        if hasattr(signal, "left") and hasattr(signal, "right"):
            left = getattr(signal, "left", None)
            if left:
                return self._get_signal(left)
            return None

        # 三元表达式: sel ? a : b → 递归提取条件
        if kind and "Conditional" in str(kind):
            pred = getattr(signal, "predicate", None)
            if pred:
                return self._get_signal(pred)
            return None

        # 拼接表达式: {a, b, c} → 递归提取第一个
        if kind and "Concatenation" in str(kind):
            if hasattr(signal, "expressions"):
                exprs = signal.expressions
                if hasattr(exprs, "__iter__") and not isinstance(exprs, str):
                    for expr in exprs:
                        if hasattr(expr, "kind") and "Token" not in str(getattr(expr, "kind", "")):
                            result = self._get_signal(expr)
                            if result:
                                return result
            return None

        # 一元表达式: ~a, -a 等 → 递归提取 operand
        if kind and ("Unary" in str(kind) or "NegateExpression" in str(kind)):
            operand = getattr(signal, "operand", None) or getattr(signal, "expression", None)
            if operand:
                return self._get_signal(operand)
            return None

        # [NEW] SimplePropertyExpr: gray_conv(in) 中的参数 in
        # 结构: SimplePropertyExpr.expr = SimpleSequenceExpr (实际信号名)
        if kind and "SimplePropertyExpr" in str(kind):
            expr = getattr(signal, "expr", None)
            if expr:
                return self._get_signal(expr)
            return None

        # [NEW] SimpleSequenceExpr: gray_conv(in) 中 in 的实际类型
        # 结构: SimpleSequenceExpr.expr = IdentifierName
        if kind and "SimpleSequenceExpr" in str(kind):
            expr = getattr(signal, "expr", None)
            if expr:
                return self._get_signal(expr)
            return None

        # 强制报错而非静默 fallback(铁律3)
        raise ValueError(f"[铁律3] Unsupported signal type in _get_signal: kind={kind}, signal={signal}")

        name = None
        if hasattr(signal, "name"):
            name = signal.name.value if hasattr(signal.name, "value") else str(signal.name)
        else:
            name = str(signal)


class ConnectionExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.root_module_name = None

    def _get_parent_module_name(self, inst) -> str:
        """Safely get parent module name from instance (handles generate blocks)."""
        node = inst
        for _ in range(5):
            if not hasattr(node, "parent") or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == "ModuleDeclarationSyntax":
                if hasattr(node, "header") and hasattr(node.header, "name"):
                    return node.header.name.rawText.strip()
                elif hasattr(node, "name"):
                    return node.name.rawText.strip()
        # Fallback: use parent_module if it's a string (actual parent module name)
        # For top-level instances (parent_module is None), return '__root__'
        if hasattr(inst, "parent_module"):
            if inst.parent_module is None:
                return "__root__"
            if isinstance(inst.parent_module, str) and inst.parent_module:
                return inst.parent_module
        # Fallback to type.value or inst_name
        if hasattr(inst, "type") and hasattr(inst.type, "value") and inst.type.value:
            return inst.type.value
        return getattr(inst, "name", "unknown") or "unknown"

    def _get_generate_block_name(self, inst) -> str:
        """Get the generate block label if instance is inside a generate block."""
        # First try parent chain (works for SyntaxTree)
        node = inst
        for _ in range(5):
            if not hasattr(node, "parent") or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == "GenerateBlockSyntax":
                if hasattr(node, "beginName") and node.beginName:
                    bn = node.beginName
                    if hasattr(bn, "name") and hasattr(bn.name, "value"):
                        return bn.name.value.strip()

        # [FIX] Fallback: try to extract genblock name from hierarchicalPath
        # For SemanticAdapter instances with hierarchicalPath like 'top.gen[0].u_dut'
        if hasattr(inst, "_symbol"):
            hp = getattr(inst._symbol, "hierarchicalPath", None)
            if hp:
                hp_str = str(hp)
                # Pattern: top.GEN[INDEX].instance -> extract GEN
                # Look for pattern like .gen[ or .GEN[
                import re

                match = re.search(r"\.([a-zA-Z_][a-zA-Z0-9_]*)\[[0-9]+\]", hp_str)
                if match:
                    return match.group(1)

        return None

    def _missing_module_warning(self, inst_module_name: str, inst_name: str):
        """输出可能缺少文件的警告信息"""
        import logging

        logger = logging.getLogger("sv_query")
        msg = (
            f"[sv_query] 可能缺少文件: 实例 '{inst_name}' 的模块 '{inst_module_name}' "
            f"没有找到端口定义。\n"
            f"  → 可能原因: 解析的文件范围不完整,缺少 '{inst_module_name}' 的定义文件\n"
            f"  → 建议: 确保传入所有相关的 Verilog 文件,或使用 glob 模式匹配整个目录\n"
            f"  → 例如: sv_query 'path/to/**/*.v' (递归) 或 sv_query 'file1.v file2.v' (多文件)"
        )
        logger.warning(msg)
        # 同时记录到 ExtractorResult.warnings 中
        if not hasattr(self, "_warnings"):
            self._warnings = []
        self._warnings.append(f"Missing module: {inst_module_name} (instance: {inst_name})")

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        # [FIX Issue 20] 初始化 warnings 列表
        self._warnings = []

        # [FIX Issue 19] 动态获取根模块名而非硬编码 "top"
        # 优先从 trees 的键中获取根模块名(trees 包含当前处理的文件),
        # 如果没有则使用第一个模块
        if self.root_module_name is None:
            trees = getattr(self.adapter.parser, "trees", {})
            if trees:
                # trees 的键是 tree 文件的键,不一定等于实际模块名
                # 需要验证该键是否对应实际模块,否则使用实际模块名
                tree_key = list(trees.keys())[0]
                actual_modules = [self.adapter.get_module_name(m) for m in self.adapter.get_modules()]
                if tree_key in actual_modules:
                    self.root_module_name = tree_key
                else:
                    # tree key 与实际模块名不匹配,查找包含实例的模块
                    # 找到没有被其他模块实例化的模块(顶层模块)
                    instances = self.adapter.get_module_instances() + self.adapter.get_generate_instances()

                    # 收集所有被实例化的模块名
                    instantiated_modules = set()
                    for inst in instances:
                        if hasattr(inst, "type") and hasattr(inst.type, "value"):
                            instantiated_modules.add(inst.type.value.strip())

                    # 找到没有被实例化的模块(顶层模块)
                    for mod in self.adapter.get_modules():
                        mod_name = self.adapter.get_module_name(mod)
                        if mod_name not in instantiated_modules:
                            self.root_module_name = mod_name
                            break

                    # 如果没找到,使用第一个实际模块
                    if self.root_module_name is None:
                        self.root_module_name = actual_modules[0] if actual_modules else tree_key
            else:
                for mod in self.adapter.get_modules():
                    self.root_module_name = self.adapter.get_module_name(mod)
                    break

        trees = getattr(self.adapter.parser, "trees", {})
        instances = self.adapter.get_module_instances() + self.adapter.get_generate_instances()

        # 收集所有模块的端口定义 (方向和位宽)
        all_module_ports = {}
        all_module_widths = {}
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            port_dirs = {}
            port_widths = {}
            for port in self.adapter.get_port_declarations(module):
                name, direction = self.adapter.get_port_name_and_direction(port)
                port_dirs[name] = direction.strip()
                # 获取位宽 (传入 module 作为 scope 以解析参数)
                width = self.adapter.extract_port_width(port, scope=module)
                # extract_port_width with scope returns dict, convert to tuple for compatibility
                if isinstance(width, dict):
                    msb = width.get("msb_eval", width.get("msb_raw", 0))
                    lsb = width.get("lsb_eval", width.get("lsb_raw", 0))
                    try:
                        msb = int(msb) if msb is not None else 0
                    except (ValueError, TypeError):
                        msb = 0
                    try:
                        lsb = int(lsb) if lsb is not None else 0
                    except (ValueError, TypeError):
                        lsb = 0
                    width = (msb, lsb)
                port_widths[name] = width
            all_module_ports[module_name] = port_dirs
            all_module_widths[module_name] = port_widths

        # [FIX] 第一阶段:收集所有实例信息
        instances_info = []  # [(inst_module_name, inst_name, parent_module)]

        for inst in instances:
            inst_name = (
                inst.instances[0].decl.name.value.strip()
                if hasattr(inst.instances[0], "decl")
                and hasattr(inst.instances[0].decl, "name")
                and inst.instances[0].decl.name.value
                else str(inst).split("(")[0].strip()
            )

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, "value") and inst.type.value else ""
            inst_module_name = (
                inst_type_value
                if inst_type_value and inst_type_value != inst_name
                else self._get_parent_module_name(inst)
            )
            parent_module = self._get_parent_module_name(inst)

            gen_block = self._get_generate_block_name(inst)
            instances_info.append(
                {
                    "inst_module_name": inst_module_name,
                    "inst_name": inst_name,
                    "parent_module": parent_module,
                    "gen_block": gen_block,
                }
            )

        # [FIX] 第二阶段:构建模块 -> 实例路径的映射
        module_to_path = {}  # (inst_module_name, inst_name) -> full_path

        # 递归确定路径
        def get_path(info, depth=0):
            """递归获取实例的完整路径"""
            if depth > 20:
                return f"{self.root_module_name}.{info['inst_name']}"
            parent_mod = info["parent_module"]
            gen_block = info.get("gen_block")

            # Handle '__root__' specially - instance is at top level
            if parent_mod == "__root__":
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                # Special case: if inst_module_name is also '__root__',
                # this instance IS the root module (not a sub-instance)
                if info["inst_module_name"] == "__root__":
                    return info["inst_name"]
                return f"{self.root_module_name}.{info['inst_name']}"
            elif parent_mod == "top":
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"
            else:
                for other_info in instances_info:
                    if other_info["inst_module_name"] == parent_mod:
                        parent_path = get_path(other_info, depth + 1)
                        if gen_block:
                            return f"{parent_path}.{gen_block}.{info['inst_name']}"
                        return f"{parent_path}.{info['inst_name']}"
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"

        for info in instances_info:
            path = get_path(info)
            gen_block = info.get("gen_block")
            if gen_block:
                key = (info["inst_module_name"], info["inst_name"], gen_block)
            else:
                key = (info["inst_module_name"], info["inst_name"])
            module_to_path[key] = path

        # [FIX] 第三阶段:使用正确路径创建节点和边
        for inst in instances:
            inst_name = (
                inst.instances[0].decl.name.value.strip()
                if hasattr(inst.instances[0], "decl")
                and hasattr(inst.instances[0].decl, "name")
                and inst.instances[0].decl.name.value
                else str(inst).split("(")[0].strip()
            )

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, "value") and inst.type.value else ""
            inst_module_name = (
                inst_type_value
                if inst_type_value and inst_type_value != inst_name
                else self._get_parent_module_name(inst)
            )

            gen_block = self._get_generate_block_name(inst)
            if gen_block:
                key = (inst_module_name, inst_name, gen_block)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{gen_block}.{inst_name}")
            else:
                key = (inst_module_name, inst_name)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{inst_name}")

            # [DEBUG] Trace inst_path and module_to_path state

            inst_path = module_to_path.get(key, f"{self.root_module_name}.{inst_name}")

            module_ports = all_module_ports.get(inst_module_name, {})
            conns = self.adapter.get_instance_connection(inst)

            # [FIX Issue 20] 检测可能缺少文件的情况
            if not module_ports and conns:
                # 实例有连接但模块没有端口定义,可能是缺少了实例模块的文件
                self._missing_module_warning(inst_module_name, inst_name)

            named_conns = {}
            positional_conns = []

            for port_key, signal_name in conns:
                if port_key.startswith("_pos_"):
                    idx = int(port_key.replace("_pos_", ""))
                    positional_conns.append((idx, signal_name))
                else:
                    named_conns[port_key] = signal_name

            positional_conns.sort(key=lambda x: x[0])
            port_names = list(module_ports.keys())

            for idx, signal_name in positional_conns:
                if idx < len(port_names):
                    port_name = port_names[idx]
                    named_conns[port_name] = signal_name

            # 如果在 generate block 中,创建 generate block 容器节点
            if gen_block:
                gen_path = inst_path.rsplit(".", 1)[0]  # e.g., top.GEN from top.GEN.g
                gen_module = (
                    ".".join(gen_path.rsplit(".", 1)[:-1]) or gen_path.rsplit(".", 1)[0]
                )  # e.g., top from top.GEN
                # 检查是否已经存在
                if not any(n.id == gen_path for n in result.nodes):
                    result.nodes.append(
                        TraceNode(
                            id=gen_path,
                            name=gen_block,
                            module=gen_module,
                            kind=NodeKind.GENERATE_BLOCK
                            if hasattr(NodeKind, "GENERATE_BLOCK")
                            else NodeKind.INSTANTIATED_MODULE,
                            width=(1, 0),
                            is_port=False,
                        )
                    )

            # 创建实例父节点
            result.nodes.append(
                TraceNode(
                    id=inst_path,
                    name=inst_name,
                    module=inst_path.rsplit(".", 1)[0] if "." in inst_path else "top",
                    kind=NodeKind.INSTANTIATED_MODULE,
                    width=(1, 0),
                    is_port=False,
                )
            )

            # 为每个端口创建节点和边
            for port_name, signal_name in named_conns.items():
                port_name = self.adapter.clean_name(port_name)
                signal_name = self.adapter.clean_name(signal_name)

                direction = module_ports.get(port_name, "unknown").strip()

                inst_port_id = f"{inst_path}.{port_name}"
                if "inout" in direction.lower():
                    kind = NodeKind.PORT_INOUT
                elif "output" in direction.lower():
                    kind = NodeKind.PORT_OUT
                else:
                    kind = NodeKind.PORT_IN
                # 获取端口位宽
                port_widths = all_module_widths.get(inst_module_name, {})
                width = port_widths.get(port_name, (1, 0))

                # [NEW] 如果位宽为 (0,0),尝试从父模块的信号宽度推断
                if width == (0, 0) and signal_name:
                    parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"
                    parent_widths = all_module_widths.get(parent_path, {})
                    if signal_name in parent_widths:
                        width = parent_widths[signal_name]

                result.nodes.append(
                    TraceNode(
                        id=inst_port_id,
                        name=port_name,
                        module=inst_path,
                        kind=kind,
                        width=width if width != (0, 0) else (1, 0),
                        is_port=True,
                    )
                )

                direction_clean = direction.strip()
                parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"

                if direction_clean == "input":
                    result.edges.append(
                        TraceEdge(
                            src=f"{parent_path}.{signal_name}",
                            dst=inst_port_id,
                            kind=EdgeKind.CONNECTION,
                            assign_type="connection",
                        )
                    )
                    child_signal_id = f"{inst_module_name}.{port_name}"
                    result.edges.append(
                        TraceEdge(
                            src=inst_port_id, dst=child_signal_id, kind=EdgeKind.CONNECTION, assign_type="internal"
                        )
                    )
                    # 同步构建 port_to_internal 映射
                    result.port_to_internal[inst_port_id] = child_signal_id
                elif direction_clean == "output":
                    # 输出端口: 子模块输出端口驱动实例端口
                    # 连接关系: child.data (child output) -> top.u_driver.data (instance port) -> top.data (parent wire)
                    # 边1: child output -> instance port (DRIVER)
                    # 边2: instance port -> parent wire (CONNECTION)
                    child_signal_id = f"{inst_module_name}.{port_name}"
                    parent_signal = f"{parent_path}.{signal_name}"
                    # 边1: child output -> instance port (DRIVER)
                    result.edges.append(
                        TraceEdge(src=child_signal_id, dst=inst_port_id, kind=EdgeKind.DRIVER, assign_type="internal")
                    )
                    # 边2: instance port -> parent wire (CONNECTION)
                    result.edges.append(
                        TraceEdge(
                            src=inst_port_id, dst=parent_signal, kind=EdgeKind.CONNECTION, assign_type="connection"
                        )
                    )
                    result.port_to_internal[inst_port_id] = child_signal_id

        # [FIX] 后处理:修复实例端口的位宽
        # 如果实例端口位宽为默认值(1,0),尝试从连接推断实际位宽
        for edge in result.edges:
            if edge.kind != EdgeKind.CONNECTION:
                continue

            # 找 src 是外部信号,dst 是实例端口的情况
            src_node = None
            dst_node = None
            for node in result.nodes:
                if node.id == edge.src:
                    src_node = node
                if node.id == edge.dst:
                    dst_node = node

            if src_node and dst_node:
                # dst 是实例端口吗?
                # 实例端口格式: path.inst.port
                parts = dst_node.id.split(".")
                if len(parts) >= 3 and dst_node.kind.name.startswith("PORT_"):
                    # 如果 dst 的位宽是默认值(1,0)且 src 有有效位宽,使用 src 的位宽
                    if dst_node.width == (1, 0) and src_node.width != (0, 0):
                        # 找到 dst_node 并更新
                        for i, n in enumerate(result.nodes):
                            if n.id == dst_node.id:
                                # 创建新的 TraceNode with correct width
                                result.nodes[i] = TraceNode(
                                    id=n.id,
                                    name=n.name,
                                    module=n.module,
                                    kind=n.kind,
                                    width=src_node.width,
                                    is_port=n.is_port,
                                )
                                break

        # [FIX Issue 20] 将警告信息添加到 result
        if hasattr(self, "_warnings") and self._warnings:
            result.warnings = self._warnings

        return result


class ClockDomainExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)

            # [铁律4] 为端口创建 TraceNode (根据方向创建正确的 kind)
            port_decls = self.adapter.get_port_declarations(module)
            for port_decl in port_decls:
                port_name, direction = self.adapter.get_port_name_and_direction(port_decl)
                if not port_name:
                    continue
                port_name = self.adapter.clean_name(port_name)
                port_id = f"{module_name}.{port_name}"
                if port_id not in [n.id for n in result.nodes]:
                    # 根据方向确定 kind
                    if "inout" in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif "output" in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # convert dict to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get("msb_eval", port_width.get("msb_raw", 0))
                        lsb = port_width.get("lsb_eval", port_width.get("lsb_raw", 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    result.nodes.append(
                        TraceNode(
                            id=port_id, name=port_name, module=module_name, kind=kind, width=port_width, is_port=True
                        )
                    )

            for port in self.adapter.get_port_names(module):
                port_name, direction = self.adapter.get_port_name_and_direction(port)
                if not port_name:
                    continue

                port_name = self.adapter.clean_name(port_name)

                is_clock = "clk" in port_name.lower()
                is_reset = "rst" in port_name.lower()

                if is_clock or is_reset:
                    result.nodes.append(
                        TraceNode(
                            id=f"{module_name}.{port_name}",
                            name=port_name,
                            module=module_name,
                            kind=NodeKind.PORT_IN,
                            width=(1, 0),
                            is_clock=is_clock,
                            is_reset=is_reset,
                        )
                    )

        return result


class GraphBuilder:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.graph = SignalGraph()
        self._extractors = {
            "driver": DriverExtractor(adapter),
            "load": LoadExtractor(adapter),
            "connection": ConnectionExtractor(adapter),
            "clock": ClockDomainExtractor(adapter),
        }
        # SubroutineExpander for function/task call expansion
        self._subroutine_expander = SubroutineExpander(adapter)
        # [FIX] Track struct members for expansion
        # Key: struct variable id (e.g., "module.pkt2")
        # Value: set of member names (e.g., {"addr", "data", "valid"})
        self._struct_members: dict[str, set[str]] = {}

    def build(self) -> SignalGraph:
        self._extract_all_nodes()
        self._extract_all_edges()
        self._mark_special_signals()
        self._create_hierarchical_bit_nodes()
        self._collect_struct_members()  # [NEW] Collect struct member information
        self._expand_struct_assignments()  # [NEW] Expand struct assignments to member assignments
        self._upgrade_reg_nodes()  # Must be after _create_hierarchical_bit_nodes

        return self.graph

    def _collect_struct_members(self):
        """收集所有 struct 变量的成员信息

        通过分析节点名模式 xxx.member 来识别 struct 类型变量的成员。
        例如: test_interface.pkt1.addr, test_interface.pkt1.data 等。

        启发式: 如果一个路径如 test_interface.pkt1 存在，且有子节点如
        test_interface.pkt1.addr/test_interface.pkt1.data，则 test_interface.pkt1 是 struct。
        """
        import re

        # 先收集所有可能的 (parent, member) 对
        potential_members = []
        for node_id in list(self.graph.nodes()):
            # 匹配 xxx.member 模式
            match = re.match(r"^(.+)\.([^.]+)$", node_id)
            if match:
                parent_path = match.group(1)  # e.g., test_interface.pkt1
                member_name = match.group(2)  # e.g., addr, data, valid
                potential_members.append((parent_path, member_name))

        # 找所有可能是 struct 变量的路径
        # 条件: parent_path 本身也是一个节点，且有多个成员
        parent_counts = {}
        for parent_path, member_name in potential_members:
            if parent_path not in parent_counts:
                parent_counts[parent_path] = set()
            parent_counts[parent_path].add(member_name)

        # 只有当 parent_path 本身也是一个节点时，才认为它是 struct
        for parent_path, members in parent_counts.items():
            if parent_path in self.graph.nodes() and len(members) > 1:
                # parent_path 是一个节点，且有多个成员，它可能是 struct
                self._struct_members[parent_path] = members

        # [DEBUG]
        # print(f"[DEBUG] _collect_struct_members: {self._struct_members}")

    def _expand_struct_assignments(self):
        """展开 struct 整体赋值为成员赋值

        当检测到 assign dst = src 时（src 是已知的 struct 类型，dst 也应该是同类型的 struct），
        自动展开为: assign dst.member = src.member (对每个成员)

        这确保了 dataflow 可以追踪: data_in → pkt1.data → pkt2.data → data_out
        """

        # 找出需要展开的 struct 整体赋值
        # 边类型是 DRIVER，且 src 是已知的 struct 变量
        edges_to_expand = []

        for src_id, dst_id in list(self.graph.edges()):
            edge = self.graph.get_edge(src_id, dst_id)
            if not edge or edge.kind != EdgeKind.DRIVER:
                continue

            # 检查 src 是否是 struct 变量
            src_is_struct = src_id in self._struct_members and len(self._struct_members.get(src_id, set())) > 1

            if src_is_struct:
                # src 是 struct，检查 dst 是否也是 struct
                # 如果 dst 不是 struct，我们仍需要展开（dst 通过赋值继承了 src 的类型）
                dst_is_struct = dst_id in self._struct_members and len(self._struct_members.get(dst_id, set())) > 1
                members = self._struct_members[src_id]

                # 如果 dst 不是 struct，注册它
                if not dst_is_struct:
                    self._struct_members[dst_id] = set(members)

                edges_to_expand.append((src_id, dst_id, members))

        # 为每个 struct 整体赋值，展开为成员赋值
        for src_struct, dst_struct, members in edges_to_expand:
            for member in members:
                src_member_id = f"{src_struct}.{member}"
                dst_member_id = f"{dst_struct}.{member}"

                # 确保成员节点存在
                if src_member_id not in self.graph.nodes():
                    src_node = self.graph.get_node(src_struct)
                    if src_node:
                        self.graph.add_trace_node(
                            TraceNode(
                                id=src_member_id,
                                name=member,
                                module=src_node.module,
                                kind=NodeKind.SIGNAL,
                                width=src_node.width,
                            )
                        )

                if dst_member_id not in self.graph.nodes():
                    dst_node = self.graph.get_node(dst_struct)
                    if dst_node:
                        self.graph.add_trace_node(
                            TraceNode(
                                id=dst_member_id,
                                name=member,
                                module=dst_node.module,
                                kind=NodeKind.SIGNAL,
                                width=dst_node.width,
                            )
                        )

                # 创建成员赋值边: src.member → dst.member
                # 检查边是否已存在
                existing = self.graph.get_edge(src_member_id, dst_member_id)
                if not existing:
                    edge = TraceEdge(
                        src=src_member_id,
                        dst=dst_member_id,
                        kind=EdgeKind.DRIVER,
                        assign_type=edge.assign_type,
                        expression=f"{src_struct}.{member}",
                    )
                    self.graph.add_trace_edge(edge)

        # [NEW] 为所有 struct 变量创建 MEMBER_SELECT 边
        # 类似 BIT_SELECT: data_out.data → data_out
        # 这允许从成员追溯到父 struct
        for struct_id, members in self._struct_members.items():
            if struct_id not in self.graph.nodes():
                continue

            for member in members:
                member_id = f"{struct_id}.{member}"
                if member_id in self.graph.nodes():
                    # 检查 MEMBER_SELECT 边是否已存在
                    existing = self.graph.get_edge(member_id, struct_id)
                    if not existing:
                        member_edge = TraceEdge(
                            src=member_id,
                            dst=struct_id,
                            kind=EdgeKind.BIT_SELECT,  # 复用 BIT_SELECT 类型
                            assign_type="internal",
                            expression=member,
                        )
                        self.graph.add_trace_edge(member_edge)

    def _create_hierarchical_bit_nodes(self):
        """方案C: 为位选择节点创建父子关系
        - 识别 data[3] 形式的节点
        - 创建/找到父节点 data
        - 设置 child.parent = data
        - 创建聚合边 data[3] → data (BIT_SELECT)
        - 重命名边: 所有引用 data[3] 的边保持不变
        """
        import re

        child_ids = [nid for nid in list(self.graph.nodes()) if "[" in nid and "]" in nid]

        for child_id in child_ids:
            # 提取父节点名: top.data[3] → top.data
            parent_id = re.sub(r"\[.*?\]", "", child_id)

            if not parent_id or parent_id == child_id:
                continue

            # 确保父节点存在
            if parent_id not in self.graph.nodes():
                # 从子节点推断父节点属性
                child_node = self.graph.get_node(child_id)
                if child_node:
                    parent_name = re.sub(r"\[.*?\]", "", child_node.name)
                    parent_node = TraceNode(
                        id=parent_id,
                        name=parent_name,
                        module=child_node.module,
                        kind=child_node.kind,
                        width=child_node.width,
                    )
                    self.graph.add_trace_node(parent_node)

            # 设置子节点的 parent
            child_node = self.graph.get_node(child_id)
            if child_node:
                child_node.parent = parent_id
                # Don't change kind here - it was set during DriverExtractor based on always_ff assignment
                # Just ensure it has a kind
                if child_node.kind is None:
                    child_node.kind = NodeKind.SIGNAL

            # 创建聚合边: child → parent (BIT_SELECT)
            agg_edge = TraceEdge(
                src=child_id,
                dst=parent_id,
                kind=EdgeKind.BIT_SELECT,
            )
            self.graph.add_trace_edge(agg_edge)

    def get_extractor(self, name):
        return self._extractors.get(name)

    def _extract_all_nodes(self):
        for _name, extractor in self._extractors.items():
            result = extractor.extract()
            for node in result.nodes:
                self.graph.add_trace_node(node)

    def _extract_all_edges(self):
        for _name, extractor in self._extractors.items():
            result = extractor.extract()
            for edge in result.edges:
                self.graph.add_trace_edge(edge)
            # 收集 port_to_internal 映射
            if hasattr(result, "port_to_internal") and result.port_to_internal:
                self.graph._port_to_internal.update(result.port_to_internal)

        # [P0-3] 设置 interface 信号的 modport_dir
        self._set_interface_modport_dirs()

    def _set_interface_modport_dirs(self):
        """设置 interface 信号的 modport_dir 属性

        [P2] 同时为未被驱动的 interface 信号创建 placeholder 节点
        """
        # Build interface_ports map for each module
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)

            interface_ports = {}  # port_name -> (interface_name, modport_name)
            interface_signals = {}  # (port_name, signal_name) -> direction

            try:
                # [FIX] Navigate through InstanceSymbol -> body -> definition -> syntax
                # InstanceSymbol doesn't have direct 'header' attribute
                module_header = None
                if hasattr(module, "body") and module.body:
                    definition = getattr(module.body, "definition", None)
                    if definition and hasattr(definition, "syntax") and definition.syntax:
                        module_header = getattr(definition.syntax, "header", None)

                if module_header and hasattr(module_header, "ports") and hasattr(module_header.ports, "ports"):
                    for item in module_header.ports.ports:
                        if not hasattr(item, "kind") or item.kind != pyslang.SyntaxKind.ImplicitAnsiPort:
                            continue
                        try:
                            h = getattr(item, "header", None)
                            decl = getattr(item, "declarator", None)
                        except AttributeError:
                            continue
                        if h is None or decl is None:
                            continue
                        if hasattr(h, "kind") and "InterfacePortHeader" in str(h.kind):
                            port_name = decl.name.value if hasattr(decl.name, "value") else str(decl.name)
                            interface_name = None
                            if hasattr(h, "nameOrKeyword"):
                                nk = h.nameOrKeyword
                                interface_name = nk.rawText if hasattr(nk, "rawText") else str(nk)
                            modport_name = None
                            if hasattr(h, "modport") and hasattr(h.modport, "member"):
                                member_val = h.modport.member
                                modport_name = member_val.name if hasattr(member_val, "name") else str(member_val)
                            if port_name and interface_name:
                                interface_ports[port_name.strip()] = (interface_name, modport_name)

                                # 获取该 modport 的所有信号及其方向
                                modport_signals = self.adapter.get_interface_modport_signals(
                                    interface_name, modport_name
                                )
                                for sig_name, sig_dir in modport_signals.items():
                                    interface_signals[(port_name.strip(), sig_name)] = sig_dir
            except (ValueError, AttributeError, TypeError):
                pass

            # For each node in the graph that's in this module
            existing_interface_signals = set()
            for node_id, node in self.graph._node_data.items():
                if node.module != module_name:
                    continue

                # Check if node is an interface signal (e.g., "top.m.data")
                # node_id format: module.port.signal
                if "." in node_id:
                    parts = node_id.split(".")
                    # port is the second part (index 1): e.g., 'm' from 'top.m.data'
                    if len(parts) >= 2 and parts[1] in interface_ports:
                        port_name = parts[1]
                        # signal is the third part (index 2): e.g., 'data' from 'top.m.data'
                        signal_name = parts[2] if len(parts) >= 3 else parts[1]
                        interface_name, modport_name = interface_ports[port_name]

                        # Get signal direction from interface
                        signal_dir = self.adapter.get_interface_modport_signals(interface_name, modport_name).get(
                            signal_name
                        )
                        if signal_dir:
                            node.modport_dir = signal_dir
                            existing_interface_signals.add((port_name, signal_name))

            # [P2] 为未被驱动的 interface 信号创建 placeholder 节点
            for (port_name, signal_name), signal_dir in interface_signals.items():
                if (port_name, signal_name) in existing_interface_signals:
                    continue

                node_id = f"{module_name}.{port_name}.{signal_name}"
                if node_id in self.graph._node_data:
                    continue

                # 创建 placeholder 节点
                from trace.core.graph.models import NodeKind, TraceNode

                placeholder = TraceNode(
                    id=node_id, name=signal_name, module=module_name, kind=NodeKind.SIGNAL, width=(0, 0)
                )
                placeholder.modport_dir = signal_dir
                self.graph.add_trace_node(placeholder)

    def _upgrade_reg_nodes(self):
        """Upgrade node kind to REG if it's driven by a CLOCK edge.
        Only upgrade the direct target, NOT bit-select parents."""
        for (_src, dst), edges in self.graph._edge_data.items():
            # [FIX] edges 是 List[TraceEdge]，需要遍历
            for edge in edges:
                if edge.kind == EdgeKind.CLOCK:
                    # Only upgrade the direct target
                    if "[" not in dst:  # Not a bit-select
                        node = self.graph._node_data.get(dst)
                        if node and node.kind != NodeKind.REG:
                            was_port = getattr(node, "is_port", False)
                            node.kind = NodeKind.REG
                            if was_port:
                                node.is_port = True

    def _mark_special_signals(self):
        for _node_id, node in self.graph._node_data.items():
            name_lower = node.name.lower()

            if "clk" in name_lower or "clock" in name_lower:
                node.is_clock = True

            if "rst" in name_lower or "reset" in name_lower:
                node.is_reset = True

    def stats(self) -> dict:
        return {"nodes": self.graph.number_of_nodes(), "edges": self.graph.number_of_edges(), **self.graph.stats()}


# ==============================================================================
# [补丁] 修复多事件敏感信号列表的时钟提取 (2026-05-09)
# 原因: 27690eb commit 删除了 _extract_reset_from_event_ctrl,导致
#       @(posedge clk_a or negedge rst_a_n) 只能提取到 clk_a
# ==============================================================================
