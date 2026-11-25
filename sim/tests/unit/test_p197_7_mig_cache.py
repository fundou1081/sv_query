"""P197.7 — graph cache declares and restores MIG capability."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer

FL = "sim/tests/fixtures/minimal_3module/filelist.f"


def _cache(monkeypatch, tmp_path):
    from sv_query.trace.core.cache import ast_cache as ac
    cache = ac.ASTCache(cache_dir=str(tmp_path))
    monkeypatch.setattr(ac, "_global_cache", cache)
    return cache


def test_mig_build_hits_cache_and_restores_module_graph(tmp_path, monkeypatch):
    _cache(monkeypatch, tmp_path)
    first = UnifiedTracer(filelist=FL, log_level="ERROR")
    first.build_graph(use_cache=True, required_capabilities={"graph", "mig"})
    assert first.get_module_graph() is not None

    second = UnifiedTracer(filelist=FL, log_level="ERROR")
    second.build_graph(use_cache=True, required_capabilities={"graph", "mig"})
    assert second._cache_status == "hit"
    assert second.get_module_graph() is not None
    assert second.get_path_resolver() is not None
    assert "mig" in second.get_built_capabilities()


def test_manifest_mig_without_payload_is_not_hydrated(tmp_path, monkeypatch):
    _cache(monkeypatch, tmp_path)
    first = UnifiedTracer(filelist=FL, log_level="ERROR")
    first.build_graph(use_cache=True, required_capabilities={"graph", "mig"})
    files = list(tmp_path.rglob("*.json.gz"))
    assert files
    data = json.load(gzip.open(files[0], "rt", encoding="utf-8"))
    data["data"]["manifest"]["capabilities"] = ["graph", "mig"]
    data["data"].pop("module_graph_data", None)
    with gzip.open(files[0], "wt", encoding="utf-8") as f:
        json.dump(data, f)
    from sv_query.trace.core.cache import get_cache
    get_cache()._memory_cache.clear()

    fresh = UnifiedTracer(filelist=FL, log_level="ERROR")
    fresh.build_graph(use_cache=True, required_capabilities={"graph", "mig"})
    assert fresh._build_phase == "ready"
    assert fresh.get_module_graph() is not None
