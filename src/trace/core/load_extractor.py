# ==============================================================================
# load_extractor.py - Load 提取器 (从 graph_builder.py 物理拆分, P1 cycle 9)
#
# 职责: 解析 SV 模块端口, 提取端口连接 (load) 关系.
# ==============================================================================

import logging

import pyslang

from .base import PyslangAdapter
from .extractor_models import ExtractorResult  # [P1 cycle 9] 共享
from .graph.models import NodeKind, TraceNode

logger = logging.getLogger(__name__)


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


