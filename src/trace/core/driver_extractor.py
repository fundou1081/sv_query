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
from typing import Any

from pyslang.pyslang.ast import (
    BinaryOperator,  # [V6.9] semantic AST only (ExpressionKind/StatementKind 已随 Step 5/6 拆走)
)

from .ast_utils import unwrap  # [V6.3+3 2026-07-27] (kind_matches 已随 Step 6 always 拆走)
from .base import PyslangAdapter
from .builder.subroutine_expander import SubroutineExpander  # [Step 7] CallSiteInfo 已随 function_extractor 拆走
from .edge_factory import TraceEdgeFactory
from .extractor_models import ExtractorResult  # [P1 cycle 9] 共享
from .graph.models import EdgeKind, NodeKind, SignalSource, TraceNode

# [V6.9] SignalExpressionVisitor removed — using semantic_adapter

logger = logging.getLogger(__name__)


# [P1 cycle 8/9] ExtractorResult 移到了 extractor_models.py (避免循环 import)
# 这里 re-export 保持向后兼容 (from trace.core.driver_extractor import ExtractorResult)
__all__ = ["DriverExtractor", "ExtractorResult"]


def _tree_complexity(d: dict) -> int:
    """计算 tree_dict 的 descendants 总数（含自身）

    用于多分支 case/if 赋值时，选择最复杂的代表表达式。
    """
    total = 1
    for c in d.get('children', []):
        total += _tree_complexity(c)
    return total


def _collect_from_tree(tree_dict: dict, dst_short: str, const_map: dict, func_info: dict) -> None:
    """从 expr_tree 树遍历提取 Const 叶子 → const_map，Call 节点 → func_info

    替代旧 regex 从源码文本扫 assign/wire 行的 const_map 提取方式，
    数据源改为表达式树本身（更准确，旧 regex 在复杂 case 会漏）。
    """
    op = tree_dict.get('op')
    lbl = tree_dict.get('label')
    if op == 'Const' and lbl:
        lst = const_map.setdefault(dst_short, [])
        if lbl not in lst:
            lst.append(lbl)
    if op == 'Call' and lbl:
        if lbl not in func_info:
            func_info[lbl] = None  # 宽度由 extract() 阶段从 semantic function symbol 补充
    for c in tree_dict.get('children', []):
        _collect_from_tree(c, dst_short, const_map, func_info)



class DriverExtractor:
    """Driver 提取器 — 从 semantic AST 的 always/assign 中提取 driver 边。"""

    # [V6.9] BinaryOperator -> 可读符号映射表
    _BINOP_SYMBOL = {
        BinaryOperator.Add: "+",
        BinaryOperator.ArithmeticShiftLeft: "<<<",
        BinaryOperator.ArithmeticShiftRight: ">>>",
        BinaryOperator.BinaryAnd: "&",
        BinaryOperator.BinaryOr: "|",
        BinaryOperator.BinaryXnor: "~^",
        BinaryOperator.BinaryXor: "^",
        BinaryOperator.CaseEquality: "===",
        BinaryOperator.CaseInequality: "!==",
        BinaryOperator.Divide: "/",
        BinaryOperator.Equality: "==",
        BinaryOperator.GreaterThan: ">",
        BinaryOperator.GreaterThanEqual: ">=",
        BinaryOperator.Inequality: "!=",
        BinaryOperator.LessThan: "<",
        BinaryOperator.LessThanEqual: "<=",
        BinaryOperator.LogicalAnd: "&&",
        BinaryOperator.LogicalEquivalence: "<->",
        BinaryOperator.LogicalImplication: "->",
        BinaryOperator.LogicalOr: "||",
        BinaryOperator.LogicalShiftLeft: "<<",
        BinaryOperator.LogicalShiftRight: ">>",
        BinaryOperator.Mod: "%",
        BinaryOperator.Multiply: "*",
        BinaryOperator.Power: "**",
        BinaryOperator.Subtract: "-",
        BinaryOperator.WildcardEquality: "==?",
        BinaryOperator.WildcardInequality: "!=?",
    }

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
        # [Plan F3-pre 2026-08-13] 条件字符串 → 条件 AST 节点映射.
        # _flatten_conditional/_flatten_case 展开时记录, 供 _collect_stmts_with_context
        # 回填 edge.condition_ast (graph_builder condition_ast 填充链路修复).
        self._cond_ast_by_str: dict[str, Any] = {}
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

        [V7.0] 自动从 ctx["condition_chain"] 提取 condition_chain，
        保证三元展开后的列表形式写到 TraceEdge 上。

        Args:
            result: TraceResult.
            src/dst: 边端点.
            kind: EdgeKind enum (default EdgeKind.DRIVER).
            assign_type: "continuous" / "nonblocking" / "alias" / "internal".
            **kwargs: forwarded to TraceEdgeFactory.make_edge
                     (expression, bit_slice, condition, sig_cond,
                      sig_cond_ast, ctx, clock_domain, condition_chain).
        """
        # [V7.0] 从 ctx 提取 condition_chain (由 _expand_and_append_assignment 写入)
        if "condition_chain" not in kwargs:
            c = kwargs.get("ctx", {})
            if isinstance(c, dict) and c.get("condition_chain"):
                kwargs["condition_chain"] = list(c["condition_chain"])

        edge = self._edge_factory.make_edge(
            src=src,
            dst=dst,
            kind=kind,
            assign_type=assign_type,
            **kwargs,
        )
        result.edges.append(edge)

    # ═══════════════════════════════════════════════════════════
    # [REFACTOR 2026-08-07 A计划] ExpressionTree 收集
    # 从 semantic AST 节点的 .syntax 构建表达式树，存入 result.expr_trees
    # 同时遍历树提取 Const → result.const_map，Call → result.func_info
    # 目标: 消灭 viz 层 SyntaxTree.fromText() 源码重读
    # ═══════════════════════════════════════════════════════════



    def _get_constructor_call(self, initializer) -> str | None:
        """[Step 7 2026-08-28] 薄壳, 实际逻辑在 extractors/function_extractor.py."""
        from .extractors.function_extractor import _get_constructor_call
        return _get_constructor_call(initializer, h=self._function_helpers())


    def _get_all_signals(self, signal) -> list[str]:
        """[Step 7 2026-08-28] 薄壳, 实际逻辑在 extractors/function_extractor.py.
        供 AssignHelpers 注入点 get_all_signals=self._get_all_signals 使用.
        """
        from .extractors.function_extractor import _get_all_signals
        return _get_all_signals(signal, h=self._function_helpers())

    def _function_helpers(self):
        """[Step 7 2026-08-28] 构造 FunctionHelpers 注入包."""
        from .extractors.function_extractor import FunctionHelpers
        return FunctionHelpers(
            adapter=self.adapter,
            get_signal=self._get_signal,
            signal_visitor=getattr(self, "_signal_visitor", None),
            edge_factory=getattr(self, "_edge_factory", None),
            subroutine_expander=getattr(self, "_subroutine_expander", None),
        )

    def _store_expr_tree(self, lhs_name, rhs_expr, module_name, result, genvar_ctx: dict | None = None) -> None:
        """从 rhs_expr.syntax 构建 ExpressionTree，存入 result.expr_trees。

        同一 lhs 多 rhs（case/if 多分支）时，收集所有 tree_dict，
        最后取「最复杂」(descendant count max) 的代表。

        [Plan G2 2026-08-27] genvar_ctx 参数 + post-process substitute:
        raw AST ExpressionTree._parse_expr emit leaves like 'acc[i]' (literal),
        即使 generate-for 已经把 LHS 'acc[i+1]' 展开成 'acc[N]'.
        现在用 ctx={'i': N} 在 graph 层 substitute leaf SignalRef 'acc[i]' → 'acc[N]'.
        用户 directive: "viz 不要再从 raw ast 拿数据, 仅从 graph 拿需要的数据".

        Args:
            lhs_name: 被赋值信号名 (不含 module 前缀)
            rhs_expr: pyslang semantic AST 表达式节点 (BinaryOp/ConditionalOp/Call...)
            module_name: 模块/实例路径前缀
            result: ExtractorResult
            genvar_ctx: {genvar_name: int_value} e.g. {'i': 2} for gen_accum iter 2
        """
        if not lhs_name or rhs_expr is None:
            return
        # [Plan F2.6 2026-08-13 BUG FIX] unwrap Conversion wrappers
        # pyslang 在 generate for 块内的 RHS (例如 `a + b`) 会包成
        # ExpressionKind.Conversion (整数提升 / type cast), .syntax 是 None
        # 导致 _store_expr_tree 早返. 递归 unwrap Conversion.operand 找到
        # 真正的 internal expression.
        cur = rhs_expr
        for _ in range(10):  # 最多解 10 层防无限循环
            if cur is None:
                return
            sk = str(getattr(cur, 'kind', ''))
            if 'Conversion' not in sk:
                break
            operand = getattr(cur, 'operand', None)
            if operand is None or operand is cur:
                break
            cur = operand
        syntax = getattr(cur, 'syntax', None)
        if syntax is None:
            return
        try:
            tokens = list(syntax)
        except (TypeError, ValueError):
            return
        if not tokens:
            return

        from .graph.viz.expression_tree import ExpressionTree
        root = ExpressionTree._parse_expr(tokens, 0, len(tokens))
        if root is None:
            return

        tree_key = f"{module_name}.{lhs_name}" if module_name else lhs_name
        tree_dict = ExpressionTree._to_dict(root)

        # [Plan G2 2026-08-27] substitute genvar refs in tree leaves
        # 'acc[i]' (literal) → 'acc[N]' (展开) where N = ctx['i']
        if genvar_ctx and tree_dict:
            tree_dict = DriverExtractor._substitute_genvar_in_tree(tree_dict, genvar_ctx)

        # 多分支合并：已有则保留更复杂的一个
        existing = result.expr_trees.get(tree_key)
        if existing is not None and _tree_complexity(tree_dict) <= _tree_complexity(existing):
            return
        result.expr_trees[tree_key] = tree_dict

        # 从树遍历提取 Const → const_map, Call → func_info
        dst_short = lhs_name
        _collect_from_tree(tree_dict, dst_short, result.const_map, result.func_info)

    @staticmethod
    def _substitute_genvar_in_tree(tree_dict, ctx):
        """[Plan G2 2026-08-27] Walk ExpressionTree._to_dict() tree and substitute
        genvar references in SignalRef leaf labels.

        raw AST ExpressionTree._parse_expr emit leaves like 'acc[i]' (literal),
        even though ctx={'i': N} is available. viz layer reads these labels
        directly → SVG has 'acc[i]' literal. 用户 directive: "viz 不要从 raw AST
        拿数据, 仅从 graph 拿需要的数据" — substitute 发生在 graph 层
        (driver_extractor._store_expr_tree), 不在 viz.

        Args:
            tree_dict: ExpressionTree._to_dict(root) — {op, label, children:[...]}
            ctx: {genvar_name: int_value} (e.g. {'i': 2})

        Returns:
            New tree_dict with leaf labels substituted (or original if no match).
        """
        if not isinstance(tree_dict, dict) or not ctx:
            return tree_dict
        op = tree_dict.get("op", "")
        label = tree_dict.get("label", "")
        children = tree_dict.get("children", []) or []
        new_label = label
        if op in ("SignalRef", "BitSelect") and label:
            if "[" in label and label.endswith("]"):
                base, _, idx_str = label[:-1].rpartition("[")
                if idx_str in ctx:
                    new_label = f"{base}[{ctx[idx_str]}]"
            elif label in ctx:
                new_label = str(ctx[label])
        new_children = [
            DriverExtractor._substitute_genvar_in_tree(c, ctx)
            for c in children if isinstance(c, dict)
        ]
        return {**tree_dict, "label": new_label, "children": new_children}

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

    def _get_all_real_signals(self, signal, module=None, genvar_ctx: dict | None = None) -> list[str]:
        """[Phase 8 / Fix F 2026-7-14 + 2026-7-15] Like _get_all_signals but filters out
        compile-time constants (Parameter, EnumValue, localparam, etc.).

        These symbols look like signals but are not real hardware signals.
        Returning them as drivers would pollute trace_fanin results.

        [FIX 2026-7-15] `module` enables resolution of Syntax AST nodes (IdentifierNameSyntax)
        via module.body.lookupName().
        """
        if signal is None:
            return []
        # [G1 iter_038] 传 ctx 到 _extract_signals_from_expr
        names = self._signal_visitor._extract_signals_from_expr(signal, genvar_ctx) or []
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

        out = []
        for item in signal_conditions:
            # 兼容新旧两种格式: (name, cond) 或 (name, cond, arm_ast)
            if len(item) == 3:
                sig_name, cond_str, arm_ast = item
            else:
                sig_name, cond_str = item
                arm_ast = None
            # Skip empty or pure-digit tokens
            if not sig_name or sig_name.isdigit():
                continue
            # [V6.9] Skip SV literal values like 5'b0, 4'hf, 32'd42 (from _get_signal on Conversion)
            if "'" in sig_name and self._is_sv_literal_token(sig_name):
                continue
            if self._is_sv_literal_token(sig_name):
                continue
            # Resolve via module.body.lookupName
            try:
                sym = body.lookupName(sig_name)
            except Exception:
                sym = None
            if sym is not None and self._is_compile_time_symbol(sym):
                continue  # Skip localparam / parameter / enum value
            if arm_ast is not None:
                out.append((sig_name, cond_str, arm_ast))
            else:
                out.append((sig_name, cond_str))
        return out

    def _get_signal(self, signal, genvar_ctx: dict | None = None) -> str | None:
        """[ARCHITECTURE_TODOLIST #1 Step 3 2026-08-27] 薄壳委托给 extractors._common.get_signal.

        原实现 200 行已迁到 src/trace/core/extractors/_common.py (共享纯函数).
        保留 self._get_signal 调用方零改动 — driver_extractor.py 内 ~40 个调用点.
        """
        from .extractors._common import get_signal
        return get_signal(signal, genvar_ctx, current_module=getattr(self, "_current_module", None))

    # ==============================================================================
    # [NEW] 语义上下文提取方法 - 从 always_ff/if 语句提取时钟域和条件
    # ==============================================================================

    def _fold_constant(self, expr, ctx: dict | None = None) -> int | None:
        """[ARCHITECTURE_TODOLIST #1 Step 3 2026-08-27] 薄壳委托给 extractors._common.fold_constant.

        原实现 ~80 行已迁到 src/trace/core/extractors/_common.py (共享纯函数).
        保留 self._fold_constant 调用方零改动.
        """
        from .extractors._common import fold_constant
        return fold_constant(expr, ctx)


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
        """[铁律4] 为非端口变量/网表声明创建 SIGNAL TraceNode. 跳过端口.

        [ARCHITECTURE_TODOLIST #1 Step 3 2026-08-27 21:33] 薄壳, 实际逻辑在
        extractors/wire_init_extractor.create_var_nodes.
        保留方法签名 (extract() 入口处调用, 不改调用方).
        行为 1:1 一致 — 同样的 TraceNode、同样的 width、同样的跳过端口逻辑.
        """
        from .extractors.wire_init_extractor import create_var_nodes
        return create_var_nodes(
            adapter=self.adapter,
            module=module,
            result=result,
            module_name=module_name,
            port_names=port_names,
        )

    def _create_net_alias_edges(self, module, result, module_name):
        """[REFACTOR 2026-06-26] 处理 alias 语句: alias b = a; → 创建 DRIVER 边 a → b.

        [ARCHITECTURE_TODOLIST #1 2026-08-27] 薄壳, 实际逻辑在 extractors/alias_extractor.py.
        保留方法签名 (外部 graph_builder 等通过 _create_net_alias_edges 调用, 不改调用方).
        行为 1:1 一致 — 同样的 DRIVER 边、同样的节点、同样的 assign_type="alias".
        """
        from .extractors.alias_extractor import extract_alias_edges
        extract_alias_edges(
            adapter=self.adapter,
            module=module,
            result=result,
            module_name=module_name,
            ensure_signal_node=self._ensure_signal_node,
            append_edge=self._append_edge,
        )

    def _extract_alias_ref_name(self, ref_expr) -> str | None:
        """[REFACTOR 2026-06-26] 从 alias ref expr 提取 .symbol.name (None if missing).

        [ARCHITECTURE_TODOLIST #1 2026-08-27] 保持本地副本 (避免跨文件依赖, alias_extractor
        是独立模块). 行为 1:1 一致.
        """
        if hasattr(ref_expr, "symbol") and hasattr(ref_expr.symbol, "name"):
            return str(ref_expr.symbol.name)
        return None

    def _create_net_decl_edges(self, module, result, module_name, port_names, genvar_ctx: dict | None = None):
        """[REFACTOR 2026-06-26] 处理带初始化器的 Net 声明: wire X = expr; → 创建 DRIVER 边.
        [V6.9] 通过 _build_signal_source 提取 source_op/operand_side/casts,
        使 net-decl 边和 assign 边的 signal source 信息一致。

        [ARCHITECTURE_TODOLIST #1 Step 3b 2026-08-28] 薄壳, 实际逻辑在
        extractors/net_decl_extractor.py。保留方法签名 (调用方零改动)。
        行为 1:1 一致 — 同样的 DRIVER 边、同样的节点、同样的 assign_type="continuous"。

        6 个共享 helper 以 Callable 注入 (沿用 Step 1+2 alias_extractor 模式):
        这些 helper 是全文件共享的 (如 _get_signal 有 35 处调用), 搬走会波及
        Step 4-7 尚未拆分的 assign/always/function 部分, 不在 Step 3b 范围。
        """
        from .extractors.net_decl_extractor import create_net_decl_edges
        create_net_decl_edges(
            adapter=self.adapter,
            module=module,
            result=result,
            module_name=module_name,
            port_names=port_names,
            store_expr_tree=self._store_expr_tree,
            ensure_signal_node=self._ensure_signal_node,
            get_signal=self._get_signal,
            get_all_real_signals=self._get_all_real_signals,
            build_signal_source=self._build_signal_source,
            append_edge=self._append_edge,
            genvar_ctx=genvar_ctx,
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

        [ARCHITECTURE_TODOLIST #1 Step 4 2026-08-28] 薄壳, 实际逻辑在
        extractors/assign_extractor.py (5 个方法 + 2 个专属 helper, 580 行)。
        保留方法签名 (调用方零改动)。行为 1:1 一致 — 同样的 4-way dispatch 顺序、
        同样的边、同样的 assign_type="continuous"。

        13 个共享 helper 打包成 AssignHelpers 注入 (到这个规模逐个传参会让签名膨胀)。
        这些 helper 仍留在本类: _get_signal 有 33 处调用; _parse_assign /
        _expr_is_compile_time / _filter_signal_conditions_by_module /
        _build_signal_source 被 _create_always_edges 共用 (Step 6 范围)。
        """
        from .extractors.assign_extractor import AssignHelpers, create_assign_edges
        create_assign_edges(
            module,
            result,
            module_name,
            h=AssignHelpers(
                adapter=self.adapter,
                store_expr_tree=self._store_expr_tree,
                get_signal=self._get_signal,
                get_all_signals=self._get_all_signals,
                get_all_real_signals=self._get_all_real_signals,
                build_signal_source=self._build_signal_source,
                append_edge=self._append_edge,
                handle_invocation=self._handle_invocation,
                find_invocations=self._find_invocations,
                parse_assign=self._parse_assign,
                expr_is_compile_time=self._expr_is_compile_time,
                filter_compile_time_signal_names=self._filter_compile_time_signal_names,
                filter_signal_conditions_by_module=self._filter_signal_conditions_by_module,
                signal_visitor=getattr(self, "_signal_visitor", None),
                edge_factory=getattr(self, "_edge_factory", None),
            ),
        )

    def _find_invocations(self, expr, invocations=None) -> list:
        """[REFACTOR 2026-06-26] 5c-helper: 递归找 Invocation/Call 表达式.

        [ARCHITECTURE_TODOLIST #1 Step 7 2026-08-28] 薄壳, 实际逻辑在
        extractors/function_extractor.py。保留方法签名 (AssignHelpers 注入点
        find_invocations=self._find_invocations 零改动)。
        """
        from .extractors.function_extractor import _find_invocations
        return _find_invocations(expr, invocations, h=self._function_helpers())

    def _handle_invocation(self, invocation, ctx, module, module_name, result, lhs_name=None):
        """[REFACTOR 2026-06-26] 处理 function/task 调用.

        [ARCHITECTURE_TODOLIST #1 Step 7 2026-08-28] 薄壳, 实际逻辑在
        extractors/function_extractor.py。保留方法签名 (Assign/AlwaysHelpers
        注入点 handle_invocation=self._handle_invocation 零改动)。
        """
        from .extractors.function_extractor import _handle_invocation
        _handle_invocation(
            invocation, ctx, module, module_name, result, lhs_name,
            h=self._function_helpers(),
        )

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
        # [V8.3] 当表达式不是 BinaryOp 时，递归查找内部 BinaryOp
        # 处理: 函数调用 (saturate(...)), 位选择, 拼接等
        if "Binary" not in root_kind_str:
            if "Call" in root_kind_str or "Subroutine" in root_kind_str or "NewArray" in root_kind_str:
                for arg_attr in ("arguments", "operands", "parameters"):
                    args = getattr(root, arg_attr, None)
                    if args:
                        for arg in args:
                            sub_op, sub_side, sub_is = self._detect_binary_op(arg, signal)
                            if sub_op:
                                return sub_op, sub_side, sub_is
            return "", "", False

        op_attr = getattr(root, "op", None)
        op = str(getattr(op_attr, "name", op_attr)) if op_attr else ""
        operand_side = ""

        for side_name in ("left", "right"):
            side = getattr(root, side_name, None)
            if side is None:
                continue
            # [V6.9] 统一用 _extract_signals_from_expr 提取信号集合
            # 然后匹配 leaf signal。pyslang 可能返回全限定名 (module.signal)
            # 或短名 (signal)，都尝试匹配。
            side_kind = str(getattr(side, "kind", ""))
            side_signals = self._signal_visitor._extract_signals_from_expr(side) or []

            # 匹配：全限定名 或 短名
            if signal in side_signals:
                operand_side = side_name
                break
            # 也检查 short name 匹配 (pyslang 返回 foo.bar, signal 可能只是 bar)
            for ss in side_signals:
                if ss.endswith("." + signal):
                    operand_side = side_name
                    break
            if operand_side:
                break

            # Fallback: .syntax 文本匹配
            if not side_signals:
                syntax_node = getattr(side, "syntax", None)
                name = str(syntax_node).strip() if syntax_node else ""
                if not name:
                    name = self._signal_visitor.get_source_text(side) or str(side)
                if name and signal == name:
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

    @staticmethod
    def _detect_inner_ops(rhs_expr, signal: str, operand_side: str) -> list[str]:
        """[V6.9] 嵌套 OP 提取

        例: (sum_ac + 128) >>> 8 → 外层 op=>>>, 内层 op=Add(+)
        """
        if rhs_expr is None or not operand_side:
            return []
        root_kind = str(getattr(rhs_expr, "kind", ""))
        if "Binary" not in root_kind:
            return []
        side = getattr(rhs_expr, operand_side, None)
        if side is None:
            return []
        side_kind = str(getattr(side, "kind", ""))
        if "Binary" not in side_kind:
            return []
        op_attr = getattr(side, "op", None)
        op_name = str(getattr(op_attr, "name", op_attr)) if op_attr else ""
        if not op_name:
            return []
        _MAP = {
            "Add": "+", "Subtract": "-", "Multiply": "*",
            "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
            "GreaterThan": ">", "LessThan": "<",
            "Equality": "==", "Inequality": "!=",
        }
        sym = _MAP.get(op_name, op_name)
        return [sym]

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

        # ---- 4b. [V8.3] 非 BinaryOp 的操作检测 ----
        # 当 rhs_expr 不是 BinaryOp 时，尝试检测其他有意义的操作
        if not op and rhs_expr is not None and signal:
            rhs_kind = str(getattr(rhs_expr, "kind", ""))
            # 位选择: sum[7:0], a[15:8] 等
            if "[" in rhs_name and "]" in rhs_name:
                op = "Slice"
                is_binary = True
            # 拼接: {a, b} → Concat
            elif "Concat" in rhs_kind or "{" in full_expression:
                op = "Concat"
                is_binary = True
            # 条件表达式 (三目): shifted[7:0] 在 ternary 分支中
            elif "Condition" in rhs_kind or "Condition" in str(getattr(inner, "kind", "")) if inner else "":
                # 在条件分支内的信号 — 试着从兄弟表达式推断
                pass  # 交给 Phase B 透传处理

        # ---- 5. 嵌套 OP 链提取 (V6.9 datapath) ----
        # 例: (sum_ac + 128) >>> 8 → 外层 op=">>>", 内层 op="Add"
        inner_ops = []
        if is_binary and rhs_expr is not None:
            inner_ops = self._detect_inner_ops(rhs_expr, signal, operand_side)

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
            inner_ops=inner_ops,
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
        except Exception as e:
            logger.debug("readable expr 提取失败: %s", e)

        # fallback 也检查: 过滤 type name 字符串
        if "ExpressionKind" in fallback or "Expression(" in fallback:
            return ""
        return fallback

    def _create_always_edges(self, module, result, module_name, genvar_ctx: dict | None = None):
        """[REFACTOR 2026-06-26] 处理 always 块 (含 always_ff/always_comb/always_latch).

        [ARCHITECTURE_TODOLIST #1 Step 6 2026-08-28] 薄壳, 实际逻辑在
        extractors/always_extractor.py (9 个方法, ~790 行)。
        保留方法签名 (调用方零改动)。行为 1:1 一致。
        共享 helper (_is_compile_time_symbol / _is_sv_literal_token) 留在本类,
        通过 AlwaysHelpers 注入。
        """
        from .extractors.always_extractor import AlwaysHelpers, _create_always_edges
        _create_always_edges(
            module, result, module_name, genvar_ctx,
            h=AlwaysHelpers(
                adapter=self.adapter,
                get_signal=self._get_signal,
                get_all_real_signals=self._get_all_real_signals,
                parse_assign=self._parse_assign,
                store_expr_tree=self._store_expr_tree,
                handle_invocation=self._handle_invocation,
                build_signal_source=self._build_signal_source,
                expr_is_compile_time=self._expr_is_compile_time,
                filter_signal_conditions_by_module=self._filter_signal_conditions_by_module,
                flatten_semantic=self._flatten_semantic,
                is_sv_literal_token=self._is_sv_literal_token,
                signal_visitor=getattr(self, "_signal_visitor", None),
                edge_factory=getattr(self, "_edge_factory", None),
                cond_ast_by_str=self._cond_ast_by_str,
            ),
        )

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

        # 1-bit SV literals: 1'bx, 1'bz 中拆分出的纯 'x'/'z'
        # 但单字母信号名 'x'/'z' 是真实信号，不能在此过滤。
        # _filter_signal_conditions_by_module 调用此函数时，
        # signal names 来自 _extract_signals_from_expr，其中 'x' 是信号名。
        # 过滤 literal fragment 的任务在 _extract_signals_from_expr 的
        # Conversion/Call 分支中已处理（跳过 IntegerLiteral）。
        if token in ("x", "z", "X", "Z"):
            return False

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

    def _flatten_assignments(self, stmt, result: list, cond_stack: list[str] | None = None):
        """[DEPRECATED] 旧 syntax-based 展开。保留兼容 _expand_and_append_assignment。

        [ARCHITECTURE_TODOLIST #1 Step 5 2026-08-28] 薄壳, 实际逻辑在
        extractors/statement_flattener.py (8 个 _flatten_* 方法, 204 行)。
        保留方法签名 (调用方零改动)。行为 1:1 一致 — 相同的 visitor 分发、
        相同的 cond_ast_by_str 副作用。
        """
        from .extractors.statement_flattener import _flatten_assignments
        _flatten_assignments(
            stmt, result, cond_stack,
            get_signal=self._get_signal,
            cond_ast_by_str=self._cond_ast_by_str,
        )

    def _flatten_semantic(self, stmt, result: list, cond_stack: list[str] | None = None):
        """[V6.9] Dispatcher — 按 StatementKind / ExpressionKind 分发到独立 visitor 方法。

        [ARCHITECTURE_TODOLIST #1 Step 5 2026-08-28] 薄壳, 委派到
        extractors/statement_flattener._flatten_semantic。
        """
        from .extractors.statement_flattener import _flatten_semantic
        _flatten_semantic(
            stmt, result, cond_stack,
            get_signal=self._get_signal,
            cond_ast_by_str=self._cond_ast_by_str,
        )


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
                    self.adapter.get_module_name(module)
                except Exception:
                    pass
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

        # [REFACTOR 2026-08-07 A计划] 收集 function 宽度到 func_info
        # _store_expr_tree 的 _collect_from_tree 只记录了 Call 节点名 (func_info[name]=None)
        # 这里遍历 module 的 function declarations，从 semantic returnType 补全宽度
        # 替代旧 regex 从源码文本扫 function 声明的方式
        if result.func_info:
            for module in self.adapter.get_modules():
                try:
                    fns = self.adapter.get_function_declarations(module)
                except Exception:
                    continue
                for fn in fns:
                    try:
                        fn_name = self.adapter.get_function_name(fn)
                    except Exception:
                        continue
                    if fn_name in result.func_info and result.func_info.get(fn_name) is None:
                        result.func_info[fn_name] = self.adapter.get_function_width(fn)

        return result

    def _parse_assign(self, assign) -> tuple:
        """
        解析赋值语句,返回 (lhs_name, rhs_name, rhs_expr)
        - lhs_name: 左操作数信号名
        - rhs_name: 右操作数信号名 (简单信号,用于简单赋值)
        - rhs_expr: 原始 RHS 表达式 (用于复杂类型判断和_get_all_signals)

        [Plan F1 2026-08-12] 从 assign.genvar_ctx 读 genvar 上下文
        (顶层 assigns 没这属性 → 空 dict {}; generate for 内的 assigns
        有 {genvar_name: entry.arrayIndex}). 传给 _get_signal 让
        ElementSelect / NamedValue 的 selector 路径能 substitute genvar
        (e.g. gen_accum[1] 里的 acc[i+1] → acc[2]).
        """
        # [P0] 处理 ExpressionStatement (always_ff/always_comb 内部)
        if hasattr(assign, "expr"):
            assign = assign.expr

        # [V6.9 fix] ExpressionStatement 包裹 InvocationExpression/CallExpression
        #          (always_comb task_call(a,b)) — 不是 assignment，返回 None 让上层处理
        kind_str = str(getattr(assign, "kind", ""))
        if "Invocation" in kind_str or "Call" in kind_str:
            return None, None, None

        # [Plan F1] 读 genvar_ctx (由 semantic_adapter.get_genvar_context() 提供)
        # pyslang symbol 不可 setattr, 所以 context 存在 adapter._genvar_context (id-keyed dict)
        genvar_ctx = self.adapter.get_genvar_context(assign) if self.adapter else {}

        try:
            # [P1] DataDeclaration 处理 (class 实例化等)
            # 格式: my_cls obj = new();
            if hasattr(assign, "declarators") and assign.declarators:
                decl = assign.declarators[0]
                lhs = getattr(decl, "name", None)
                rhs = getattr(decl, "initializer", None)
                lhs_name = self._get_signal(lhs, genvar_ctx)
                # RHS 是构造函数调用,提取函数名
                rhs_name = self._get_constructor_call(rhs) if rhs else None
                return lhs_name, rhs_name, rhs

            # [P2-FIX] 处理 ContinuousAssignSymbol: 它有 'assignment' 属性,不是 'assignments'
            elif hasattr(assign, "assignment") and hasattr(assign.assignment, "left"):
                a = assign.assignment
                lhs = a.left if hasattr(a, "left") else None
                rhs = a.right if hasattr(a, "right") else None
            else:
                # Nonblocking/BlockingAssignmentExpression (always 块 procedural assign)
                rhs = getattr(assign, "right", None) or getattr(assign, "rhs", None)
                lhs = getattr(assign, "left", None) or getattr(assign, "lhs", None)

            lhs_name = self._get_signal(lhs, genvar_ctx)
            rhs_name = self._get_signal(rhs, genvar_ctx)

            return lhs_name, rhs_name, rhs
        except Exception:
            # [铁律3] 解析失败时返回空值,但记录错误上下文
            return None, None, None

