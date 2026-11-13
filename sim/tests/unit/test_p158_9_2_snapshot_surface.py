"""test_p158_9_2_snapshot_surface.py — [P158.9.2] snapshot 往返保真契约

背景（arch_eval P0.2 / SEMANTIC_CONTRACTS §3 验收）:
  SignalGraph.to_dict 曾不序列化 edge 的 condition_chain / source /
  function_return / is_function_call / extra, node 的 extra。
  实测损失面（2026-11-11, minimal_3module 31 nodes / 72 edges）:
    - condition_chain 32/32 非空全丢 → dataflow 条件提取在 snapshot
      路径上与 live 分叉（dataflow.py:238 回退消费 condition_chain）;
    - source 11/11 非空全丢 → DriverInfo 派生 property 失源;
    - node.extra 16 条丢（direction / width 键）。

本文件锁定验收标准"不许中间态"——每个缺失字段要么补齐、要么显式
声明不保证，不允许静默半丢:

  A. edge 全字段往返保真, 唯一例外 condition_ast（运行期 AST,
     显式声明不保证 — 锁定为 None, 防止有人以为它被持久化）;
  B. node 全字段 + JSON-safe extra 往返保真;
  C. effective_condition 由 add_trace_edge 重算恢复（非序列化路径）;
  D. 旧格式快照（无新键）向后兼容, 默认值不炸;
  E. CLI 端到端: snapshot save → dataflow analyze --from-snapshot
     与 live --filelist 的条件语义一致（true-positive, 反分叉）。

独立 oracle:
  - 字段集来自 dataclasses.fields(TraceEdge/TraceNode), 不是手抄清单;
  - CLI 对比双跑 live/snapshot, 输出互为 oracle。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, fields
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from sv_query.trace.unified_tracer import UnifiedTracer  # noqa: E402
from sv_query.trace.core.graph.models import SignalGraph, TraceEdge, TraceNode  # noqa: E402

MINIMAL_FILELIST = str(PROJECT_ROOT / "sim/tests/fixtures/minimal_3module/filelist.f")
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")

# P158.9.2 显式声明不保证的运行期字段（快照路径上恒为默认值）
DECLARED_NOT_PERSISTED = frozenset({"condition_ast"})
# 快照增量键（from_dict 旧格式兼容测试用）
NEW_EDGE_KEYS = ("condition_chain", "function_return", "is_function_call", "source", "extra")


@pytest.fixture(scope="module")
def live_graph() -> SignalGraph:
    tracer = UnifiedTracer(filelist=MINIMAL_FILELIST, log_level="ERROR")
    tracer.build_graph()
    return tracer.get_graph()


@pytest.fixture(scope="module")
def roundtripped(live_graph) -> SignalGraph:
    return SignalGraph.from_dict(live_graph.to_dict())


def _all_edges(graph: SignalGraph) -> list[TraceEdge]:
    return [e for (s, d) in graph.edges() for e in graph._edge_data.get((s, d), [])]


# ---------------------------------------------------------------------------
# A. edge 全字段往返保真（condition_ast 是唯一声明例外）
# ---------------------------------------------------------------------------
class TestEdgeRoundTrip:
    def test_node_and_edge_counts_preserved(self, live_graph, roundtripped):
        assert roundtripped.number_of_nodes() == live_graph.number_of_nodes()
        assert len(_all_edges(roundtripped)) == len(_all_edges(live_graph))

    def test_all_edge_fields_fully_roundtripped(self, live_graph, roundtripped):
        """除 condition_ast 外, 任意边字段往返后必须相等 — 不许中间态。"""
        src_edges, dst_edges = _all_edges(live_graph), _all_edges(roundtripped)
        mismatches: dict[str, int] = {}
        for e1, e2 in zip(src_edges, dst_edges):
            for f in fields(e1):
                if f.name in DECLARED_NOT_PERSISTED:
                    continue  # 单独由下方测试锁定语义
                v1, v2 = getattr(e1, f.name), getattr(e2, f.name)
                if f.name == "source":
                    bad = (v1 is None) != (v2 is None) or (v1 is not None and v1 != v2)
                else:
                    bad = v1 != v2
                if bad:
                    mismatches[f.name] = mismatches.get(f.name, 0) + 1
        assert mismatches == {}, f"快照往返丢字段: {mismatches}"

    def test_condition_ast_is_declared_none_not_half_state(self, live_graph, roundtripped):
        """condition_ast = 运行期 AST, 显式不持久化: 恢复后恒为 None,
        不允许出现'有些边有 AST 有些没有'的中间态错觉。"""
        src_has_ast = sum(1 for e in _all_edges(live_graph) if e.condition_ast is not None)
        restored = [e.condition_ast for e in _all_edges(roundtripped)]
        assert all(v is None for v in restored)
        # fixture 必须真的产生过 AST, 否则本测试在测空气
        assert src_has_ast > 0, "fixture 未覆盖 condition_ast 非空场景"

    def test_condition_chain_true_positive(self, live_graph, roundtripped):
        """minimal_3module 至少 30 条边带 condition_chain (dataflow 回退消费)。"""
        src_chains = [e for e in _all_edges(live_graph) if e.condition_chain]
        assert len(src_chains) >= 30, f"fixture 覆盖不足: {len(src_chains)}"
        for e in _all_edges(roundtripped):
            assert list(e.condition_chain) == list(
                _all_edges(live_graph)[_all_edges(roundtripped).index(e)].condition_chain
            ) if e.condition_chain else True

    def test_source_bit_slice_derived_property_survives(self, live_graph, roundtripped):
        """source 往返后派生 property (bit_slice) 必须可用且一致。"""
        src_with_source = [e for e in _all_edges(live_graph) if e.source is not None]
        assert src_with_source, "fixture 无 source 边, 测试在测空气"
        pairs = zip(_all_edges(live_graph), _all_edges(roundtripped))
        n_checked = 0
        for e1, e2 in pairs:
            if e1.source is None:
                assert e2.source is None
                continue
            assert e2.source is not None
            assert e1.source.bit_slice == e2.source.bit_slice
            assert e1.source.full_expression == e2.source.full_expression
            n_checked += 1
        assert n_checked == len(src_with_source)


# ---------------------------------------------------------------------------
# B. node 全字段 + JSON-safe extra 往返保真
# ---------------------------------------------------------------------------
class TestNodeRoundTrip:
    def test_all_node_fields_fully_roundtripped(self, live_graph, roundtripped):
        for nid in live_graph.nodes():
            n1, n2 = live_graph.get_node(nid), roundtripped.get_node(nid)
            assert n2 is not None, f"节点丢失: {nid}"
            for f in fields(n1):
                assert getattr(n1, f.name) == getattr(n2, f.name), f"{nid}.{f.name}"

    def test_node_extra_direction_width_preserved(self, live_graph, roundtripped):
        """port direction / width 存在 node.extra, 快照不得丢。"""
        directions = {
            nid: live_graph.get_node(nid).extra.get("direction")
            for nid in live_graph.nodes()
            if live_graph.get_node(nid).extra.get("direction")
        }
        assert directions, "fixture 无 extra.direction, 测试在测空气"
        for nid, d in directions.items():
            assert roundtripped.get_node(nid).extra.get("direction") == d


# ---------------------------------------------------------------------------
# C. effective_condition 重算路径（非序列化）
# ---------------------------------------------------------------------------
def test_effective_condition_recomputed_on_restore(live_graph, roundtripped):
    ok = sum(
        1 for e1, e2 in zip(_all_edges(live_graph), _all_edges(roundtripped))
        if e1.effective_condition == e2.effective_condition
    )
    assert ok == len(_all_edges(live_graph))


# ---------------------------------------------------------------------------
# D. 旧格式快照向后兼容（新键缺失 → 默认值, 不炸）
# ---------------------------------------------------------------------------
def test_old_format_snapshot_still_loads(live_graph):
    data = live_graph.to_dict()
    for e in data["edges"]:
        for k in NEW_EDGE_KEYS:
            e.pop(k, None)
    for n in data["nodes"]:
        n.pop("extra", None)
    g_old = SignalGraph.from_dict(data)
    assert g_old.number_of_nodes() == live_graph.number_of_nodes()
    # 默认值语义: 旧快照的 condition_chain 为空列表, function 标记 False
    for e in _all_edges(g_old):
        assert e.condition_chain == []
        assert e.function_return is False
        assert e.is_function_call is False


# ---------------------------------------------------------------------------
# E. CLI 端到端: live vs snapshot 的 dataflow 条件一致（反分叉）
# ---------------------------------------------------------------------------
class TestCliSnapshotParity:
    @pytest.fixture(scope="class")
    def snapshot_tag(self, tmp_path_factory):
        tag = "p158_9_2_test"
        snap_dir = tmp_path_factory.mktemp("svq_snaps")
        env = dict(os.environ, SVQ_SNAPSHOT_DIR=str(snap_dir), PYTHONPATH=SRC)
        r = subprocess.run(
            [sys.executable, RUN_CLI, "snapshot", "save", MINIMAL_FILELIST,
             "--filelist", MINIMAL_FILELIST, "--tag", tag, "--json"],
            capture_output=True, text=True, timeout=120, env=env, cwd=str(PROJECT_ROOT),
        )
        assert r.returncode == 0, f"snapshot save 失败: {r.stderr[-400:]}"
        return tag, env

    def _dataflow(self, args: list[str], env: dict) -> dict:
        r = subprocess.run(
            [sys.executable, RUN_CLI, "dataflow", "analyze"] + args + ["--json"],
            capture_output=True, text=True, timeout=120, env=env, cwd=str(PROJECT_ROOT),
        )
        assert r.returncode == 0, f"dataflow 失败: {r.stderr[-400:]}"
        # stdout 为单个 JSON 对象 (日志走 stderr); 从首个 { 起解析, 容忍前导行
        return json.loads(r.stdout[r.stdout.find("{"):])

    def test_dataflow_conditions_parity_live_vs_snapshot(self, snapshot_tag):
        tag, env = snapshot_tag
        live = self._dataflow(
            ["top_minimal.valid_i", "top_minimal.ready_o", "--filelist", MINIMAL_FILELIST], dict(os.environ))
        snap = self._dataflow(
            ["top_minimal.valid_i", "top_minimal.ready_o", "--from-snapshot", tag], env)
        lr, sr = live["result"], snap["result"]
        # 核心断言: 路径与条件语义不得因 snapshot 丢失 condition_chain 而分叉
        assert sr["is_reachable"] == lr["is_reachable"]
        assert sr["paths_count"] == lr["paths_count"]
        assert sr.get("all_conditions") == lr.get("all_conditions"), (
            "snapshot 与 live 的条件语义分叉 — condition_chain 丢失回归"
        )
