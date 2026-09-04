# sva_extractor.py - SVA 结构化提取器
#
# 使用 Semantic AST (SVCompiler) 提取 SVA 结构。
#
# [铁律1] 必须使用编译后 Semantic AST
# [铁律3] 不可信则不输出

import logging
import re

from .compiler import SVCompiler
from .graph.sva_models import SVAAssertionNode, SVAGraph, SVAPropertyNode, SVASequenceNode

logger = logging.getLogger(__name__)


class SVAExtractor:
    """SVA 结构化提取器

    从 Semantic AST 提取 sequence/property/assert 结构。
    [铁律1] 通过 SVCompiler 获取编译后 AST。
    """

    def __init__(self, sources: dict[str, str], strict: bool = True):
        # [FIX 2026-06-12 Req-15] strict 默认 True 跟原语义一致, 但 CLI caller 可传 False
        self._sources = sources
        self._strict = strict
        # [iter_121] 解析期元数据 (每次 extract 重建):
        #   _decl_names[id] = 声明的 formal/local 名 (非信号, 从信号集剔除)
        #   _inst_args[name] = 该 property/sequence 被实例化时的实参标识符集
        #   (assert property(p_arg(a,b)) → p_arg: {a,b})
        self._decl_names: dict[str, set[str]] = {}
        self._inst_args: dict[str, set[str]] = {}

    def extract(self) -> SVAGraph:
        """提取所有 SVA 结构"""
        graph = SVAGraph()
        self._decl_names = {}
        self._inst_args = {}

        try:
            # [FIX 2026-06-12 Req-15] 传 strict=跟 caller 一致, 避免 non-strict CLI 仍报"编译失败"
            compiler = SVCompiler(sources=self._sources, log_level="NONE", strict=self._strict)
            root = compiler.get_root()
            self._walk(root, graph)
        except Exception as e:
            graph.errors.append(f"编译失败: {e}")

        # [iter_121] 后处理: sequence/property 引用展开 + formal 参数剔除/实参并入
        self._resolve_refs_and_args(graph)

        # 建立信号关联索引
        self._build_signal_refs(graph)

        return graph

    def _walk(self, node, graph: SVAGraph, prefix: str = ""):
        """递归遍历 Semantic AST"""
        kind = str(getattr(node, "kind", ""))

        if "Instance" in kind:
            name = str(getattr(node, "name", "")).strip()
            new_prefix = f"{prefix}.{name}" if prefix else name
            if hasattr(node, "body"):
                try:
                    for child in node.body:
                        self._walk(child, graph, new_prefix)
                except TypeError as _e:
                    logger.debug("提取失败 (TypeError): %s", _e)
                    pass
            return

        if "ClassType" in kind:
            name = str(getattr(node, "name", "")).strip()
            new_prefix = f"{prefix}.{name}" if prefix else name
            # 从 syntax 树遍历 class 内容
            syntax = getattr(node, "syntax", None)
            if syntax:
                self._walk_class_syntax(syntax, graph, new_prefix)
            return

        # [iter_121] 收紧 kind 匹配: 旧子串 ('Sequence'/'Property' in kind) 会把
        # covergroup option/type_option (ClassProperty 之类) 误当 SVA 声明
        # (对抗: interface 内 cg → prop 列表出现 top.u_bus.option) — 只处理
        # 真 Sequence / Property 声明 (精确 kind)
        if kind == "SymbolKind.Sequence" or kind == "SequenceSymbol":
            seq = self._parse_sequence(node, prefix)
            if seq:
                graph.sequences[seq.id] = seq
            return

        if kind == "SymbolKind.Property" or kind == "PropertySymbol":
            prop = self._parse_property(node, prefix)
            if prop:
                graph.properties[prop.id] = prop
            return

        # ProceduralBlock 的 syntax 可能是 ConcurrentAssertionMember
        if "ProceduralBlock" in kind:
            syntax = getattr(node, "syntax", None)
            if syntax:
                syntax_kind = str(getattr(syntax, "kind", ""))
                if "ConcurrentAssertion" in syntax_kind or "ImmediateAssertion" in syntax_kind:
                    self._parse_assertion_syntax(syntax, graph, prefix)
                    return
                # [iter_062] ProceduralBlockSyntax → 深挖 block 内的 immediate assertion
                # (always_comb begin assume(...); cover(...); end 形态:
                #  ProceduralBlockSyntax.statement = BlockStatementSyntax.items = [...] )
                self._collect_immediate_assertions(syntax, graph, prefix)
                return

        # [iter_062] StatementBlock 的 syntax 可能是 ImmediateAssertionStatement
        # (过程块内 `assert (expr) else $error(...)` / `assume (expr)` / `cover (expr)`)
        if "StatementBlock" in kind:
            syntax = getattr(node, "syntax", None)
            if syntax is not None and "ImmediateAssertion" in type(syntax).__name__:
                self._parse_immediate_assertion(syntax, graph, prefix)
                return

        if "ConcurrentAssertion" in kind or "ImmediateAssertion" in kind:
            self._parse_assertion(node, graph, prefix)
            return

        # [iter_121] generate 块下钻 — generate-for/if 内的 assert property 之前
        # 0 提取 (对抗 #5): GenerateBlockArray/GenerateBlock 无普通子节点遍历路径
        if "GenerateBlockArray" in kind or "GenerateBlock" in kind:
            try:
                entries = list(node) if "GenerateBlockArray" in kind else [node]
                for entry in entries:
                    if getattr(entry, "isUninstantiated", False):
                        continue
                    try:
                        for child in entry:
                            self._walk(child, graph, prefix)
                    except TypeError as _e:
                        logger.debug("generate 下钻失败 (TypeError): %s", _e)
            except (TypeError, AttributeError) as _e:
                logger.debug("generate 遍历失败: %s", _e)
            return

        # 遍历 CompilationUnit
        if "CompilationUnit" in kind:
            try:
                for child in node:
                    self._walk(child, graph, prefix)
            except TypeError as _e:
                logger.debug("提取失败 (TypeError): %s", _e)
                pass
            return

        # 遍历 Package
        if "Package" in kind:
            try:
                for child in node:
                    self._walk(child, graph, prefix)
            except TypeError as _e:
                logger.debug("提取失败 (TypeError): %s", _e)
                pass
            return

        # 遍历子节点
        try:
            for child in node:
                self._walk(child, graph, prefix)
        except TypeError as _e:
            logger.debug("提取失败 (TypeError): %s", _e)
            pass

    # =========================================================================
    # Sequence 解析
    # =========================================================================

    def _parse_sequence(self, node, prefix: str = "") -> SVASequenceNode | None:
        """解析 SequenceSymbol"""
        name = str(getattr(node, "name", "")).strip()
        if not name:
            return None

        signals = []
        timing_ops = []
        clock = ""

        syntax = getattr(node, "syntax", None)
        if syntax:
            signals, timing_ops, clock = self._extract_from_syntax(syntax)

        seq_id = f"{prefix}.{name}" if prefix else name

        # [iter_121] 剔除声明的 formal/local (参数不是信号; 对抗 #1/#3)
        decls = self._collect_decl_identifiers(syntax)
        if decls:
            self._decl_names[seq_id] = decls
            signals = [s for s in signals if s not in decls]

        return SVASequenceNode(
            id=seq_id,
            name=name,
            signals=signals,
            timing_ops=timing_ops,
            clock=clock,
        )

    # =========================================================================
    # Property 解析
    # =========================================================================

    def _parse_property(self, node, prefix: str = "") -> SVAPropertyNode | None:
        """解析 PropertySymbol"""
        name = str(getattr(node, "name", "")).strip()
        if not name:
            return None

        signals = []
        operators = []
        disable_iff = ""
        clock = ""

        syntax = getattr(node, "syntax", None)
        if syntax:
            signals, operators, clock, disable_iff = self._extract_property_from_syntax(syntax)

        prop_id = f"{prefix}.{name}" if prefix else name

        # [iter_121] 剔除声明的 formal/local (对抗 #1/#3)
        decls = self._collect_decl_identifiers(syntax)
        if decls:
            self._decl_names[prop_id] = decls
            signals = [s for s in signals if s not in decls]

        return SVAPropertyNode(
            id=prop_id,
            name=name,
            signals=signals,
            operators=operators,
            disable_iff=disable_iff,
            clock=clock,
        )

    # =========================================================================
    # Assertion 解析
    # =========================================================================

    def _parse_assertion_syntax(self, syntax_node, graph: SVAGraph, prefix: str = ""):
        """从 syntax 节点解析 assertion"""
        # [iter_121] generate 内断言经 ConcurrentAssertionMemberSyntax 包装 —
        # 解包到 ConcurrentAssertionStatementSyntax 再处理 (对抗 #5)
        while syntax_node is not None and "MemberSyntax" in type(syntax_node).__name__:
            inner = None
            try:
                for c in syntax_node:
                    inner = c
                    break
            except TypeError:
                break
            syntax_node = inner

        assertion_kind = ""
        property_ref = ""
        message = ""
        signals = []

        syntax_str = str(syntax_node)
        if "assert" in syntax_str.lower():
            assertion_kind = "assert"
        elif "assume" in syntax_str.lower():
            assertion_kind = "assume"
        elif "cover" in syntax_str.lower():
            assertion_kind = "cover"

        # 提取 property 引用
        prop_ref = self._find_property_ref(syntax_node)
        # [iter_121] 捕获实例化实参 (assert property(p_arg(a,b)) → a,b)
        self._capture_invocation_args(syntax_node)
        if prop_ref:
            property_ref = f"{prefix}.{prop_ref}" if prefix else prop_ref

        # 提取信号
        signals = self._extract_signals_from_syntax(syntax_node)

        # 提取消息
        msg = self._extract_assertion_message(syntax_node)
        if msg:
            message = msg

        if assertion_kind:
            assertion_id = f"{prefix}.assert_{len(graph.assertions)}" if prefix else f"assert_{len(graph.assertions)}"
            graph.assertions.append(
                SVAAssertionNode(
                    id=assertion_id,
                    kind=assertion_kind,
                    property_ref=property_ref,
                    signals=signals,
                    message=message,
                )
            )

    def _collect_immediate_assertions(self, syntax, graph: SVAGraph, prefix: str = ""):
        """[iter_062] 递归收集 syntax 树中的 ImmediateAssertionStatementSyntax.

        形态: ProceduralBlockSyntax.statement = BlockStatementSyntax,
              BlockStatementSyntax.items = [ImmediateAssertionStatementSyntax, ...]
        """
        if syntax is None:
            return
        if "ImmediateAssertionStatementSyntax" in type(syntax).__name__:
            self._parse_immediate_assertion(syntax, graph, prefix)
            return
        # 遍历 statement / items / members
        for attr in ("statement", "items", "members", "statements"):
            v = getattr(syntax, attr, None)
            if v is None:
                continue
            try:
                if hasattr(v, "__iter__") and not isinstance(v, str):
                    for c in v:
                        self._collect_immediate_assertions(c, graph, prefix)
                else:
                    self._collect_immediate_assertions(v, graph, prefix)
            except TypeError:
                continue

    def _parse_immediate_assertion(self, syntax, graph: SVAGraph, prefix: str = ""):
        """[iter_062] 提取 immediate assertion (过程块内 assert/assume/cover 语句).

        pyslang 呈现: 语义层 StatementBlock.syntax = ImmediateAssertionStatementSyntax,
        有 keyword (assert/assume/cover) + expr + action (else 分支).
        """
        keyword = str(getattr(syntax, "keyword", "")).strip()
        if not keyword:
            return
        kind_map = {"assert": "assert", "assume": "assume", "cover": "cover"}
        assertion_kind = kind_map.get(keyword.lower())
        if not assertion_kind:
            return

        # 提取信号 (从 expr)
        expr = getattr(syntax, "expr", None)
        signals = []
        if expr is not None:
            signals = self._extract_signals_from_syntax(expr) or []

        # 提取消息 (action: else $error("..."))
        message = ""
        action = getattr(syntax, "action", None)
        if action is not None:
            msg = self._extract_assertion_message(action)
            if msg:
                message = msg

        # [iter_062] 去重: 命名 immediate_assert 会经 StatementBlock 与
        # BlockStatementSyntax.items 两个路径到达, 避免重复.
        for existing in graph.assertions:
            if (existing.kind == assertion_kind
                    and existing.signals == signals
                    and existing.message == message):
                return

        assertion_id = f"{prefix}.assert_{len(graph.assertions)}" if prefix else f"assert_{len(graph.assertions)}"
        graph.assertions.append(
            SVAAssertionNode(
                id=assertion_id,
                kind=assertion_kind,
                signals=signals,
                message=message,
            )
        )

    def _parse_assertion(self, node, graph: SVAGraph, prefix: str = ""):
        """解析 ConcurrentAssertionMember"""
        str(getattr(node, "kind", ""))

        # 找 assert/assume/cover statement
        assertion_kind = ""
        property_ref = ""
        message = ""
        signals = []

        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))

            if "AssertProperty" in ck:
                assertion_kind = "assert"
            elif "AssumeProperty" in ck:
                assertion_kind = "assume"
            elif "CoverProperty" in ck:
                assertion_kind = "cover"
            else:
                continue

            # 提取 property 引用
            prop_ref = self._find_property_ref(child)
            if prop_ref:
                # 构建完整路径
                property_ref = f"{prefix}.{prop_ref}" if prefix else prop_ref

            # 提取信号
            signals = self._extract_signals_from_syntax(child)

            # 提取消息
            msg = self._extract_assertion_message(child)
            if msg:
                message = msg

        if assertion_kind:
            assertion_id = f"{prefix}.assert_{len(graph.assertions)}" if prefix else f"assert_{len(graph.assertions)}"
            graph.assertions.append(
                SVAAssertionNode(
                    id=assertion_id,
                    kind=assertion_kind,
                    property_ref=property_ref,
                    signals=signals,
                    message=message,
                )
            )

    # =========================================================================
    # Syntax 树遍历辅助
    # =========================================================================

    def _extract_from_syntax(self, node):
        """从 SequenceDeclarationSyntax 提取信号、时序操作符、时钟"""
        signals = []
        timing_ops = []
        clock = ""

        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))

            if "EventControl" in ck or "Clocking" in ck:
                clock = self._extract_clock_from_event(child)

            if "SequenceExpr" in ck or "Sequence" in ck:
                s, t = self._extract_sequence_expr(child)
                signals.extend(s)
                timing_ops.extend(t)

        return signals, timing_ops, clock

    def _extract_property_from_syntax(self, node):
        """从 PropertyDeclarationSyntax 提取"""
        signals = []
        operators = []
        disable_iff = ""
        clock = ""

        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))

            if "PropertySpec" in ck:
                for sub in self._iter_children(child):
                    sk = str(getattr(sub, "kind", ""))
                    if "EventControl" in sk or "Clocking" in sk:
                        clock = self._extract_clock_from_event(sub)
                    elif "DisableIff" in sk:
                        disable_iff = self._extract_disable_iff(sub)
                    elif "PropertyExpr" in sk or "Implication" in sk:
                        s, o = self._extract_property_expr(sub)
                        signals.extend(s)
                        operators.extend(o)

        return signals, operators, clock, disable_iff

    def _extract_sequence_expr(self, node):
        """从 sequence 表达式提取信号和时序操作符"""
        signals = []
        timing_ops = []

        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))

            # [iter_121] 时钟子树不进信号 (时钟走 clock 字段; 对抗 #2 多时钟噪声)
            if "EventControl" in ck or "SignalEvent" in ck or "Clocking" in ck:
                continue

            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name and name not in ("clk", "clk_i"):
                    signals.append(name)

            elif "Invocation" in ck:
                # [iter_121] sequence/property 引用或函数调用: callee 名非信号
                # (对抗 #2/#4) — 跳过首 IdentifierName (callee), 其余 (实参) 递归
                for sub in self._iter_children(child):
                    if type(sub).__name__ == "IdentifierNameSyntax":
                        continue
                    s, t = self._extract_sequence_expr(sub)
                    signals.extend(s)
                    timing_ops.extend(t)

            elif "DelayedSequence" in ck or "Delay" in ck:
                delay = self._extract_delay(child)
                if delay:
                    timing_ops.append(delay)
                s, t = self._extract_sequence_expr(child)
                signals.extend(s)
                timing_ops.extend(t)

            elif "DelayedSequenceElement" in ck:
                # ##1 b 中的延迟元素
                delay = self._extract_delay(child)
                if delay:
                    timing_ops.append(delay)
                s, t = self._extract_sequence_expr(child)
                signals.extend(s)
                timing_ops.extend(t)

            elif "SequenceExpr" in ck or "SimpleSequence" in ck:
                s, t = self._extract_sequence_expr(child)
                signals.extend(s)
                timing_ops.extend(t)

            elif "SyntaxList" in ck or isinstance(child, list):
                # v10: SyntaxList 包装, v11: 已是 plain list
                s, t = self._extract_sequence_expr(child)
                signals.extend(s)
                timing_ops.extend(t)

        return list(set(signals)), timing_ops

    def _extract_property_expr(self, node):
        """从 property 表达式提取信号和操作符"""
        signals = []
        operators = []

        node_str = str(node)

        # 检查蕴含操作符
        if "|->" in node_str:
            operators.append("|->")
        if "|=>" in node_str:
            operators.append("|=>")
        if "[*" in node_str:
            ops = re.findall(r"\[\*\d+\]", node_str)
            operators.extend(ops)

        # 提取信号
        # [FIX V6.1 2026-07-20] Recurse into ALL non-Token children.
        # Previous logic skipped system function calls ($changed(x), $rose(x)).
        # Bug-2 root cause: $changed(state_q) had no recursion path because
        # the SystemFunctionCall / ItsArgumentExpression kinds didn't match
        # any of the explicit kind checks above.
        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))
            if "Token" in ck:
                continue  # Token: skip
            # [iter_121] 时钟子树不进信号 (多时钟噪声)
            if "EventControl" in ck or "SignalEvent" in ck or "Clocking" in ck:
                continue
            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name and name not in ("clk", "clk_i"):
                    signals.append(name)
            elif "Invocation" in ck:
                # [iter_121] property/sequence 引用或函数调用: callee 非信号
                for sub in self._iter_children(child):
                    if type(sub).__name__ == "IdentifierNameSyntax":
                        continue
                    s, o = self._extract_property_expr(sub)
                    signals.extend(s)
                    operators.extend(o)
            else:
                # Recurse into all other constructs (system calls,
                # parenthesized exprs, sequences, etc.)
                s, o = self._extract_property_expr(child)
                signals.extend(s)
                operators.extend(o)

        return list(set(signals)), operators

    def _extract_clock_from_event(self, node) -> str:
        """从 EventControl 提取时钟名"""
        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))
            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name:
                    return name
            elif "Event" in ck or "Signal" in ck:
                # 递归
                clock = self._extract_clock_from_event(child)
                if clock:
                    return clock
        return ""

    def _extract_disable_iff(self, node) -> str:
        """提取 disable iff 条件"""
        return str(node).strip()

    def _extract_delay(self, node) -> str:
        """提取延迟操作符 ##1 或 ##[1:3]"""
        node_str = str(node).strip()
        match = re.search(r"##(\d+|\[.+\])", node_str)
        if match:
            return f"##{match.group(1)}"
        return ""

    def _find_property_ref(self, node) -> str:
        """找 property 引用

        从 AssertPropertyStatement 中提取 property 名称。
        结构: PropertySpec -> SimplePropertyExpr -> SimpleSequenceExpr -> IdentifierName

        [iter_121] inline property (含蕴含算子) 不是"引用" — 直接返 '' (旧逻辑
        把内联断言首信号 a 误当 property 名, 对抗 #5: ref=top.a).
        """
        node_str = str(node)
        if "|->" in node_str or "|=>" in node_str or "[*" in node_str:
            return ""
        kind = str(getattr(node, "kind", ""))

        # PropertySpec 包含 property 引用
        if "PropertySpec" in kind:
            for child in self._iter_children(node):
                ref = self._find_property_ref(child)
                if ref:
                    return ref
            return ""

        # SimplePropertyExpr / SimpleSequenceExpr 包含 IdentifierName
        if "PropertyExpr" in kind or "SequenceExpr" in kind:
            for child in self._iter_children(node):
                ck = str(getattr(child, "kind", ""))
                if "IdentifierName" in ck:
                    name = self._get_identifier_name(child)
                    if name and name not in ("clk", "clk_i", "rst_n"):
                        return name
                else:
                    ref = self._find_property_ref(child)
                    if ref:
                        return ref

        # [iter_121] InvocationExpressionSyntax: callee = property/sequence 引用
        if "Invocation" in kind:
            for child in self._iter_children(node):
                if type(child).__name__ == "IdentifierNameSyntax":
                    name = self._get_identifier_name(child)
                    if name and name not in ("clk", "clk_i", "rst_n"):
                        return name
            return ""

        # 递归进入子节点
        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))
            if (
                "PropertySpec" in ck
                or "PropertyExpr" in ck
                or "SequenceExpr" in ck
                or "AssertProperty" in ck
                or "AssumeProperty" in ck
                or "CoverProperty" in ck
                or "Invocation" in ck
            ):
                ref = self._find_property_ref(child)
                if ref:
                    return ref

        return ""

    def _extract_assertion_message(self, node) -> str:
        """提取 assertion 消息"""
        node_str = str(node)
        match = re.search(r'\$error\s*\("([^"]+)"\)', node_str)
        if match:
            return match.group(1)
        return ""

    def _extract_signals_from_syntax(self, node) -> list[str]:
        """从语法节点提取所有信号名

        [iter_121] 增强:
        - 位选/部分选 (y[i] / d[3:0]) 只收 base (selector 是 genvar/常量索引,
          非被监控信号; 对抗 #5: y[i] 之前只出 'i')
        - 时钟子树 (EventControl) 不进信号 (时钟走 clock 字段)
        """
        signals = []
        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))
            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name and name not in ("clk", "clk_i", "rst_n"):
                    signals.append(name)
            elif "IdentifierSelectName" in type(child).__name__:
                # [iter_121] y[i] / y[3:0]: base 名是首个 Token 子节点 (y),
                # selector (i) 在 ElementSelect/RangeSelect 子树 — 只收 base,
                # 不下钻 selector
                for _c in self._iter_children(child):
                    if "Token" in type(_c).__name__:
                        nm = str(_c).strip()
                        if nm and nm not in ("clk", "clk_i", "rst_n"):
                            signals.append(nm)
                        break
                    break  # 非 Token (selector 子树) → 停止
            elif "EventControl" in ck or "SignalEvent" in ck or "Clocking" in ck:
                continue
            elif "Select" in ck and hasattr(child, "value"):
                # ElementSelect/RangeSelect: 只收 base (.value), 不下钻 selector
                s = self._extract_signals_from_syntax(getattr(child, "value", None))
                signals.extend(s)
            elif "Token" not in ck:
                try:
                    s = self._extract_signals_from_syntax(child)
                    signals.extend(s)
                except Exception as e:
                    logger.debug("SVA 提取失败: %s", e)
                    pass
        return list(set(signals))

    # =========================================================================
    # 工具方法
    # =========================================================================

    def _walk_class_syntax(self, syntax_node, graph: SVAGraph, prefix: str):
        """从 syntax 树遍历 class 内容，提取 SVA 结构"""
        for child in self._iter_children(syntax_node):
            ck = str(getattr(child, "kind", ""))

            if "PropertyDeclaration" in ck:
                name = self._get_syntax_name(child)
                if name:
                    signals, operators, clock, disable_iff = self._extract_property_from_syntax(child)
                    prop_id = f"{prefix}.{name}"
                    graph.properties[prop_id] = SVAPropertyNode(
                        id=prop_id,
                        name=name,
                        signals=signals,
                        operators=operators,
                        disable_iff=disable_iff,
                        clock=clock,
                    )

            elif "SequenceDeclaration" in ck:
                name = self._get_syntax_name(child)
                if name:
                    signals, timing_ops, clock = self._extract_from_syntax(child)
                    seq_id = f"{prefix}.{name}"
                    graph.sequences[seq_id] = SVASequenceNode(
                        id=seq_id,
                        name=name,
                        signals=signals,
                        timing_ops=timing_ops,
                        clock=clock,
                    )

            elif "ConcurrentAssertion" in ck or "ImmediateAssertion" in ck:
                self._parse_assertion_syntax(child, graph, prefix)

            elif "SyntaxList" in ck or isinstance(child, list):
                self._walk_class_syntax(child, graph, prefix)

    def _get_syntax_name(self, node) -> str:
        """从 syntax 节点获取名称"""
        name = getattr(node, "name", None)
        if name:
            try:
                return str(name).strip()
            except Exception as e:
                logger.debug("SVA 提取失败: %s", e)
                pass
        return ""

    def _iter_children(self, node):
        """安全遍历子节点"""
        try:
            yield from node
        except TypeError as _e:
            logger.debug("提取失败 (TypeError): %s", _e)
            pass

    def _get_identifier_name(self, node) -> str:
        """获取标识符名称"""
        # 方式1: .identifier.value
        ident = getattr(node, "identifier", None)
        if ident:
            try:
                return str(ident.value).strip()
            except Exception as e:
                logger.debug("SVA 提取失败: %s", e)
                pass
        # 方式2: .name
        name = getattr(node, "name", None)
        if name:
            try:
                return str(name).strip()
            except Exception as e:
                logger.debug("SVA 提取失败: %s", e)
                pass
        # 方式3: 从 syntax 提取
        syntax = getattr(node, "syntax", None)
        if syntax:
            token = getattr(syntax, "name", None)
            if token:
                try:
                    return str(token).strip()
                except Exception as e:
                    logger.debug("SVA 提取失败: %s", e)
                    pass
        return ""

    def _collect_decl_identifiers(self, syntax) -> set:
        """[iter_121] 收集 property/sequence 声明的 formal/local 标识符 —
        这些是参数/局部变量, 不是信号 (对抗 #1 formal 当信号 / #3 local 当信号).

        容器: AssertionItemPortListSyntax (formal 列表) /
              LocalVariableDeclarationSyntax (局部变量声明)
        """
        if syntax is None:
            return set()
        out = set()

        def walk(n):
            if n is None:
                return
            tn = type(n).__name__
            if tn in ("AssertionItemPortListSyntax", "LocalVariableDeclarationSyntax"):
                for c in self._iter_children(n):
                    ctn = type(c).__name__
                    if ctn == "IdentifierNameSyntax":
                        nm = self._get_identifier_name(c)
                        if nm:
                            out.add(nm)
                    elif ctn in ("DeclaratorSyntax", "AssertionItemPortSyntax"):
                        # formal/local 名在 .name = Token(TokenKind.Identifier)
                        tok = getattr(c, "name", None)
                        if tok is not None:
                            try:
                                val = getattr(tok, "value", None)
                                nm = str(val.value if hasattr(val, "value") else val) if val is not None else str(tok)
                            except Exception:
                                nm = str(tok)
                            if nm:
                                out.add(nm.strip())
                return  # 只收容器层声明名, 不再下钻 (避免收进默认值等)
            try:
                for c in n:
                    walk(c)
            except TypeError:
                pass

        walk(syntax)
        return out

    def _capture_invocation_args(self, syntax_node) -> None:
        """[iter_121] 捕获 assert property(p(a,b)) 的实例化实参 (对抗 #1):
        找到 InvocationExpressionSyntax 的 callee 名 + ArgumentList 内标识符,
        记入 self._inst_args[callee]."""
        if syntax_node is None:
            return

        def idents_under(n, acc):
            if n is None:
                return
            tn = type(n).__name__
            if tn == "IdentifierNameSyntax":
                nm = self._get_identifier_name(n)
                if nm:
                    acc.add(nm)
                return
            try:
                for c in n:
                    idents_under(c, acc)
            except TypeError:
                pass

        def walk(n):
            if n is None:
                return
            tn = type(n).__name__
            if "Invocation" in tn:
                callee = ""
                arglist = None
                for c in self._iter_children(n):
                    if type(c).__name__ == "IdentifierNameSyntax":
                        if not callee:
                            callee = self._get_identifier_name(c)
                    elif "ArgumentList" in type(c).__name__:
                        arglist = c
                if callee and arglist:
                    acc = set()
                    idents_under(arglist, acc)
                    self._inst_args.setdefault(callee, set()).update(acc)
                return  # 不再下钻外层 invocation
            try:
                for c in n:
                    walk(c)
            except TypeError:
                pass

        walk(syntax_node)

    def _resolve_refs_and_args(self, graph: SVAGraph) -> None:
        """[iter_121] 后处理:
        1. sequence/property 引用展开 — 信号集里的序列名替换成该序列的信号
           (对抗 #2: property 引 sequence 时内部信号 a,b 丢失)
        2. 实例化实参并入 property 信号 (对抗 #1: p_arg(a,b) → a,b 进 signals,
           不再只剩形式参)
        """
        seq_by_name = {s.name: s for s in graph.sequences.values()}
        memo: dict[str, set[str]] = {}
        visiting: set[str] = set()

        def resolve_seq(sname: str) -> set:
            if sname in memo:
                return memo[sname]
            if sname in visiting:  # 环保护
                return set()
            seq = seq_by_name.get(sname)
            if seq is None:
                return set()
            visiting.add(sname)
            out = set()
            for sig in seq.signals:
                if sig in seq_by_name:
                    out |= resolve_seq(sig)
                else:
                    out.add(sig)
            visiting.discard(sname)
            memo[sname] = out
            return out

        # sequence 自身引用展开
        for seq in graph.sequences.values():
            if any(s in seq_by_name for s in seq.signals):
                seq.signals = list(resolve_seq(seq.name))

        # property: 引用展开 + 实参并入
        for pid, prop in graph.properties.items():
            final = []
            for sig in prop.signals:
                if sig in seq_by_name:
                    for s in sorted(resolve_seq(sig)):
                        if s not in final:
                            final.append(s)
                    if sig not in prop.sequences:
                        prop.sequences.append(sig)
                elif sig not in final:
                    final.append(sig)
            # 实参 (assert property(p_arg(a,b)) → a,b)
            for a in sorted(self._inst_args.get(prop.name, set())):
                if a not in final:
                    final.append(a)
            prop.signals = final

        # assertion: 若 property_ref 已知 property, 信号并入 property 展开后的集
        prop_by_id = {p.id: p for p in graph.properties.values()}
        for a in graph.assertions:
            p = prop_by_id.get(a.property_ref)
            if p is not None:
                merged = list(a.signals)
                for s in p.signals:
                    if s not in merged:
                        merged.append(s)
                a.signals = merged

    # =========================================================================
    # 信号关联索引
    # =========================================================================

    def _build_signal_refs(self, graph: SVAGraph):
        """建立信号 → SVA 节点的关联索引"""
        # Sequence 信号
        for sid, seq in graph.sequences.items():
            for sig in seq.signals:
                if sig not in graph.signal_refs:
                    graph.signal_refs[sig] = []
                if sid not in graph.signal_refs[sig]:
                    graph.signal_refs[sig].append(sid)

        # Property 信号
        for pid, prop in graph.properties.items():
            for sig in prop.signals:
                if sig not in graph.signal_refs:
                    graph.signal_refs[sig] = []
                if pid not in graph.signal_refs[sig]:
                    graph.signal_refs[sig].append(pid)

        # Assertion 信号
        for a in graph.assertions:
            for sig in a.signals:
                if sig not in graph.signal_refs:
                    graph.signal_refs[sig] = []
                if a.id not in graph.signal_refs[sig]:
                    graph.signal_refs[sig].append(a.id)
