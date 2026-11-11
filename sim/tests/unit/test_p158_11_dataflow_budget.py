"""test_p158_11_dataflow_budget.py — [P158.11.2b] dataflow 有界搜索契约

背景（SEMANTIC_CONTRACTS §3）:
  dataflow._find_paths 曾用 `list(nx.all_simple_paths(...))` 先物化**全部**
  简单路径:
    - 分支图指数爆炸 → 长时间不返回；
    - 无路径时 all_simple_paths 仍遍历指数级死胡同；
    - `paths[:max_paths]` 之后静默截断，JSON 没有任何截断字段；
    - 预算耗尽与"真的没有路径"在输出上不可区分。

本文件锁定五条：
  A. 完整搜索 → `search_status="complete"`, 无截断字段
  B. max_paths 收满 → `truncated=true` + `max_paths_reached`（不是静默 slice）
  C. work budget 耗尽且无结果 → `is_reachable is None` + `unknown`（**不能是 false**）
  D. deadline 超时 → `deadline_reached` + unknown
  E. 有界 DFS 与 `nx.all_simple_paths` 路径**顺序一致**（golden 不受影响）

独立 oracle:
  - 路径总数 256 由 fixture 结构直接推出（8 级菱形，每级翻倍：2^7 × 2），
    不是由被测实现反向生成；
  - 顺序一致性直接与 networkx 公开 API 对比，不依赖本实现。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from trace.unified_tracer import UnifiedTracer  # noqa: E402
from trace.core.graph.dataflow import DataFlowGraph  # noqa: E402
from trace.core.graph.search_budget import SearchBudget  # noqa: E402

DIAMOND_FILELIST = PROJECT_ROOT / "sim/tests/fixtures/dataflow_budget/filelist.f"
MINIMAL_FILELIST = PROJECT_ROOT / "sim/tests/fixtures/minimal_3module/filelist.f"
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")

DIAMOND_SRC = "diamond_top.s0"
DIAMOND_DST = "diamond_top.y"
# 8 级菱形: 第 i 级每个节点有 2^(i-1) 条路径; 第 8 级两个节点汇到 y
EXPECTED_PATHS = 2 ** 7 * 2  # 256


@pytest.fixture(scope="module")
def diamond():
    tracer = UnifiedTracer(filelist=str(DIAMOND_FILELIST), log_level="ERROR")
    tracer.build_graph()
    return DataFlowGraph(tracer.get_graph(), tracer.get_module_graph())


@pytest.fixture(scope="module")
def minimal():
    tracer = UnifiedTracer(filelist=str(MINIMAL_FILELIST), log_level="ERROR")
    tracer.build_graph()
    return DataFlowGraph(tracer.get_graph(), tracer.get_module_graph())


# ---------------------------------------------------------------------------
# A. 完整搜索: 不得声称截断
# ---------------------------------------------------------------------------
class TestCompleteSearch:
    def test_all_paths_found_without_truncation(self, diamond):
        r = diamond.analyze(DIAMOND_SRC, DIAMOND_DST, max_paths=10_000)
        assert r.is_reachable is True
        assert r.paths_count == EXPECTED_PATHS
        assert r.truncated is False
        assert r.truncation_reason == ""
        assert r.search_status == "complete"
        assert r.expansions > 0

    def test_small_graph_true_negative(self, minimal):
        """不存在的截断不能报: 小图正常查询必须是 complete。"""
        r = minimal.analyze("top_minimal.valid_i", "top_minimal.sa1.valid_i")
        assert r.is_reachable is True
        assert r.truncated is False
        assert r.search_status == "complete"


# ---------------------------------------------------------------------------
# B. max_paths: 收满必须显式
# ---------------------------------------------------------------------------
class TestMaxPaths:
    def test_cap_is_explicit(self, diamond):
        r = diamond.analyze(DIAMOND_SRC, DIAMOND_DST, max_paths=10)
        assert r.paths_count == 10
        assert r.truncated is True
        assert r.truncation_reason == "max_paths_reached"
        assert r.is_reachable is True

    def test_exactly_max_paths_is_not_truncated_when_no_more(self, minimal):
        r = minimal.analyze("top_minimal.valid_i", "top_minimal.sa1.valid_i",
                            max_paths=1)
        assert r.paths_count == 1
        assert r.truncated is False, "恰好等于上限且没有更多路径时不得报截断"


# ---------------------------------------------------------------------------
# C/D. 硬预算: 必须是 unknown, 不能是 "不可达"
# ---------------------------------------------------------------------------
class TestHardBudget:
    def test_work_budget_exhaustion_is_unknown_not_false(self, diamond):
        r = diamond.analyze(DIAMOND_SRC, DIAMOND_DST, max_expansions=5)
        assert r.is_reachable is None, "预算耗尽 ≠ 不可达"
        assert r.truncated is True
        assert r.truncation_reason == "max_expansions_reached"
        assert r.search_status == "unknown"
        assert r.paths_count == 0
        assert r.expansions == 5, "work 计数必须真实累加"

    def test_deadline_exhaustion_is_unknown(self, diamond):
        r = diamond.analyze(DIAMOND_SRC, DIAMOND_DST, timeout_s=0.0)
        assert r.is_reachable is None
        assert r.truncation_reason == "deadline_reached"
        assert r.search_status == "unknown"

    def test_partial_result_keeps_paths_but_marks_truncated(self, diamond):
        """先找到路径再耗尽 → found:true + truncated:true（契约允许的另一条分支）。"""
        r = diamond.analyze(DIAMOND_SRC, DIAMOND_DST, max_expansions=60)
        assert r.is_reachable is True
        assert r.truncated is True
        assert r.truncation_reason == "max_expansions_reached"
        assert 0 < r.paths_count < EXPECTED_PATHS

    def test_real_absent_path_is_false_not_unknown(self, minimal):
        """搜索完成后确认无路径 = false；与预算耗尽必须可区分。"""
        r = minimal.analyze("top_minimal.sa1.clk", "top_minimal.sa1.ready_q")
        assert r.is_reachable is False
        assert r.truncated is False
        assert r.search_status == "complete"


# ---------------------------------------------------------------------------
# E. 与 networkx 的遍历序一致（golden 兼容）
# ---------------------------------------------------------------------------
class TestTraversalParity:
    @pytest.mark.parametrize("src,dst", [
        (DIAMOND_SRC, DIAMOND_DST),
        ("top_minimal.valid_i", "top_minimal.sa1.valid_i"),
        ("top_minimal.valid_i", "top_minimal.sa1.lp1.data_i"),
        ("top_minimal.sa1.la1.sum", "top_minimal.data_o"),
    ])
    def test_path_order_matches_networkx(self, diamond, minimal, src, dst):
        dfg = diamond if src.startswith("diamond") else minimal
        graph = dfg._data_graph()
        if src not in graph or dst not in graph:
            pytest.skip(f"fixture 不含 {src}/{dst}")
        state = SearchBudget(max_expansions=200_000, deadline=None,
                             max_paths=100_000, max_depth=50)
        mine = list(dfg._bounded_simple_paths(graph, src, dst, 50, state))
        theirs = list(nx.all_simple_paths(graph, src, dst, cutoff=50))
        assert mine == theirs, "有界 DFS 必须与 nx.all_simple_paths 同遍历序"


# ---------------------------------------------------------------------------
# CLI: 字段必须出现在 JSON 里
# ---------------------------------------------------------------------------
def _cli_json(*args) -> dict:
    r = subprocess.run([sys.executable, RUN_CLI, *args],
                       cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout[:400]}\n{r.stderr[:400]}"
    return json.loads(r.stdout)


class TestCliSurface:
    def test_budget_exhaustion_visible_in_json(self):
        data = _cli_json("dataflow", "analyze", DIAMOND_SRC, DIAMOND_DST,
                         "--filelist", "sim/tests/fixtures/dataflow_budget/filelist.f",
                         "--max-expansions", "5", "--json")
        result = data["result"]
        assert result["is_reachable"] is None
        assert result["search_status"] == "unknown"
        assert result["truncated"] is True
        assert result["truncation_reason"] == "max_expansions_reached"
        assert result["machine"]["unknown_kind"] == "search_budget_exhausted"

    def test_timeout_flag_is_accepted(self):
        data = _cli_json("dataflow", "analyze", DIAMOND_SRC, DIAMOND_DST,
                         "--filelist", "sim/tests/fixtures/dataflow_budget/filelist.f",
                         "--timeout", "0", "--json")
        assert data["result"]["truncation_reason"] == "deadline_reached"
        assert data["params"]["timeout"] == 0.0

    def test_complete_run_has_no_unknown_machine(self):
        data = _cli_json("dataflow", "analyze",
                         "top_minimal.valid_i", "top_minimal.sa1.valid_i",
                         "--filelist", "sim/tests/fixtures/minimal_3module/filelist.f",
                         "--json")
        result = data["result"]
        assert result["is_reachable"] is True
        assert result["search_status"] == "complete"
        assert result["truncated"] is False
        assert "machine" not in result
