# ==============================================================================
# trace_evidence.py - Trace Evidence Resolver (Stage 2)
#
# 职责: 给定一个信号, 返回其 driver edge 的完整源码证据:
# - enclosing always_ff 块 (完整源码)
# - enclosing if 块 (完整源码, 如有)
# - source_location (行号, 文件)
# - source_text (该行源码)
# - parent_chain (完整 enclosing scope 链)
# - credibility_score (0-1, 借鉴 sv-trace)
#
# 架构:
# - 不递归 walk syntax tree, 改用 pyslang semantic API + .syntax.sourceRange
# - snippet 用 offset 切片 (text[start.offset:end.offset]) 而非按行号切割
# - 借鉴 sv-trace 的 credibility scoring (0-1 量化)
# ==============================================================================

from dataclasses import dataclass, field
from typing import Optional

from .coverage_models import SourceLocation, SourceSnippet
from .graph.models import TraceEdge, NodeKind


# ==============================================================================
# Evidence 数据类
# ==============================================================================

@dataclass
class Evidence:
    """完整源码证据

    Attributes:
        signal: 查询的信号 ID
        source_location: 该行源码位置 (file, line_start, line_end, column)
        source_text: 该行源码文本
        source_expr: 驱动表达式 (RHS), 用于 cross-validation (sv-trace 借鉴)
        enclosing_always: enclosing always_ff 块 (back-compat, also always_comb)
        enclosing_always_comb: enclosing always_comb 块
        enclosing_if: enclosing if 块
        enclosing_assign: enclosing continuous assign 块
        enclosing_class: enclosing class declaration
        enclosing_constraint: enclosing constraint block
        enclosing_chain: 完整 enclosing scope 链 (从内到外, 列表)
    """
    signal: str
    source_location: SourceLocation | None = None
    source_text: str = ""
    source_expr: str = ""  # [V4] 驱动表达式 (cross-validation 用)
    enclosing_always: SourceSnippet | None = None
    enclosing_always_comb: SourceSnippet | None = None
    enclosing_if: SourceSnippet | None = None
    enclosing_assign: SourceSnippet | None = None
    enclosing_class: SourceSnippet | None = None
    enclosing_constraint: SourceSnippet | None = None
    enclosing_chain: list[SourceSnippet] = field(default_factory=list)

    # ------------------------------------------------------------------
    # [V4] Cross-validation 字段 (借鉴 sv-trace M5.1)
    # ------------------------------------------------------------------
    @property
    def matches_signal_name(self) -> bool:
        """主 evidence snippet 中能找到 signal_name (LHS)"""
        if not self.signal:
            return False
        # 在每个 enclosing_* 中查找
        for snippet in [
            self.enclosing_always,
            self.enclosing_always_comb,
            self.enclosing_if,
            self.enclosing_assign,
            self.enclosing_class,
            self.enclosing_constraint,
        ]:
            if snippet and snippet.text and self.signal.split(".")[-1] in snippet.text:
                return True
        return False

    @property
    def matches_source_expr(self) -> bool:
        """主 evidence snippet 中能找到 source_expr (RHS)"""
        if not self.source_expr:
            return False
        for snippet in [
            self.enclosing_always,
            self.enclosing_always_comb,
            self.enclosing_if,
            self.enclosing_assign,
            self.enclosing_class,
            self.enclosing_constraint,
        ]:
            if snippet and snippet.text and self.source_expr in snippet.text:
                return True
        return False

    @property
    def is_verified(self) -> bool:
        """evidence 是否交叉验证通过

        借鉴 sv-trace: snippet_present + (matches_source_expr OR matches_signal_name)
        """
        snippet_present = any(
            s and s.text
            for s in [
                self.enclosing_always,
                self.enclosing_always_comb,
                self.enclosing_if,
                self.enclosing_assign,
                self.enclosing_class,
                self.enclosing_constraint,
            ]
        )
        return snippet_present and (self.matches_source_expr or self.matches_signal_name)

    @property
    def credibility_score(self) -> float:
        """可信度量化 0-1 (借鉴 sv-trace)

        - snippet_present: 0.2
        - matches_source_expr: 0.4
        - matches_signal_name: 0.2
        - cross-validation 额外加分: 0.2
        """
        score = 0.0
        any_snippet = any(
            s and s.text
            for s in [
                self.enclosing_always,
                self.enclosing_always_comb,
                self.enclosing_if,
                self.enclosing_assign,
                self.enclosing_class,
                self.enclosing_constraint,
            ]
        )
        if any_snippet:
            score += 0.2
        if self.matches_source_expr:
            score += 0.4
        if self.matches_signal_name:
            score += 0.2
        # 交叉验证 (既 match expr 又 match signal): 0.2
        if self.matches_source_expr and self.matches_signal_name:
            score += 0.2
        return min(1.0, score)


# ==============================================================================
# TraceEvidenceResolver - 重构版 (semantic API + offset slicing)
# ==============================================================================

class TraceEvidenceResolver:
    """Trace evidence 解析器 - 重构版 (V4)

    重构要点:
    1. 不递归 walk syntax tree, 改用 pyslang semantic API
       - ClassDefinition: 走 compilation.getRoot().compilationUnits
       - ContinuousAssign: 走 module.body
       - AlwaysCombBlock: 走 module.body
    2. snippet 用 offset 切片 (text[start.offset:end.offset])
       不再 split('\n') 按行号切割
    3. 添加 credibility_score 借鉴 sv-trace M5.1
    """

    def __init__(self, graph, adapter):
        self.graph = graph
        self.adapter = adapter

    # ==================================================================
    # 主入口: resolve()
    # ==================================================================

    def resolve(self, signal_id: str) -> Evidence:
        """解析单个信号的 evidence

        步骤 (V4 重构):
        1. class/constraint 节点 → semantic API 路径
        2. 其他 → edge + semantic API 路径
        """
        ev = Evidence(signal=signal_id)

        # 0. [V4] class/constraint 节点特殊处理
        if self._is_class_or_constraint_node(signal_id):
            return self._resolve_class_or_constraint_evidence_via_semantic(signal_id, ev)

        # 1. 找 incoming edge
        edge = self._find_incoming_edge(signal_id)
        if edge is None:
            return ev

        # 2. 存 source_expr 供 cross-validation 用
        ev.source_expr = edge.expression or edge.condition or ""

        # 3. source_location + source_text (从 edge)
        ev.source_location = edge.source_location
        if ev.source_location and not ev.source_location.is_empty():
            # [V4-FIX] 用 edge.condition_ast (semantic) 拿 source text, 不用我们自己的 SourceLocation
            full_text = self.adapter.get_source_text(edge.condition_ast) if edge.condition_ast else ""
            if full_text:
                ev.source_text = self._extract_line_by_offset(full_text, ev.source_location)

        # 4. 找 start_syn (用于 walk parent chain)
        # V4: 优先用 condition_ast.syntax, fallback 用 semantic API
        start_syn = None
        if edge.condition_ast is not None:
            start_syn = getattr(edge.condition_ast, "syntax", None)
        elif edge.assign_type == "continuous":
            start_syn = self._find_continuous_assign_syntax_semantic(signal_id)
        elif self._is_always_kind(edge.assign_type):
            start_syn = self._find_always_block_syntax_semantic(signal_id)

        if start_syn is None:
            return ev

        # 5. 走 parent chain
        chain_syn = self._walk_parent_chain(start_syn, max_depth=8)
        ev.enclosing_chain = [self._snippet_from_syntax(n) for n in chain_syn if n is not None]
        ev.enclosing_chain = [s for s in ev.enclosing_chain if s is not None]

        # 6. 分类检测 enclosing_*
        for n in chain_syn:
            if n is None:
                continue
            kind = str(getattr(n, "kind", ""))
            snippet = self._snippet_from_syntax(n)
            if snippet is None:
                continue
            if "AlwaysFF" in kind and ev.enclosing_always is None:
                ev.enclosing_always = snippet
            elif "AlwaysComb" in kind:
                if ev.enclosing_always is None:
                    ev.enclosing_always = snippet
                if ev.enclosing_always_comb is None:
                    ev.enclosing_always_comb = snippet
            elif kind == "SyntaxKind.ConditionalStatement" and ev.enclosing_if is None:
                ev.enclosing_if = snippet
            elif "ContinuousAssign" in kind and ev.enclosing_assign is None:
                ev.enclosing_assign = snippet
            elif "ClassDeclaration" in kind and ev.enclosing_class is None:
                ev.enclosing_class = snippet
            elif "ConstraintDeclaration" in kind and ev.enclosing_constraint is None:
                ev.enclosing_constraint = snippet

        # 7. source_text fallback (assign 边可能没 source_location)
        if ev.source_text == "" and ev.enclosing_assign is not None:
            ev.source_location = ev.enclosing_assign.location
            if ev.enclosing_assign.text:
                ev.source_text = ev.enclosing_assign.text.split("\n")[0].strip()

        return ev

    def resolve_chain(self, signal_id: str, max_depth: int = 5) -> list[Evidence]:
        """递归解析 driver 链上每一步的 evidence"""
        result = []
        visited = set()
        self._resolve_chain_recursive(signal_id, result, visited, depth=0, max_depth=max_depth)
        return result

    def _resolve_chain_recursive(self, signal_id, result, visited, depth, max_depth):
        if signal_id in visited or depth > max_depth:
            return
        visited.add(signal_id)
        ev = self.resolve(signal_id)
        result.append(ev)
        for driver_id in self._get_drivers(signal_id):
            self._resolve_chain_recursive(driver_id, result, visited, depth + 1, max_depth)

    # ==================================================================
    # V4: Edge 查找 (保留 V3 逻辑)
    # ==================================================================

    def _find_incoming_edge(self, signal_id: str) -> TraceEdge | None:
        """找 signal_id 的 incoming edge, 优先有 condition_ast 的"""
        if self.graph is None:
            return None
        best = None
        for _key, edges in self.graph._edge_data.items():
            for edge in edges:
                if edge.dst == signal_id:
                    if edge.condition_ast is not None:
                        return edge
                    if best is None:
                        best = edge
        return best

    def _get_drivers(self, signal_id: str) -> list[str]:
        if self.graph is None:
            return []
        drivers = []
        for _key, edges in self.graph._edge_data.items():
            for edge in edges:
                if edge.dst == signal_id and edge.src not in drivers:
                    drivers.append(edge.src)
        return drivers

    def _is_always_kind(self, assign_type: str) -> bool:
        return assign_type in ("nonblocking", "blocking") or "always" in assign_type

    # ==================================================================
    # V4: Snippet 构造 (offset-based slicing)
    # ==================================================================

    def _snippet_from_syntax(self, syn) -> SourceSnippet | None:
        """[V4] 从 syntax 节点构造 SourceSnippet

        用 offset 切片: text[start.offset:end.offset] 替代按行号 split
        优势:
        - 单次切片, 性能更好
        - 不受 line 准确性影响 (跨多行 always 块)
        - 保留原始格式 (无 leading newline)
        """
        if syn is None:
            return None
        sr = getattr(syn, "sourceRange", None)
        if sr is None:
            return None
        try:
            sm = self._get_source_manager()
            if sm is None:
                return None
            filename = sm.getFileName(sr.start) or ""
            start_line = sm.getLineNumber(sr.start)
            start_col = sm.getColumnNumber(sr.start)
            end_line = sm.getLineNumber(sr.end)
            end_col = sm.getColumnNumber(sr.end)
        except Exception:
            return None
        if not filename:
            return None

        # V4: offset-based slicing (替代 _extract_lines)
        try:
            buffer_id = sr.start.buffer
            full_text = sm.getSourceText(buffer_id)
            if full_text:
                # 去掉 pyslang 在 in-memory 文本末尾加的 \x00
                if full_text.endswith('\x00'):
                    full_text = full_text[:-1]
                start_off = sr.start.offset
                end_off = sr.end.offset
                text = full_text[start_off:end_off]
            else:
                text = ""
        except Exception:
            text = ""

        return SourceSnippet(
            location=SourceLocation(
                file=filename,
                line_start=start_line,
                line_end=end_line,
                column=start_col,
            ),
            text=text,
        )

    def _get_source_manager(self):
        """从 adapter 拿 SourceManager (兼容不同 adapter 结构)"""
        try:
            comp = self.adapter._compiler.get_compilation()
            return comp.sourceManager
        except Exception:
            return None

    def _get_source_text_for_location(self, loc: SourceLocation) -> str:
        """从 location 拿 source text"""
        if not loc or not loc.file:
            return ""
        try:
            sm = self._get_source_manager()
            if sm is None:
                return ""
            # 找该文件对应的 buffer
            # 用 filename 反查 buffer_id (pyslang 内部映射)
            # 简化: 从已有 location 反查 buffer
            # 这里用 line 拿
            return sm.getSourceText(getattr(loc, 'buffer_id', 0)) or ""
        except Exception:
            return ""

    def _extract_line_by_offset(self, full_text: str, loc: SourceLocation) -> str:
        """从 full_text 提取 loc.line_start 那一行 (legacy, 仅做 fallback)"""
        if not full_text or loc.line_start <= 0:
            return ""
        lines = full_text.split("\n")
        if loc.line_start > len(lines):
            return ""
        return lines[loc.line_start - 1].strip()

    # ==================================================================
    # V4: 父链 walk (保留)
    # ==================================================================

    def _walk_parent_chain(self, start_syn, max_depth: int = 8) -> list:
        """走 syntax parent 链"""
        chain = []
        cur = start_syn
        d = 0
        while cur is not None and d < max_depth:
            chain.append(cur)
            cur = getattr(cur, "parent", None)
            d += 1
        return chain

    # ==================================================================
    # V4: Class / Constraint 节点 — 改用 Semantic API
    # ==================================================================

    def _is_class_or_constraint_node(self, signal_id: str) -> bool:
        """检查是否是 class/constraint 节点"""
        if self.graph is None:
            return False
        node = self.graph.get_node(signal_id)
        if node is None:
            return False
        return node.kind in {
            NodeKind.CLASS_PROPERTY,
            NodeKind.CLASS_INSTANCE_PROPERTY,
            NodeKind.CONSTRAINT_BLOCK,
            NodeKind.CONSTRAINT_EXPR,
            NodeKind.CONSTRAINT_IF,
            NodeKind.CONSTRAINT_ELSE,
        }

    def _resolve_class_or_constraint_evidence_via_semantic(self, signal_id: str, ev: Evidence) -> Evidence:
        """[V4 重构] 用 semantic API 拿 class/constraint evidence

        不递归 walk syntax tree:
        - Class: compilation.getRoot().compilationUnits[i].compilationUnit[j]
        - Class members: class.syntax.items (1 hop, 不递归)
        - Snippet: offset-based slicing
        """
        node = self.graph.get_node(signal_id)
        if node is None:
            return ev

        # 拆 signal_id: "packet.addr" → class="packet", name="addr"
        parts = signal_id.split(".")
        if len(parts) < 2:
            return ev
        class_name = parts[0]
        name = parts[-1]

        # [V4] 用 semantic API 找 class symbol
        class_symbol = self._find_class_symbol_semantic(class_name)
        if class_symbol is None:
            return ev

        # class 自身的 evidence
        class_syn = class_symbol.syntax
        if class_syn is None:
            return ev

        class_snippet = self._snippet_from_syntax(class_syn)
        if class_snippet is not None:
            ev.enclosing_class = class_snippet
            ev.source_location = class_snippet.location
            if class_snippet.text:
                ev.source_text = class_snippet.text.split("\n")[0].strip()

        # class items 的 snippets (不递归, 直接 items)
        class_items_chain = []
        for sitem in getattr(class_syn, 'items', []):
            snip = self._snippet_from_syntax(sitem)
            if snip:
                class_items_chain.append(snip)

        # [V4] 对 CLASS_PROPERTY / CONSTRAINT_EXPR, 找 enclosing_constraint
        if node.kind in (NodeKind.CLASS_PROPERTY, NodeKind.CONSTRAINT_EXPR):
            # 在 class items 中找 ConstraintDeclaration with matching name
            constraint_snip = None
            for sitem in getattr(class_syn, 'items', []):
                kind_str = str(getattr(sitem, 'kind', ''))
                if 'ConstraintDeclaration' in kind_str:
                    sitem_name = self._get_syn_name(sitem)
                    # 优先按 name 匹配, fallback 按 property 引用匹配
                    if sitem_name == name:
                        constraint_snip = self._snippet_from_syntax(sitem)
                        break
                    # fallback: 字符串包含
                    if constraint_snip is None and self._snippet_contains_text(sitem, name):
                        constraint_snip = self._snippet_from_syntax(sitem)
            if constraint_snip is not None:
                ev.enclosing_constraint = constraint_snip

        # [V4] 对 CONSTRAINT_BLOCK 节点, 自身就是 constraint
        elif node.kind == NodeKind.CONSTRAINT_BLOCK:
            for sitem in getattr(class_syn, 'items', []):
                kind_str = str(getattr(sitem, 'kind', ''))
                if 'ConstraintDeclaration' in kind_str:
                    sitem_name = self._get_syn_name(sitem)
                    if sitem_name == name:
                        ev.enclosing_constraint = self._snippet_from_syntax(sitem)
                        break

        # 构造 enclosing_chain: class items + class
        ev.enclosing_chain = class_items_chain
        if ev.enclosing_class is not None:
            ev.enclosing_chain.append(ev.enclosing_class)

        return ev

    def _find_class_symbol_semantic(self, class_name: str):
        """[V4] 用 semantic API 找指定 class name 的 ClassType"""
        try:
            comp = self.adapter._compiler.get_compilation()
            root = comp.getRoot()
        except Exception:
            return None
        for cu in root.compilationUnits:
            for item in cu.compilationUnit:
                if 'Class' in str(type(item)) and str(getattr(item, 'name', '')) == class_name:
                    return item
        return None

    def _get_syn_name(self, syn) -> str:
        """从 syntax 节点拿名字 (兼容 value/identifier/str)"""
        if not hasattr(syn, 'name') or syn.name is None:
            return ""
        n = syn.name
        if hasattr(n, 'value') and n.value is not None:
            return str(n.value).strip()
        if hasattr(n, 'identifier') and n.identifier is not None:
            return str(n.identifier).strip()
        return str(n).strip()

    def _snippet_contains_text(self, syn, text: str) -> bool:
        """检查 syntax 节点的 snippet 是否包含 text"""
        snip = self._snippet_from_syntax(syn)
        return snip is not None and text in (snip.text or "")

    # ==================================================================
    # V4: Continuous Assign — 改用 Semantic API
    # ==================================================================

    def _find_continuous_assign_syntax_semantic(self, signal_id: str):
        """[V4] 用 semantic API 找驱动 signal_id 的 ContinuousAssignSyntax

        不递归 walk syntax tree:
        - 走 module.body 找 ContinuousAssignSymbol
        - 从 symbol.assignment.syntax.sourceRange 拿范围
        """
        lhs_name = signal_id.split(".")[-1] if signal_id else ""
        if not lhs_name:
            return None
        try:
            comp = self.adapter._compiler.get_compilation()
            root = comp.getRoot()
        except Exception:
            return None
        # 走所有 topInstance.body
        for inst in root.topInstances:
            body = getattr(inst, 'body', None)
            if body is None:
                continue
            for member in body:
                kind_str = str(getattr(member, 'kind', ''))
                if 'ContinuousAssign' in kind_str:
                    # 检查 LHS 是否匹配
                    if self._continuous_assign_drives_name(member, lhs_name):
                        return getattr(member.assignment, 'syntax', None)
        return None

    def _continuous_assign_drives_name(self, continuous_assign_sym, lhs_name: str) -> bool:
        """检查 ContinuousAssignSymbol 是否驱动 lhs_name"""
        if not hasattr(continuous_assign_sym, 'assignment'):
            return False
        ass = continuous_assign_sym.assignment
        if ass is None or not hasattr(ass, 'left'):
            return False
        # ass.left 可能是 NamedValueExpression, .symbol 是 target variable
        left = ass.left
        # 多种方式拿名字: .name (string), .symbol.name, str(left)
        candidate = None
        if hasattr(left, 'symbol') and left.symbol is not None:
            candidate = str(getattr(left.symbol, 'name', '')).strip()
        if not candidate and hasattr(left, 'name'):
            candidate = str(getattr(left, 'name', '')).strip()
        if not candidate:
            # fallback: str() 整个 left
            candidate = str(left).strip()
        return candidate == lhs_name

    # ==================================================================
    # V4: Always Block (always_comb / always_ff) — 改用 Semantic API
    # ==================================================================

    def _find_always_block_syntax_semantic(self, signal_id: str):
        """[V4] 用 semantic API 找驱动 signal_id 的 always 块

        走 module.body 找 ProceduralBlockSymbol:
        - kind == SymbolKind.ProceduralBlock
        - procedureKind: AlwaysComb / AlwaysFF / Initial
        - 走 symbol.syntax.sourceRange 拿范围
        """
        lhs_name = signal_id.split(".")[-1] if signal_id else ""
        if not lhs_name:
            return None
        try:
            comp = self.adapter._compiler.get_compilation()
            root = comp.getRoot()
        except Exception:
            return None
        for inst in root.topInstances:
            body = getattr(inst, 'body', None)
            if body is None:
                continue
            for member in body:
                kind_str = str(getattr(member, 'kind', ''))
                # [V4-FIX] ProceduralBlockSymbol 在 semantic API 中 kind=ProceduralBlock
                # 不是 AlwaysCombBlock (后者只在 syntax 树)
                if 'ProceduralBlock' not in kind_str:
                    continue
                # 检查 procedureKind 区分 always_comb/always_ff
                proc_kind = getattr(member, 'procedureKind', None)
                if proc_kind is None:
                    continue
                proc_kind_str = str(proc_kind)
                # 只处理 always_comb / always_ff, 跳过 initial
                if 'Always' not in proc_kind_str:
                    continue
                # [V4-FIX] 检查 statement (或 syntax body) 是否包含 LHS
                stmt = getattr(member, 'statement', None)
                stmt_str = str(stmt) if stmt is not None else ""
                # LHS 检测
                if lhs_name in stmt_str or self._lhs_in_always_syntax(member, lhs_name):
                    return getattr(member, 'syntax', None)
        return None

    def _lhs_in_always_syntax(self, proc_block_sym, lhs_name: str) -> bool:
        """检查 always 块 (ProceduralBlockSymbol) 的 syntax 是否包含 lhs_name"""
        syn = getattr(proc_block_sym, 'syntax', None)
        if syn is None:
            return False
        # statement 是 BlockStatementSyntax, 用 .body
        stmt = getattr(syn, 'statement', None)
        if stmt is None:
            return False
        return lhs_name in str(stmt)
