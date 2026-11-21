"""D7 — cache/snapshot atomic writes + explicit corrupt reads."""
from __future__ import annotations

import gzip

import pytest

from sv_query.trace.core.cache.ast_cache import ASTCache
from sv_query.trace.core.snapshot_manager import SnapshotManager


def test_cache_write_is_atomic_and_readable(tmp_path):
    cache = ASTCache(cache_dir=str(tmp_path))
    key = cache.compute_sources_hash({"a.sv": "module a; endmodule\n"})
    cache.put_by_key(key, {"answer": 42})

    assert list(tmp_path.rglob("*.tmp")) == []
    loaded = cache.get_by_key(key)
    assert loaded is not None
    assert loaded["data"]["answer"] == 42


def test_truncated_gzip_cache_is_explicitly_missed(tmp_path):
    cache = ASTCache(cache_dir=str(tmp_path))
    key = "truncated"
    path = tmp_path / f"{key}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write('{"version": "2.0", "sources_hash": "truncated", "data": {}}')
    # Cut the gzip stream so decompression raises EOFError.
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 2])

    assert cache.get_by_key(key) is None


def test_snapshot_write_is_atomic_and_corrupt_read_is_explicit(tmp_path):
    manager = SnapshotManager(base_dir=str(tmp_path))
    graph = {
        "version": "1.0", "nodes": [], "edges": [],
        "node_count": 0, "edge_count": 0,
    }
    manager.save("atomic", graph)
    assert list(tmp_path.rglob("*.tmp")) == []
    assert manager.load("atomic")["tag"] == "atomic"

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid snapshot"):
        manager.load("bad")


def test_graph_cache_key_uses_cache_version_constant():
    from sv_query.trace.core.cache.ast_cache import CACHE_VERSION
    from sv_query.trace.unified_tracer import UnifiedTracer

    tracer = UnifiedTracer(sources={"a.sv": "module a; endmodule\n"}, log_level="ERROR")
    key = tracer._graph_cache_key(None)
    assert key is not None
    identity = tracer._build_identity(None)
    assert identity.cache_schema == CACHE_VERSION
    assert identity.graph_semantics
    assert "-v17-" not in key
