# ==============================================================================
# driver_extractor.py - Driver 提取器 (从 graph_builder.py 物理拆分, P1 cycle 8)
#
# 职责: 解析 SV always 块 / assign 语句, 提取 driver / condition / expression
#       关系, 返回 ExtractorResult.
#
# 拆分背景:
# - graph_builder.py 3054 行含 5 个类, DriverExtractor 1742 行
# - 之前 P1 cycle 1-3 改用 TraceEdgeFactory 消除 12+ 模板重复, 物理拆分现在
#   变"自然结果" (按 v2 plan 结构改完, 拆分变成低风险)
# - 0 逻辑改动, 0 净代码
#
# 兼容性:
# - graph_builder.py 加 re-export, 现有 import `from trace.core.graph_builder
#   import DriverExtractor` 仍工作
# - trace.core.__init__.py 通过 graph_builder 间接 re-export
# - cli/commands/expression.py 直接 import graph_builder, 仍工作
# ==============================================================================

import logging
import warnings
from typing import Any

from .base import PyslangAdapter
from .builder.subroutine_expander import CallSiteInfo, SubroutineExpander
from .edge_factory import TraceEdgeFactory
from .extractor_models import ExtractorResult  # [P1 cycle 9] 共享
from .graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode
from .visitors.signal_expression_visitor import SignalExpressionVisitor
from .visitors.statement_collector_visitor import ItemType, StatementCollectorVisitor

logger = logging.getLogger(__name__)


# [P1 cycle 8/9] ExtractorResult 移到了 extractor_models.py (避免循环 import)
# 这里 re-export 保持向后兼容 (from trace.core.driver_extractor import ExtractorResult)
__all__ = ["DriverExtractor", "ExtractorResult"]


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
        # [Phase 4 2026-07-11] If set, walk these (instance_path, module) pairs
        # instead of iterating all modules. This produces instance-aware signal IDs.
        # None = legacy behavior (use all modules with type name as prefix).
        self._instance_paths: list[tuple[str, Any]] | None = None

    def _append_edge(
        self,
        result,
        src: str,
        dst: str,
        kind: EdgeKind = EdgeKind.DRIVER,
        assign_type: str = "",
        **kwargs,
    ) -> None:
        """[V4 2026-07-15] 统一入口: factory 创建 + append.

        Consolidates the 7 directly-constructed `TraceEdge(...)` append sites in
        this module to a single helper that delegates to `TraceEdgeFactory`. Any
        new field added to TraceEdge (e.g. `source_location`, `confidence`,
        `function_return`, `condition_ast`) only needs handling at ONE point
        in the factory, not 20.

        Args:
            result: TraceResult.
            src/dst: 边端点.
            kind: EdgeKind enum (default EdgeKind.DRIVER).
            assign_type: "continuous" / "nonblocking" / "alias" / "internal".
            **kwargs: forwarded to TraceEdgeFactory.make_edge
                     (expression, bit_slice, condition, sig_cond,
                      sig_cond_ast, ctx, clock_domain).
        """
        edge = self._edge_factory.make_edge(
            src=src,
            dst=dst,
            kind=kind,
            assign_type=assign_type,
            **kwargs,
        )
        result.edges.append(edge)

    def set_instance_paths(self, instance_paths: list[tuple[str, Any]]) -> None:
        """[Phase 4 2026-07-11] Configure instance-aware signal extraction.

        Args:
            instance_paths: List of (instance_path, pyslang InstanceSymbol) pairs.
                Each signal in those instances will be named 'instance_path.signal_name'
                (correctly namespaced under user target).
        """
        self._instance_paths = instance_paths


    def _expr_is_compile_time(self, ast_node, module=None) -> bool:
        """[Phase 8 / Fix F 2026-7-14 + 2026-7-15] Check if an AST expression is a compile-time
        constant (parameter, enum value, localparam, etc.).

        Returns True if the expression evaluates to a compile-time constant.

        [FIX 2026-7-15] Handle Syntax AST nodes (IdentifierNameSyntax etc.) which don't have
        a .symbol attribute. Use module.body.lookupName() to resolve them.
        """
        if ast_node is None:
            return False
        # NamedValueExpression: check symbol.kind
        if hasattr(ast_node, "symbol") and hasattr(ast_node, "kind"):
            sym = getattr(ast_node, "symbol", None)
            if sym is not None:
                return self._is_compile_time_symbol(sym)
        # [NEW 2026-7-15] Syntax AST (IdentifierNameSyntax): look up via module body
        # These appear when the same identifier is used in different contexts (e.g., case item
        # pattern AND procedural assignment in same always block). pyslang returns Syntax node
        # for some uses and Semantic node for others.
        if module is not None and hasattr(ast_node, "identifier"):
            id_attr = getattr(ast_node, "identifier", None)
            if id_attr is not None:
                name_val = getattr(id_attr, "value", None) or str(id_attr)
                if name_val and module is not None and hasattr(module, "body"):
                    body = getattr(module, "body", None)
                    if body is not None and hasattr(body, "lookupName"):
                        sym = body.lookupName(name_val)
                        if sym is not None:
                            return self._is_compile_time_symbol(sym)
        # IntegerLiteral: not a symbol but literal - OK as driver
        kind = getattr(ast_node, "kind", None)
        kind_name = str(kind).split(".")[-1] if kind else ""
        if "Literal" in kind_name:
            return False  # Integer literal is OK as driver
        return False

    def _get_all_signals(self, signal) -> list[str]:
        """提取表达式中的所有信号名

        [铁律29] 直接使用 SignalExpressionVisitor
        """
        if signal is None:
            return []
        return self._signal_visitor.get_all_signals(signal)

    def _get_all_real_signals(self, signal, module=None) -> list[str]:
        """[Phase 8 / Fix F 2026-7-14 + 2026-7-15] Like _get_all_signals but filters out
        compile-time constants (Parameter, EnumValue, localparam, etc.).

        These symbols look like signals but are not real hardware signals.
        Returning them as drivers would pollute trace_fanin results.

        [FIX 2026-7-15] `module` enables resolution of Syntax AST nodes (IdentifierNameSyntax)
        via module.body.lookupName().
        """
        if signal is None:
            return []
        names = self._signal_visitor.get_all_signals(signal)
        return self._filter_compile_time_signal_names(signal, names, module=module)

    def _filter_compile_time_signal_names(self, ast_node, names: list[str], module=None) -> list[str]:
        """Walk AST and collect names whose symbol.kind is NOT compile-time.

        [FIX 2026-7-15] Add module parameter to enable Syntax AST lookup via module.body.lookupName.
        """
        if ast_node is None or not names:
            return names

        out: list[str] = []
        # Recursively walk AST collecting (name, symbol_kind) pairs
        symbol_kinds: dict[str, str] = {}

        def _walk(node):
            if node is None:
                return
            # NamedValueExpression has .symbol attribute
            if hasattr(node, "symbol") and hasattr(node, "kind"):
                sym = getattr(node, "symbol", None)
                if sym is not None:
                    try:
                        sym_name = sym.name
                    except (UnicodeDecodeError, Exception):
                        sym_name = None
                    if sym_name and isinstance(sym_name, str):
                        sym_kind = str(getattr(sym, "kind", "")).split(".")[-1]
                        symbol_kinds[sym_name.strip()] = sym_kind
                    return  # No need to recurse into NamedValue
            # [NEW 2026-7-15] IdentifierNameSyntax: resolve via module.body.lookupName
            if module is not None and hasattr(node, "identifier"):
                id_attr = getattr(node, "identifier", None)
                if id_attr is not None:
                    name_val = getattr(id_attr, "value", None) or str(id_attr)
                    if name_val:
                        body = getattr(module, "body", None)
                        if body is not None and hasattr(body, "lookupName"):
                            try:
                                # [V8 FIX 2026-07-16] pyslang 在 partial AST (UnknownModule)
                                # 状态下会触发 mutex lock failed: Invalid argument.
                                # 完整 project 测试依赖这不会发生, 但 naplespu uart.f 等
                                # 含未知依赖的 filelist 需要 graceful fallback.
                                sym = body.lookupName(name_val)
                            except RuntimeError as e:
                                if "mutex" in str(e).lower():
                                    # partial AST: 跳过这个 identifier, 保守返回所有 names
                                    # (意味着可能漏掉一些 compile-time filter, 但不会 crash)
                                    return
                                raise
                            if sym is not None:
                                sym_kind = str(getattr(sym, "kind", "")).split(".")[-1]
                                symbol_kinds[name_val.strip()] = sym_kind
                                return
            # Recurse children
            for attr in ("left", "right", "operand", "operand0", "operand1",
                         "value", "expr", "expression", "elements", "operands",
                         "args", "arguments"):
                child = getattr(node, attr, None)
                if child is None:
                    continue
                if isinstance(child, list):
                    for c in child:
                        _walk(c)
                else:
                    _walk(child)

        _walk(ast_node)
        for name in names:
            kind = symbol_kinds.get(name.strip(), "")
            if kind in ("Parameter", "EnumValue", "TypeParameter", "Specparam",
                        "Genvar", "LocalParameter"):
                continue  # Skip compile-time symbols
            out.append(name)
        return out

    def _filter_signal_conditions_by_module(
        self,
        signal_conditions: list[tuple[str, str]],
        module=None,
    ) -> list[tuple[str, str]]:
        """[Phase 8 / Fix F.6 2026-7-15] Filter ternary branch signals to drop localparams.

        Companion to _expr_is_compile_time (which works on AST nodes):
        this filters the (name, condition_str) tuples that come back from
        _signal_visitor.get_signals_with_conditions().

        When pyslang extracts signals from a ternary's true/false branches,
        it returns plain strings (e.g., "S0", "4'd15") instead of AST nodes.
        The compile-time filter on AST nodes therefore misses localparam
        references inside ternary branches.

        This helper resolves each name via module.body.lookupName() and drops
        any whose symbol kind is Parameter/EnumValue/etc.

        Args:
            signal_conditions: [(signal_name, condition_str), ...]
            module: Module InstanceBody (for module.body.lookupName)

        Returns:
            Filtered list with compile-time symbols removed.
        """
        if not signal_conditions or module is None:
            return signal_conditions

        body = getattr(module, "body", None)
        if body is None or not hasattr(body, "lookupName"):
            return signal_conditions

        out: list[tuple[str, str]] = []
        for sig_name, cond_str in signal_conditions:
            # Skip SV literals and pure-digit tokens (no need to lookup)
            if not sig_name or sig_name.isdigit():
                out.append((sig_name, cond_str))
                continue
            if self._is_sv_literal_token(sig_name):
                out.append((sig_name, cond_str))
                continue
            # Resolve via module.body.lookupName
            try:
                sym = body.lookupName(sig_name)
            except Exception:
                sym = None
            if sym is not None and self._is_compile_time_symbol(sym):
                continue  # Skip localparam / parameter / enum value
            out.append((sig_name, cond_str))
        return out

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

        def find_clock(expr: object) -> str:
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

        def find_reset(expr: object) -> str:
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
                            try:
                                s = str(syntax).strip()
                                if s:
                                    return s
                            except (UnicodeDecodeError, TypeError):
                                pass
                        # 尝试获取符号名
                        if hasattr(cond_expr, "symbol"):
                            sym = getattr(cond_expr, "symbol", None)
                            if sym:
                                try:
                                    name = sym.name
                                except (UnicodeDecodeError, TypeError, Exception):
                                    name = None
                                if name:
                                    try:
                                        return str(name).strip()
                                    except (UnicodeDecodeError, TypeError):
                                        return "<id:non-utf8>"
                        try:
                            return str(cond_expr).strip()
                        except (UnicodeDecodeError, TypeError):
                            return "<id:non-utf8>"
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

    # [REFACTOR 2026-06-26 B-Phase 1-2] 抽 port + var node 创建
    def _create_port_nodes(self, module, result, module_name):
        """[铁律4] 为端口创建 TraceNode (根据方向创建正确的 kind)"""
        port_decls = self.adapter.get_port_declarations(module)
        for port_decl in port_decls:
            port_name, direction = self.adapter.get_port_name_and_direction(port_decl)
            if not port_name:
                continue
            port_name = self.adapter.clean_name(port_name)
            port_id = f"{module_name}.{port_name}"
            if port_id not in [n.id for n in result.nodes]:
                kind = self._infer_port_kind(direction)
                port_width = self._extract_port_width_as_tuple(port_decl, module)
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

    def _infer_port_kind(self, direction: str) -> NodeKind:
        """根据方向字符串推断 port kind."""
        d = direction.lower()
        if "inout" in d:
            return NodeKind.PORT_INOUT
        if "output" in d:
            return NodeKind.PORT_OUT
        return NodeKind.PORT_IN

    def _extract_port_width_as_tuple(self, port_decl, module) -> tuple:
        """[FIX] extract_port_width 返回 dict 时转换为 (msb, lsb) tuple."""
        port_width = self.adapter.extract_port_width(port_decl, scope=module)
        if not isinstance(port_width, dict):
            return port_width
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
        return (msb, lsb)

    def _collect_port_names(self, module) -> set:
        """[REFACTOR 2026-06-26] 收集模块的所有 port name (用于 var decl dedup)."""
        port_names = set()
        for port_decl in self.adapter.get_port_declarations(module):
            pn, _ = self.adapter.get_port_name_and_direction(port_decl)
            if pn:
                port_names.add(self.adapter.clean_name(pn))
        return port_names

    def _create_var_nodes(self, module, result, module_name, port_names):
        """[铁律4] 为非端口变量/网表声明创建 SIGNAL TraceNode. 跳过端口."""
        for var_decl in self.adapter.get_variable_declarations(module):
            var_name = self.adapter.get_signal_name(var_decl)
            if not var_name or var_name in port_names:
                continue
            var_name = self.adapter.clean_name(var_name)
            var_id = f"{module_name}.{var_name}"
            if var_id not in [n.id for n in result.nodes]:
                var_width = self.adapter.extract_data_width(var_decl)
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

    def _create_net_alias_edges(self, module, result, module_name):
        """[REFACTOR 2026-06-26] 处理 alias 语句: alias b = a; → 创建 DRIVER 边 a → b."""
        for alias in self.adapter.get_net_aliases(module):
            refs = getattr(alias, "netReferences", None)
            if not refs or len(refs) < 2:
                continue
            # refs[0] = target (b), refs[1] = source (a)
            target_name = self._extract_alias_ref_name(refs[0])
            source_name = self._extract_alias_ref_name(refs[1])
            if not target_name or not source_name:
                continue
            target_id = f"{module_name}.{target_name}"
            source_id = f"{module_name}.{source_name}"
            self._ensure_signal_node(result, source_id, source_name, module_name)
            self._ensure_signal_node(result, target_id, target_name, module_name)
            # [V4] factory 统一入口
            self._append_edge(
                result,
                src=source_id,
                dst=target_id,
                kind=EdgeKind.DRIVER,
                assign_type="alias",
            )

    def _extract_alias_ref_name(self, ref_expr) -> str | None:
        """[REFACTOR 2026-06-26] 从 alias ref expr 提取 .symbol.name (None if missing)."""
        if hasattr(ref_expr, "symbol") and hasattr(ref_expr.symbol, "name"):
            return str(ref_expr.symbol.name)
        return None

    def _create_net_decl_edges(self, module, result, module_name, port_names):
        """[REFACTOR 2026-06-26] 处理带初始化器的 Net 声明: wire X = expr; → 创建 DRIVER 边."""
        for net_decl in self.adapter.get_net_declarations(module):
            # NetSymbol (semantic AST): 有 name + initializer, 没有 declarators
            # 访问 .name 时可能触发 utf-8 转换 (escape 序列), 需要 try/except
            try:
                raw_name = getattr(net_decl, "name", "")
                lhs_name = self.adapter.clean_name(raw_name or "")
            except (UnicodeDecodeError, TypeError):
                lhs_name = "<id:non-utf8>"
            if not lhs_name or lhs_name in port_names:
                continue
            try:
                init = getattr(net_decl, "initializer", None)
            except (UnicodeDecodeError, TypeError):
                init = None
            if init is None:
                continue
            lhs_id = f"{module_name}.{lhs_name}"
            self._ensure_signal_node(result, lhs_id, lhs_name, module_name)
            rhs_expr_str = self._get_signal(init) or ""
            rhs_signals = self._get_all_real_signals(init, module=module) if init else []
            for src_name in rhs_signals:
                src_id = f"{module_name}.{src_name}"
                self._ensure_signal_node(result, src_id, src_name, module_name)
                if src_id != lhs_id:
                    # [V4] factory 统一入口
                    self._append_edge(
                        result,
                        src=src_id,
                        dst=lhs_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        expression=rhs_expr_str,
                    )

    def _ensure_signal_node(self, result, node_id, name, module_name, file: str = "", line: int = 0):
        """[REFACTOR 2026-06-26] 确保 result.nodes 包含 node_id 的 SIGNAL TraceNode.
        [V6.2 2026-07-20] Optional file/line for source-location annotations.
        """
        if node_id in [n.id for n in result.nodes]:
            return
        result.nodes.append(
            TraceNode(id=node_id, name=name, module=module_name, kind=NodeKind.SIGNAL,
                      width=(1, 0), file=file, line=line)
        )

    # [REFACTOR 2026-06-26 B-Phase 5] 抽 assign phase: 4 sub-method + dispatch
    def _create_assign_edges(self, module, result, module_name):
        """[REFACTOR 2026-06-26] 处理所有 continuous assign 语句.

        4 sub-phase dispatch:
        - 5a: _handle_concat_assign (LHS/RHS 是 Concatenation)
        - 5b: _handle_call_assign (RHS 是 CallExpression)
        - 5c: _handle_binary_invocation_assign (Binary 含 Invocation)
        - 5d: _handle_normal_assign (其他)
        """
        for assign in self.adapter.get_assignments(module):
            raw_lhs, raw_rhs = self._extract_assign_lr(assign)
            if self._handle_concat_assign(assign, raw_lhs, raw_rhs, module, result, module_name):
                continue
            if self._handle_call_assign(assign, raw_lhs, raw_rhs, module, result, module_name):
                continue
            if self._handle_binary_invocation_assign(assign, raw_rhs, module, result, module_name):
                continue
            self._handle_normal_assign(assign, module, result, module_name)

    def _extract_assign_lr(self, assign) -> tuple:
        """[REFACTOR 2026-06-26] 从 assign 节点提取 (raw_lhs, raw_rhs). None if missing."""
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
        return raw_lhs, raw_rhs

    def _handle_concat_assign(self, assign, raw_lhs, raw_rhs, module, result, module_name) -> bool:
        """[REFACTOR 2026-06-26] 5a: 处理 Concatenation 拼接赋值. 处理了 return True (已 dispatch), 否则 False."""
        if not (raw_lhs and hasattr(raw_lhs, "kind") and "Concatenation" in str(raw_lhs.kind)):
            return False
        # 提取 LHS 拼接中的所有位选信号
        lhs_elements = []
        lhs_operands = getattr(raw_lhs, "operands", None) or getattr(raw_lhs, "expressions", None)
        if lhs_operands and hasattr(lhs_operands, "__iter__") and not isinstance(lhs_operands, str):
            for op in lhs_operands:
                op_kind = getattr(op, "kind", None)
                if not op_kind or "Token" in str(op_kind):
                    continue
                if "ElementSelect" in str(op_kind) or "RangeSelect" in str(op_kind):
                    name = self._get_signal(op)
                    if name:
                        lhs_elements.append(name)
                elif "Identifier" in str(op_kind) or "NamedValue" in str(op_kind):
                    name = self._get_signal(op)
                    if name:
                        lhs_elements.append(name)

        # 提取 RHS 拼接中的所有信号
        # [FIX 2026-06-26] 当 LHS 是 concat 但 RHS 不是 (e.g. CallExpression),
        # return False 让 _handle_call_assign 接着处理 (跟原代码 if-elif chain 行为一致)
        if not (raw_rhs and hasattr(raw_rhs, "kind") and "Concatenation" in str(raw_rhs.kind)):
            return False
        rhs_signals = []
        rhs_operands = getattr(raw_rhs, "operands", None) or getattr(raw_rhs, "expressions", None)
        if rhs_operands and hasattr(rhs_operands, "__iter__") and not isinstance(rhs_operands, str):
            for op in rhs_operands:
                op_kind = getattr(op, "kind", None)
                if not op_kind or "Token" in str(op_kind):
                    continue
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
                    # [V4] factory 统一入口
                    self._append_edge(
                        result,
                        src=rhs_sig,
                        dst=dst_node_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
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
                    # [V4] factory 统一入口
                    self._append_edge(
                        result,
                        src=src_node_id,
                        dst=dst_node_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                    )
        return True

    def _handle_call_assign(self, assign, raw_lhs, raw_rhs, module, result, module_name) -> bool:
        """[REFACTOR 2026-06-26] 5b: 处理 RHS 是 CallExpression (函数调用)."""
        if not (raw_rhs and hasattr(raw_rhs, "kind") and "Call" in str(raw_rhs.kind)):
            return False
        # 先创建 LHS 节点(函数调用的目标)
        lhs_name = None
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
        # 调用 _handle_invocation,传入 lhs_name 作为目标
        self._handle_invocation(raw_rhs, {}, module, module_name, result, lhs_name)
        return True

    def _handle_binary_invocation_assign(self, assign, raw_rhs, module, result, module_name) -> bool:
        """[REFACTOR 2026-06-26] 5c: 处理 BinaryExpression 包含 InvocationExpression.

        例: assign result = a & my_func(b);
        """
        if not (raw_rhs and hasattr(raw_rhs, "kind") and "Binary" in str(raw_rhs.kind)):
            return False
        invocations_found = self._find_invocations(raw_rhs)
        if not invocations_found:
            return False
        raw_lhs = None
        if hasattr(assign, "assignments") and assign.assignments:
            raw_lhs = assign.assignments[0].left
        lhs_name = self._get_signal(raw_lhs) if raw_lhs else None
        for invocation in invocations_found:
            self._handle_invocation(invocation, {}, module, module_name, result, lhs_name)
        return True

    def _find_invocations(self, expr, invocations=None) -> list:
        """[REFACTOR 2026-06-26] 5c-helper: 递归找表达式中的 InvocationExpression / CallExpression.

        之前是 inline closure, 现在抽 public method 可单测.
        """
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
                    self._find_invocations(c, invocations)
        else:
            for child_attr in ["left", "right", "predicate", "condition"]:
                child = getattr(expr, child_attr, None)
                if child:
                    self._find_invocations(child, invocations)
        return invocations

    def _handle_normal_assign(self, assign, module, result, module_name) -> None:
        """[REFACTOR 2026-06-26] 5d: 默认 assign 处理 (call/concat/binary-invocation 之外的).

        处理 ScopedName (tb.data), ConditionalOp, bit_slice, 等.
        这是最大的 sub-method (~197 lines).
        """
        lhs, rhs, rhs_expr = self._parse_assign(assign)
        if not (lhs and (rhs or rhs_expr is not None)):
            return
        # [FIX] ScopedName: tb.data → 创建父子节点和 BIT_SELECT 边
        if "." in lhs:
            lhs_parts = lhs.split(".")
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
            for i in range(len(lhs_parts) - 1):
                child_name = ".".join(lhs_parts[: i + 2])
                parent_name = ".".join(lhs_parts[: i + 1])
                child_id = f"{module_name}.{child_name}"
                parent_id = f"{module_name}.{parent_name}"
                if child_id != parent_id:
                    existing = next(
                        ((e.src, e.dst) for e in result.edges if e.src == child_id and e.dst == parent_id),
                        None,
                    )
                    if not existing:
                        # [V4] factory 统一入口
                        self._append_edge(
                            result,
                            src=child_id,
                            dst=parent_id,
                            kind=EdgeKind.BIT_SELECT,
                            assign_type="internal",
                        )

        dst_node_id = f"{module_name}.{lhs}"
        if dst_node_id not in [n.id for n in result.nodes]:
            result.nodes.append(TraceNode(id=dst_node_id, name=lhs, module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)))
        rhs_kind = str(getattr(rhs_expr, "kind", "")) if rhs_expr else ""
        if "EqualsValueClause" in rhs_kind:
            rhs_signals = []
        else:
            rhs_signals = self._get_all_real_signals(rhs_expr, module=module) if rhs_expr else [rhs]

        ternary_condition = self._extract_ternary_condition(rhs_expr)

        has_conditional = False
        check_expr = rhs_expr
        for _ in range(5):  # 解包多层包装
            if check_expr is None:
                break
            rhs_kind_name = getattr(check_expr, "kind", None)
            rhs_kind_str = (
                rhs_kind_name.name if hasattr(rhs_kind_name, "name")
                else str(rhs_kind_name) if rhs_kind_name else ""
            )
            if "ConditionalOp" in rhs_kind_str:
                has_conditional = True
                break
            operand = getattr(check_expr, "operand", None)
            if operand is None or operand is check_expr:
                break
            check_expr = operand

        if not rhs_signals:
            # [Phase 8 / Fix F 2026-7-14] If rhs_expr is a compile-time symbol (parameter,
            # enum value, localparam), don't fall back to [rhs] - that would re-add
            # the parameter as a fake driver.
            # [FIX 2026-7-15] Pass module for Syntax AST resolution.
            if rhs_expr is not None and self._expr_is_compile_time(rhs_expr, module=module):
                rhs_signals = []  # Stay empty, no driver
            else:
                rhs_signals = [rhs]
        if rhs_expr:
            try:
                expr_str = self._signal_visitor.visit(rhs_expr) or str(rhs_expr)
            except (UnicodeDecodeError, TypeError):
                expr_str = "<expr:non-utf8>"
        else:
            expr_str = rhs or ""

        if has_conditional:
            # [Phase 8 / Fix F.6 2026-7-15] Filter compile-time symbols
            # (localparam/parameter) from ternary branch signals.
            signal_conditions = self._signal_visitor.get_signals_with_conditions(rhs_expr)
            signal_conditions = self._filter_signal_conditions_by_module(
                signal_conditions, module=module
            )
            for rhs_name, sig_cond in signal_conditions:
                if not rhs_name:
                    continue
                bit_slice = ""
                if "[" in rhs_name and "]" in rhs_name:
                    start = rhs_name.index("[")
                    bit_slice = rhs_name[start:]
                if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                    result.edges.append(
                        self._edge_factory.make_edge(
                            src=rhs_name,
                            dst=dst_node_id,
                            kind=EdgeKind.DRIVER,
                            assign_type="continuous",
                            expression=rhs_name,
                            bit_slice=bit_slice,
                            sig_cond=sig_cond,
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
                        self._edge_factory.make_edge(
                            src=src_node_id,
                            dst=dst_node_id,
                            kind=EdgeKind.DRIVER,
                            assign_type="continuous",
                            expression=expr_str,
                            bit_slice=bit_slice,
                            sig_cond=sig_cond,
                        )
                    )
        else:
            for rhs_name in rhs_signals:
                if not rhs_name:
                    continue
                bit_slice = ""
                if "[" in rhs_name and "]" in rhs_name:
                    start = rhs_name.index("[")
                    bit_slice = rhs_name[start:]
                if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                    # [V4] factory 统一入口
                    self._append_edge(
                        result,
                        src=rhs_name,
                        dst=dst_node_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        expression=rhs_name,
                        bit_slice=bit_slice,
                        condition=ternary_condition,
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
                    # [V4] factory 统一入口
                    self._append_edge(
                        result,
                        src=src_node_id,
                        dst=dst_node_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        expression=expr_str,
                        bit_slice=bit_slice,
                        condition=ternary_condition,
                    )

    def _create_always_edges(self, module, result, module_name):
        """[REFACTOR 2026-06-26] 处理 always 块 (含 always_ff/always_comb/always_latch).

        遍历 always 块的语句, 处理:
        - INVOCATION: 调 _handle_invocation
        - Assignment + InvocationExpression RHS: 调 _handle_invocation
        - 普通 Assignment: 解析 lhs/rhs, 创建 DRIVER edge + CLOCK/RESET edge
        """
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
                    # [FIX 2026-7-15] Pass module for Syntax AST resolution
                    rhs_signals = self._get_all_real_signals(rhs_expr, module=module) if rhs_expr else [rhs]
                    if not rhs_signals:
                        # [Phase 8 / Fix F 2026-7-14] Skip if compile-time symbol
                        # [FIX 2026-7-15] Pass module for Syntax AST resolution
                        if rhs_expr is not None and self._expr_is_compile_time(rhs_expr, module=module):
                            rhs_signals = []
                        else:
                            rhs_signals = [rhs]
                    # [P0-2] 计算完整表达式字符串
                    if rhs_expr:
                        try:
                            expr_str = self._signal_visitor.visit(rhs_expr) or str(rhs_expr)
                        except (UnicodeDecodeError, TypeError):
                            expr_str = "<expr:non-utf8>"
                    else:
                        expr_str = rhs or ""

                    # [BUG-FIX] 嵌套三元: 为每个信号提取对应条件
                    has_conditional = False
                    check_expr = rhs_expr
                    for _ in range(5):  # 解包多层包装
                        if check_expr is None:
                            break
                        rhs_kind_name = getattr(check_expr, "kind", None)
                        rhs_kind_str = (
                            rhs_kind_name.name if hasattr(rhs_kind_name, "name")
                            else str(rhs_kind_name) if rhs_kind_name else ""
                        )
                        if "ConditionalOp" in rhs_kind_str:
                            has_conditional = True
                            break
                        operand = getattr(check_expr, "operand", None)
                        if operand is None or operand is check_expr:
                            break
                        check_expr = operand

                    if has_conditional:
                        # [Phase 8 / Fix F.6 2026-7-15] Filter compile-time symbols
                        # (localparam/parameter) from ternary branch signals.
                        signal_conditions = self._signal_visitor.get_signals_with_conditions(rhs_expr)
                        signal_conditions = self._filter_signal_conditions_by_module(
                            signal_conditions, module=module
                        )
                        for sig_rhs_name, sig_cond in signal_conditions:
                            if not sig_rhs_name:
                                continue
                            bit_slice = ""
                            if "[" in sig_rhs_name and "]" in sig_rhs_name:
                                start = sig_rhs_name.index("[")
                                bit_slice = sig_rhs_name[start:]
                            if sig_rhs_name and not sig_rhs_name[0].isalpha() and not sig_rhs_name.startswith("_"):
                                result.edges.append(
                                    self._edge_factory.make_edge(
                                        src=sig_rhs_name,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="nonblocking",
                                        expression=sig_rhs_name,
                                        bit_slice=bit_slice,
                                        clock_domain=ctx.get("clock", ""),
                                        sig_cond=sig_cond,
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
                                    self._edge_factory.make_edge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="nonblocking",
                                        expression=expr_str,
                                        bit_slice=bit_slice,
                                        clock_domain=ctx.get("clock", ""),
                                        sig_cond=sig_cond,
                                    )
                                )
                    else:
                        for rhs_name in rhs_signals:
                            if not rhs_name:
                                continue
                            bit_slice = ""
                            if "[" in rhs_name and "]" in rhs_name:
                                start = rhs_name.index("[")
                                bit_slice = rhs_name[start:]
                            if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                                result.edges.append(
                                    self._edge_factory.make_edge(
                                        src=rhs_name,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="nonblocking",
                                        bit_slice=bit_slice,
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
                                    self._edge_factory.make_edge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="nonblocking",
                                        bit_slice=bit_slice,
                                        expression=expr_str,
                                        ctx=ctx,
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
                            self._edge_factory.make_edge(
                                src=clock_node_id,
                                dst=dst_node_id,
                                expression="",  # CLOCK 边无 expression
                                kind=EdgeKind.CLOCK,
                                assign_type="nonblocking",
                                clock_domain=clock_signal,
                                ctx=ctx,
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
                            self._edge_factory.make_edge(
                                src=reset_node_id,
                                dst=dst_node_id,
                                expression="",  # RESET 边无 expression
                                kind=EdgeKind.RESET,
                                assign_type="nonblocking",
                                clock_domain=clock_signal,
                                ctx=ctx,
                            )
                        )


                    # [Phase 7.3 / Fix A 2026-07-13] CONDITION-DRIVEN drivers
                    # Bug: 在 if-else statement-level conditions 里,
                    # q <= literal_only 会被简化为 `literal → q` 边,
                    # 但 condition 里的信号 (e.g. cpu_state) 不会作为 driver 出现.
                    # 修复: 从 ctx.effective_condition 提取所有信号名, 添加为 DRIVER 边
                    # (kind=DRIVER 但带 sig_cond, 让 trace_fanin/dataflow 能找到完整 driver chain).
                    self._add_condition_drivers(
                        dst_node_id, ctx, module_name, result
                    )

    def _add_condition_drivers(
        self,
        dst_node_id: str,
        ctx: dict,
        module_name: str,
        result,
    ) -> None:
        """[Phase 7.6 / Fix E.4 2026-7-14] Disabled: condition signals no longer
        added as DRIVER edges.

        ROOT CAUSE (user verified 2026-7-14):
        Fix A (2026-7-13) added cond signals as DRIVER edges.
        test_case_stmt / test_complex_conditions golden expects "drivers = RHS only":
          - case (sel) 2'b00: y=a;  → drivers = [a, b, 0], NOT sel
          - if (a) q<=b;            → drivers = [b],       NOT a
          - case (1'b1) a: y=1;     → drivers = [1, 0],   NOT a, b
        Fix A violates dataflow semantics: dataflow driver = the actual value
        expression (RHS), condition is only gating context (controlflow).

        REMEDIATION:
        1. condition signals do NOT enter driver list
        2. RHS extraction still produces drivers (test cases pass)
        3. condition still stored in sig_cond context (for controlflow queries)
        4. picorv32.trap trace_fanin improvement comes from more precise RHS
           extraction (separate fix)

        Keep Fix C/D/E.1 infrastructure: _collect_signals_from_ast,
        _is_sv_literal_token still available for controlflow/coverage analysis,
        just don't write DRIVER edges.
        """
        # [Phase 7.6 / Fix E.4] No-op: compute cond_signals for analysis but don't
        # write DRIVER edges. Tests want drivers = RHS only.
        cond_signals: set[str] = set()

        # AST extraction (Fix C/D infrastructure, not used for graph)
        ast_nodes: list = []
        cond_exprs_list = ctx.get("_cond_exprs") or []
        if isinstance(cond_exprs_list, list):
            ast_nodes.extend(cond_exprs_list)
        condition_ast = ctx.get("condition_ast")
        if condition_ast is not None:
            ast_nodes.append(condition_ast)

        for ast_node in ast_nodes:
            if ast_node is None:
                continue
            try:
                self._collect_signals_from_ast(ast_node, cond_signals)
            except Exception:
                pass

        # Fallback string scan (Fix E.1 filter applied, but no DRIVER edge written)
        if not cond_signals:
            effective_cond = ctx.get("effective_condition", "")
            if effective_cond:
                current = ""
                for c in effective_cond:
                    if c.isalnum() or c == "_":
                        current += c
                    elif c == "[":
                        continue
                    else:
                        if current and current not in ("0", "1"):
                            if not self._is_sv_literal_token(current):
                                cond_signals.add(current)
                        current = ""
                if current and current not in ("0", "1"):
                    if not self._is_sv_literal_token(current):
                        cond_signals.add(current)

        # [Phase 7.6 / Fix E.4] DO NOT write DRIVER edges.
        # Original edge-creation loop removed. Tests expect drivers = RHS only.
        return
    _EXCLUDED_SYMBOL_KINDS = {
        "Parameter",        # parameter [2:0] cpu_state_trap = 3'd0;
        "EnumValue",       # enum value (same as Parameter effectively)
        "TypeParameter",    # type parameter
        "Specparam",        # specparam
        "Genvar",           # generate variable (compile-time)
    }

    def _collect_signals_from_ast(self, ast_node, cond_signals):
        """[Phase 7.5 / Fix D 2026-07-13] Traverse AST to extract NamedValueExpression,
        but skip Symbol kind = parameter/enum value (compile-time constants).

        Difference from _signal_visitor.get_all_signals(): this version checks
        symbol.kind to exclude Parameter/EnumValue/etc, keeping only real signals.
        """
        if ast_node is None:
            return

        # NamedValueExpression: simple variable reference
        if hasattr(ast_node, "symbol") and hasattr(ast_node, "kind"):
            sym = getattr(ast_node, "symbol", None)
            if sym is not None:
                # Check symbol kind - skip parameters/enum values
                sym_kind = getattr(sym, "kind", None)
                sym_kind_name = str(sym_kind).split(".")[-1] if sym_kind else ""
                if sym_kind_name in self._EXCLUDED_SYMBOL_KINDS:
                    return  # Skip this NamedValue, don't recurse
                # Real signal - extract name
                try:
                    name = sym.name
                except (UnicodeDecodeError, TypeError, Exception):
                    name = None
                if name:
                    name = name.strip() if isinstance(name, str) else str(name)
                    if self._is_valid_signal_name(name):
                        # Strip bit select suffix [..]
                        if "[" in name:
                            name = name.split("[", 1)[0]
                        if name and self._is_valid_signal_name(name):
                            cond_signals.add(name)
                return  # NamedValue, no need to recurse

        # Recurse into child nodes
        for attr in ("left", "right", "value", "operand", "operand0", "operand1",
                     "expression", "expr", "elements", "operands", "args", "arguments"):
            child = getattr(ast_node, attr, None)
            if child is None:
                continue
            if isinstance(child, list):
                for c in child:
                    if c is not None:
                        self._collect_signals_from_ast(c, cond_signals)
            else:
                self._collect_signals_from_ast(child, cond_signals)

    @staticmethod
    def _is_compile_time_symbol(sym) -> bool:
        """[Phase 8 / Fix F 2026-7-14] Detect Parameter/EnumValue/Localparam symbols.

        These look like signals but are compile-time constants.
        Used by RHS extraction to skip them (they're not real signal drivers).
        """
        if sym is None:
            return False
        sym_kind = getattr(sym, "kind", None)
        sym_kind_name = str(sym_kind).split(".")[-1] if sym_kind else ""
        return sym_kind_name in {
            "Parameter",      # parameter [2:0] foo = 3'd0;
            "EnumValue",     # enum values
            "TypeParameter",  # type parameters
            "Specparam",      # spec parameters
            "Genvar",         # generate variables
            "LocalParameter", # localparam (SystemVerilog localparam)
        }

    @staticmethod
    def _is_valid_signal_name(name):
        """Check if looks like a valid SV identifier (exclude AST noise and literals)"""
        if not name or len(name) < 2:
            return False
        if not (name[0].isalpha() or name[0] == "_"):
            return False
        if not all(c.isalnum() or c == "_" for c in name):
            return False
        if name.isdigit() or name in ("0", "1"):
            return False
        if "'" in name:  # SystemVerilog literal like "2'b10"
            return False
        return True

    @staticmethod
    def _is_sv_literal_token(token):
        """[Phase 7.6 / Fix E.1 2026-7-14] Detect if a token is a SystemVerilog literal
        fragment (e.g., 'b00', 'a' from '2'b00'; 'ff' from '8'hff').

        Returns True if token is part of an SV literal value, False otherwise.
        Used to filter string-fallback candidates that look like identifiers but
        are actually literal fragments.

        Examples (True = literal):
          "2", "8", "16"        - pure digits
          "3.14", "0.5"         - decimal numbers
          "x", "z", "X", "Z"    - 1-bit unknown / high-impedance
          "b00", "hff", "o17"   - base-letter + digits (literal fragment)
          "ff", "ab", "dead"    - all-hex chars (could be hex literal or signal)
        Examples (False = signal):
          "sel", "a", "b", "data", "my_reg", "alu_out_q"
        """
        if not token:
            return False

        # Pure digits: 2, 8, 16
        if token.isdigit():
            return True

        # Decimal number: 3.14, 0.5
        try:
            float(token)
            return True
        except (ValueError, TypeError):
            pass

        # 1-bit SV literals
        if token in ("x", "z", "X", "Z"):
            return True

        # Base-letter fragments from literal: "b00", "hff", "o17", "d42"
        # After splitting on "'", "2'b00" → ["2", "b00"]
        # "b" / "h" / "o" / "d" followed by hex digits = literal base+value
        if len(token) >= 2 and token[0].lower() in ("b", "h", "o", "d"):
            rest = token[1:]
            if rest and all(c in "0123456789abcdefABCDEF_xz" for c in rest):
                return True

        # All-hex chars (e.g., "ff", "ab", "dead", "face")
        if len(token) >= 2 and all(c in "0123456789abcdefABCDEF" for c in token):
            if any(c in "abcdefABCDEF" for c in token):
                return True

        # Otherwise: looks like a real signal name
        return False

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

        # [Phase 4 2026-07-11] If instance_paths set, iterate (path, module) pairs
        # instead of just modules. This makes signal IDs use full instance paths
        # (e.g., 'darksocv.bridge0.core0.REGS' instead of 'darkriscv.REGS'),
        # so pipeline/timing inside target see sub-instance registers.
        if self._instance_paths:
            for inst_path, module in self._instance_paths:
                module_name = inst_path  # Use instance path as prefix
                try:
                    type_name = self.adapter.get_module_name(module)
                except Exception:
                    type_name = '?'
                # [FIX Issue 21] 设置当前模块上下文,供 _get_signal 获取参数映射
                self._current_module = module
                # [P1-3] 获取当前模块的源文件位置
                try:
                    src_file, src_line, _, _ = self.adapter.get_source_location(module)
                except Exception:
                    src_file, src_line = '', 0
                self._current_source_file = src_file

                # [REFACTOR 2026-06-26 B-Phase 1-2] 抽 _create_port_nodes + _create_var_nodes
                self._create_port_nodes(module, result, module_name)
                port_names = self._collect_port_names(module)
                self._create_var_nodes(module, result, module_name, port_names)

                # [REFACTOR 2026-06-26 B-Phase 3-4] 抽 _create_net_alias_edges + _create_net_decl_edges
                self._create_net_alias_edges(module, result, module_name)
                self._create_net_decl_edges(module, result, module_name, port_names)

                # [REFACTOR 2026-06-26 B-Phase 5] 抽 _create_assign_edges (含 4 sub-method)
                self._create_assign_edges(module, result, module_name)

                # [REFACTOR 2026-06-26 B-Phase 6] 抽 _create_always_edges
                self._create_always_edges(module, result, module_name)
        else:
            # 旧路径: 遍历所有 modules (兼容行为)
            for module in self.adapter.get_modules():
                module_name = self.adapter.get_module_name(module)
                # [FIX Issue 21] 设置当前模块上下文,供 _get_signal 获取参数映射
                self._current_module = module
                # [P1-3] 获取当前模块的源文件位置
                src_file, src_line, _, _ = self.adapter.get_source_location(module)
                self._current_source_file = src_file

                # [REFACTOR 2026-06-26 B-Phase 1-2] 抽 _create_port_nodes + _create_var_nodes
                self._create_port_nodes(module, result, module_name)
                port_names = self._collect_port_names(module)
                self._create_var_nodes(module, result, module_name, port_names)

                # [REFACTOR 2026-06-26 B-Phase 3-4] 抽 _create_net_alias_edges + _create_net_decl_edges
                self._create_net_alias_edges(module, result, module_name)
                self._create_net_decl_edges(module, result, module_name, port_names)

                # [REFACTOR 2026-06-26 B-Phase 5] 抽 _create_assign_edges (含 4 sub-method)
                self._create_assign_edges(module, result, module_name)

                # [REFACTOR 2026-06-26 B-Phase 6] 抽 _create_always_edges
                self._create_always_edges(module, result, module_name)

        # [Stage 1] post-processing: 给带 condition_ast 的边填 source_location
        # 一次性后处理比每个创建点都填更简洁
        for edge in result.edges:
            ast_node = getattr(edge, "condition_ast", None)
            if ast_node is None:
                continue
            if edge.source_location is not None:
                continue  # 已有
            try:
                loc = self.adapter.get_source_location(ast_node)
                if loc[0]:  # file 非空
                    from .graph.models import SourceLocation
                    edge.source_location = SourceLocation(
                        file=loc[0], line_start=loc[1], line_end=loc[1], column=loc[2]
                    )
            except Exception:
                pass  # source_location 失败不影响 edge

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
            # [Stage 6] v10: SequentialBlockStatement children 含 [SyntaxList(...)]
            #         v11: children 直接是 plain list (SyntaxList 已展开)
            statements = None
            for i, child in enumerate(stmt):
                child_kind = str(getattr(child, "kind", ""))
                if ("SyntaxList" in child_kind or isinstance(child, list)) and i == 4:
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
        call_info = self._parse_invocation_call(invocation)
        if not call_info:
            return
        call_name, call_args, named_args = call_info
        task_def = self._find_task_definition(module, call_name)
        if not task_def:
            return
        # [HANDOFF] def_params 由 _create_invocation_edges 内部根据 task kind 计算
        self._create_invocation_edges(
            invocation, ctx, module, module_name, result, lhs_name,
            call_name, call_args, named_args, task_def,
        )

    def _parse_invocation_call(self, invocation) -> tuple | None:
        """[REFACTOR 2026-06-26] 解析 invocation → (call_name, call_args, named_args).

        Returns None if call_name / args 缺失.
        """

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
            return None

        # 获取调用参数 (OrderedArgument 或 NamedArgument 列表)
        args_node = getattr(invocation, "arguments", None)
        if args_node is None:
            return None

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
        return call_name, call_args, named_args


    def _find_task_definition(self, module, call_name) -> tuple:
        """[REFACTOR 2026-06-26] 找 task/function 定义.

        Returns (task_def, def_params). Both may be None/empty.
        """
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
            return None
        return task_def


    def _create_invocation_edges(self, invocation, ctx, module, module_name, result, lhs_name,
                                 call_name, call_args, named_args, task_def):
        """[REFACTOR 2026-06-26] 建 invocation 边 (含 def_params + param_map + function + output)."""
        try:
            # 内部计算 def_params
            if "Task" in str(getattr(task_def, "kind", "")):
                def_params = self.adapter.get_task_params(task_def)
            else:
                def_params = self.adapter.get_function_params(task_def)
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
                                self._edge_factory.make_edge(
                                    src=func_return_id,
                                    dst=dst_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="continuous",
                                    ctx=ctx,
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
                                    self._edge_factory.make_edge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        ctx=ctx,
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
                                        self._edge_factory.make_edge(
                                            src=src_node_id,
                                            dst=dst_node_id,
                                            kind=EdgeKind.DRIVER,
                                            assign_type="continuous",
                                            ctx=ctx,
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
                            self._edge_factory.make_edge(
                                src=src_node_id,
                                dst=dst_node_id,
                                kind=EdgeKind.DRIVER,
                                assign_type="nonblocking",
                                ctx=ctx,
                            )
                        )
            # [REFACTOR 2026-06-26] silent (preserve original except: pass behavior)
            return
        except Exception:
            return
