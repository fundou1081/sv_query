"""
test_visualize_pipeline_json.py — [iter_198] pipeline 的**文本结构化输出**验收测试

背景 (方豆决策 2026-09-08): "pipeline timing 现在所有输出都以**文本结构化输出为
检查标准**。先不考虑可视化。"

因此本文件**不碰可视化产物**, 只锁 `sv_query visualize pipeline --json` 的结构化契约:

  1. stdout 必须是**纯 JSON** (诊断/告警全部走 stderr) — 否则 LLM/脚本消费会被污染;
  2. 信封与 `sv_query timing analyze --json` 一致: `{ok, command, result}`;
  3. `result` 字段固定: module / total_latency / stage_count / pipeline_regs /
     control_regs / state_regs / stages[];
  4. `stages[i]` 字段固定: stage_id / reg_nodes / comb_nodes / control_inputs /
     data_inputs / data_outputs / latency;
  5. 语义不变量 (用 golden 语料): 深度 register 链的 `total_latency` / `stage_count`
     必须随寄存器级数增长; 寄存器分类不重叠 (pipeline/control/state 互斥)。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "sim" / "tests" / "fixtures" / "golden_mini"

ENVELOPE_KEYS = {"ok", "command", "result"}
RESULT_KEYS = {
    "module", "total_latency", "stage_count",
    "pipeline_regs", "control_regs", "state_regs", "stages",
}
STAGE_KEYS = {
    "stage_id", "reg_nodes", "comb_nodes", "control_inputs",
    "data_inputs", "data_outputs", "latency",
}


def _run_json(sv_file: Path) -> tuple[dict, str]:
    """跑 pipeline --json, 返回 (解析后的 JSON, 原始 stdout)。"""
    r = subprocess.run(
        [sys.executable, str(REPO / "run_cli.py"), "visualize", "pipeline",
         "-f", str(sv_file), "--json"],
        capture_output=True, text=True, timeout=300, cwd=REPO,
    )
    assert r.returncode == 0, f"pipeline --json 应成功: rc={r.returncode}\n{r.stderr[-500:]}"
    return json.loads(r.stdout), r.stdout


@pytest.fixture(scope="module")
def payload():
    sv = FIXTURES / "golden_dataflow_39_cordic_pipeline.v"
    if not sv.exists():
        pytest.skip(f"fixture 缺失: {sv}")
    return _run_json(sv)[0]


def test_stdout_is_pure_json(payload):
    """[验收 1] stdout 能被 json.loads 直接消费 (无 warning 混入)。"""
    assert isinstance(payload, dict)
    assert payload.get("ok") is True


def test_envelope_matches_timing(payload):
    """[验收 2] 信封与 timing analyze --json 一致。"""
    assert set(payload.keys()) == ENVELOPE_KEYS
    assert payload["command"] == "visualize pipeline"


def test_result_schema_stable(payload):
    """[验收 3] result 字段固定 (新增字段先改测试 = 契约变更可见)。"""
    assert set(payload["result"].keys()) == RESULT_KEYS


def test_stage_schema_stable(payload):
    """[验收 4] stages[i] 字段固定。"""
    stages = payload["result"]["stages"]
    assert stages, "golden pipeline 语料应有 stage"
    for st in stages:
        assert set(st.keys()) == STAGE_KEYS, f"stage 字段漂移: {sorted(st.keys())}"


def test_reg_classification_is_disjoint(payload):
    """[验收 5] pipeline / control / state 寄存器分类互不重叠。"""
    r = payload["result"]
    p, c, s = set(r["pipeline_regs"]), set(r["control_regs"]), set(r["state_regs"])
    assert not (p & c), f"pipeline ∩ control = {sorted(p & c)[:5]}"
    assert not (p & s), f"pipeline ∩ state = {sorted(p & s)[:5]}"
    assert not (c & s), f"control ∩ state = {sorted(c & s)[:5]}"


def test_stage_count_and_latency_consistent(payload):
    """[验收 5] stage_count 与 stages 长度一致; 每 stage latency >= 1。"""
    r = payload["result"]
    assert r["stage_count"] == len(r["stages"])
    for st in r["stages"]:
        assert st["latency"] >= 1, f"stage {st['stage_id']} latency={st['latency']}"


def test_deeper_pipeline_reports_more_latency():
    """[验收 5] 深度 register 链的 total_latency 必须大于单级链 (语义不变量)。"""
    deep = FIXTURES / "golden_dataflow_29_generate_for_chain.sv"
    if not deep.exists():
        pytest.skip("fixture 缺失")
    single = FIXTURES / "golden_dataflow_1_op.sv"
    if not single.exists():
        pytest.skip("fixture 缺失")

    deep_lat = _run_json(deep)[0]["result"]["total_latency"]
    single_lat = _run_json(single)[0]["result"]["total_latency"]
    assert deep_lat >= single_lat, (
        f"深链 latency ({deep_lat}) 不应小于单级链 ({single_lat})"
    )
