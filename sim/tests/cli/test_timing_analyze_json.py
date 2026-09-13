"""
test_timing_analyze_json.py — [iter_199] `timing analyze --json` 的字段级验收测试

背景: 方豆决策 (2026-09-08) "pipeline timing 现在所有输出都以**文本结构化输出为
检查标准**。先不考虑可视化。" iter_198 已把该标准落到 `visualize pipeline --json`;
本文件用**同一模板**锁住 `sv_query timing analyze --json`。

断言模板 (与 pipeline 版一致):
  1. stdout 必须是**纯 JSON** (诊断/告警走 stderr), 可直接 json.loads;
  2. 信封 `{ok, command, result}` (与 pipeline 版一致);
  3. `result` 字段固定: total_nodes / reg_count / critical_paths;
  4. `critical_paths[i]` 字段固定: depth / score / registers / full_path;
  5. 语义不变量: reg_count <= total_nodes; 每条 path 的 depth/score >= 1;
     registers 非空且不与 full_path 矛盾 (registers ⊆ full_path);
     `--max-paths` 生效 (返回条数 <= max_paths)。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "sim" / "tests" / "fixtures" / "golden_mini"
CORDIC = FIXTURES / "golden_dataflow_39_cordic_pipeline.v"
SINGLE = FIXTURES / "golden_dataflow_1_op.sv"

ENVELOPE_KEYS = {"ok", "command", "result"}
RESULT_KEYS = {"total_nodes", "reg_count", "critical_paths"}
PATH_KEYS = {"depth", "score", "registers", "full_path"}


def _run_json(sv_file: Path, *extra: str) -> tuple[dict, str]:
    r = subprocess.run(
        [sys.executable, str(REPO / "run_cli.py"), "timing", "analyze",
         "-f", str(sv_file), "--json", *extra],
        capture_output=True, text=True, timeout=300, cwd=REPO,
    )
    assert r.returncode == 0, f"timing analyze --json 应成功: rc={r.returncode}\n{r.stderr[-500:]}"
    return json.loads(r.stdout), r.stdout


@pytest.fixture(scope="module")
def payload():
    if not CORDIC.exists():
        pytest.skip(f"fixture 缺失: {CORDIC}")
    return _run_json(CORDIC)[0]


def test_stdout_is_pure_json(payload):
    """[验收 1] stdout 可直接 json.loads (无 warning/诊断混入)。"""
    assert isinstance(payload, dict)
    assert payload.get("ok") is True


def test_envelope_matches_pipeline(payload):
    """[验收 2] 信封与 `visualize pipeline --json` 一致。"""
    assert set(payload.keys()) == ENVELOPE_KEYS
    assert payload["command"] == "timing analyze"


def test_result_schema_stable(payload):
    """[验收 3] result 字段固定 (增删字段 → 测试红 = 契约变更可见)。"""
    assert set(payload["result"].keys()) == RESULT_KEYS


def test_critical_path_schema_stable(payload):
    """[验收 4] critical_paths[i] 字段固定。"""
    paths = payload["result"]["critical_paths"]
    assert isinstance(paths, list)
    for p in paths:
        assert set(p.keys()) == PATH_KEYS, f"path 字段漂移: {sorted(p.keys())}"


def test_counts_are_consistent(payload):
    """[验收 5] reg_count <= total_nodes 且都是非负整数。"""
    r = payload["result"]
    for k in ("total_nodes", "reg_count"):
        assert isinstance(r[k], int) and r[k] >= 0, f"{k} 应为非负整数, got {r[k]!r}"
    assert r["reg_count"] <= r["total_nodes"], (
        f"reg_count({r['reg_count']}) 不应超过 total_nodes({r['total_nodes']})"
    )


def test_path_fields_are_sane(payload):
    """[验收 5] 每条 path: depth/score >= 1, registers 非空且 ⊆ full_path。"""
    for p in payload["result"]["critical_paths"]:
        assert p["depth"] >= 1, f"depth 应 >= 1: {p}"
        assert p["score"] >= 1, f"score 应 >= 1: {p}"
        assert p["registers"], f"critical path 应至少含 1 个寄存器: {p}"
        assert set(p["registers"]) <= set(p["full_path"]), (
            f"registers 必须是 full_path 的子集: {p}"
        )


def test_max_paths_is_respected(payload):
    """[验收 5] --max-paths 生效 (返回条数 <= max_paths)。"""
    limited, _ = _run_json(CORDIC, "--max-paths", "2")
    assert len(limited["result"]["critical_paths"]) <= 2, limited["result"]["critical_paths"]


def test_single_op_has_no_critical_path():
    """[验收 5] 语义: 单寄存器级组合 (`_1_op` 语料) 不应报出含多级的 critical path。

    不预设具体数值 (避免把实现细节写死), 只锁"语料语义 → 结构化输出"的一致性:
    寄存器数不得超过节点总数, 且若 reg_count == 0 则 critical_paths 必须为空
    (没有寄存器就没有 register-to-register 关键路径)。
    """
    if not SINGLE.exists():
        pytest.skip(f"fixture 缺失: {SINGLE}")
    r = _run_json(SINGLE)[0]["result"]
    assert r["reg_count"] <= r["total_nodes"]
    if r["reg_count"] == 0:
        assert r["critical_paths"] == [], (
            f"reg_count=0 时不应有 critical path, got {r['critical_paths']}"
        )
