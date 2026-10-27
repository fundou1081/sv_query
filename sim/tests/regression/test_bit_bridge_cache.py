"""[iter_302 / PLAN P13.1] 图缓存 key 必须包含 SVQ_BIT_BRIDGE 模式。

P0 回归：`one` 建图后切 `full` 会命中旧图（5 vs 37 节点）→ 查询静默错误。
修复：key 加 `-bb{one|full}`；旧 key 自然失效。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.cache import ast_cache as ac  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC = """
module sub(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
module top(input [7:0] a, output [7:0] y);
  sub u(.a(a), .y(y));
endmodule
"""


def _build(monkeypatch, tmp_path):
    monkeypatch.setattr(ac, "_global_cache", ac.ASTCache(cache_dir=str(tmp_path)))
    tracer = UnifiedTracer(sources={"t.sv": SRC}, log_level="ERROR")
    graph = tracer.build_graph(use_cache=True)
    return tracer, graph


class TestCacheModeKey:
    def test_key_differs_by_mode(self, monkeypatch):
        monkeypatch.delenv("SVQ_BIT_BRIDGE", raising=False)
        t = UnifiedTracer(sources={"t.sv": SRC}, log_level="ERROR")
        k_one = t._graph_cache_key(None)
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "one")
        k_one2 = t._graph_cache_key(None)
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        k_full = t._graph_cache_key(None)
        assert k_one.endswith("-bbone")
        assert k_one2 == k_one
        assert k_full.endswith("-bbfull")
        assert k_one != k_full

    def test_invalid_mode_normalizes_to_one(self, monkeypatch):
        t = UnifiedTracer(sources={"t.sv": SRC}, log_level="ERROR")
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "bogus")
        assert t._graph_cache_key(None).endswith("-bbone")


class TestModeSwitchEndToEnd:
    def test_switch_modes_rebuilds_correct_graph(self, monkeypatch, tmp_path):
        tmp_path.mkdir(exist_ok=True)
        monkeypatch.delenv("SVQ_BIT_BRIDGE", raising=False)
        _, g_one = _build(monkeypatch, tmp_path)
        n_one = len(g_one.nodes())

        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        _, g_full = _build(monkeypatch, tmp_path)
        n_full = len(g_full.nodes())
        assert n_full > n_one, (n_one, n_full)
        assert n_full >= 20, n_full

        monkeypatch.setenv("SVQ_BIT_BRIDGE", "one")
        _, g_one_again = _build(monkeypatch, tmp_path)
        assert len(g_one_again.nodes()) == n_one

    def test_same_mode_hits_cache(self, monkeypatch, tmp_path):
        tmp_path.mkdir(exist_ok=True)
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "one")
        _, g1 = _build(monkeypatch, tmp_path)
        stats1 = ac.get_cache().cache_stats()
        _, g2 = _build(monkeypatch, tmp_path)
        stats2 = ac.get_cache().cache_stats()
        assert len(g1.nodes()) == len(g2.nodes())
        # 同 key → 不新增条目
        assert stats2["total_entries"] == stats1["total_entries"] == 1

    def test_full_mode_separate_cache_entry(self, monkeypatch, tmp_path):
        tmp_path.mkdir(exist_ok=True)
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "one")
        _build(monkeypatch, tmp_path)
        monkeypatch.setenv("SVQ_BIT_BRIDGE", "full")
        _build(monkeypatch, tmp_path)
        assert ac.get_cache().cache_stats()["total_entries"] == 2
