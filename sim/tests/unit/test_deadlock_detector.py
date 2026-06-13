"""Test deadlock detector (B 2026-06-13)

Verifies:
- Combinational loop detection (valid in ready's driver chain)
- Cross-channel loop detection (A.ready driven by B.ready)
- response_after_request detection (D.valid not derived from A.valid)
- Severity / kind / channel fields correctly populated
"""
import pytest

from applications.bus.deadlock import (
    DeadlockFinding,
    detect_deadlock_candidates,
    _bfs_drivers,
    _bfs_path,
    _find_valid_ready_pairs,
)
from applications.bus.semantics import load_semantics
from trace.core.graph.models import SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_node(name: str, width=(0, 0), kind=NodeKind.SIGNAL, module="m") -> TraceNode:
    """快速构造一个 TraceNode, 用 (module.name) 作为 node id."""
    return TraceNode(
        id=f"{module}.{name}", name=name, module=module, kind=kind,
        width=width, is_clock=False, is_reset=False, is_enable=False,
    )


def _make_edge(src: str, dst: str, kind: EdgeKind = EdgeKind.DRIVER) -> TraceEdge:
    return TraceEdge(
        src=src, dst=dst, kind=kind, expression="", condition="",
    )


def _build_graph(edges: list[tuple[str, str]]) -> SignalGraph:
    """构造一个最小 SignalGraph, 含指定边。
    边格式: (src, dst) — 节点 id 必须以 'm.' 前缀 (module = 'm')
    """
    g = SignalGraph()
    # 收集所有节点
    nodes = set()
    for src, dst in edges:
        nodes.add(src)
        nodes.add(dst)
    for nid in nodes:
        # 拆分 module.name
        parts = nid.rsplit(".", 1)
        mod = parts[0] if len(parts) > 1 else "m"
        nm = parts[1] if len(parts) > 1 else nid
        kind = NodeKind.REG if nm == "valid_a" or "_valid" in nm else NodeKind.SIGNAL
        # 1-bit signals
        w = (0, 0)
        g.add_trace_node(_make_node(nm, w, kind, mod))
    for src, dst in edges:
        g.add_trace_edge(_make_edge(src, dst))
    return g


# ---------------------------------------------------------------------------
# BFS driver 路径测试
# ---------------------------------------------------------------------------

def test_bfs_drivers_direct():
    """ready ← valid 直接驱动"""
    g = _build_graph([("m.valid_a", "m.ready_a")])
    drivers = _bfs_drivers(g, "m.ready_a", max_depth=3)
    assert "m.valid_a" in drivers


def test_bfs_drivers_chain():
    """ready ← x ← valid (2 跳)"""
    g = _build_graph([("m.valid_a", "m.x"), ("m.x", "m.ready_a")])
    drivers = _bfs_drivers(g, "m.ready_a", max_depth=5)
    assert "m.valid_a" in drivers
    assert "m.x" in drivers


def test_bfs_drivers_max_depth():
    """深度限制: 3 跳以上不搜"""
    g = _build_graph([
        ("m.v0", "m.v1"),
        ("m.v1", "m.v2"),
        ("m.v2", "m.v3"),
        ("m.v3", "m.r"),
    ])
    # max_depth=2: 找不到 v0 (要 4 跳)
    drivers = _bfs_drivers(g, "m.r", max_depth=2)
    assert "m.v0" not in drivers
    # max_depth=10: 找到
    drivers_deep = _bfs_drivers(g, "m.r", max_depth=10)
    assert "m.v0" in drivers_deep


def test_bfs_path_returns_path():
    g = _build_graph([("m.valid_a", "m.x"), ("m.x", "m.ready_a")])
    path = _bfs_path(g, "m.ready_a", "m.valid_a", max_depth=5)
    assert path[0] == "m.ready_a"
    assert path[-1] == "m.valid_a"
    assert "m.x" in path


# ---------------------------------------------------------------------------
# Combinational loop detection
# ---------------------------------------------------------------------------

def test_detect_combinational_loop_basic():
    """valid_a ← ready_a (直接组合环)"""
    sem = load_semantics("TL-UL")
    g = _build_graph([("m.a_valid", "m.a_ready")])
    findings = detect_deadlock_candidates(sem, g)
    # 应该至少 1 个 finding (TL-UL-A-VALID-INDEP-OF-READY)
    loop_findings = [f for f in findings if f.kind == "no_combinational_loop"]
    assert len(loop_findings) >= 1
    f = loop_findings[0]
    assert f.severity == "error"
    assert "a_valid" in f.description
    assert "a_ready" in f.description


def test_detect_no_finding_when_independent():
    """valid_a 与 ready_a 独立 (无环) → 无 finding"""
    sem = load_semantics("TL-UL")
    # 没有任何边, valid 和 ready 是孤立节点
    g = _build_graph([])
    g.add_trace_node(_make_node("a_valid", (0, 0), NodeKind.REG, "m"))
    g.add_trace_node(_make_node("a_ready", (0, 0), NodeKind.SIGNAL, "m"))
    findings = detect_deadlock_candidates(sem, g)
    loop_findings = [f for f in findings if f.kind == "no_combinational_loop"]
    assert len(loop_findings) == 0


def test_detect_combinational_loop_chain():
    """valid_a ← x ← ready_a (2 跳链)"""
    sem = load_semantics("TL-UL")
    g = _build_graph([
        ("m.a_valid", "m.x"),
        ("m.x", "m.a_ready"),
    ])
    findings = detect_deadlock_candidates(sem, g)
    loop_findings = [f for f in findings if f.kind == "no_combinational_loop"]
    assert len(loop_findings) >= 1


# ---------------------------------------------------------------------------
# Cross-channel loop detection
# ---------------------------------------------------------------------------

def test_detect_cross_channel_loop():
    """a_ready ← d_ready (跨通道) → 候选"""
    sem = load_semantics("TL-UL")
    g = _build_graph([("m.d_ready", "m.a_ready")])
    # 加上 valid 信号 (protocol 规则需要 valid+ready 配对才能查)
    g.add_trace_node(_make_node("a_valid", (0, 0), NodeKind.REG, "m"))
    g.add_trace_node(_make_node("d_valid", (0, 0), NodeKind.REG, "m"))
    findings = detect_deadlock_candidates(sem, g)
    cross_findings = [f for f in findings if f.kind == "no_cross_channel_loop"]
    assert len(cross_findings) >= 1
    f = cross_findings[0]
    assert "A" in f.channels or "D" in f.channels


def test_detect_no_cross_channel_loop_when_independent():
    """a_ready 独立, d_ready 独立 → 无 finding"""
    sem = load_semantics("TL-UL")
    g = _build_graph([])
    g.add_trace_node(_make_node("a_ready", (0, 0), NodeKind.SIGNAL, "m"))
    g.add_trace_node(_make_node("d_ready", (0, 0), NodeKind.SIGNAL, "m"))
    findings = detect_deadlock_candidates(sem, g)
    cross_findings = [f for f in findings if f.kind == "no_cross_channel_loop"]
    assert len(cross_findings) == 0


# ---------------------------------------------------------------------------
# Response after request
# ---------------------------------------------------------------------------

def test_response_after_request_violated():
    """D.valid 不来自 A.valid (孤儿) → 候选"""
    sem = load_semantics("TL-UL")
    # d_valid 完全独立 (没有 a_valid 在 driver 链中)
    g = _build_graph([])
    g.add_trace_node(_make_node("a_valid", (0, 0), NodeKind.REG, "m"))
    g.add_trace_node(_make_node("d_valid", (0, 0), NodeKind.REG, "m"))
    g.add_trace_node(_make_node("a_ready", (0, 0), NodeKind.SIGNAL, "m"))
    g.add_trace_node(_make_node("d_ready", (0, 0), NodeKind.SIGNAL, "m"))
    findings = detect_deadlock_candidates(sem, g)
    resp_findings = [f for f in findings if f.kind == "response_after_request"]
    assert len(resp_findings) >= 1


def test_response_after_request_satisfied():
    """D.valid ← A.valid → 满足依赖, 无 finding"""
    sem = load_semantics("TL-UL")
    g = _build_graph([("m.a_valid", "m.d_valid")])
    findings = detect_deadlock_candidates(sem, g)
    resp_findings = [f for f in findings if f.kind == "response_after_request"]
    # D.valid 的 driver 链包含 a_valid → 不应报
    assert len(resp_findings) == 0


# ---------------------------------------------------------------------------
# Finding 字段
# ---------------------------------------------------------------------------

def test_finding_fields_populated():
    sem = load_semantics("TL-UL")
    g = _build_graph([("m.a_valid", "m.a_ready")])
    findings = detect_deadlock_candidates(sem, g)
    assert len(findings) > 0
    f = findings[0]
    assert isinstance(f, DeadlockFinding)
    assert f.rule_id
    assert f.severity in ("error", "warning", "info")
    assert f.kind
    assert f.node_ids
    assert f.description
    assert f.evidence  # 至少有 path 字符串


# ---------------------------------------------------------------------------
# 自动 valid/ready 配对
# ---------------------------------------------------------------------------

def test_auto_find_valid_ready_pairs():
    """_find_valid_ready_pairs 应该自动配对 a_valid ↔ a_ready"""
    g = _build_graph([])
    g.add_trace_node(_make_node("a_valid", (0, 0), NodeKind.REG, "m"))
    g.add_trace_node(_make_node("a_ready", (0, 0), NodeKind.SIGNAL, "m"))
    g.add_trace_node(_make_node("d_valid", (0, 0), NodeKind.REG, "m"))
    g.add_trace_node(_make_node("d_ready", (0, 0), NodeKind.SIGNAL, "m"))
    pairs = _find_valid_ready_pairs(g)
    assert len(pairs) >= 2
    # 至少有 1 对配对了
    valid_ids = {p.valid for p in pairs}
    ready_ids = {p.ready for p in pairs}
    assert "m.a_valid" in valid_ids
    assert "m.a_ready" in ready_ids
