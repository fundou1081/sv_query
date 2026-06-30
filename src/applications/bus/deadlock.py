"""
applications.bus.deadlock - 静态死锁候选检测

[2026-06-13] Phase C: 协议语义 → 死锁候选分析

设计要点
========

1. **输入**: ProtocolSemantics (来自 YAML) + SignalGraph (来自 graph builder)
2. **输出**: DeadlockFinding 列表, 每个 finding 有:
   - 规则 ID (跟 protocol semantics 的 deadlock_rules 对应)
   - 严重程度 (error/warning/info)
   - 涉及节点 ID 列表
   - 描述
3. **检测类型**:
   - combinational loop: 通道内部 valid ↔ ready 组合环
   - cross-channel loop: 跨通道 ready 链形成环 (SCC)
   - response_after_request: 响应通道没有在请求通道的 driver 链中

算法
====

1. 从 handshake scan 结果拿所有 (valid, ready) 对 + type
2. 对每个协议规则:
   a. **combinational loop**: 检查 ready 的 driver 链是否包含 valid
   b. **cross-channel loop**: 构造 channel dependency graph, 找 SCC
3. 返回 finding 列表

限制
====

- 静态分析只能找"潜在"死锁, 仿真才能确认
- 不能识别"条件永远 false" (需要 model check)
- 不处理时序环 (multi-cycle 死锁)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .semantics import ProtocolSemantics, ChannelRule
from trace.core.handshake_detector import HandshakeInfo
from trace.core.graph.models import SignalGraph, EdgeKind


@dataclass
class DeadlockFinding:
    """[B1 2026-06-13] 单个死锁候选。

    Attributes:
        rule_id: 对应 ProtocolSemantics.deadlock_rules[].id
        severity: 严重程度 (error/warning/info)
        kind: 规则类型 (no_combinational_loop / no_cross_channel_loop / ...)
        channels: 涉及的协议通道 (e.g. ["A", "D"])
        node_ids: 涉及的信号节点 ID 列表
        description: 人类可读说明
        evidence: 静态证据 (e.g. driver 链)
    """
    rule_id: str
    severity: str
    kind: str
    channels: list[str]
    node_ids: list[str]
    description: str
    evidence: str = ""

    def __repr__(self) -> str:
        nodes_short = ", ".join(self.node_ids[:3])
        if len(self.node_ids) > 3:
            nodes_short += f", ... (+{len(self.node_ids)-3})"
        return (
            f"DeadlockFinding({self.severity} {self.rule_id} "
            f"on [{','.join(self.channels)}] nodes=[{nodes_short}])"
        )


def detect_deadlock_candidates(
    semantics: ProtocolSemantics,
    graph: SignalGraph,
    handshake_pairs: list[HandshakeInfo] | None = None,
) -> list[DeadlockFinding]:
    """[B1] 主入口: 从 graph + semantics 找死锁候选。

    Args:
        semantics: 协议语义定义
        graph: SignalGraph 实例
        handshake_pairs: 可选, 来自 handshake scan 的 (valid, ready) 对列表
                          (None 时自动从 graph 提取)

    Returns:
        List of DeadlockFinding
    """
    findings: list[DeadlockFinding] = []

    # 1. 自动提取 handshake pairs (从 graph 找 valid/ready 命名约定)
    if handshake_pairs is None:
        handshake_pairs = _find_valid_ready_pairs(graph)

    # 2. 按规则类型分发
    for rule in semantics.deadlock_rules:
        if rule.kind == "no_combinational_loop":
            new_findings = _check_combinational_loop(rule, graph, handshake_pairs)
            findings.extend(new_findings)
        elif rule.kind == "no_cross_channel_loop":
            new_findings = _check_cross_channel_loop(rule, semantics, graph, handshake_pairs)
            findings.extend(new_findings)
        elif rule.kind == "response_after_request":
            new_findings = _check_response_after_request(rule, semantics, graph, handshake_pairs)
            findings.extend(new_findings)
        # 其他 kind 暂不实现, 留作扩展点

    return findings


# ---------------------------------------------------------------------------
# Handshake pair 提取
# ---------------------------------------------------------------------------

# 信号名模式: valid 跟 ready 配对
_VALID_SUFFIXES = ("_valid", "valid", "_vld", "vld")
_READY_SUFFIXES = ("_ready", "ready", "_rdy", "rdy")


def _find_valid_ready_pairs(graph: SignalGraph) -> list[HandshakeInfo]:
    """[B1] 从 graph 找所有 (valid, ready) 对。

    启发式:
      1. 找 1-bit PORT_IN/REG/SIGNAL 节点
      2. 名字以 _valid 结尾 (canonical) → 找对应 _ready
      3. 同一 module 下, 名字差一个 suffix
    """
    pairs: list[HandshakeInfo] = []
    # 收集 1-bit 节点
    one_bit_nodes = []
    for nid in graph.nodes():
        node = graph.get_node(nid)
        if node is None:
            continue
        # [Bug-fix 2026-06-13] width 可能是 3-tuple (1, 0, 0) — 防御
        try:
            w_tuple = tuple(node.width)
            w_msb = w_tuple[0] if len(w_tuple) > 0 else 0
            w_lsb = w_tuple[1] if len(w_tuple) > 1 else 0
        except (TypeError, ValueError, IndexError):
            w_msb, w_lsb = 0, 0
        w = abs(w_msb - w_lsb) + 1 if w_msb >= w_lsb else 1
        if w == 1 and node.name:
            one_bit_nodes.append((nid, node))
    # 配对
    valid_set = {(nid, node.name) for nid, node in one_bit_nodes
                 if any(node.name.lower().endswith(s) for s in _VALID_SUFFIXES)}
    ready_set = {(nid, node.name) for nid, node in one_bit_nodes
                 if any(node.name.lower().endswith(s) for s in _READY_SUFFIXES)}
    for v_nid, v_name in valid_set:
        # 找同 module 下的 ready
        v_module = v_nid.rsplit(".", 1)[0] if "." in v_nid else ""
        v_base = v_name
        for s in sorted(_VALID_SUFFIXES, key=len, reverse=True):
            if v_name.lower().endswith(s):
                v_base = v_name[:-len(s)] if v_name.lower().endswith(s) else v_name
                break
        for r_nid, r_name in ready_set:
            r_module = r_nid.rsplit(".", 1)[0] if "." in r_nid else ""
            if v_module and r_module and v_module != r_module:
                continue
            for s in sorted(_READY_SUFFIXES, key=len, reverse=True):
                if r_name.lower().endswith(s):
                    r_base = r_name[:-len(s)] if r_name.lower().endswith(s) else r_name
                    if r_base.lower() == v_base.lower():
                        pairs.append(HandshakeInfo(
                            valid=v_nid,
                            ready=r_nid,
                            handshake_type="UNKNOWN",
                            channel="UNKNOWN",
                            condition="",
                            effective_condition="",
                            assign_type="",
                            clock_domain="",
                            extra={},
                        ))
                    break
    return pairs


# ---------------------------------------------------------------------------
# Rule 1: combinational loop
# ---------------------------------------------------------------------------

def _check_combinational_loop(
    rule,
    graph: SignalGraph,
    handshake_pairs: list[HandshakeInfo],
) -> list[DeadlockFinding]:
    """[B1] 检查 valid ↔ ready 组合环。

    算法: 对每对 (valid, ready):
      1. 从 graph 找 ready 的 driver 节点 (BFS, depth ≤ 5)
      2. 看 valid 是否在 ready 的 driver 链中
      3. 如果是 → combinational loop 候选
    """
    findings: list[DeadlockFinding] = []
    for pair in handshake_pairs:
        # 找 ready 的 driver 链
        ready_id = pair.ready
        drivers = _bfs_drivers(graph, ready_id, max_depth=5)
        if pair.valid in drivers:
            # valid 在 ready 的 driver 链中 → 候选循环
            path = _bfs_path(graph, ready_id, pair.valid, max_depth=5)
            findings.append(DeadlockFinding(
                rule_id=rule.id,
                severity=rule.severity,
                kind=rule.kind,
                channels=rule.channels,
                node_ids=[pair.valid, pair.ready] + path[1:-1],
                description=(
                    f"{pair.valid} is in the driver chain of "
                    f"{pair.ready} (depth ≤ 5) — potential combinational loop."
                ),
                evidence=" → ".join(path[:5]) + ("..." if len(path) > 5 else ""),
            ))
    return findings


def _bfs_drivers(graph: SignalGraph, start: str, max_depth: int = 5) -> set[str]:
    """[B1] BFS 找 start 节点的所有上游 driver (深度限制)."""
    if start not in graph.nodes():
        return set()
    visited: set[str] = set()
    queue = [(start, 0)]
    while queue:
        nid, depth = queue.pop(0)
        if depth > max_depth or nid in visited:
            continue
        visited.add(nid)
        for pred in graph.predecessors(nid):
            queue.append((pred, depth + 1))
    visited.discard(start)
    return visited


def _bfs_path(graph: SignalGraph, start: str, target: str, max_depth: int = 5) -> list[str]:
    """[B1] BFS 找 start → target 的一条路径 (限深)."""
    if start == target:
        return [start]
    if start not in graph.nodes() or target not in graph.nodes():
        return []
    visited: set[str] = {start}
    queue = [(start, [start])]
    while queue:
        nid, path = queue.pop(0)
        if len(path) > max_depth:
            continue
        for pred in graph.predecessors(nid):
            if pred in visited:
                continue
            visited.add(pred)
            new_path = path + [pred]
            if pred == target:
                return new_path
            queue.append((pred, new_path))
    return []


# ---------------------------------------------------------------------------
# Rule 2: cross-channel loop
# ---------------------------------------------------------------------------

def _check_cross_channel_loop(
    rule,
    semantics: ProtocolSemantics,
    graph: SignalGraph,
    handshake_pairs: list[HandshakeInfo],
) -> list[DeadlockFinding]:
    """[B1] 跨通道 ready 链成环检测。

    算法:
      1. 构造 channel dependency graph: 节点 = 通道, 边 = 通道 A 的 ready 依赖通道 B 的 ready
      2. 找 SCC (强连通分量), size > 1 → 候选
    """
    findings: list[DeadlockFinding] = []
    if not rule.channels or len(rule.channels) < 2:
        return findings

    # 通道 ready 的 driver 链
    ch_to_ready: dict[str, str] = {}
    for ch in rule.channels:
        ch_spec = semantics.channel(ch)
        if not ch_spec:
            continue
        # 找这个通道的 ready 信号 (in handshake_pairs)
        for pair in handshake_pairs:
            if pair.ready.endswith(ch_spec.ready):
                ch_to_ready[ch] = pair.ready
                break

    # 对每对通道 (A, B), 检查 A.ready 的 driver 链是否含 B.ready
    for ch_a in rule.channels:
        for ch_b in rule.channels:
            if ch_a == ch_b:
                continue
            ready_a = ch_to_ready.get(ch_a)
            ready_b = ch_to_ready.get(ch_b)
            if not ready_a or not ready_b:
                continue
            drivers = _bfs_drivers(graph, ready_a, max_depth=10)
            if ready_b in drivers:
                # A.ready ← B.ready 候选环
                path = _bfs_path(graph, ready_a, ready_b, max_depth=10)
                findings.append(DeadlockFinding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    kind=rule.kind,
                    channels=rule.channels,
                    node_ids=[ready_a, ready_b] + (path[1:-1] if path else []),
                    description=(
                        f"{ch_a}.ready ({ready_a}) is in the driver chain of "
                        f"{ch_b}.ready ({ready_b}) — potential cross-channel deadlock."
                    ),
                    evidence=" → ".join(path[:5]) + ("..." if path and len(path) > 5 else ""),
                ))
    return findings


# ---------------------------------------------------------------------------
# Rule 3: response after request
# ---------------------------------------------------------------------------

def _check_response_after_request(
    rule,
    semantics: ProtocolSemantics,
    graph: SignalGraph,
    handshake_pairs: list[HandshakeInfo],
) -> list[DeadlockFinding]:
    """[B1] 检查 response 通道 valid 是否能追溯到 request 通道。

    算法:
      1. 找所有有 depends_on 的通道 (response channels)
      2. 对每个 response 通道, 检查 valid 的 driver 链是否包含 request.valid
      3. 不包含 → 死锁候选 (response 可能先于 request)
    """
    findings: list[DeadlockFinding] = []
    for ch in semantics.channels:
        if not ch.depends_on:
            continue
        # 找 response.valid 和 request.valid
        resp_valid = None
        req_valids = []
        for pair in handshake_pairs:
            if pair.valid.endswith(ch.valid):
                resp_valid = pair.valid
            for dep in ch.depends_on:
                dep_ch = semantics.channel(dep)
                if dep_ch and pair.valid.endswith(dep_ch.valid):
                    req_valids.append(pair.valid)
        if not resp_valid or not req_valids:
            continue
        # 检查 resp.valid 的 driver 链是否包含任一 request.valid
        drivers = _bfs_drivers(graph, resp_valid, max_depth=10)
        if not any(req in drivers for req in req_valids):
            # 没找到 request.valid 在 driver 链中 → 候选
            findings.append(DeadlockFinding(
                rule_id=rule.id,
                severity=rule.severity,
                kind=rule.kind,
                channels=rule.channels,
                node_ids=[resp_valid] + req_valids,
                description=(
                    f"{ch.name}.valid ({resp_valid}) is not in the driver chain of "
                    f"any request.valid ({', '.join(req_valids[:2])}). "
                    f"Response may arrive before request — potential deadlock."
                ),
                evidence=f"resp.valid drivers: {sorted(drivers)[:5]}...",
            ))
    return findings
