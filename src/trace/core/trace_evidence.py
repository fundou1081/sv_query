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
        enclosing_if: enclosing if 块的 SourceSnippet (含位置 + 文本)
        enclosing_chain: 完整 enclosing scope 链 (从内到外, 列表)
    """
    signal: str
    source_location: SourceLocation | None = None
    source_text: str = ""
    enclosing_always: SourceSnippet | None = None
    enclosing_if: SourceSnippet | None = None
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
        if edge.condition_ast is None:
            return ev

        syn = getattr(edge.condition_ast, "syntax", None)
        if syn is None:
            return ev

        chain_syn = self._walk_parent_chain(syn, max_depth=8)
        ev.enclosing_chain = [self._make_snippet(n) for n in chain_syn]

        # 4. 找 enclosing always/if
        # 走整个 chain 找最大范围的 (避免匹配到 Predicate/Expression 这类中间节点)
        for n in chain_syn:
            kind = str(getattr(n, "kind", ""))
            snippet = self._make_snippet(n)
            if "AlwaysFF" in kind and ev.enclosing_always is None:
                ev.enclosing_always = snippet
            # 只匹配精确的 "ConditionalStatement" (跳过 Predicate/Expression 等中间 kind)
            elif kind == "SyntaxKind.ConditionalStatement" and ev.enclosing_if is None:
                ev.enclosing_if = snippet

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
