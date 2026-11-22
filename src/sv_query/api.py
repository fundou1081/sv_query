"""Stable Python query facade (P194.3).

Two layers are intentionally separate:

- ``Session``: transport-agnostic request/response contract (no graph).
- ``QueryClient``: owns one GraphSession and exposes its handlers through
  ``Session.execute`` for a stable Python entry point.

``GraphSession`` remains the low-level, graph-owning API; ``trace.*`` modules are
internal implementation details.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .graph_session import GraphSession
from .session import Session

API_FACADE_VERSION = "1"


class QueryClient:
    """Stable Python facade: one graph, request/response queries."""

    def __init__(
        self,
        *,
        file: str | Path | None = None,
        filelist: str | None = None,
        from_snapshot: str | None = None,
        use_cache: bool = True,
        refresh_each_request: bool = True,
    ) -> None:
        self._graph_session = GraphSession(
            file=file, filelist=filelist, from_snapshot=from_snapshot,
            use_cache=use_cache,
        )
        self._session = Session(handlers=self._graph_session.handlers())
        self._refresh_each_request = refresh_each_request
        self._closed = False

    @property
    def graph_session(self) -> GraphSession:
        if self._closed:
            raise RuntimeError("QueryClient is closed")
        return self._graph_session

    def execute(self, request: Mapping[str, object]) -> dict[str, object]:
        """Execute one Session request against the owned graph."""
        if self._closed:
            raise RuntimeError("QueryClient is closed")
        if self._refresh_each_request:
            self._graph_session.refresh()
        return self._session.execute(request)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._graph_session.close()

    def __enter__(self) -> "QueryClient":
        if self._closed:
            raise RuntimeError("QueryClient is closed")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def open_query(**kwargs) -> QueryClient:
    """Open a local QueryClient; use as a context manager."""
    return QueryClient(**kwargs)
