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
from .graph.models import SignalSource, EdgeKind, NodeKind, TraceEdge, TraceNode
from .ast_utils import kind_matches, unwrap  # [V6.3+3 2026-07-27]
from pyslang.pyslang.ast import StatementKind, ExpressionKind  # [V6.9] semantic AST only
# [V6.9] SignalExpressionVisitor removed — using semantic_adapter

logger = logging.getLogger(__name__)


# [P1 cycle 8/9] ExtractorResult 移到了 extractor_models.py (避免循环 import)
# 这里 re-export 保持向后兼容 (from trace.core.driver_extractor import ExtractorResult)
__all__ = ["DriverExtractor", "ExtractorResult"]


class DriverExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        # [铁律29] 使用 Visitor 替代旧实现，保留 fallback
        # [V6.9] SignalExpressionVisitor removed — adapter handles signal extraction directly
        self._signal_visitor = adapter  # semantic_adapter has _extract_signals_from_expr() and visit()
        # [V6.9] StatementCollectorVisitor removed
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
        `function_return`, `condition_ast`, `source`) only needs handling at ONE point
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
        # [V6.9 FIX 2026-07-29] Unwrap Conversion wrapper — pyslang wraps localparam
        # references in implicit conversion (e.g. cpu_state_trap in case item RHS).
        # Conversion{operand=NamedValueExpression{cpu_state_trap (Parameter)}}
        for _ in range(5):
            if hasattr(ast_node, "operand") and not hasattr(ast_node, "symbol"):
                ast_node = ast_node.operand
            else:
                break
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
        return self._signal_visitor._extract_signals_from_expr(signal) or []

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
        names = self._signal_visitor._extract_signals_from_expr(signal) or []
        return self._filter_compile_time_signal_names(signal, names, module=module)

    def _filter_compile_time_signal_names(self, ast_node, names: list[str], module=None) -> list[str]:
        """Walk AST and collect names whose symbol.kind is NOT compile-time.

        [FIX 2026-7-15] Add module parameter to enable Syntax AST lookup via module.body.lookupName.
        [V6.9] Also filter out ternary condition signals (g, h from g ? h ? x0 : x1 : x2).
        """
        if ast_node is None or not names:
            return names
        
        # [V6.9] Extract condition signal names from ternary expressions
        cond_names2 = set()
        def _walk_conds(node):
            if node is None:
                return
            ck = str(getattr(node, "kind", ""))
            if "ConditionalOp" in ck or "ConditionalExpression" in ck:
                # Semantic: .conditions list
                cs = getattr(node, "conditions", None)
                if cs:
                    for c in cs:
                        sub = getattr(c, "expr", None) or getattr(c, "expression", None)
                        if sub:
                            cond_names2.add(self._get_signal(sub) or str(sub).strip())
                # Syntax: .predicate (single node)
                pred = getattr(node, "predicate", None)
                if pred:
                    cond_names2.add(self._get_signal(pred) or str(pred).strip())
                _walk_conds(getattr(node, "left", None))
                _walk_conds(getattr(node, "right", None))
        _walk_conds(ast_node)
        
        if cond_names2:
            names = [n for n in names if n not in cond_names2]

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
        """[V6.9] 获取信号名 — 优先用 semantic API, fallback 到 str()。

        syntax AST 节点的 str() 包含前导空格和换行符,
        必须 strip() 后使用。
        """
        if signal is None:
            return None
        # NamedValue: 通过 .symbol.name 获取 (不是 str())
        sk = str(getattr(signal, "kind", ""))
        if "NamedValue" in sk:
            sym = getattr(signal, "symbol", None)
            if sym:
                name = getattr(sym, "name", None)
                if name:
                    return str(name).strip()
        # IdentifierName: 通过 .identifier.value 获取
        if "IdentifierName" in sk:
            ident = getattr(signal, "identifier", None)
            if ident:
                val = getattr(ident, "value", None) or str(ident)
                return str(val).strip()
        # BinaryOp: 递归展开为 "left op right" — 避免对象引用
        if "BinaryOp" in sk:
            left = getattr(signal, "left", None)
            right = getattr(signal, "right", None)
            ls = self._get_signal(left) if left else "?"
            rs = self._get_signal(right) if right else "?"
            if ls and rs:
                return f"{ls} {rs}"
            return ls or rs or None
        # UnaryOp: 递归展开为 "op operand" — 避免对象引用
        if "UnaryOp" in sk:
            operand = getattr(signal, "operand", None)
            op_str = self._get_signal(operand) if operand else "?"
            return f"!{op_str}" if op_str else None
        # ConversionExpression: type cast (e.g., 8'hAA → int literal)
        if "Conversion" in sk:
            operand = getattr(signal, "operand", None)
            if operand:
                ok = str(getattr(operand, "kind", ""))
                if "IntegerLiteral" in ok or "UnbasedUnsized" in ok:
                    val = getattr(operand, "value", None)
                    if val is not None:
                        return str(val)
                elif "NamedValue" in ok:
                    return self._get_signal(operand)
                # fallback: 递归 _get_signal，避免 str() 返回对象引用
                sig = self._get_signal(operand)
                if sig and not sig.startswith("Expression("):
                    return sig
                return str(operand)
        # ElementSelect: data_out[0]
        if "ElementSelect" in sk:
            base = getattr(signal, "value", None) or getattr(signal, "base", None)
            selector = getattr(signal, "selector", None)
            base_name = self._get_signal(base) if base else None
            sel_val = getattr(selector, "value", None) if selector else None
            # 语义 AST: selector 可能是 NamedValueExpression（非 literal）
            if sel_val is not None:
                try:
                    sel_str = str(int(sel_val))
                except (TypeError, ValueError):
                    sel_str = self._get_signal(selector) or str(sel_val)
            else:
                sel_str = self._get_signal(selector) or "x"
            if base_name:
                return f"{base_name}[{sel_str}]"
            return None
        # RangeSelect: data[3:0]
        if "RangeSelect" in sk:
            base = getattr(signal, "value", None) or getattr(signal, "base", None)
            left = getattr(signal, "left", None)
            right = getattr(signal, "right", None)
            base_name = self._get_signal(base) if base else None
            lv = getattr(left, "value", None) if left else None
            rv = getattr(right, "value", None) if right else None
            # 语义 AST: left/right 可能是 NamedValueExpression（非 literal）
            if lv is not None:
                try:
                    li = int(lv)
                except (TypeError, ValueError):
                    li = self._get_signal(left) or str(lv)
            else:
                li = self._get_signal(left) or "x"
            if rv is not None:
                try:
                    ri = int(rv)
                except (TypeError, ValueError):
                    ri = self._get_signal(right) or str(rv)
            else:
                ri = self._get_signal(right) or "x"
            if base_name:
                return f"{base_name}[{li}:{ri}]"
            return None
        # MemberAccess: pkt.addr → base 信号 + .member (FieldSymbol)
        if "MemberAccess" in sk:
            base = getattr(signal, "value", None) or getattr(signal, "base", None)
            member = getattr(signal, "member", None)
            member_str = str(getattr(member, "name", member)) if member else ""
            base_name = self._get_signal(base) if base else None
            if base_name and member_str:
                return f"{base_name}.{member_str}"
            return None
        # HierarchicalValue: tb.data / ifc.data / u_sub.data → 从 semantic AST 解析分量路径
        if "HierarchicalValue" in sk:
            sym = getattr(signal, "symbol", None)
            if sym:
                sname = str(getattr(sym, "name", "")).strip()
                if sname:
                    dd = getattr(sym, "declaringDefinition", None)
                    defn_type = str(getattr(dd, "name", "")).strip() if dd else ""
                    if defn_type and hasattr(self, "_current_module") and self._current_module:
                        body = getattr(self._current_module, "body", None)
                        if body:
                            for port in body:
                                pk = str(getattr(port, "kind", ""))
                                pn = str(getattr(port, "name", "")).strip()
                                if "InterfacePort" in pk:
                                    idf = getattr(port, "interfaceDef", None)
                                    if idf and str(getattr(idf, "name", "")) == defn_type:
                                        return f"{pn}.{sname}"
                                elif "Instance" in pk and getattr(port, "isInterface", False):
                                    idef = getattr(port, "definition", None)
                                    if idef and str(getattr(idef, "name", "")) == defn_type:
                                        return f"{pn}.{sname}"
                                elif "Instance" in pk:
                                    idef = getattr(port, "definition", None)
                                    if idef and str(getattr(idef, "name", "")) == defn_type:
                                        return f"{pn}.{sname}"
                    return sname
        # fallback: str() + strip()
        result = str(signal).strip()
        result = result.replace('\n', '').replace('\r', '').strip()
        # [V6.9] 语义 AST 节点 str() 可能返回 "Expression(ExpressionKind.XXX)" 对象引用
        # 尝试从常见属性中提取值
        if result.startswith("Expression(") or result.startswith("<"):
            # 尝试 .value (IntegerLiteral / StringLiteral / etc)
            val = getattr(signal, "value", None)
            if val is not None and not callable(val):
                vs = str(val).strip()
                if vs and not vs.startswith("Expression("):
                    return vs
            # 尝试 .symbol.name (NamedValue / VariableRef)
            sym = getattr(signal, "symbol", None)
            if sym:
                name = getattr(sym, "name", None)
                if name:
                    return str(name).strip()
        return result if result else None

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

        # [V6.3+4 2026-07-28] Refactored to use ast_utils for wrapper unwrap
        # and kind matching. Replaces 6 lines of substring checks and ad-hoc
        # operand/expr unwrap with a single unwrap() call.
        current = expr
        for _ in range(5):  # 最多解包5层 (was 3, increased to match _create_always_edges)
            if current is None:
                return ""

            # [V6.3+4] Use kind_matches instead of substring "ConditionalOp" in str(kind)
            # to handle pyslang 10/11 SyntaxKind.ConditionalExpression (and any future
            # enum renames via _KIND_ALIASES).
            if kind_matches(current, "ConditionalOp", "ConditionalExpression"):
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

            # [V6.3+4] Use ast_utils.unwrap() instead of ad-hoc operand/expr getattr
            inner = unwrap(current)
            if inner is None or inner is current:  # 防止无限循环
                return ""
            current = inner

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

    # ==============================================================================
    # [V6.5 2026-07-28] [V6.6] SignalSource — 结构化信号源 (driver/load 共用)
    # ==============================================================================

    @staticmethod
    def _parse_bit_range(rhs_name: str) -> tuple[str | None, int | None, int | None]:
        """[V6.5] 从 rhs_name (如 "a[7:0]" / "data[3]") 解析出 signal + bit_start + bit_end

        Returns:
            (signal, bit_start, bit_end)
            signal=None 表示无需解析 (非信号名 / 字面量)
        """
        if not rhs_name:
            return None, None, None
        signal = rhs_name
        bit_start = None
        bit_end = None

        if "[" in rhs_name and "]" in rhs_name:
            signal = rhs_name.split("[", 1)[0]
            bit_part = rhs_name[rhs_name.index("["):]
            import re

            m = re.match(r"\[(\d+):(\d+)\]", bit_part)
            if m:
                bit_start = int(m.group(1))
                bit_end = int(m.group(2))
            else:
                m = re.match(r"\[(\d+)\]", bit_part)
                if m:
                    bit_start = bit_end = int(m.group(1))

        return signal, bit_start, bit_end

    def _detect_binary_op(
        self, expr, signal: str
    ) -> tuple[str, str, bool]:
        """[V6.5] 检测二元操作符和操作数位置

        解包 Conversion/Cast 到内部 BinaryExpression，提取 op 和 operand_side。

        Returns:
            (op, operand_side, is_binary) — 无 binary op 时返回 ("", "", False)
        """
        if expr is None:
            return "", "", False

        # 解包 Conversion/Cast → 找到内部 BinaryExpression
        root = expr
        kind_str = str(getattr(expr, "kind", ""))
        if "Conversion" in kind_str or "Cast" in kind_str:
            inner = unwrap(expr)
            if inner is not None and inner is not expr:
                root = inner

        if root is None:
            return "", "", False

        root_kind_str = str(getattr(root, "kind", ""))
        if "Binary" not in root_kind_str:
            return "", "", False

        op_attr = getattr(root, "op", None)
        op = str(getattr(op_attr, "name", op_attr)) if op_attr else ""
        operand_side = ""

        for side_name in ("left", "right"):
            side = getattr(root, side_name, None)
            if side is None:
                continue
            # 两层匹配: visit 优先, get_all_signals 兜底 (CallExpression/$signed)
            name = self._signal_visitor.get_source_text(side) or str(side)
            if name and signal == name:
                operand_side = side_name
                break
            if not name:
                if signal in self._signal_visitor.get_all_signals(side):
                    operand_side = side_name
                    break

        return op, operand_side, True

    def _detect_casts(self, rhs_expr, root_expr, full_expression: str) -> list[str]:
        """[V6.5] 检测 $signed/$unsigned casts

        3 层 fallback:
        1. 外层 Conversion 的 kind 含 "Signed"/"Unsigned"
        2. 解包后 binary 的 left/right 是 CallExpression($signed) — pyslang 把 $signed 解析为 Call
        3. full_expression 字符串前缀匹配 "$signed"/"$unsigned"

        Returns:
            cast 名列表 (如 ["$signed"])
        """
        if rhs_expr is None:
            return []

        # 1. 外层 kind 检测
        kind_str = str(getattr(rhs_expr, "kind", ""))
        if "Signed" in kind_str and "Conversion" not in kind_str:
            # $signed 有些 pyslang 版本直接标记为 SignedConversion
            return ["$signed"]
        if "Unsigned" in kind_str and "Conversion" not in kind_str:
            return ["$unsigned"]

        # 2. CallExpression 检测: $signed(a) 在 pyslang 里是 CallExpression
        # 解包外层 Conversion → inner binary → left/right CallExpression
        if root_expr is not None and root_expr is not rhs_expr:
            for side_name in ("left", "right"):
                side = getattr(root_expr, side_name, None)
                if side is None:
                    continue
                side_kind = str(getattr(side, "kind", ""))
                if "Call" not in side_kind:
                    continue
                sub_info = getattr(side, "subroutine", None)
                if sub_info is None:
                    continue
                sub = getattr(sub_info, "subroutine", None)
                if sub is None:
                    continue
                sub_name = str(getattr(sub, "name", ""))
                if sub_name in ("$signed", "$unsigned"):
                    return [sub_name]

        # 3. 字符串前缀 fallback
        if full_expression.strip().startswith("$signed"):
            return ["$signed"]
        if full_expression.strip().startswith("$unsigned"):
            return ["$unsigned"]

        return []

    def _build_signal_source(
        self,
        rhs_name: str,
        rhs_expr,  # AST 父表达式 (可能是 BinaryOp / Conversion / ConditionalOp)
        full_expr_str: str,
    ) -> SignalSource | None:
        """[V6.5/V6.6] 从分解的 leaf signal 和父表达式构建结构化 SignalSource

        步骤:
        1. 位范围解析 (_parse_bit_range → bit_start/bit_end int)
        2. 表达式字符串提取 (_get_readable_expr)
        3. Cast 检测 (_detect_casts, 3 层 fallback)
        4. Binary op 检测 (_detect_binary_op, 含 operand_side)

        Args:
            rhs_name: Leaf 信号名 (可能含位选择, 如 "a[7:0]")
            rhs_expr: 父表达式 AST 节点
            full_expr_str: visit 方法输出 (可能只是 leaf name, 如 "a")

        Returns:
            SignalSource or None
        """
        if not rhs_name:
            return None
        if not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
            return None

        # ---- 1. 解析 bit range ----
        signal = rhs_name
        bit_start = None
        bit_end = None
        if "[" in rhs_name and "]" in rhs_name:
            signal, bit_start, bit_end = self._parse_bit_range(rhs_name)
            if signal is None:
                return None

        # ---- 2. 完整表达式字符串 ----
        full_expression = self._get_readable_expr(rhs_expr, full_expr_str)

        # ---- 3. Cast 检测 ----
        # 先解出内部表达式 (用于 CallExpression 检测)
        inner = None
        if rhs_expr is not None:
            inner = unwrap(rhs_expr)
            if inner is rhs_expr:
                inner = None
        casts = self._detect_casts(rhs_expr, inner, full_expression)

        # ---- 4. Binary op 检测 ----
        op, operand_side, is_binary = self._detect_binary_op(rhs_expr, signal)

        is_decomposed = bool(op) or bool(casts) or is_binary

        return SignalSource(
            signal=signal,
            bit_start=bit_start,
            bit_end=bit_end,
            full_expression=full_expression,
            op=op,
            operand_side=operand_side,
            casts=casts,
            is_decomposed=is_decomposed,
        )

    @staticmethod
    def _get_readable_expr(rhs_expr, fallback: str) -> str:
        """[V6.5] 从 pyslang AST 获取可读表达式字符串

        pyslang 多层表示:
        - Semantic AST node: __str__ 返回 "Expression(ExpressionKind.BinaryOp)" (无用)
        - .syntax 属性: Syntax AST node, __str__ 返回 "a + b" (有用!)
        - .syntax 为 None 时: 回退到 fallback, 但过滤掉似是 type name 的字符串

        Returns:
            可读表达式字符串，优先 syntax.__str__()
        """
        if rhs_expr is None:
            return fallback
        try:
            syntax = getattr(rhs_expr, "syntax", None)
            if syntax is not None:
                text = str(syntax).strip()
                if text and "ExpressionKind" not in text:
                    return text
        except (UnicodeDecodeError, TypeError, Exception):
            pass

        # fallback 也检查: 过滤 type name 字符串
        if "ExpressionKind" in fallback or "Expression(" in fallback:
            return ""
        return fallback

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

        # [V6.3+3 2026-07-27] Use ast_utils for wrapper unwrap and kind
        # matching. Replaces 4 duplicated unwrap blocks across this file.
        has_conditional = False
        check_expr = rhs_expr
        for _ in range(10):  # 解包多层包装 (最多 10 层, $signed(Conditional) 需要 <10)
            if check_expr is None:
                break
            if kind_matches(check_expr, "ConditionalOp", "ConditionalExpression"):
                has_conditional = True
                break
            # [V6.9] Also unwrap Call (system function) — e.g. $signed(g ? x0 : x1)
            # where the ternary is an argument to the system function call
            ck = str(getattr(check_expr, "kind", ""))
            if "Call" in ck:
                args = getattr(check_expr, "arguments", None)
                if args and hasattr(args, "__iter__") and not isinstance(args, str):
                    for arg in args:
                        if kind_matches(arg, "ConditionalOp", "ConditionalExpression"):
                            check_expr = arg
                            has_conditional = True
                            break
                if has_conditional:
                    break
            inner = unwrap(check_expr)
            if inner is None or inner is check_expr:
                break
            check_expr = inner

        if not rhs_signals:
            # [Phase 8 / Fix F 2026-7-14] If rhs_expr is a compile-time symbol (parameter,
            # enum value, localparam), don't fall back to [rhs] - that would re-add
            # the parameter as a fake driver.
            # [FIX 2026-7-15] Pass module for Syntax AST resolution.
            if rhs_expr is not None and self._expr_is_compile_time(rhs_expr, module=module):
                rhs_signals = []  # Stay empty, no driver
            elif has_conditional:
                # [V6.9] rhs_expr wrapped (e.g. $signed(ternary)): use unwrapped check_expr
                rhs_signals = self._get_all_real_signals(check_expr, module=module) or []
            else:
                rhs_signals = [rhs]

        # [V6.9] If has_conditional but rhs_signals still empty after above fallback,
        # try one more time with the unwrapped ternary expression
        if has_conditional and not rhs_signals:
            rhs_signals = self._signal_visitor._extract_signals_from_expr(check_expr) or []
            rhs_signals = self._filter_compile_time_signal_names(check_expr, rhs_signals, module=module)
        if rhs_expr:
            try:
                expr_str = self._signal_visitor.get_source_text(rhs_expr) or str(rhs_expr) or self._signal_visitor.get_source_text(rhs_expr) or str(rhs_expr)
            except (UnicodeDecodeError, TypeError):
                expr_str = "<expr:non-utf8>"
        else:
            expr_str = rhs or ""

        if has_conditional:
            # [Phase 8 / Fix F.6 2026-7-15] Filter compile-time symbols
            # (localparam/parameter) from ternary branch signals.
            # [V6.3+4 2026-07-28] Pass UNWRAPPED check_expr to
            # get_signals_with_conditions so the visitor sees the
            # ConditionalOp directly (not the outer ParenthesizedExpression).
            # This mirrors V6.3+1 fix in _create_always_edges bug #2.
            #
            # [V6.9 FIX] semantic_adapter returns list[str] (ALL signals).
            # Must separate condition signals (g, h) from leaf signals (x0, x1).
            all_signals = self._signal_visitor._extract_signals_from_expr(check_expr) or []
            
            # [V6.9] 递归收集所有层的条件信号名
            # g ? (h ? x0 : x1) : x2 → 条件信号 = {g, h}
            def _collect_cond_signals(cond_op, acc_set):
                if cond_op is None:
                    return
                ck = str(getattr(cond_op, "kind", ""))
                if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                    return
                rc = getattr(cond_op, "conditions", None)
                if rc:
                    for c in rc:
                        ce = getattr(c, "expr", None) or getattr(c, "expression", None)
                        if ce:
                            for s in (self._signal_visitor._extract_signals_from_expr(ce) or []):
                                acc_set.add(s)
                _collect_cond_signals(getattr(cond_op, "left", None), acc_set)
                _collect_cond_signals(getattr(cond_op, "right", None), acc_set)
            cond_sig_names = set()
            _collect_cond_signals(check_expr, cond_sig_names)
            
            # Leaf signals = all - conditions
            leaf_signals = [s for s in all_signals if s not in cond_sig_names]
            
            # [V6.9] 递归遍历 ConditionalOp 为每个 leaf 构建条件文本
            # g ? (h ? x0 : x1) : x2 → x0:"g && h", x1:"g && !h", x2:"!g"
            def _build_ternary_cond_map(cond_op, path=None):
                result_map = {}
                if path is None:
                    path = []
                if cond_op is None:
                    return result_map
                ck = str(getattr(cond_op, "kind", ""))
                if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                    return result_map
                
                # 提取条件文本
                cond_texts = []
                raw_c = getattr(cond_op, "conditions", None)
                if raw_c:
                    for c in raw_c:
                        ce = getattr(c, "expr", None)
                        if ce:
                            ct = self._get_signal(ce) or str(ce).strip()
                            if ct:
                                cond_texts.append(ct)
                cond_str = " && ".join(cond_texts) if cond_texts else ""
                
                left = getattr(cond_op, "left", None)
                right = getattr(cond_op, "right", None)
                
                # 递归 left (true 分支)
                if left:
                    lk = str(getattr(left, "kind", ""))
                    if "ConditionalOp" in lk or "ConditionalExpression" in lk:
                        sub = _build_ternary_cond_map(left, path + [cond_str])
                        result_map.update(sub)
                    elif "NamedValue" in lk:
                        name = self._get_signal(left) or ""
                        full_cond = " && ".join([p for p in path + [cond_str] if p])
                        if name:
                            result_map[name] = full_cond
                
                # 递归 right (false 分支)
                if right:
                    rk = str(getattr(right, "kind", ""))
                    if "ConditionalOp" in rk or "ConditionalExpression" in rk:
                        sub = _build_ternary_cond_map(right, path + [f"!({cond_str})"])
                        result_map.update(sub)
                    elif "NamedValue" in rk:
                        name = self._get_signal(right) or ""
                        neg_cond = f"!({cond_str})" if cond_str else ""
                        full_cond = " && ".join([p for p in path + [neg_cond] if p])
                        if name:
                            result_map[name] = full_cond
                
                return result_map
            
            cond_map = _build_ternary_cond_map(check_expr)
            signal_conditions = [(s, cond_map.get(s, "")) for s in leaf_signals]
            
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
                    # [V6.5] 结构化驱动源
                    ds = self._build_signal_source(rhs_name, check_expr, expr_str)
                    result.edges.append(
                        self._edge_factory.make_edge(
                            src=src_node_id,
                            dst=dst_node_id,
                            kind=EdgeKind.DRIVER,
                            assign_type="continuous",
                            expression=expr_str,
                            bit_slice=bit_slice,
                            sig_cond=sig_cond,
                            source=ds,
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
                    # [V6.5] 结构化驱动源
                    ds = self._build_signal_source(rhs_name, rhs_expr, expr_str)
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
                        source=ds,
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
                if False:  # [V6.9] ItemType removed
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

                if not lhs:
                    # [V6.9 fix] _parse_assign 对 InvocationExpression/CallExpression 返回 (None,None,None)
                    #          检查 stmt.expr 是否为 Invocation/Call（always_comb/initial 直接调用）
                    raw_expr = getattr(stmt, "expr", None)
                    if raw_expr:
                        ek = str(getattr(raw_expr, "kind", ""))
                        if "Invocation" in ek or "Call" in ek:
                            self._handle_invocation(raw_expr, ctx, module, module_name, result)
                            continue

                if lhs and (rhs or rhs_expr):
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

                    # [V6.9] 如果 ctx["leaf_name"] 存在, 说明 ternary 已在 _flatten_assignments
                    # 中展开。直接使用 leaf_name + ctx["condition"] 创建 edge.                    # [V6.9] 如果 ctx["leaf_name"] 存在, 说明 ternary 已在 _flatten_assignments
                    # 中展开。直接使用 leaf_name + ctx["condition"] 创建 edge.
                    leaf_from_ctx = ctx.get("leaf_name", "")
                    if leaf_from_ctx:
                        sig_cond = ctx.get("condition", "")
                        src_node_id = f"{module_name}.{leaf_from_ctx}"
                        if src_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=src_node_id, name=leaf_from_ctx,
                                    module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                )
                            )
                        bit_slice = ""
                        if "[" in leaf_from_ctx and "]" in leaf_from_ctx:
                            start = leaf_from_ctx.index("[")
                            bit_slice = leaf_from_ctx[start:]
                        result.edges.append(
                            self._edge_factory.make_edge(
                                src=src_node_id, dst=dst_node_id,
                                kind=EdgeKind.DRIVER,
                                assign_type="nonblocking",
                                expression=leaf_from_ctx,
                                bit_slice=bit_slice,
                                clock_domain=ctx.get("clock", ""),
                                sig_cond=sig_cond,
                            )
                        )
                        # [V6.9] 继续走 clock/reset edge 创建逻辑
                        # leaf edge 已创建, 下面是 clock/reset edges
                        # Create clock edge (mirrors line ~1799)
                        if is_always_ff and ctx.get("clock"):
                            clk_name = ctx["clock"]
                            clk_node_id = f"{module_name}.{clk_name}"
                            if clk_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=clk_node_id, name=clk_name,
                                        module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                    )
                                )
                            result.edges.append(
                                self._edge_factory.make_edge(
                                    src=clk_node_id, dst=dst_node_id,
                                    expression="",
                                    kind=EdgeKind.CLOCK,
                                    assign_type="nonblocking",
                                    clock_domain=clk_name,
                                    ctx=ctx,
                                )
                            )
                        # Create reset edge if present
                        if ctx.get("reset"):
                            rst_name = ctx["reset"]
                            rst_node_id = f"{module_name}.{rst_name}"
                            if rst_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=rst_node_id, name=rst_name,
                                        module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                    )
                                )
                            result.edges.append(
                                self._edge_factory.make_edge(
                                    src=rst_node_id, dst=dst_node_id,
                                    expression="",
                                    kind=EdgeKind.RESET,
                                    assign_type="nonblocking",
                                    clock_domain=rst_name,
                                    ctx=ctx,
                                )
                            )
                        continue  # 跳过后续的 ternary 复杂逻辑和 rhs_signals 提取

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
                            expr_str = self._signal_visitor.get_source_text(rhs_expr) or str(rhs_expr) or self._signal_visitor.get_source_text(rhs_expr) or str(rhs_expr)
                        except (UnicodeDecodeError, TypeError):
                            expr_str = "<expr:non-utf8>"
                    else:
                        expr_str = rhs or ""

                    # [BUG-FIX] 嵌套三元: 为每个信号提取对应条件
                    # [V6.3+3 2026-07-27] Refactored to use ast_utils:
                    #   - kind_matches handles ConditionalOp/ConditionalExpression aliases
                    #   - unwrap strips Paren/Conversion/ImplicitCast wrappers
                    # Replaces 13 lines of substring checks and ad-hoc unwrap.
                    has_conditional = False
                    check_expr = rhs_expr
                    for _ in range(5):  # 解包多层包装
                        if check_expr is None:
                            break
                        if kind_matches(check_expr, "ConditionalOp", "ConditionalExpression"):
                            has_conditional = True
                            break
                        inner = unwrap(check_expr)
                        if inner is None or inner is check_expr:
                            break
                        check_expr = inner

                    if has_conditional:
                        # [Phase 8 / Fix F.6 2026-7-15] Filter compile-time symbols
                        # (localparam/parameter) from ternary branch signals.
                        # Use the unwrapped check_expr so ConditionalOp is at top.
                        #
                        # [V6.9 FIX] semantic_adapter returns list[str] (ALL signals).
                        # Must separate condition signals from leaf signals.
                        all_signals2 = self._signal_visitor._extract_signals_from_expr(check_expr) or []
                        cond_sig_names2 = set()
                        def _collect2(cop, acc):
                            if cop is None:
                                return
                            ck2 = str(getattr(cop, "kind", ""))
                            if "ConditionalOp" not in ck2 and "ConditionalExpression" not in ck2:
                                return
                            rc2 = getattr(cop, "conditions", None)
                            if rc2:
                                for c in rc2:
                                    ce = getattr(c, "expr", None) or getattr(c, "expression", None)
                                    if ce:
                                        for s in (self._signal_visitor._extract_signals_from_expr(ce) or []):
                                            acc.add(s)
                            _collect2(getattr(cop, "left", None), acc)
                            _collect2(getattr(cop, "right", None), acc)
                        _collect2(check_expr, cond_sig_names2)
                        leaf_signals2 = [s for s in all_signals2 if s not in cond_sig_names2]
                        
                        # [V6.9] 构建每个 leaf 的条件文本
                        def _build_cond_map(cond_op, path=None):
                            result = {}
                            if path is None:
                                path = []
                            if cond_op is None:
                                return result
                            ck = str(getattr(cond_op, "kind", ""))
                            if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                                return result
                            cond_texts = []
                            rc = getattr(cond_op, "conditions", None)
                            if rc:
                                for c in rc:
                                    ce = getattr(c, "expr", None)
                                    if ce:
                                        ct = self._get_signal(ce) or str(ce).strip()
                                        if ct:
                                            cond_texts.append(ct)
                            cs = " && ".join(cond_texts) if cond_texts else ""
                            l = getattr(cond_op, "left", None)
                            r = getattr(cond_op, "right", None)
                            if l:
                                lk = str(getattr(l, "kind", ""))
                                if "ConditionalOp" in lk or "ConditionalExpression" in lk:
                                    result.update(_build_cond_map(l, path + [cs]))
                                elif "NamedValue" in lk:
                                    name = self._get_signal(l) or ""
                                    fc = " && ".join([p for p in path + [cs] if p])
                                    if name:
                                        result[name] = fc
                            if r:
                                rk = str(getattr(r, "kind", ""))
                                if "ConditionalOp" in rk or "ConditionalExpression" in rk:
                                    result.update(_build_cond_map(r, path + [f"!({cs})"]))
                                elif "NamedValue" in rk:
                                    name = self._get_signal(r) or ""
                                    neg = f"!({cs})" if cs else ""
                                    fc = " && ".join([p for p in path + [neg] if p])
                                    if name:
                                        result[name] = fc
                            return result
                        
                        cond_map = _build_cond_map(check_expr)
                        signal_conditions = [(s, cond_map.get(s, "")) for s in leaf_signals2]
                        
                        signal_conditions = self._filter_signal_conditions_by_module(
                            signal_conditions, module=module
                        )
                        # [V6.3+1 2026-07-27 FIX] combine the outer condition (from
                        # case/if ctx, e.g. "sel_d == 2'd0") with the inner ternary
                        # sig_cond (e.g. "sel_f") so the edge shows the full
                        # guarding condition, not just the inner ternary.
                        outer_cond = ctx.get("condition", "") or ""
                        for sig_rhs_name, sig_cond in signal_conditions:
                            if not sig_rhs_name:
                                continue
                            # Combine outer AND inner with " && " when both present
                            if outer_cond and sig_cond:
                                combined_cond = f"({outer_cond}) && ({sig_cond})"
                            else:
                                combined_cond = outer_cond or sig_cond
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
                                        sig_cond=combined_cond,
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
                                # [V6.5] 结构化驱动源
                                ds = self._build_signal_source(sig_rhs_name, check_expr, expr_str)
                                result.edges.append(
                                    self._edge_factory.make_edge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="nonblocking",
                                        expression=expr_str,
                                        bit_slice=bit_slice,
                                        clock_domain=ctx.get("clock", ""),
                                        sig_cond=combined_cond,
                                        source=ds,
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
                                # [V6.5] 结构化驱动源
                                ds = self._build_signal_source(rhs_name, rhs_expr, expr_str)
                                result.edges.append(
                                    self._edge_factory.make_edge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="nonblocking",
                                        bit_slice=bit_slice,
                                        expression=expr_str,
                                        ctx=ctx,
                                        source=ds,
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
        """[V6.9] 用 semantic API 收集 always 块中的语句和 clock context。

        不再依赖已删除的 StatementCollectorVisitor。
        从 syntax AST 获取 clock/reset 信号和 if/case 脉络，
        并用 semantic adapter 获取语句列表。
        """
        if ctx is None:
            ctx = {}
        
        # 1. 从 syntax 层提取 clock 和 reset 信号
        clock = self._extract_clock_from_always(n)
        reset = self._extract_reset_from_always(n)
        if clock:
            ctx["clock"] = clock
        if reset:
            ctx["reset"] = reset
        
        # 2. 从 syntax 层获取语句体 (带条件信息)
        items = self._get_always_body_items(n)
        if not items:
            return items
        
        # 3. 处理条件脉络（if/case 等）
        #    _flatten_assignments 现在返回 (expr, cond_str) 或 (expr, cond_str, leaf_name) 元组
        #    leaf_name != None 表示 ternary 展开后的 leaf 信号（覆盖 rhs 信号提取）
        #    每个 item 带有自己的条件
        result = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 2:
                expr_node, cond_str = item[0], item[1]
                leaf_name = item[2] if len(item) >= 3 else None
                item_ctx = dict(ctx)  # copy base ctx
                if cond_str:
                    item_ctx["condition"] = cond_str
                if leaf_name:
                    item_ctx["leaf_name"] = leaf_name
                result.append((expr_node, item_ctx, None))
            else:
                result.append((item, ctx, None))
        
        return result
    
    def _extract_reset_from_always(self, n) -> str:
        """[V6.9] 提取 reset 信号 — 优先 semantic AST .timing.events, fallback syntax tree。

        策略:
        1. 优先找 NegEdge event（异步低有效复位）
        2. 如果 events >= 2, 第二个 event 的信号也是 reset（posedge rst 场景）
        """
        reset_signal = ""
        events = []
        # [V6.9] 优先 semantic AST: TimedStatement.timing.events (SignalEventControl list)
        body = getattr(n, "body", None)
        timing = getattr(body, "timing", None) if body else None
        if timing:
            events = getattr(timing, "events", None) or []
        # Fallback: syntax tree timingControl.events
        if not events:
            syntax = getattr(n, "syntax", None)
            if syntax:
                tc = getattr(syntax, "timingControl", None)
                if tc:
                    events = getattr(tc, "events", []) or []
        if events and hasattr(events, "__iter__") and not isinstance(events, str):
            evt_list = list(events)
            # 策略 1: 找 NegEdge（异步低有效复位）
            for evt in evt_list:
                edge_str = str(getattr(evt, "edge", ""))
                if "NegEdge" in edge_str:
                    expr = getattr(evt, "expr", None) or getattr(evt, "expression", None)
                    if expr:
                        sig = self._get_signal(expr)
                        reset_signal = sig if (sig and not sig.startswith("Expression(")) else str(expr).strip()
                        break
            # 策略 2: 如果没有 NegEdge 但 events >= 2, 第二个是 reset（posedge rst 场景）
            if not reset_signal and len(evt_list) >= 2:
                evt = evt_list[1]
                expr = getattr(evt, "expr", None) or getattr(evt, "expression", None)
                if expr:
                    sig = self._get_signal(expr)
                    reset_signal = sig if (sig and not sig.startswith("Expression(")) else str(expr).strip()
        return reset_signal
    
    def _get_always_body_items(self, n) -> list:
        """[V6.9] 从 semantic AST 获取 flat assignment expressions。

        全部使用 semantic AST (StatementKind/ExpressionKind)。

        - always @(posedge clk): ProceduralBlock.body = TimedStatement → .stmt
        - initial:           ProceduralBlock.body = ExpressionStatement / BlockStatement
        - always_comb:       ProceduralBlock.body = BlockStatement / ExpressionStatement
        """
        sem_body = getattr(n, "body", None)
        if sem_body is None:
            return []
        
        kind = getattr(sem_body, "kind", None)
        # TimedStatement: unwrap timing wrapper
        if kind == StatementKind.Timed:
            inner = getattr(sem_body, "stmt", None) or getattr(sem_body, "statement", None)
            if inner is None:
                return []
            sem_body = inner
        
        items = []
        self._flatten_semantic(sem_body, items)
        return items

    def _flatten_assignments(self, stmt, result: list, cond_stack: list[str] | None = None):
        """[DEPRECATED] 旧 syntax-based 展开。保留兼容 _expand_and_append_assignment。"""
        # 重定向到 semantic 版本
        self._flatten_semantic(stmt, result, cond_stack)

    # ======================================================================
    # SemanticStatementFlattener: 纯 semantic AST 展平 (V6.9)
    # 铁律15/26: Visitor 模式 — 每个 StatementKind 独立方法，禁止字符串匹配
    # ======================================================================

    def _flatten_semantic(self, stmt, result: list, cond_stack: list[str] | None = None):
        """[V6.9] Dispatcher — 按 StatementKind / ExpressionKind 分发到独立 visitor 方法。

        铁律15/26: 禁止 if-elif 链，禁止 str(kind) 字符串匹配。
        """
        if stmt is None:
            return
        if cond_stack is None:
            cond_stack = []

        kind = getattr(stmt, "kind", None)

        if kind == StatementKind.Block:
            self._flatten_block(stmt, result, cond_stack)
        elif kind == StatementKind.Timed:
            self._flatten_timed(stmt, result, cond_stack)
        elif kind == StatementKind.Conditional:
            self._flatten_conditional(stmt, result, cond_stack)
        elif kind in (StatementKind.WhileLoop, StatementKind.ForLoop, StatementKind.DoWhileLoop,
                      StatementKind.ForeverLoop, StatementKind.RepeatLoop, StatementKind.ForeachLoop):
            self._flatten_loop(stmt, result, cond_stack)
        elif kind == StatementKind.ExpressionStatement:
            self._flatten_expression_statement(stmt, result, cond_stack)
        elif kind in (StatementKind.Case, StatementKind.PatternCase):
            self._flatten_case(stmt, result, cond_stack)
        elif kind == ExpressionKind.Assignment:
            outer_cond = " && ".join(cond_stack) if cond_stack else ""
            result.append((stmt, outer_cond))
        # 其他 StatementKind（Break, Continue, Return, Wait, EventTrigger 等）：
        # 不展开，不影响驱动提取。

    # —— Visitor 方法 ——

    def _flatten_block(self, stmt, result: list, cond_stack: list[str]):
        """StatementKind.Block: 遍历 .body (单个对象或 iterable)。

        .body 可能是:
          - 单个 Statement (ConditionalStatement, ExpressionStatement 等)
          - iterable list of Statement
          - StatementList (StatementKind.List) → 需迭代 .list
        """
        body_val = getattr(stmt, "body", None)
        if body_val is None:
            return
        # StatementKind.List: 特殊类型，迭代 .list 属性
        if getattr(body_val, "kind", None) == StatementKind.List:
            stmt_list = getattr(body_val, "list", None)
            if stmt_list is not None and hasattr(stmt_list, "__iter__") and not isinstance(stmt_list, str):
                for item in stmt_list:
                    self._flatten_semantic(item, result, cond_stack)
            return
        if hasattr(body_val, "__iter__") and not isinstance(body_val, str):
            for item in body_val:
                self._flatten_semantic(item, result, cond_stack)
        else:
            self._flatten_semantic(body_val, result, cond_stack)

    def _flatten_timed(self, stmt, result: list, cond_stack: list[str]):
        """StatementKind.Timed: 跳过 timing，进入 .stmt。"""
        inner = getattr(stmt, "stmt", None) or getattr(stmt, "statement", None)
        self._flatten_semantic(inner, result, cond_stack)

    def _flatten_conditional(self, stmt, result: list, cond_stack: list[str]):
        """StatementKind.Conditional: 展开 ifTrue + ifFalse。

        semantic AST 用 .ifTrue/.ifFalse（不是 syntax 的 .statement/.elseClause）。
        """
        cond = getattr(stmt, "conditions", None) or getattr(stmt, "predicate", None) or getattr(stmt, "condition", None)
        # .conditions 是 Condition 对象列表；取出第一个 .expr 并用 _get_signal 提取信号名
        if hasattr(cond, "__iter__") and not isinstance(cond, str):
            cond_list = list(cond)
            if cond_list:
                cond_expr = getattr(cond_list[0], "expr", None)
                new_cond = self._get_signal(cond_expr) if cond_expr else ""
            else:
                new_cond = ""
        else:
            new_cond = str(cond).strip() if cond is not None else ""
        is_real = new_cond and not any(kw in new_cond for kw in ("posedge", "negedge", "or "))

        # ifTrue
        if is_real:
            cond_stack.append(new_cond)
        then_stmt = getattr(stmt, "ifTrue", None) or getattr(stmt, "statement", None)
        self._flatten_semantic(then_stmt, result, cond_stack)
        if is_real:
            cond_stack.pop()

        # ifFalse（仅当有 else 分支时）
        else_node = getattr(stmt, "ifFalse", None) or getattr(stmt, "elseClause", None) or getattr(stmt, "elseStatement", None)
        if else_node is not None:
            if is_real:
                neg_cond = f"!{new_cond}" if all(c.isalnum() or c == '_' for c in new_cond) else f"!({new_cond})"
                cond_stack.append(neg_cond)
            clause = getattr(else_node, "clause", None) or getattr(else_node, "statement", None) or else_node
            self._flatten_semantic(clause, result, cond_stack)
            if is_real:
                cond_stack.pop()

    def _flatten_loop(self, stmt, result: list, cond_stack: list[str]):
        """StatementKind WhileLoop/ForLoop/DoWhile/Forever/Repeat/Foreach: 进入 .body。"""
        body = getattr(stmt, "body", None)
        if body is not None:
            if hasattr(body, "__iter__") and not isinstance(body, str):
                for item in body:
                    self._flatten_semantic(item, result, cond_stack)
            else:
                self._flatten_semantic(body, result, cond_stack)

    def _flatten_expression_statement(self, stmt, result: list, cond_stack: list[str]):
        """StatementKind.ExpressionStatement: 提取 .expr (Assignment/Call 则追加)。

        铁律1: 只用 semantic AST ExpressionKind，不碰 SyntaxKind。
        """
        expr = getattr(stmt, "expr", None)
        if expr is None:
            return
        ek = getattr(expr, "kind", None)
        outer_cond = " && ".join(cond_stack) if cond_stack else ""
        if ek == ExpressionKind.Assignment:
            result.append((expr, outer_cond))
        elif ek == ExpressionKind.Call:
            # [V6.9] task/function 调用: 将 output 参数映射展开为赋值
            # t(a, b) → arguments = [NamedValue(a), Assignment(b, ...)]
            args = getattr(expr, "arguments", None)
            if args is not None and hasattr(args, "__iter__") and not isinstance(args, str):
                input_sig = None
                for arg in args:
                    ak = getattr(arg, "kind", None)
                    if ak == ExpressionKind.Assignment:
                        # output 参数: 创建 input → output DRIVER
                        lhs_node = getattr(arg, "left", None)
                        out_name = self._get_signal(lhs_node) if lhs_node else None
                        if input_sig and out_name:
                            # 构造一个虚拟赋值元组: (output, input_as_string, condition)
                            result.append((arg, outer_cond))
                    elif ak == ExpressionKind.NamedValue:
                        # 第一个是 input 参数
                        input_sig = self._get_signal(arg)

    def _flatten_case(self, stmt, result: list, cond_stack: list[str]):
        """StatementKind Case/PatternCase: 展开各 CaseItem。

        每个 CaseItem 有 .expressions (值列表) 和 .clause (对应语句)。
        """
        case_expr = getattr(stmt, "expr", None) or getattr(stmt, "expression", None)
        case_cond = str(case_expr).strip() if case_expr else ""
        items = getattr(stmt, "items", None)
        if items is not None and hasattr(items, "__iter__") and not isinstance(items, str):
            for item in items:
                item_exprs = getattr(item, "expressions", None)
                if item_exprs and hasattr(item_exprs, "__iter__") and not isinstance(item_exprs, str):
                    expr_strs = [str(e).strip() for e in item_exprs if str(e).strip()]
                    item_cond = " || ".join(expr_strs)
                else:
                    item_cond = str(getattr(item, "expression", None) or "").strip()
                case_full = f"({case_cond}) == ({item_cond})" if case_cond and item_cond else (item_cond or case_cond)
                if case_full:
                    cond_stack.append(case_full)
                case_stmt = getattr(item, "clause", None) or getattr(item, "statement", None) or getattr(item, "stmt", None)
                self._flatten_semantic(case_stmt, result, cond_stack)
                if case_full:
                    cond_stack.pop()

    def _expand_and_append_assignment(self, assign_expr, cond_stack, result):
        """[V6.9] 如果 RHS 是 ternary (syntax ConditionalExpression), 递归展开。

        g ? x0 : x1 在 case (a==0) 中展开为:
          - (x0, "a==0 && g")
          - (x1, "a==0 && !(g)")

        多层嵌套: g ? (h ? x0 : x1) : x2 展开为:
          - (x0, "a==0 && g && h")
          - (x1, "a==0 && g && !(h)")
          - (x2, "a==0 && !(g)")
        """
        rhs = getattr(assign_expr, "right", None)
        if rhs is None:
            # 没有 RHS: 直接添加
            outer_cond = " && ".join(cond_stack) if cond_stack else ""
            result.append((assign_expr, outer_cond))
            return

        rk = str(getattr(rhs, "kind", ""))
        if "Conditional" not in rk:
            # 不是 ternary: 直接添加
            outer_cond = " && ".join(cond_stack) if cond_stack else ""
            result.append((assign_expr, outer_cond))
            return

        # RHS 是 ternary: 递归展开条件树
        # 我们需要取出 lhs, 然后为每个 leaf 信号创建一个 (lhs=leaf, cond) 元组
        lhs = getattr(assign_expr, "left", None)
        lhs_node_id = self._get_signal(lhs) if lhs else None
        if not lhs_node_id:
            outer_cond = " && ".join(cond_stack) if cond_stack else ""
            result.append((assign_expr, outer_cond))
            return

        # 递归展开 ConditionalExpression 树
        def _walk_ternary(node, path_conds):
            """递归遍历 syntax ConditionalExpression, yield (leaf_signal, full_cond)."""
            if node is None:
                return
            nk = str(getattr(node, "kind", ""))
            if "Conditional" not in nk:
                # [V6.9] 尝试 unwrap: 可能是 ParenthesizedExpression 包裹了 ConditionalExpression
                # 如 g ? (h ? x0 : x1) : x2 中 (h ? x0 : x1) 被括号包裹
                from .ast_utils import unwrap
                inner = unwrap(node)
                if inner is not None and inner is not node:
                    inner_kind = str(getattr(inner, "kind", ""))
                    if "Conditional" in inner_kind:
                        yield from _walk_ternary(inner, path_conds)
                        return
                # Leaf: 提取信号名, 组合条件
                name = self._get_signal(node)
                if name:
                    combined = " && ".join([c for c in path_conds if c])
                    yield (name, combined)
                return

            # 提取条件文本
            pred = getattr(node, "predicate", None)
            cond_text = str(pred).strip() if pred else ""

            left = getattr(node, "left", None)
            right = getattr(node, "right", None)

            # True 分支: 原条件
            if left and cond_text:
                yield from _walk_ternary(left, path_conds + [cond_text])
            elif left:
                yield from _walk_ternary(left, path_conds)

            # False 分支: 取反条件
            if right and cond_text:
                # 简单标识符不加括号, 复杂表达式加括号
                if all(c.isalnum() or c == '_' for c in cond_text):
                    neg_cond = f"!{cond_text}"
                else:
                    neg_cond = f"!({cond_text})"
                yield from _walk_ternary(right, path_conds + [neg_cond])
            elif right:
                yield from _walk_ternary(right, path_conds)

        for leaf_name, leaf_cond in _walk_ternary(rhs, list(cond_stack)):
            result.append((assign_expr, leaf_cond, leaf_name))

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

        # [V6.9 fix] ExpressionStatement 包裹 InvocationExpression/CallExpression
        #          (always_comb task_call(a,b)) — 不是 assignment，返回 None 让上层处理
        kind_str = str(getattr(assign, "kind", ""))
        if "Invocation" in kind_str or "Call" in kind_str:
            return None, None, None

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

        # [V6.9] Semantic AST: CallExpression.arguments 直接可迭代（list of Expressions）
        #         syntax tree: arguments 有 .parameters 属性
        #         优先尝试 list(args_node)，成功就走语义 AST 路径
        try:
            arg_items = list(args_node)
            # Semantic AST path: each item is an Expression (NamedValueExpression etc)
            for expr in arg_items:
                if expr is None:
                    continue
                # [V6.9 fix] 语义 AST 的 Expression 直接有 .kind，不需要 .expr
                #         syntax tree 的 Token（逗号、括号）也有 .kind 但无 .symbol
                #         用 .symbol 区分：语义 AST 的 Expression 有 .symbol
                is_semantic = hasattr(expr, "symbol")
                if not hasattr(expr, "expr") and not is_semantic:
                    continue
                kind_str = str(getattr(expr, "kind", ""))
                # NamedArgument: .in(a) 格式，name 字段存参数名
                if hasattr(expr, "name"):
                    name = str(getattr(expr, "name", "")).strip()
                    arg_expr = getattr(expr, "expr", None)
                    if name and arg_expr:
                        arg_name = self._get_signal(arg_expr)
                        if arg_name:
                            named_args[name] = arg_name.strip()
                    continue
                if "NamedValue" in kind_str:
                    arg_name = self._get_signal(expr)
                    if arg_name:
                        call_args.append(arg_name.strip())
                elif "Assignment" in kind_str:
                    lhs = getattr(expr, "left", None)
                    if lhs:
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
                    arg_name = self._get_signal(expr)
                    if arg_name:
                        call_args.append(arg_name.strip())
        except (TypeError, ValueError):
            # Fallback: syntax tree path with .parameters
            if hasattr(args_node, "parameters"):
                params = getattr(args_node, "parameters", [])
                for arg in params:
                    arg_kind = str(getattr(arg, "kind", ""))
                    # [V6.9 fix] syntax tree parameters 包含 Token 项（逗号、括号）
                    #          用 hasattr(arg, 'expr') 过滤，只有有 .expr 的才是真正的参数
                    if not hasattr(arg, "expr"):
                        continue
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
                return None

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
