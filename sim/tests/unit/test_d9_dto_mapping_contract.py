"""D9 / P183.3 — DTO 映射单一性契约。

决策见 `docs/architecture/dto_mapping_audit_2026-11-17.md`：
**每个上下文保留一份 canonical projection，不强制合并成一个全局 DTO。**

本测试锁定三件事：
  A. snapshot 投影 = 全保真（TraceNode 全字段；TraceEdge 除声明不持久化的
     `effective_condition` / `condition_ast`）；
  B. CLI/core 投影字段集与 `sv_query.cli._registry.JSON_CONTRACT` 一致；
  C. 各上下文投影互不相等 —— 未来若把它们合并成单一 DTO，这里会红。

独立 oracle（不是手抄字段清单）:
  - `dataclasses.fields(TraceNode/TraceEdge)`；
  - `sv_query.cli._registry.JSON_CONTRACT`（`capabilities --json` 的同一来源）。
"""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from sv_query.cli._registry import JSON_CONTRACT  # noqa: E402
from sv_query.cli.core.semantic._common import node_dict  # noqa: E402
from sv_query.cli.core.semantic.trace_common import (  # noqa: E402
    _node_to_dict,
    edge_evidence_dict,
)
from sv_query.trace.core.graph.models import (  # noqa: E402
    EdgeKind,
    NodeKind,
    SignalGraph,
    TraceEdge,
    TraceNode,
)
from sv_query.trace.core.query.subgraph import build_subgraph  # noqa: E402

# 快照显式不持久化的字段：effective_condition 由 add_trace_edge 重算；
# condition_ast 是运行期 AST 对象（见 docs/dev/SNAPSHOT_SURFACE.md）。
SNAPSHOT_DECLARED_NOT_PERSISTED = frozenset({
    "effective_condition",
    "condition_ast",
})


def _graph() -> SignalGraph:
    graph = SignalGraph()
    graph.add_trace_node(TraceNode(
        id="top.a", name="a", module="top", kind=NodeKind.SIGNAL, width=(7, 0),
    ))
    graph.add_trace_node(TraceNode(
        id="top.b", name="b", module="top", kind=NodeKind.REG, width=(7, 0),
    ))
    graph.add_trace_edge(TraceEdge(
        src="top.a", dst="top.b", kind=EdgeKind.DRIVER,
        condition="en && a", expression="a",
    ))
    return graph


def test_snapshot_node_projection_is_full_fidelity():
    """snapshot 是唯一全保真投影：TraceNode 的每个 dataclass 字段都必须出现。"""
    payload = _graph().to_dict()["nodes"][0]
    assert set(payload) == {f.name for f in fields(TraceNode)}


def test_snapshot_edge_projection_is_full_fidelity_except_declared():
    """snapshot edge 字段集 = 全部字段 - 已声明的两个非持久化字段。"""
    graph = _graph()
    data = graph.to_dict()
    edge_payload = data["edges"][0]

    expected = {f.name for f in fields(TraceEdge)} - SNAPSHOT_DECLARED_NOT_PERSISTED
    assert set(edge_payload) == expected
    assert "effective_condition" not in edge_payload
    assert "condition_ast" not in edge_payload

    restored = SignalGraph.from_dict(data)
    live_edge = graph.get_edges("top.a", "top.b")[0]
    restored_edge = restored.get_edges("top.a", "top.b")[0]
    # effective_condition 走重算恢复，不是持久化字段
    assert restored_edge.effective_condition == live_edge.effective_condition
    # condition_ast 显式不保证：恢复后恒为 None（不是“有时有”的中间态）
    assert restored_edge.condition_ast is None


def test_context_projections_stay_distinct_and_match_contract():
    """每个上下文一份 canonical projection：字段集各自锁定，且互不合并。"""
    graph = _graph()
    node = graph.get_node("top.a")
    edge = graph.get_edges("top.a", "top.b")[0]

    minimal = node_dict(node)
    trace = _node_to_dict(node)
    evidence = edge_evidence_dict(edge)
    sub = build_subgraph(graph, ["top.a"], depth=1)
    sub_node = next(n for n in sub["nodes"] if n["id"] == "top.a")
    sub_edge = next(e for e in sub["edges"] if e["src"] == "top.a")

    # B. 每个投影的字段集以其公开契约（JSON_CONTRACT）为 oracle。
    assert set(minimal) == set(JSON_CONTRACT["class_instance"])
    assert set(trace) == set(JSON_CONTRACT["trace_node"])
    assert set(evidence) == set(JSON_CONTRACT["edge_evidence"])
    assert set(sub_node) == set(JSON_CONTRACT["subgraph_node"]) - {"file", "line"}
    assert set(sub_edge) == set(JSON_CONTRACT["subgraph_edge"]) - {"file", "line"}

    # C. snapshot 与 CLI/core 投影不是同一份 DTO（禁止强制全局合并）。
    snapshot_node_keys = set(graph.to_dict()["nodes"][0])
    snapshot_edge_keys = set(graph.to_dict()["edges"][0])
    assert set(trace) != snapshot_node_keys
    assert set(sub_node) != snapshot_node_keys
    assert set(evidence) != snapshot_edge_keys
    assert set(sub_edge) != snapshot_edge_keys
