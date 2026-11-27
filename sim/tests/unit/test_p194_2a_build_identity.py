"""P194.2a — BuildIdentity completeness and cache manifest behavior."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sv_query.trace.core.cache.build_identity import BuildIdentity  # noqa: E402

BASE = {
    "source_hash": "abc",
    "include_dirs": ("inc",),
    "preprocess_macros": True,
    "inject_timescale": True,
    "top_modules": ("top",),
    "target_module": "top",
    "bit_bridge": "one",
    "cache_schema": "3.5",
    "pyslang_version": "11",
    "sv_query_version": "0.3.3",
}


def _identity(**changes) -> BuildIdentity:
    return BuildIdentity(**{**BASE, **changes})


def test_key_changes_when_any_graph_input_changes():
    base = _identity()
    variants = [
        _identity(source_hash="other"),
        _identity(include_dirs=("other",)),
        _identity(preprocess_macros=False),
        _identity(inject_timescale=False),
        _identity(top_modules=("other",)),
        _identity(target_module="other"),
        _identity(bit_bridge="full"),
        _identity(cache_schema="4.0"),
        _identity(graph_semantics="4"),
        _identity(pyslang_version="12"),
        _identity(sv_query_version="0.3.8"),
    ]
    assert base.key() == _identity().key()  # stable for equal inputs
    assert all(base.key() != v.key() for v in variants)


def test_manifest_declares_graph_capability_only():
    manifest = _identity().manifest()
    assert manifest["capabilities"] == ["graph"]
    assert _identity().manifest({"graph", "mig"})["capabilities"] == ["graph", "mig"]
    assert manifest["graph_semantics"] == "3"
    assert manifest["cache_schema"] == "3.5"
    from sv_query.trace.core.cache.ast_cache import CACHE_VERSION
    assert CACHE_VERSION == "3.5"
    assert manifest["build_identity"]["preprocess_macros"] is True


def test_cache_entry_without_manifest_is_not_hydrated(tmp_path, monkeypatch):
    from sv_query.trace.core.cache import ast_cache as ac
    from sv_query.trace.unified_tracer import UnifiedTracer
    monkeypatch.setattr(ac, "_global_cache", ac.ASTCache(cache_dir=str(tmp_path)))
    fl = "sim/tests/fixtures/minimal_3module/filelist.f"
    tracer = UnifiedTracer(filelist=fl, log_level="ERROR")
    tracer.build_graph(use_cache=True)
    cache_files = list(tmp_path.glob("*.json.gz"))
    assert cache_files
    path = cache_files[0]
    data = json.load(gzip.open(path, "rt", encoding="utf-8"))
    data["data"].pop("manifest", None)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f)

    from sv_query.trace.core.cache import get_cache
    get_cache()._memory_cache.clear()
    fresh = UnifiedTracer(filelist=fl, log_level="ERROR")
    fresh.build_graph(use_cache=True)
    assert fresh._build_phase == "ready"  # rebuilt, not hydrated from partial entry


def test_graph_semantics_bump_invalidates_old_assignment_cache():
    old = _identity(graph_semantics="2")
    assert old.key() != _identity().key()
    assert _identity().manifest()["graph_semantics"] == "3"


def test_old_semantics_entry_cannot_hydrate_new_cache(tmp_path):
    from sv_query.trace.core.cache.ast_cache import ASTCache

    cache = ASTCache(cache_dir=str(tmp_path))
    old = _identity(graph_semantics="2")
    cache.put_by_key(old.key(), {"payload": "old"}, project_key="proj")
    assert cache.get_by_key(old.key()) is not None
    assert cache.get_by_key(_identity().key()) is None
