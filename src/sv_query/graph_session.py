"""Local graph session — one tracer, many read-only queries (P194.2c).

This is a library seam for persistent agents; the CLI ``session --serve`` stdio
adapter is a thin wrapper around it. It owns one UnifiedTracer and never
rebuilds for subsequent graph queries.
"""
from __future__ import annotations

from pathlib import Path

from .trace._safe import safe_attr
from .trace.core.graph.dataflow import DataFlowGraph
from .trace.core.query import session_ops
from .trace.core.snapshot_manager import SnapshotManager
from .trace.unified_tracer import SnapshotCapabilityError, UnifiedTracer


class SignalNotFoundError(ValueError):
    """Structured query error for a missing graph endpoint."""

    error_code = "E_SIGNAL_NOT_FOUND"


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
        self._file = str(file) if file else None
        self._filelist = filelist
        self._cache_key = None
        self._log_level = log_level
        self._use_cache = use_cache
        self._closed = False
        self._generation = 0
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
            self.tracer.build_graph(use_cache=use_cache, required_capabilities={"graph", "mig"})
        self._cache_key = self._current_cache_key()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("GraphSession is closed")

    @property
    def graph(self):
        self._ensure_open()
        return self.tracer.get_graph()

    @property
    def generation(self) -> int:
        """Increments on refresh; callers must re-fetch gs.graph after it changes."""
        self._ensure_open()
        return self._generation

    def _current_cache_key(self) -> str | None:
        self._ensure_open()
        if self._from_snapshot:
            return None
        if self._file:
            source = Path(self._file).read_text(encoding="utf-8")
            identity = self.tracer._build_identity(
                None, sources_override={str(Path(self._file).resolve()): source})
        else:
            identity = self.tracer._build_identity(None)
        if identity is None:
            target = self._filelist or self._file or "<unknown>"
            raise RuntimeError(
                f"cannot compute build identity for {target!r}; "
                "source/filelist closure is missing or unreadable")
        return identity.key()

    def refresh(self) -> bool:
        """Rebuild when source content changed; return whether a rebuild happened.

        A rebuild increments ``generation`` and replaces the tracer graph. External
        references to the previous graph are not mutated; callers must re-fetch
        ``gs.graph`` / re-run queries after refresh.
        """
        self._ensure_open()
        if self._from_snapshot:
            return False
        current = self._current_cache_key()
        if current is None or current == self._cache_key:
            return False
        # A tracer caches its compiler/filelist after the first build; rebuild
        # from a fresh tracer so changed files are re-read (force alone is not enough).
        if self._file:
            source = Path(self._file).read_text(encoding="utf-8")
            tracer = UnifiedTracer(
                sources={str(Path(self._file).resolve()): source},
                log_level=self._log_level,
            )
        else:
            tracer = UnifiedTracer(filelist=self._filelist, log_level=self._log_level)
        tracer.build_graph(use_cache=self._use_cache, required_capabilities={"graph", "mig"})
        self.tracer = tracer
        self._cache_key = current
        self._generation += 1
        return True

    def _require_mig(self) -> None:
        self._ensure_open()
        caps = self.tracer.get_built_capabilities()
        if "mig" not in caps:
            raise SnapshotCapabilityError(frozenset({"graph", "mig"}), caps)

    def cache_info(self) -> dict:
        self._ensure_open()
        if self._from_snapshot:
            return {"status": "snapshot", "key": None,
                    "capabilities": sorted(self.tracer.get_built_capabilities())}
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
        self._ensure_open()
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
        self._ensure_open()
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

    def drivers(self, signal: str, *, depth: int | None = None,
                module: str | None = None) -> dict:
        self._ensure_open()
        self._require_mig()
        rows = self.tracer.trace_fanin_detailed(signal, module=module, depth=depth)
        return {
            "signal": signal,
            "drivers": [{
                "id": d.id,
                "kind": d.node.kind.name if hasattr(d.node.kind, "name") else str(d.node.kind),
                "module": d.node.module,
                "expression": d.expression,
                "condition": d.condition,
                "assign_type": d.assign_type,
                "distance": d.distance,
            } for d in rows],
            "count": len(rows),
        }

    def loads(self, signal: str, *, depth: int | None = None,
              module: str | None = None) -> dict:
        self._ensure_open()
        self._require_mig()
        rows = self.tracer.trace_fanout(signal, module=module, depth=depth)
        return {
            "signal": signal,
            "loads": [{
                "id": n.id,
                "kind": n.kind.name if hasattr(n.kind, "name") else str(n.kind),
                "module": n.module,
            } for n in rows],
            "count": len(rows),
        }

    def paths(self, src: str, dst: str, *, directed: bool = False) -> dict:
        self._ensure_open()
        self._require_mig()
        graph = self.tracer.get_graph()
        unknown = [x for x in (src, dst) if x not in graph.nodes()]
        if unknown:
            raise SignalNotFoundError(
                f"signal id not found in graph: {', '.join(unknown)}")
        resolver = self.tracer.get_path_resolver()
        if resolver is None:
            raise ValueError("path resolver unavailable")
        path = resolver.find_path(src, dst, directed=directed)
        return {"src": src, "dst": dst, "directed": directed,
                "mode": "data" if directed else "structural",
                "found": path is not None,
                "hop_count": (len(path) - 1) if path else None,
                "path": path}

    def dataflow(self, src: str, dst: str, *, max_paths: int = 100) -> dict:
        self._ensure_open()
        self._require_mig()
        graph = self.graph
        if src not in graph.nodes() or dst not in graph.nodes():
            raise ValueError("signal id not found in graph")
        result = DataFlowGraph(graph, self.tracer.get_module_graph()).analyze(
            src, dst, max_paths=max_paths)
        return {
            "from": src,
            "to": dst,
            "is_reachable": result.is_reachable,
            "paths_count": result.paths_count,
            "truncated": result.truncated,
            "truncation_reason": result.truncation_reason,
            "paths": [[seg.from_signal for seg in p.segments] + [dst]
                      for p in result.paths],
        }

    def instances(self, *, path: str | None = None, module: str | None = None,
                  depth: int | None = None) -> dict:
        self._ensure_open()
        self._require_mig()
        return session_ops.instances(self.tracer, path=path, module=module, depth=depth)

    def scope(self, path: str) -> dict:
        self._ensure_open()
        self._require_mig()
        return session_ops.scope(self.tracer, path)

    def verify_claim(self, claim: object) -> dict:
        self._ensure_open()
        self._require_mig()
        return session_ops.verify_claim(self.tracer, claim)

    def verify_consistency(self, *, checks=("connection",), signal=None,
                           max_nodes: int = 200, full: bool = False) -> dict:
        self._ensure_open()
        self._require_mig()
        return session_ops.verify_consistency(
            self.tracer, checks=checks, signal=signal, max_nodes=max_nodes, full=full)

    def handlers(self) -> dict:
        """Session op handlers backed by this one graph."""
        self._ensure_open()


        def nodes(request):
            return self.graph_nodes(
                kind=request.get("kind"), module=request.get("module"),
                match=request.get("match"), detail=bool(request.get("detail")),
            )

        def edges(request):
            return self.graph_edges(
                kind=request.get("kind"), src=request.get("src"), dst=request.get("dst"),
            )

        def drivers(request):
            return self.drivers(request.get("signal"), depth=request.get("depth"),
                                module=request.get("module"))

        def loads(request):
            return self.loads(request.get("signal"), depth=request.get("depth"),
                              module=request.get("module"))

        def paths(request):
            return self.paths(request.get("src"), request.get("dst"),
                              directed=bool(request.get("directed")))

        def dataflow(request):
            return self.dataflow(request.get("src"), request.get("dst"),
                                 max_paths=int(request.get("max_paths", 100)))

        def instances(request):
            return self.instances(path=request.get("path"),
                                  module=request.get("module"),
                                  depth=request.get("depth"))

        def scope(request):
            return self.scope(request.get("path"))

        def verify_claim(request):
            return self.verify_claim(request.get("claim"))

        def verify_consistency(request):
            return self.verify_consistency(
                checks=request.get("checks") or ("connection",),
                signal=request.get("signal"),
                max_nodes=int(request.get("max_nodes", 200)),
                full=bool(request.get("full")),
            )

        return {"graph_nodes": nodes, "graph_edges": edges,
                "drivers": drivers, "loads": loads,
                "paths": paths, "dataflow": dataflow,
                "instances": instances, "scope": scope,
                "verify_claim": verify_claim,
                "verify_consistency": verify_consistency}

    def __enter__(self) -> GraphSession:
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.tracer = None
