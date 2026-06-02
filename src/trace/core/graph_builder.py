# ==============================================================================
# graph_builder.py - Builder Layer
# ==============================================================================

import logging
from dataclasses import dataclass, field

import pyslang

from .base import PyslangAdapter
from .builder.subroutine_expander import SubroutineExpander
from .driver_extractor import DriverExtractor  # [P1 cycle 8] re-export 保兼容
from .graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode

logger = logging.getLogger(__name__)


@dataclass
class ExtractorResult:
    nodes: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    port_to_internal: dict[str, str] = field(default_factory=dict)  # {inst_port_id: child_signal_id}



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
