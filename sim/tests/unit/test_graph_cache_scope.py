"""test_graph_cache_scope.py — [iter_270] 图缓存: scope 隔离 + 真正命中

背景（iter_270 实测）:
  ① `ASTCache.put_by_key` 把 payload 包在 `"data"` 里, 而 `unified_tracer` 直接查
     `"graph_data"` → 图缓存**从未命中过**（静默 miss, 无任何 warning）
  ② 缓存 key 只含 sources hash, 不含图模式 → 模块级/实例级共用 key,
     先建哪个就命中哪个（静默返回错误图）
  ③ filelist 模式 `_sources` 为空 → 完全跳过缓存（真实工程永远不命中）

本文件锁定修复后的三条:
  A. 缓存 key 随 instance_scope / target_module 变化
  B. 写入后能用**新 tracer** 命中（且不重新跑管线）
  C. filelist 模式也能算出 key（内容 hash）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC_SV = PROJECT_ROOT / "sim/tests/fixtures/golden_mini/inst_demo.sv"
FILELIST = PROJECT_ROOT / "sim/tests/fixtures/minimal_3module/filelist.f"


class TestCacheKey:
    def test_scope_and_target_change_key(self):
        t = UnifiedTracer(sources={"inst_demo.sv": SRC_SV.read_text()}, log_level="ERROR")
        k_mod = t._graph_cache_key(False, None)
        k_inst = t._graph_cache_key(True, None)
        k_target = t._graph_cache_key(False, "inst_demo")
        assert k_mod and k_inst and k_target
        assert len({k_mod, k_inst, k_target}) == 3, "scope/target 必须影响 key"

    def test_filelist_mode_has_key(self):
        """C: filelist 模式以前 key 为 None（缓存被跳过）。"""
        t = UnifiedTracer(filelist=str(FILELIST), log_level="ERROR")
        assert not t._sources, "该模式应没有 sources"
        key = t._graph_cache_key(True, None)
        assert key and key.endswith("-s1-tall")


class TestCacheHit:
    def test_second_build_uses_cache(self, tmp_path, monkeypatch):
        """B: 第二次构建必须命中缓存, 不重跑 GraphBuilder。"""
        monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path))
        src = {"inst_demo.sv": SRC_SV.read_text()}

        t1 = UnifiedTracer(sources=src, log_level="ERROR")
        g1 = t1.build_graph(use_cache=True, instance_scope=True)

        # 第二次: 如果缓存命中, GraphBuilder.build 不应被调用
        from trace.core.graph_builder import GraphBuilder

        calls = {"n": 0}
        orig = GraphBuilder.build

        def _boom(self):  # noqa: ANN001 — 只有命中缓存才不会走到这里
            calls["n"] += 1
            return orig(self)

        monkeypatch.setattr(GraphBuilder, "build", _boom)

        t2 = UnifiedTracer(sources=src, log_level="ERROR")
        g2 = t2.build_graph(use_cache=True, instance_scope=True)

        assert calls["n"] == 0, "缓存未命中: 管线被重新执行"
        assert set(g1.nodes()) == set(g2.nodes())

    def test_scope_isolation_no_cross_hit(self, tmp_path, monkeypatch):
        """A/B: 先建模块级, 再请求实例级 —— 不能拿到模块级的图。"""
        monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path))
        src = {"inst_demo.sv": SRC_SV.read_text()}

        t1 = UnifiedTracer(sources=src, log_level="ERROR")
        t1.build_graph(use_cache=True, instance_scope=False)

        t2 = UnifiedTracer(sources=src, log_level="ERROR")
        g2 = t2.build_graph(use_cache=True, instance_scope=True)

        prefixes = {n.split(".")[0] for n in g2.nodes()}
        assert "sub_adder" not in prefixes, f"命中了模块级缓存: {sorted(prefixes)}"
