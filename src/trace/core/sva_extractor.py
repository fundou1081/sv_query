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

    def __init__(self, sources: dict[str, str]):
        self._sources = sources

    def extract(self) -> SVAGraph:
        """提取所有 SVA 结构"""
        graph = SVAGraph()

        try:
            compiler = SVCompiler(sources=self._sources, log_level="NONE")
            root = compiler.get_root()
            self._walk(root, graph)
        except Exception as e:
            graph.errors.append(f"编译失败: {e}")

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
                except TypeError:
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

        if "Sequence" in kind:
            seq = self._parse_sequence(node, prefix)
            if seq:
                graph.sequences[seq.id] = seq
            return

        if "Property" in kind:
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

        if "ConcurrentAssertion" in kind or "ImmediateAssertion" in kind:
            self._parse_assertion(node, graph, prefix)
            return

        # 遍历 CompilationUnit
        if "CompilationUnit" in kind:
            try:
                for child in node:
                    self._walk(child, graph, prefix)
            except TypeError:
                pass
            return

        # 遍历 Package
        if "Package" in kind:
            try:
                for child in node:
                    self._walk(child, graph, prefix)
            except TypeError:
                pass
            return

        # 遍历子节点
        try:
            for child in node:
                self._walk(child, graph, prefix)
        except TypeError:
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

            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name and name not in ("clk", "clk_i"):
                    signals.append(name)

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

            elif "SyntaxList" in ck:
                # SyntaxList 包含子表达式
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
        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))
            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name and name not in ("clk", "clk_i"):
                    signals.append(name)
            elif "PropertyExpr" in ck or "SequenceExpr" in ck or "SimpleProperty" in ck:
                s, o = self._extract_property_expr(child)
                signals.extend(s)
                operators.extend(o)
            elif "Expression" in ck or "Parenthesized" in ck or "Logical" in ck:
                # 递归提取表达式中的信号
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
        """
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
        """从语法节点提取所有信号名"""
        signals = []
        for child in self._iter_children(node):
            ck = str(getattr(child, "kind", ""))
            if "IdentifierName" in ck:
                name = self._get_identifier_name(child)
                if name and name not in ("clk", "clk_i", "rst_n"):
                    signals.append(name)
            elif "Token" not in ck:
                try:
                    s = self._extract_signals_from_syntax(child)
                    signals.extend(s)
                except Exception:
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

            elif "SyntaxList" in ck:
                self._walk_class_syntax(child, graph, prefix)

    def _get_syntax_name(self, node) -> str:
        """从 syntax 节点获取名称"""
        name = getattr(node, "name", None)
        if name:
            try:
                return str(name).strip()
            except Exception:
                pass
        return ""

    def _iter_children(self, node):
        """安全遍历子节点"""
        try:
            yield from node
        except TypeError:
            pass

    def _get_identifier_name(self, node) -> str:
        """获取标识符名称"""
        # 方式1: .identifier.value
        ident = getattr(node, "identifier", None)
        if ident:
            try:
                return str(ident.value).strip()
            except Exception:
                pass
        # 方式2: .name
        name = getattr(node, "name", None)
        if name:
            try:
                return str(name).strip()
            except Exception:
                pass
        # 方式3: 从 syntax 提取
        syntax = getattr(node, "syntax", None)
        if syntax:
            token = getattr(syntax, "name", None)
            if token:
                try:
                    return str(token).strip()
                except Exception:
                    pass
        return ""

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
