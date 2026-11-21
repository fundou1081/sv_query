"""Local graph session — one tracer, many read-only queries (P194.2c).

This is a library seam for persistent agents; the CLI ``session --serve`` stdio
adapter is a thin wrapper around it. It owns one UnifiedTracer and never
rebuilds for subsequent graph queries.
"""
from __future__ import annotations

from pathlib import Path

from .trace._safe import safe_attr
from .trace.core.snapshot_manager import SnapshotManager
from .trace.unified_tracer import UnifiedTracer


class GraphSession:
    """One built graph, reusable graph queries, optional snapshot hydration."""

    def __init__(
        self,
        *,
        file: str | Path | None = None,
        filelist: str | None = None,
        from_snapshot: str | None = None,
        log_level: str = "ERROR",
        use_cache: bool = True,
    ) -> None:
        self._from_snapshot = from_snapshot
        if from_snapshot:
            if file or filelist:
                raise ValueError("from_snapshot is mutually exclusive with file/filelist")
            snapshot = SnapshotManager().load(from_snapshot)
            if snapshot is None:
                raise ValueError(f"Snapshot not found: {from_snapshot}")
            self.tracer = UnifiedTracer(sources={}, log_level=log_level)
            self.tracer.load_snapshot(snapshot)
        else:
            if not file and not filelist:
                raise ValueError("file or filelist is required")
            if file and not filelist:
                src = Path(file).read_text(encoding="utf-8")
                self.tracer = UnifiedTracer(
                    sources={str(Path(file).resolve()): src},
                    log_level=log_level,
                )
            else:
                self.tracer = UnifiedTracer(filelist=filelist, log_level=log_level)
            self.tracer.build_graph(use_cache=use_cache)

    @property
    def graph(self):
        return self.tracer.get_graph()

    def cache_info(self) -> dict:
        if self._from_snapshot:
            return {"status": "snapshot", "key": None, "capabilities": ["graph", "mig"]}
        return self.tracer.cache_info()

    def _node_row(self, nid: str, node, detail: bool) -> dict:
        node_kind = node.kind.name if hasattr(node.kind, "name") else str(node.kind)
        item = {"id": nid, "name": safe_attr(node, "name", ""),
                "kind": node_kind, "module": node.module}
        if detail:
            extra = node.extra if hasattr(node, "extra") else {}
            item.update({
                "width": node.width,
                "expression": extra.get("expression", ""),
                "operands": extra.get("operands", []),
                "signals": extra.get("signals", []),
                "function_name": extra.get("function_name", ""),
                "condition": extra.get("condition", ""),
                "true_branch": extra.get("true_branch", ""),
                "false_branch": extra.get("false_branch", ""),
            })
        return item

    def graph_nodes(self, *, kind: str | None = None, module: str | None = None,
                    match: str | None = None, detail: bool = False) -> dict:
        rows = []
        for nid in self.graph.nodes():
            node = self.graph.get_node(nid)
            if node is None:
                continue
            row = self._node_row(nid, node, detail)
            if kind and row["kind"] != kind:
                continue
            if module and row["module"] != module:
                continue
            if match and match.lower() not in nid.lower():
                continue
            rows.append(row)
        return {"nodes": rows, "total": len(rows)}

    def graph_edges(self, *, kind: str | None = None, src: str | None = None,
                    dst: str | None = None) -> dict:
        graph = self.graph
        rows = []
        for e_src, e_dst in graph.edges():
            edge = graph.get_edge(e_src, e_dst)
            if edge is None:
                continue
            edge_kind = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
            if kind and edge_kind != kind:
                continue
            if src and e_src != src:
                continue
            if dst and e_dst != dst:
                continue
            rows.append({"src": e_src, "dst": e_dst, "kind": edge_kind})
        return {"edges": rows, "total": len(rows)}

    def handlers(self) -> dict:
        """Session op handlers backed by this one graph."""
        def nodes(request):
            return self.graph_nodes(
                kind=request.get("kind"), module=request.get("module"),
                match=request.get("match"), detail=bool(request.get("detail")),
            )

        def edges(request):
            return self.graph_edges(
                kind=request.get("kind"), src=request.get("src"), dst=request.get("dst"),
            )

        return {"graph_nodes": nodes, "graph_edges": edges}

    def close(self) -> None:
        self.tracer = None
