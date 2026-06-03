# ==============================================================================
# trace_evidence.py - Trace Evidence Resolver (Stage 2)
#
# 职责: 给定一个信号, 返回其 driver edge 的完整源码证据:
# - enclosing always_ff 块 (完整源码)
# - enclosing if 块 (完整源码, 如有)
# - source_location (行号, 文件)
# - source_text (该行源码)
# - parent_chain (完整 enclosing scope 链)
#
# 架构: 复用 SourceLocation / SourceSnippet 数据类 (Stage 1 加的字段)
# 数据流: 接收 SignalGraph + SemanticAdapter, 走 pyslang syntax.parent 链
# ==============================================================================

from dataclasses import dataclass, field

from .coverage_models import SourceLocation, SourceSnippet
from .graph.models import TraceEdge


@dataclass
class Evidence:
    """完整源码证据

    Attributes:
        signal: 查询的信号 ID
        source_location: 该行源码位置 (file, line_start, line_end, column)
        source_text: 该行源码文本 (懒加载时机)
        enclosing_always: enclosing always_ff 块的 SourceSnippet (含位置 + 文本)
                          [back-compat] 也覆盖 always_comb 块
        enclosing_always_comb: enclosing always_comb 块 (新增字段, 仅 always_comb 填充)
        enclosing_if: enclosing if 块的 SourceSnippet (含位置 + 文本)
        enclosing_assign: enclosing continuous assign 块 (新增, 仅 assign 填充)
        enclosing_class: enclosing class declaration (新增, 仅 class 内项填充)
        enclosing_constraint: enclosing constraint block (新增, 仅 class 内项填充)
        enclosing_chain: 完整 enclosing scope 链 (从内到外, 列表)
    """
    signal: str
    source_location: SourceLocation | None = None
    source_text: str = ""
    enclosing_always: SourceSnippet | None = None
    enclosing_always_comb: SourceSnippet | None = None
    enclosing_if: SourceSnippet | None = None
    enclosing_assign: SourceSnippet | None = None
    enclosing_class: SourceSnippet | None = None
    enclosing_constraint: SourceSnippet | None = None
    enclosing_chain: list[SourceSnippet] = field(default_factory=list)


class TraceEvidenceResolver:
    """Trace evidence 解析器

    用法:
        tracer = UnifiedTracer(...)
        graph = tracer.build_graph()
        sem = tracer._get_adapter()  # 或外部传入
        resolver = TraceEvidenceResolver(graph=graph, adapter=sem)
        ev = resolver.resolve("top.q")
        print(ev.enclosing_always.text)
    """

    def __init__(self, graph, adapter):
        self.graph = graph
        self.adapter = adapter

    def resolve(self, signal_id: str) -> Evidence:
        """解析单个信号的 evidence

        步骤:
        1. 找信号的所有 incoming edges (drivers)
        2. 选第一个有 condition_ast + source_location 的 edge
        3. 走 condition_ast.syntax.parent 链找 enclosing always/if
        4. 提取 source text (通过 semantic_adapter.get_source_text)
        """
        ev = Evidence(signal=signal_id)

        # 0. [V3] class/constraint 节点特殊处理: 无 condition_ast, 从 syntax 树中查找
        if self._is_class_or_constraint_node(signal_id):
            return self._resolve_class_or_constraint_evidence(signal_id, ev)

        # 1. 找 incoming edge
        edge = self._find_incoming_edge(signal_id)
        if edge is None:
            return ev

        # 2. source_location + source_text
        ev.source_location = edge.source_location
        if ev.source_location and not ev.source_location.is_empty():
            full_text = self.adapter.get_source_text(edge.condition_ast) if edge.condition_ast else ""
            ev.source_text = self._extract_line(full_text, ev.source_location)

        # 3. 走 syntax parent 链
        # [V3-FIX] 3 路径:
        # - always_ff/always_comb: 走 condition_ast.syntax.parent 链 (从内到外)
        # - continuous assign: 从 syntax tree 中找 ContinuousAssignSyntax 作为起始节点
        # - always_comb 无 condition_ast: 从 syntax tree 中找 AlwaysCombBlock 作为起始节点
        start_syn = None
        if edge.condition_ast is not None:
            start_syn = getattr(edge.condition_ast, "syntax", None)
        elif edge.assign_type == "continuous" or (edge.source_location is None and edge.expression):
            # [V3-FIX] 连续赋值 fallback: 从 syntax tree 中查找
            start_syn = self._find_continuous_assign_syntax(signal_id)
        # [V3-FIX] 始终尝试 always_comb fallback (如果不是 assign)
        if start_syn is None and edge.assign_type != "continuous":
            start_syn = self._find_always_comb_syntax(signal_id)

        if start_syn is None:
            return ev

        chain_syn = self._walk_parent_chain(start_syn, max_depth=8)
        ev.enclosing_chain = [self._make_snippet(n) for n in chain_syn]

        # 4. 找 enclosing always/if/assign
        # 走整个 chain 找最大范围的 (避免匹配到 Predicate/Expression 这类中间节点)
        for n in chain_syn:
            kind = str(getattr(n, "kind", ""))
            snippet = self._make_snippet(n)
            if "AlwaysFF" in kind and ev.enclosing_always is None:
                ev.enclosing_always = snippet
            elif "AlwaysComb" in kind:
                # [V3] always_comb 填充到两个字段:
                # - enclosing_always (back-compat, 同 always_ff)
                # - enclosing_always_comb (新加字段, 明确类型)
                if ev.enclosing_always is None:
                    ev.enclosing_always = snippet
                if ev.enclosing_always_comb is None:
                    ev.enclosing_always_comb = snippet
            # 只匹配精确的 "ConditionalStatement" (跳过 Predicate/Expression 等中间 kind)
            elif kind == "SyntaxKind.ConditionalStatement" and ev.enclosing_if is None:
                ev.enclosing_if = snippet
            elif "ContinuousAssign" in kind and ev.enclosing_assign is None:
                ev.enclosing_assign = snippet
            # [V3] class/constraint 节点识别
            elif "ClassDeclaration" in kind and ev.enclosing_class is None:
                ev.enclosing_class = snippet
            elif "ConstraintDeclaration" in kind and ev.enclosing_constraint is None:
                ev.enclosing_constraint = snippet

        # [V3-FIX] 如果 enclosing_assign 已找到, 试着用其源文件填充 source_text
        # (assign 边可能没有 source_location, 需要从 syntax 树反推)
        if ev.source_text == "" and ev.enclosing_assign is not None:
            ev.source_location = ev.enclosing_assign.location
            ev.source_text = ev.enclosing_assign.text.split("\n")[0].strip() if ev.enclosing_assign.text else ""

        return ev

    def resolve_chain(self, signal_id: str, max_depth: int = 5) -> list[Evidence]:
        """递归解析 driver 链上每一步的 evidence

        返回列表: 从起始信号开始, 每个 driver 一个 Evidence
        """
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
        # 递归到 drivers
        for driver_id in self._get_drivers(signal_id):
            self._resolve_chain_recursive(driver_id, result, visited, depth + 1, max_depth)

    def _find_incoming_edge(self, signal_id: str) -> TraceEdge | None:
        """找 signal_id 的 incoming edge (driver)

        优先选有 condition_ast 的 (这样能解析出 enclosing always/if)
        """
        if self.graph is None:
            return None
        best = None
        for _key, edges in self.graph._edge_data.items():
            for edge in edges:
                if edge.dst == signal_id:
                    if edge.condition_ast is not None:
                        return edge  # 优先返回有 AST 的
                    if best is None:
                        best = edge
        return best

    def _get_drivers(self, signal_id: str) -> list[str]:
        """拿 signal 的所有 driver 信号 ID (outgoing from drivers)"""
        if self.graph is None:
            return []
        drivers = []
        for _key, edges in self.graph._edge_data.items():
            for edge in edges:
                if edge.dst == signal_id and edge.src not in drivers:
                    drivers.append(edge.src)
        return drivers

    def _walk_parent_chain(self, start_syn, max_depth: int = 8) -> list:
        """走 syntax parent 链, 收集所有 syntax 节点

        从 start_syn 开始, 一直走到 root (深度上限 max_depth)
        """
        chain = []
        cur = start_syn
        d = 0
        while cur is not None and d < max_depth:
            chain.append(cur)
            cur = getattr(cur, "parent", None)
            d += 1
        return chain

    def _make_snippet(self, syn) -> SourceSnippet | None:
        """从 syntax 节点构造 SourceSnippet (含位置 + 文本)"""
        if syn is None:
            return None
        sr = getattr(syn, "sourceRange", None)
        if sr is None:
            return None

        # 拿 file/line/col
        try:
            sm = self.adapter._compiler.get_compilation().sourceManager
            filename = sm.getFileName(sr.start) or ""
            start_line = sm.getLineNumber(sr.start)
            start_col = sm.getColumnNumber(sr.start)
            end_line = sm.getLineNumber(sr.end)
            end_col = sm.getColumnNumber(sr.end)
        except Exception:
            return None

        if not filename:
            return None

        # 拿 source text
        try:
            full_text = sm.getSourceText(sr.start.buffer)
            text = self._extract_lines(full_text, start_line, end_line, start_col, end_col)
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

    def _extract_line(self, full_text: str, loc: SourceLocation) -> str:
        """从 full_text 提取 loc 指定的那一行"""
        if not full_text or loc.line_start <= 0:
            return ""
        lines = full_text.split("\n")
        if loc.line_start > len(lines):
            return ""
        return lines[loc.line_start - 1].strip()

    def _extract_lines(self, full_text: str, start_line: int, end_line: int,
                      start_col: int, end_col: int) -> str:
        """从 full_text 提取 [start_line, end_line] 范围 (1-indexed)

        返回多行字符串, 保留原始行
        """
        if not full_text or start_line <= 0:
            return ""
        lines = full_text.split("\n")
        if start_line > len(lines):
            return ""
        end_line = min(end_line, len(lines))
        return "\n".join(lines[start_line - 1:end_line])

    # =========================================================================
    # [V3] class / constraint 节点 evidence 解析
    # =========================================================================

    def _is_class_or_constraint_node(self, signal_id: str) -> bool:
        """检查 signal_id 是否是 class 内项或 constraint 块

        通过 graph 节点 kind 检查:
        - CLASS_PROPERTY  (e.g., "packet.addr")
        - CLASS_INSTANCE_PROPERTY
        - CONSTRAINT_BLOCK (e.g., "packet.c_addr")
        - CONSTRAINT_EXPR
        """
        if self.graph is None:
            return False
        from .graph.models import NodeKind
        node = self.graph.get_node(signal_id)
        if node is None:
            return False
        class_constraint_kinds = {
            NodeKind.CLASS_PROPERTY,
            NodeKind.CLASS_INSTANCE_PROPERTY,
            NodeKind.CONSTRAINT_BLOCK,
            NodeKind.CONSTRAINT_EXPR,
            NodeKind.CONSTRAINT_IF,
            NodeKind.CONSTRAINT_ELSE,
        }
        return node.kind in class_constraint_kinds

    def _resolve_class_or_constraint_evidence(self, signal_id: str, ev: Evidence) -> Evidence:
        """从 syntax 树中查找 class/constraint 节点, 走 parent 链拿 enclosing

        对 CLASS_PROPERTY:
            - enclosing_class = ClassDeclaration
            - enclosing_constraint = ConstraintDeclaration (调用此 property 的)

        对 CONSTRAINT_BLOCK:
            - enclosing_class = ClassDeclaration

        对 CONSTRAINT_EXPR:
            - enclosing_constraint = ConstraintDeclaration
            - enclosing_class = ClassDeclaration
        """
        # 拿对应的 graph 节点确定类型
        from .graph.models import NodeKind
        node = self.graph.get_node(signal_id)
        if node is None:
            return ev

        # 拿 syntax tree
        comp = self.adapter._compiler.get_compilation()
        syntax_trees = comp.getSyntaxTrees()
        if not syntax_trees:
            return ev

        # 拆 signal_id: "packet.addr" → class="packet", name="addr"
        parts = signal_id.split(".")
        if len(parts) < 2:
            return ev
        class_name = parts[0]
        name = parts[-1] if len(parts) >= 2 else ""

        # 走 syntax 树找 ClassDeclarationSyntax
        start_syn = None
        for tree in syntax_trees:
            start_syn = self._find_syntax_node_by_name(tree.root, "ClassDeclaration", class_name)
            if start_syn:
                break
        if start_syn is None:
            return ev

        # 走 parent 链 (从 ClassDeclaration 开始)
        chain_syn = self._walk_parent_chain(start_syn, max_depth=4)
        ev.enclosing_chain = [self._make_snippet(n) for n in chain_syn]

        # 从 chain 中拿 enclosing_class
        for n in chain_syn:
            kind = str(getattr(n, "kind", ""))
            snippet = self._make_snippet(n)
            if "ClassDeclaration" in kind and ev.enclosing_class is None:
                ev.enclosing_class = snippet
                # class 本身就是 source
                ev.source_location = snippet.location
                ev.source_text = snippet.text.split("\n")[0].strip() if snippet.text else ""
                break

        # 如果是 CLASS_PROPERTY 或 CONSTRAINT_EXPR, 还需要找 enclosing_constraint
        if node.kind in (NodeKind.CLASS_PROPERTY, NodeKind.CONSTRAINT_EXPR):
            # 在 class 内查找 ConstraintDeclarationSyntax
            constraint_syn = self._find_syntax_node_in_class(
                start_syn, "ConstraintDeclaration", name
            )
            if constraint_syn is not None:
                # 走 constraint 的 parent 链 (ConstraintDeclaration → ClassDeclaration)
                c_chain = self._walk_parent_chain(constraint_syn, max_depth=4)
                c_snippets = [s for s in (self._make_snippet(n) for n in c_chain) if s is not None]
                for n, snippet in zip(c_chain, c_snippets):
                    kind = str(getattr(n, "kind", ""))
                    if "ConstraintDeclaration" in kind and ev.enclosing_constraint is None:
                        ev.enclosing_constraint = snippet
                    elif "ClassDeclaration" in kind and ev.enclosing_class is None:
                        ev.enclosing_class = snippet
                # 合并 snippets 到 enclosing_chain
                ev.enclosing_chain = c_snippets + ev.enclosing_chain
            else:
                # 在 class 内找所有 ConstraintDeclaration (generic class)
                all_constraint_syns = self._find_all_syntax_nodes_in_class(
                    start_syn, "ConstraintDeclaration"
                )
                for c_syn in all_constraint_syns:
                    # 检查这个 constraint 是否引用了我们的 property
                    if self._constraint_references_property(c_syn, name, parts[1] if len(parts) > 2 else ""):
                        # Walk to get the constraint snippet
                        c_chain = self._walk_parent_chain(c_syn, max_depth=4)
                        c_snippets = [s for s in (self._make_snippet(n) for n in c_chain) if s is not None]
                        for n, snippet in zip(c_chain, c_snippets):
                            kind = str(getattr(n, "kind", ""))
                            if "ConstraintDeclaration" in kind and ev.enclosing_constraint is None:
                                ev.enclosing_constraint = snippet
                                break
                        # Add first match to enclosing_chain
                        ev.enclosing_chain = c_snippets + ev.enclosing_chain
                        break  # Use first match

        return ev

    def _find_syntax_node_by_name(self, root, target_kind: str, name: str):
        """在 syntax 树中查找指定 kind + name 的节点

        target_kind: "ClassDeclaration" / "ConstraintDeclaration" / "ClassProperty"
        name: class 名 / constraint 名 / property 名
        """
        if root is None:
            return None
        kind_str = str(getattr(root, "kind", ""))
        # 匹配: ClassDeclaration with name="packet", etc.
        if target_kind in kind_str:
            node_name = self._get_syntax_node_name(root)
            if node_name == name:
                return root
        # 递归进入子节点
        if hasattr(root, "__iter__") and not isinstance(root, str):
            for child in root:
                found = self._find_syntax_node_by_name(child, target_kind, name)
                if found is not None:
                    return found
        # 单个属性 (如 .statement, .body)
        for attr in ["statement", "body", "members", "items", "declarator", "declarators"]:
            if hasattr(root, attr):
                sub = getattr(root, attr)
                if sub is not None:
                    found = self._find_syntax_node_by_name(sub, target_kind, name)
                    if found is not None:
                        return found
        return None

    def _get_syntax_node_name(self, node) -> str:
        """从 syntax 节点拿名字 (去掉 'Symbol' / 前后空格)"""
        # ClassDeclaration has .name (a token)
        if hasattr(node, "name"):
            name_attr = node.name
            if name_attr is not None:
                # name may be a token (has .text or .value)
                if hasattr(name_attr, "value"):
                    return str(name_attr.value).strip()
                if hasattr(name_attr, "text"):
                    return str(name_attr.text).strip()
                return str(name_attr).strip()
        return ""

    def _find_syntax_node_in_class(self, class_syn, target_kind: str, name: str):
        """在 class 节点内找指定 kind + name 的节点"""
        if class_syn is None:
            return None
        # class.items 列出所有成员 (注意:不是 .members)
        items = getattr(class_syn, "items", None)
        if items is None:
            members = getattr(class_syn, "members", None)
            items = members
        if items is not None and hasattr(items, "__iter__"):
            for member in items:
                if member is None:
                    continue
                kind_str = str(getattr(member, "kind", ""))
                if target_kind in kind_str:
                    node_name = self._get_syntax_node_name(member)
                    if node_name == name:
                        return member
        return None

    def _find_all_syntax_nodes_in_class(self, class_syn, target_kind: str) -> list:
        """在 class 节点内找所有指定 kind 的节点"""
        results = []
        if class_syn is None:
            return results
        items = getattr(class_syn, "items", None)
        if items is None:
            items = getattr(class_syn, "members", None)
        if items is not None and hasattr(items, "__iter__"):
            for member in items:
                if member is None:
                    continue
                kind_str = str(getattr(member, "kind", ""))
                if target_kind in kind_str:
                    results.append(member)
        return results

    def _constraint_references_property(self, constraint_syn, prop_name: str, _instance_name: str = "") -> bool:
        """检查 constraint 块是否引用了指定 property (粗糙字符串检查)"""
        if constraint_syn is None:
            return False
        # 拿 constraint 的 source text
        snippet = self._make_snippet(constraint_syn)
        if snippet is None:
            return False
        return prop_name in snippet.text

    # =========================================================================
    # [V3] continuous assign 节点 evidence 解析 (fallback path)
    # =========================================================================

    def _find_continuous_assign_syntax(self, signal_id: str):
        """[V3] 从 syntax 树中查找驱动 signal_id 的 ContinuousAssignSyntax

        适用场景: assign 边的 condition_ast 为 None, source_location 也为 None
        此时需要从 syntax 树里找 ContinuousAssignSyntax 作为起始节点
        """
        # 拿 LHS 信号名: "top.y" → "y"
        parts = signal_id.split(".")
        lhs_name = parts[-1] if parts else signal_id
        if not lhs_name:
            return None

        # 拿 syntax tree
        try:
            comp = self.adapter._compiler.get_compilation()
            syntax_trees = comp.getSyntaxTrees()
        except Exception:
            return None
        if not syntax_trees:
            return None

        for tree in syntax_trees:
            found = self._walk_syntax_find_continuous_assign(tree.root, lhs_name)
            if found is not None:
                return found
        return None

    def _walk_syntax_find_continuous_assign(self, node, lhs_name: str):
        """在 syntax 树中递归查找 ContinuousAssignSyntax 匹配 LHS name"""
        if node is None:
            return None
        kind = str(getattr(node, "kind", ""))
        if "ContinuousAssign" in kind:
            # 看 LHS 是否匹配
            ass_list = getattr(node, "assignments", None)
            if ass_list:
                for ass in ass_list:
                    if self._extract_lhs_name(ass) == lhs_name:
                        return node
        # 递归
        if hasattr(node, "__iter__") and not isinstance(node, str):
            for child in node:
                found = self._walk_syntax_find_continuous_assign(child, lhs_name)
                if found is not None:
                    return found
        for attr in ["statement", "body", "items"]:
            sub = getattr(node, attr, None)
            if sub is not None:
                found = self._walk_syntax_find_continuous_assign(sub, lhs_name)
                if found is not None:
                    return found
        return None

    def _extract_lhs_name(self, assign_expr) -> str:
        """从 AssignmentExpression 中提取 LHS 信号名"""
        if assign_expr is None:
            return ""
        left = getattr(assign_expr, "left", None)
        if left is None:
            return ""
        # IdentifierNameSyntax has .name (Token with .value)
        name_attr = getattr(left, "name", None)
        if name_attr is not None:
            value = getattr(name_attr, "value", None)
            if value:
                return str(value).strip()
            return str(name_attr).strip()
        # 也许 left 本身是 NamedPort / ExpressionStatement
        return str(left).strip()

    def _find_always_comb_syntax(self, signal_id: str):
        """[V3] 从 syntax 树中查找驱动 signal_id 的 AlwaysCombBlock

        适用场景: always_comb 边的 condition_ast 为 None
        """
        # 拿 LHS 信号名
        parts = signal_id.split(".")
        lhs_name = parts[-1] if parts else signal_id
        if not lhs_name:
            return None
        try:
            comp = self.adapter._compiler.get_compilation()
            syntax_trees = comp.getSyntaxTrees()
        except Exception:
            return None
        if not syntax_trees:
            return None
        for tree in syntax_trees:
            found = self._walk_syntax_find_always_comb(tree.root, lhs_name)
            if found is not None:
                return found
        return None

    def _walk_syntax_find_always_comb(self, node, lhs_name: str):
        """在 syntax 树中递归查找 AlwaysCombBlock (其 LHS 包含 lhs_name)"""
        if node is None:
            return None
        kind = str(getattr(node, "kind", ""))
        if "AlwaysCombBlock" in kind or "AlwaysFFBlock" in kind:
            # 检查这个 always 块是否驱动了 lhs_name
            stmt = getattr(node, "statement", None) or getattr(node, "body", None)
            if stmt is not None and lhs_name in str(stmt):
                return node
        if hasattr(node, "__iter__") and not isinstance(node, str):
            for child in node:
                found = self._walk_syntax_find_always_comb(child, lhs_name)
                if found is not None:
                    return found
        for attr in ["statement", "body", "items"]:
            sub = getattr(node, attr, None)
            if sub is not None:
                found = self._walk_syntax_find_always_comb(sub, lhs_name)
                if found is not None:
                    return found
        return None
