"""[iter_287 / PLAN P3.2] 缓存按工程过期：单工程版本数 + 年龄。

背景: 原来只有全局总量 LRU（`SVQ_CACHE_MAX_MB`）。一个改得勤的大工程会产出
大量内容版本，把其它工程的缓存挤出总量上限；也没有"条目放太久就失效"的机制。

本文件锁定三条新行为:
  A. 工程身份只由**路径**决定（同路径不同内容 = 同一工程）
  B. 单工程最多保留 N 个版本（`SVQ_CACHE_MAX_ENTRIES_PER_PROJECT`），其它工程不受影响
  C. 超过 `SVQ_CACHE_MAX_AGE_DAYS` 的条目被淘汰；旧格式（无工程段）仍可读
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.cache.ast_cache import (  # noqa: E402
    CACHE_VERSION,
    DEFAULT_MAX_AGE_DAYS,
    ENV_CACHE_MAX_AGE_DAYS,
    ENV_CACHE_MAX_ENTRIES_PER_PROJECT,
    ENV_CACHE_MAX_MB,
    PROJECT_INFIX,
    ASTCache,
)


def _write(c: ASTCache, content_key: str, project: str | None, payload: dict | None = None) -> Path:
    body = {"version": "1.0", "sources_hash": content_key,
            "cached_at": "2026-10-25T00:00:00", "data": payload or {"graph_data": {"n": 1}}}
    path = c._cache_path(content_key, project)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(body, f)
    return path


def _age(path: Path, days: float) -> None:
    ts = time.time() - days * 86400
    os.utime(path, (ts, ts))


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_CACHE_MAX_MB, raising=False)
    monkeypatch.delenv(ENV_CACHE_MAX_ENTRIES_PER_PROJECT, raising=False)
    monkeypatch.delenv(ENV_CACHE_MAX_AGE_DAYS, raising=False)
    return ASTCache(cache_dir=str(tmp_path))


class TestProjectKey:
    def test_depends_only_on_paths(self, cache, tmp_path):
        f1 = tmp_path / "a.sv"
        f1.write_text("module a; endmodule")
        k1 = cache.compute_project_key(sources={str(f1): "old"})
        k2 = cache.compute_project_key(sources={str(f1): "new content"})
        assert k1 and k1 == k2, "工程身份不应随内容变化"

    def test_different_paths_differ(self, cache, tmp_path):
        f1, f2 = tmp_path / "a.sv", tmp_path / "b.sv"
        f1.write_text("module a; endmodule")
        f2.write_text("module b; endmodule")
        assert cache.compute_project_key(sources={str(f1): ""}) != cache.compute_project_key(
            sources={str(f2): ""})

    def test_filelist_key_stable_and_distinct(self, cache, tmp_path):
        for n in ("a", "b"):
            (tmp_path / f"{n}.sv").write_text(f"module {n}; endmodule")
        fa, fb = tmp_path / "pa.f", tmp_path / "pb.f"
        fa.write_text("a.sv\n")
        fb.write_text("b.sv\n")
        assert cache.compute_project_key(filelist=str(fa)) == cache.compute_project_key(filelist=str(fa))
        assert cache.compute_project_key(filelist=str(fa)) != cache.compute_project_key(filelist=str(fb))

    def test_missing_filelist_returns_none(self, cache, tmp_path):
        assert cache.compute_project_key(filelist=str(tmp_path / "nope.f")) is None
        assert cache.compute_project_key() is None


class TestProjectExpiry:
    def test_newest_n_per_project_kept(self, cache, monkeypatch):
        monkeypatch.setenv(ENV_CACHE_MAX_ENTRIES_PER_PROJECT, "2")
        paths = []
        for i in range(4):
            p = _write(cache, f"content{i}-v2-tall", "projA")
            _age(p, days=10 - i)  # content3 最新
            paths.append(p)
        other = _write(cache, "contentX-v2-tall", "projB")
        cache._enforce_size_limit()

        remaining = {p.name for p in cache.cache_dir.iterdir()}
        kept = [p.name for p in paths if p.name in remaining]
        assert len(kept) == 2, f"projA 应只保留 2 个版本，实际 {kept}"
        assert paths[3].name in remaining and paths[2].name in remaining
        assert other.name in remaining, "其它工程不应被连带淘汰"

    def test_zero_entries_means_unlimited(self, cache, monkeypatch):
        monkeypatch.setenv(ENV_CACHE_MAX_ENTRIES_PER_PROJECT, "0")
        for i in range(5):
            _write(cache, f"c{i}-v2-tall", "projA")
        cache._enforce_size_limit()
        assert len(list(cache.cache_dir.glob(f"*{PROJECT_INFIX}projA*"))) == 5

    def test_age_expiry(self, cache, monkeypatch):
        monkeypatch.setenv(ENV_CACHE_MAX_AGE_DAYS, "1")
        stale = _write(cache, "stale-v2-tall", "projA")
        fresh = _write(cache, "fresh-v2-tall", "projA")
        _age(stale, days=10)
        cache._enforce_size_limit()
        assert not stale.exists(), "超龄条目应被淘汰"
        assert fresh.exists(), "新鲜条目应保留"

    def test_zero_age_means_unlimited(self, cache, monkeypatch):
        monkeypatch.setenv(ENV_CACHE_MAX_AGE_DAYS, "0")
        stale = _write(cache, "stale-v2-tall", "projA")
        _age(stale, days=365)
        cache._enforce_size_limit()
        assert stale.exists()

    def test_global_size_limit_still_works(self, cache, monkeypatch):
        monkeypatch.setenv(ENV_CACHE_MAX_MB, "1")
        monkeypatch.setenv(ENV_CACHE_MAX_ENTRIES_PER_PROJECT, "0")
        # gzip 对重复字符几乎零成本 —— 用不可压缩内容才能触发总量上限
        import base64
        big = base64.b64encode(os.urandom(600 * 1024)).decode()
        p1 = _write(cache, "big1-v2-tall", "projA", {"graph_data": {"blob": big}})
        p2 = _write(cache, "big2-v2-tall", "projB", {"graph_data": {"blob": big}})
        _age(p1, days=5)
        cache._enforce_size_limit()
        assert not p1.exists(), "全局超限应按 mtime 淘汰最旧"
        assert p2.exists()


class TestBackwardCompatibility:
    def test_legacy_file_readable(self, cache):
        """旧格式（无工程段）仍可读 —— 升级后不强制重建全部缓存。"""
        legacy = cache._cache_path("oldkey-v2-tall")
        body = {"version": CACHE_VERSION, "sources_hash": "oldkey-v2-tall",
                "cached_at": "", "data": {"graph_data": {"n": 2}}}
        with gzip.open(legacy, "wt", encoding="utf-8") as f:
            json.dump(body, f)
        hit = ASTCache(cache_dir=str(cache.cache_dir)).get_by_key(
            "oldkey-v2-tall", project_key="deadbeef")
        assert hit is not None and hit["data"]["graph_data"]["n"] == 2

    def test_legacy_participates_in_age_expiry(self, cache, monkeypatch):
        monkeypatch.setenv(ENV_CACHE_MAX_AGE_DAYS, "1")
        legacy = cache._cache_path("oldkey-v2-tall")
        body = {"version": CACHE_VERSION, "sources_hash": "oldkey-v2-tall",
                "cached_at": "", "data": {}}
        with gzip.open(legacy, "wt", encoding="utf-8") as f:
            json.dump(body, f)
        _age(legacy, days=10)
        cache._enforce_size_limit()
        assert not legacy.exists()

    def test_invalidate_removes_all_project_variants(self, cache):
        a = _write(cache, "same-v2-tall", "projA")
        b = _write(cache, "same-v2-tall", "projB")
        cache.invalidate("same-v2-tall")
        assert not a.exists() and not b.exists()


def test_defaults_are_documented_values():
    assert DEFAULT_MAX_AGE_DAYS == 30
