"""test_p158_data_edge_contract.py — [P158.1 / P158.2] 语义契约回归

背景 (P158.1):
  2026-11-11 四角度评审发现: 8 个机械门禁全绿时, `paths --directed` 仍可把
  **CLOCK 边**当成数据路径并返回 `verified`:
    - `paths top_minimal.sa1.clk top_minimal.sa1.ready_q --directed` → found:true
    - `verify claim type=path` (同一对) → verified
    - `dataflow analyze` (同一对) → is_reachable:true + latency_cycles:1

  根因: `PathResolver` / `DataFlowGraph` 各自维护 edge 策略, 接受**全部** edge kind。

本文件是 **true-positive** 回归 (SEMANTIC_CONTRACTS §8.3):
  - CLOCK/RESET 边**不得**成为数据路径 (paths / verify / dataflow 三处一致)
  - 真实数据路径**必须**仍然 found / verified / reachable (不被误伤)
  - 无向 `paths` 仍是结构连通性, 但必须标注 mode
  - 枚举有界: work budget / deadline 耗尽 → 显式 truncated + truncation_reason

**独立 oracle**: 期望值来自 **RTL 语义** (always @(posedge clk) 的 clk 只驱动
时序, 不驱动 ready_q 的数据) + **fixture 源码**, 不是从被测实现反向生成的。
mutation 说明见 `test_mutation_*`。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# [iter_239 1b] 快照目录隔离 (测试不写用户 home)
os.environ.setdefault("SVQ_SNAPSHOT_DIR", tempfile.mkdtemp(prefix="svq_p158_"))
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")

FILELIST = PROJECT_ROOT / "sim/tests/fixtures/minimal_3module/filelist.f"
FILELIST_REL = "sim/tests/fixtures/minimal_3module/filelist.f"

# ---------------------------------------------------------------------------
# 独立 oracle (手写, 不由被测实现生成)
# ---------------------------------------------------------------------------
# fixture 源码 (sim/tests/fixtures/minimal_3module/sub.sv):
#   always @(posedge clk or negedge rst_n) begin
#       if (!rst_n) ready_q <= 0;
#       else       ready_q <= leaf_ready;     <- ready_q 的**数据**来自 leaf_ready
#   end
#   assign ready_o = ready_q;
# → clk 与 ready_q 之间只有 CLOCK 边; 数据上 clk **不驱动** ready_q。
CLOCK_SRC = "top_minimal.sa1.clk"
CLOCK_DST = "top_minimal.sa1.ready_q"

# 真实数据对 (顶层端口 → 实例端口, CONNECTION 边)
DATA_SRC = "top_minimal.valid_i"
DATA_DST = "top_minimal.sa1.valid_i"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", RUN_CLI, *args], cwd=str(PROJECT_ROOT),
                          capture_output=True, text=True, timeout=300)


def _json(*args) -> dict:
    r = _run(*args)
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout[:500]}\n{r.stderr[:500]}"
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def tracer():
    from trace.unified_tracer import UnifiedTracer

    t = UnifiedTracer(filelist=str(FILELIST), log_level="ERROR")
    t.build_graph()
    return t


@pytest.fixture(scope="module")
def resolver(tracer):
    return tracer.get_path_resolver()


@pytest.fixture(scope="module")
def inst_resolver():
    """inst_demo 的 resolver (多路径图, 用于有界枚举测试)。"""
    from trace.unified_tracer import UnifiedTracer

    src = (PROJECT_ROOT / "sim/tests/fixtures/golden_mini/inst_demo.sv").read_text()
    t = UnifiedTracer(sources={"inst_demo.sv": src}, log_level="ERROR")
    t.build_graph()
    return t.get_path_resolver()


# ---------------------------------------------------------------------------
# 1. edge 契约: 唯一实现 + 三分类正确
# ---------------------------------------------------------------------------
class TestEdgeContract:
    def test_contract_module_is_single_source(self):
        """DATA/CONTROL/STRUCTURAL 三集合必须存在且互斥。"""
        from trace.core.graph.contracts import (
            CONTROL_EDGE_KINDS,
            DATA_EDGE_KINDS,
            STRUCTURAL_EDGE_KINDS,
        )
        from trace.core.graph.models import EdgeKind

        assert DATA_EDGE_KINDS == {EdgeKind.DRIVER, EdgeKind.CONNECTION}
        assert EdgeKind.CLOCK in CONTROL_EDGE_KINDS
        assert EdgeKind.RESET in CONTROL_EDGE_KINDS
        assert EdgeKind.BIT_SELECT in STRUCTURAL_EDGE_KINDS
        # 三类互斥 (契约: 每条边归一类)
        assert not (DATA_EDGE_KINDS & CONTROL_EDGE_KINDS)
        assert not (DATA_EDGE_KINDS & STRUCTURAL_EDGE_KINDS)
        assert not (CONTROL_EDGE_KINDS & STRUCTURAL_EDGE_KINDS)

    def test_no_command_local_edge_policy(self):
        """消费者必须引用 contracts, 不自己写 edge kind 集合。

        扫描: paths/verify/dataflow 相关模块里不得出现裸的
        `("DRIVER", "CONNECTION")` 之类的本地集合。
        """
        import re

        offenders = []
        pattern = re.compile(r"""["']DRIVER["']\s*,\s*["']CONNECTION["']""")
        for rel in ("src/cli/core/semantic/paths.py",
                    "src/cli/core/semantic/verify.py",
                    "src/trace/core/graph/dataflow.py",
                    "src/trace/core/module_instance_graph.py"):
            text = (PROJECT_ROOT / rel).read_text()
            if pattern.search(text):
                offenders.append(rel)
        assert not offenders, f"本地 edge 策略 (第二份实现): {offenders}"

    def test_is_data_edge_classifier(self):
        """classifier 按 kind 判定, 不按名字字符串。"""
        from trace.core.graph.contracts import has_data_edge, is_data_edge
        from trace.core.graph.models import EdgeKind

        class _E:
            def __init__(self, kind):
                self.kind = kind

        assert is_data_edge(_E(EdgeKind.DRIVER)) is True
        assert is_data_edge(_E(EdgeKind.CONNECTION)) is True
        assert is_data_edge(_E(EdgeKind.CLOCK)) is False
        assert is_data_edge(_E(EdgeKind.RESET)) is False
        assert is_data_edge(_E(EdgeKind.BIT_SELECT)) is False
        assert has_data_edge([_E(EdgeKind.CLOCK), _E(EdgeKind.DRIVER)]) is True
        assert has_data_edge([_E(EdgeKind.CLOCK)]) is False


# ---------------------------------------------------------------------------
# 2. true-positive: CLOCK 边不得成为数据路径 (三个消费者一致)
# ---------------------------------------------------------------------------
class TestClockIsNotADataPath:
    def test_resolver_directed_finds_no_clock_path(self, resolver):
        """PathResolver 有向 (数据) 模式: clk → ready_q 必须不可达。"""
        assert resolver.find_path(CLOCK_SRC, CLOCK_DST, directed=True) is None, \
            "CLOCK 边不得被当成数据路径"

    def test_resolver_undirected_still_connected(self, resolver):
        """无向 = 结构连通性: 必须仍可达 (语义不同, 不是功能坏了)。"""
        assert resolver.find_path(CLOCK_SRC, CLOCK_DST, directed=False) is not None, \
            "无向模式是结构连通性, clk 与 ready_q 结构上相连"

    def test_resolver_directed_finds_real_data_path(self, resolver):
        """真实数据对必须仍可达 (不被误伤)。"""
        assert resolver.find_path(DATA_SRC, DATA_DST, directed=True) is not None

    def test_find_all_paths_directed_excludes_clock(self, resolver):
        """枚举模式同样必须排除 CLOCK。"""
        assert resolver.find_all_paths(CLOCK_SRC, CLOCK_DST, directed=True) == []

    def test_cli_paths_directed_clock_not_found(self):
        """CLI: `paths --directed` 对 clk → ready_q 必须 found=false。"""
        d = _json("paths", CLOCK_SRC, CLOCK_DST, "--directed",
                  "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        assert d["found"] is False, f"CLOCK 边被当成数据路径了: {d.get('path')}"
        assert d["mode"] == "data"

    def test_cli_paths_undirected_labels_structural_mode(self):
        """CLI: 无向查询必须标注 mode=structural (不能当数据关系用)。"""
        d = _json("paths", CLOCK_SRC, CLOCK_DST, "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        assert d["directed"] is False
        assert d["mode"] == "structural"

    def test_cli_paths_directed_real_data_found(self):
        """CLI: 真实数据对必须 found=true (true-negative 不能误伤)。"""
        d = _json("paths", DATA_SRC, DATA_DST, "--directed",
                  "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        assert d["found"] is True
        assert d["path"][0] == DATA_SRC and d["path"][-1] == DATA_DST

    def test_verify_claim_path_clock_not_verified(self):
        """CLI: `verify claim type=path` 对 clk → ready_q 绝不能 verified。"""
        claim = json.dumps({"type": "path", "from": CLOCK_SRC, "to": CLOCK_DST})
        d = _json("verify", "claim", "--claim", claim,
                  "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        assert d["result"]["status"] != "verified", \
            f"CLOCK 路径被 verified 了: {d['result']}"

    def test_verify_claim_path_real_data_verified(self):
        """CLI: 真实数据对必须 verified (不被误伤)。"""
        claim = json.dumps({"type": "path", "from": DATA_SRC, "to": DATA_DST})
        d = _json("verify", "claim", "--claim", claim,
                  "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        assert d["result"]["status"] == "verified", f"真实数据路径没被 verified: {d['result']}"

    def test_verify_claim_path_explicit_nodes_rejects_clock_hop(self):
        """显式 nodes 的 claim: CLOCK hop 不得算数据边。"""
        claim = json.dumps({"type": "path", "from": CLOCK_SRC, "to": CLOCK_DST,
                            "nodes": [CLOCK_SRC, CLOCK_DST]})
        d = _json("verify", "claim", "--claim", claim,
                  "--filelist", FILELIST_REL, "--json")
        assert d["result"]["status"] != "verified", \
            f"显式 CLOCK hop 被 verified 了: {d['result']}"

    def test_dataflow_analyze_clock_not_reachable(self):
        """CLI: `dataflow analyze` 对 clk → ready_q 必须 not reachable。"""
        d = _json("dataflow", "analyze", CLOCK_SRC, CLOCK_DST,
                  "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        r = d["result"]
        assert r["is_reachable"] is False, f"CLOCK 路径可达了: {r}"
        assert r["paths_count"] == 0

    def test_dataflow_analyze_real_data_reachable(self):
        """CLI: 真实数据对必须 reachable (不被误伤)。"""
        d = _json("dataflow", "analyze", DATA_SRC, DATA_DST,
                  "--filelist", FILELIST_REL, "--json")
        assert d["ok"] is True
        assert d["result"]["is_reachable"] is True
        assert d["result"]["paths_count"] >= 1

    def test_three_consumers_agree_on_clock_pair(self, tracer, resolver):
        """不变式: paths(--directed) / verify path / dataflow 三处结论一致。

        这是本文件的核心不变式 —— 契约 §2.2 要求三者共用同一 edge 策略。
        """
        from trace.core.graph.dataflow import DataFlowGraph

        dfg = DataFlowGraph(tracer.get_graph(), tracer.get_module_graph())
        got_path = resolver.find_path(CLOCK_SRC, CLOCK_DST, directed=True) is not None
        got_df = dfg.analyze(CLOCK_SRC, CLOCK_DST, max_paths=20).is_reachable
        claim = json.dumps({"type": "path", "from": CLOCK_SRC, "to": CLOCK_DST})
        got_verify = _json("verify", "claim", "--claim", claim,
                           "--filelist", FILELIST_REL, "--json")["result"]["status"] == "verified"
        assert got_path is False
        assert got_df is False
        assert got_verify is False


# ---------------------------------------------------------------------------
# 3. BIT_SELECT 只作为位展开, 不作为数据路径段
# ---------------------------------------------------------------------------
class TestBitSelectIsExpansionNotSegment:
    BUS_SRC = "top.a"
    BUS_DST = "top.y"

    @pytest.fixture(scope="class")
    def bus_tracer(self):
        from trace.unified_tracer import UnifiedTracer

        src = """module leaf (input a, output y);
  assign y = a;
endmodule
module top (input [3:0] a, output [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    leaf u_leaf (.a(a[i]), .y(y[i]));
  end endgenerate
endmodule
"""
        t = UnifiedTracer(sources={"bus.sv": src}, log_level="ERROR")
        t.build_graph(use_cache=False, target_module="top")
        return t

    def test_bus_query_aggregates_all_entries(self, bus_tracer):
        """总线查询仍聚合全部 entry (位展开没坏)。"""
        from trace.core.graph.dataflow import DataFlowGraph

        dfg = DataFlowGraph(bus_tracer.get_graph(),
                            getattr(bus_tracer, "_module_graph", None))
        r = dfg.analyze(self.BUS_SRC, self.BUS_DST)
        assert r.paths_count == 4, f"bus 查询应聚合 4 entry, got {r.paths_count}"

    def test_segments_are_data_edges_only(self, bus_tracer):
        """每条 segment 的边必须是 DRIVER / CONNECTION (不是 BIT_SELECT)。"""
        from trace.core.graph.contracts import is_data_edge
        from trace.core.graph.dataflow import DataFlowGraph

        graph = bus_tracer.get_graph()
        dfg = DataFlowGraph(graph, getattr(bus_tracer, "_module_graph", None))
        r = dfg.analyze(self.BUS_SRC, self.BUS_DST)
        assert r.paths_count == 4
        for p in r.paths:
            for seg in p.segments:
                edges = graph.get_edges(seg.from_signal, seg.to_signal)
                assert edges, f"segment 无边: {seg.from_signal}→{seg.to_signal}"
                assert any(is_data_edge(e) for e in edges), (
                    f"segment 不是数据边: {seg.from_signal}→{seg.to_signal} "
                    f"kinds={[e.kind.name for e in edges]}"
                )

    def test_bit_select_edge_exists_but_is_not_data(self, bus_tracer):
        """前提核对: 图里**确实**有 BIT_SELECT 边 (否则本测试是空转)。"""
        graph = bus_tracer.get_graph()
        edges = graph.get_edges("top.y[0]", "top.y")
        assert edges and edges[0].kind.name == "BIT_SELECT", \
            "fixture 前提不成立: 期望 top.y[0] --BIT_SELECT--> top.y"


# ---------------------------------------------------------------------------
# 4. 有界枚举 (P158.2): 截断必须显式, 不静默 cap
# ---------------------------------------------------------------------------
class TestBoundedEnumeration:
    def test_max_expansions_truncates_explicitly(self, inst_resolver):
        """work budget 耗尽 → truncated=True + 明确 reason。"""
        r = inst_resolver.find_all_paths_detailed(
            "inst_demo.in_a", "inst_demo.add_out", max_expansions=1,
        )
        assert r.truncated is True
        assert r.truncation_reason == "max_expansions_reached"

    def test_deadline_truncates_explicitly(self, inst_resolver):
        """wall-clock deadline 耗尽 → truncated=True + 明确 reason。"""
        import time

        r = inst_resolver.find_all_paths_detailed(
            "inst_demo.in_a", "inst_demo.add_out",
            max_expansions=10_000_000, deadline=time.monotonic() - 1,
        )
        assert r.truncated is True
        assert r.truncation_reason == "deadline_reached"

    def test_max_paths_reason_only_when_more_exist(self, inst_resolver):
        """恰好 N 条路径时**不**应报 max_paths_reached (没被截断)。"""
        r = inst_resolver.find_all_paths_detailed(
            "inst_demo.in_a", "inst_demo.add_out", max_paths=50,
        )
        assert r.truncated is False
        assert r.truncation_reason == ""

    def test_cli_all_exposes_truncation_fields(self):
        """CLI `--all` 必须输出 truncated + truncation_reason (契约字段)。"""
        d = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--all",
                  "--max-expansions", "1", "-f",
                  "sim/tests/fixtures/golden_mini/inst_demo.sv", "--json")
        assert d["ok"] is True
        assert d["truncated"] is True
        assert d["truncation_reason"] == "max_expansions_reached"

    def test_cli_canonical_exposes_truncation_fields(self):
        """CLI `--canonical` 也必须暴露截断 (不能静默 cap)。"""
        d = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--canonical",
                  "--max-expansions", "1", "-f",
                  "sim/tests/fixtures/golden_mini/inst_demo.sv", "--json")
        assert d["ok"] is True
        assert d["truncated"] is True
        assert d["truncation_reason"] == "max_expansions_reached"

    def test_cli_timeout_is_accepted(self):
        """`--timeout` 存在且生效 (不是摆设)。"""
        d = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--all",
                  "--timeout", "0.001", "-f",
                  "sim/tests/fixtures/golden_mini/inst_demo.sv", "--json")
        assert d["ok"] is True
        assert "truncated" in d and "truncation_reason" in d

    def test_large_graph_query_is_bounded(self):
        """大图查询必须在预算内返回, 不得静默卡死 (C-03)。

        用一张**合成大图** (不依赖外部 snapshot, 保证可复现):
        构造一个宽度 × 深度的链 + 大量 CLOCK 边, 无向枚举必然爆炸。
        """
        from trace.core.graph.models import (
            EdgeKind,
            NodeKind,
            SignalGraph,
            TraceEdge,
            TraceNode,
        )
        from trace.core.module_instance_graph import ModuleInstanceGraph, PathResolver

        g = SignalGraph()
        n = 400
        for i in range(n):
            g.add_trace_node(TraceNode(id=f"s{i}", name=f"s{i}", module="m",
                                       kind=NodeKind.SIGNAL, width=(0, 0)))
        for i in range(n - 1):
            g.add_trace_edge(TraceEdge(src=f"s{i}", dst=f"s{i+1}", kind=EdgeKind.DRIVER))
        # 每条链边旁挂一条 CLOCK 边 → 无向遍历的分支因子爆炸
        for i in range(n - 1):
            g.add_trace_edge(TraceEdge(src=f"s{i}", dst=f"s{i+1}", kind=EdgeKind.CLOCK))

        pr = PathResolver(g, ModuleInstanceGraph(adapter=None))
        import time

        t0 = time.monotonic()
        r = pr.find_all_paths_detailed("s0", f"s{n-1}", max_paths=10,
                                       max_expansions=5000)
        elapsed = time.monotonic() - t0
        assert elapsed < 30, f"枚举超时: {elapsed:.1f}s"
        assert r.truncated is True
        assert r.truncation_reason in ("max_expansions_reached", "max_paths_reached",
                                       "max_depth_reached", "deadline_reached")


# ---------------------------------------------------------------------------
# 5. mutation: 关掉检查实现, 上面那些 true-positive 断言必须**变红**
# ---------------------------------------------------------------------------
class TestMutation:
    """mutation 测试 (SEMANTIC_CONTRACTS §8.3): 关闭数据边过滤实现。

    做法: monkeypatch `contracts.DATA_EDGE_KINDS` 让它包含 CLOCK
    (等价于"实现退回旧行为: 接受全部 edge kind"), 然后**重跑 guard 断言**:
    guard 必须**失败** —— 这才证明 guard 真的在检查, 而不是恒真。

    断言写成 `with pytest.raises(AssertionError): <guard 断言>`:
    guard 变红 = 通过; guard 仍绿 = 失败 (测试报红)。
    """

    @staticmethod
    def _guard_asserts_no_clock_path(resolver) -> None:
        """guard 断言: 有向 (数据) 模式下 CLOCK 路径必须不可达。"""
        assert resolver.find_path(CLOCK_SRC, CLOCK_DST, directed=True) is None, \
            "CLOCK 边不得被当成数据路径"

    @staticmethod
    def _guard_asserts_dataflow_unreachable(tracer) -> None:
        """guard 断言: dataflow 对 CLOCK 对必须 not reachable。"""
        from trace.core.graph import dataflow

        dfg = dataflow.DataFlowGraph(tracer.get_graph(), tracer.get_module_graph())
        dfg._data_graph_cache = None
        assert dfg.analyze(CLOCK_SRC, CLOCK_DST, max_paths=20).is_reachable is False, \
            "CLOCK 路径可达了"

    def test_mutation_relaxes_data_edge_kinds_turns_guard_red(self, resolver, monkeypatch):
        """mutation: 数据边集合被放宽 → PathResolver 的 guard 必须变红。"""
        from trace.core.graph import contracts

        monkeypatch.setattr(
            contracts, "DATA_EDGE_KINDS",
            frozenset(contracts.DATA_EDGE_KINDS | {contracts.EdgeKind.CLOCK}),
        )
        # PathResolver 运行时读 contracts → mutation 生效
        with pytest.raises(AssertionError):
            self._guard_asserts_no_clock_path(resolver)

    def test_mutation_relaxes_data_edge_kinds_turns_dataflow_guard_red(self, tracer, monkeypatch):
        """mutation: 数据边集合被放宽 → dataflow 的 guard 必须变红。"""
        from trace.core.graph import contracts

        monkeypatch.setattr(
            contracts, "DATA_EDGE_KINDS",
            frozenset(contracts.DATA_EDGE_KINDS | {contracts.EdgeKind.CLOCK}),
        )
        with pytest.raises(AssertionError):
            self._guard_asserts_dataflow_unreachable(tracer)

    def test_mutation_disables_budget_turns_truncation_guard_red(self, inst_resolver, monkeypatch):
        """mutation: 去掉 work budget → 截断 guard 必须变红。

        把 `max_expansions` 变成无穷大 (等价于"没有预算的实现"),
        此时 `truncated` 不再为 True → guard 断言失败。
        """
        from trace.core.module_instance_graph import PathResolver

        original = PathResolver.find_all_paths_detailed

        def _no_budget(self, *a, **kw):
            kw["max_expansions"] = 10**9
            kw["deadline"] = None
            return original(self, *a, **kw)

        monkeypatch.setattr(PathResolver, "find_all_paths_detailed", _no_budget)
        with pytest.raises(AssertionError):
            r = inst_resolver.find_all_paths_detailed(
                "inst_demo.in_a", "inst_demo.add_out", max_expansions=1)
            assert r.truncated is True
            assert r.truncation_reason == "max_expansions_reached"
