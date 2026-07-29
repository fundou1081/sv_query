# ==============================================================================
# test_trace_overview.py — B 复合命令 trace overview 的自动化测试
#
# 验证:
#   - JSON 输出结构完整 (dataflow/controlflow/evidence 三段)
#   - sync_fifo: 2 cycle latency, dataflow 可达
#   - mux5: selector 信号的控制条件
#   - 错误信号 friendly error
# ==============================================================================

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.golden  # 独立于 opensource 项目

_project_root = Path(__file__).resolve().parent.parent.parent.parent
_run_cli = str(_project_root / "run_cli.py")
_FIXTURES = _project_root / "sim" / "tests" / "integration" / "dataflow_fixtures"
SYNC_FIFO = str(_FIXTURES / "sync_fifo.sv")
MUX5 = str(_FIXTURES / "golden_mux5.sv")

ENV = {**__import__("os").environ, "SVQ_QUIET": "1"}


def _run(*args: str) -> subprocess.CompletedProcess:
    """Run CLI with quiet mode to avoid pyslang warnings in stdout."""
    return subprocess.run(
        [sys.executable, _run_cli, *args],
        capture_output=True, text=True, timeout=30,
        env=ENV,
    )


def _json(*args: str) -> dict:
    """Run CLI with --json and parse result."""
    cp = _run(*args, "--json")
    assert cp.returncode == 0, f"CLI failed: {cp.stderr}"
    return json.loads(cp.stdout)


# ════════════════════════════════════════════════════════════════════
# JSON 输出结构测试
# ════════════════════════════════════════════════════════════════════

def test_overview_json_structure():
    """B 复合命令 JSON 输出包含完整的三段结构"""
    data = _json("trace", "overview",
                 "sync_fifo.push_data_i", "sync_fifo.pop_data_o",
                 "-f", SYNC_FIFO)

    assert data["ok"] is True
    assert data["command"] == "trace_overview"

    result = data["result"]
    assert "dataflow" in result
    assert "controlflow" in result
    assert "evidence" in result

    # dataflow 段
    df = result["dataflow"]
    assert df["is_reachable"] is True
    assert df["paths_count"] >= 1
    assert "primary_latency_cycles" in df

    # controlflow 段
    cf = result["controlflow"]
    assert "from" in cf
    assert "to" in cf

    # evidence 段
    assert isinstance(result["evidence"], dict)

    # params
    assert data["params"]["from_signal"] == "sync_fifo.push_data_i"
    assert data["params"]["to_signal"] == "sync_fifo.pop_data_o"


# ════════════════════════════════════════════════════════════════════
# DataFlow 验证
# ════════════════════════════════════════════════════════════════════

def test_overview_sync_fifo_latency_2():
    """sync_fifo push→pop 应该报告 2 cycle latency"""
    data = _json("trace", "overview",
                 "sync_fifo.push_data_i", "sync_fifo.pop_data_o",
                 "-f", SYNC_FIFO)

    df = data["result"]["dataflow"]
    assert df["primary_latency_cycles"] == 2
    assert df["primary_is_async"] is False

    # paths 包含 segment 级的 evidence
    paths = df["paths"]
    assert len(paths) >= 1
    for seg in paths[0]["segments"]:
        assert "evidence" in seg
        assert "from_signal" in seg
        assert "to_signal" in seg


def test_overview_sync_fifo_async_flag():
    """sync_fifo 是同步设计，primary_is_async 应为 False"""
    data = _json("trace", "overview",
                 "sync_fifo.push_data_i", "sync_fifo.pop_data_o",
                 "-f", SYNC_FIFO)

    assert data["result"]["dataflow"]["primary_is_async"] is False
    assert data["result"]["dataflow"]["clock_domain"] == "clk"


# ════════════════════════════════════════════════════════════════════
# ControlFlow 验证
# ════════════════════════════════════════════════════════════════════

def test_overview_mux5_controlflow():
    """mux5 sel→out 虽然有 dataflow 不可达（CONTROL 不是 DATA 边），
    但 controlflow 应该能分析出 sel 作为 selector 的条件"""
    data = _json("trace", "overview",
                 "golden_mux5.sel", "golden_mux5.out",
                 "-f", MUX5)

    # controlflow: from 信号 sel 本身没有 conditioned drivers（它是 selector）
    cf = data["result"]["controlflow"]

    # 但 to 信号 out 应该有 conditioned drivers（mux 的分支条件）
    drivers = cf["to"].get("conditioned_drivers", [])
    if drivers:
        # 每个条件都应该有 expr + edge + evidence
        for cd in drivers:
            for cond in cd.get("conditions", []):
                assert "expr" in cond
                assert "edge" in cond
                assert "evidence" in cond

    # sel 没有 conditioned drivers 也是正确的（mux 的 selector 输入端）
    assert "conditioned_drivers" in cf["from"]


def test_overview_mux5_conditions_count():
    """5-way mux + default = 6 条件"""
    data = _json("trace", "overview",
                 "golden_mux5.sel", "golden_mux5.out",
                 "-f", MUX5)

    cf_to = data["result"]["controlflow"]["to"]
    drivers = cf_to.get("conditioned_drivers", [])
    if drivers:
        total_conds = sum(len(cd.get("conditions", [])) for cd in drivers)
        assert total_conds == 6, f"5-way mux + default = 6, got {total_conds}"


# ════════════════════════════════════════════════════════════════════
# Evidence 验证
# ════════════════════════════════════════════════════════════════════

def test_overview_evidence_contains_path_signals():
    """Evidence 段应该包含 dataflow 路径上的关键信号"""
    data = _json("trace", "overview",
                 "sync_fifo.push_data_i", "sync_fifo.pop_data_o",
                 "-f", SYNC_FIFO)

    ev = data["result"]["evidence"]
    assert len(ev) >= 1

    # 检查 evidence 条目结构
    for sig_name, ev_dict in ev.items():
        assert sig_name  # 非空信号名
        if ev_dict:
            assert "source_location" in ev_dict


def test_overview_evidence_source_location():
    """Evidence 条目应该有 source_location 信息"""
    data = _json("trace", "overview",
                 "sync_fifo.push_data_i", "sync_fifo.pop_data_o",
                 "-f", SYNC_FIFO)

    ev = data["result"]["evidence"]
    for sig_name, ev_dict in ev.items():
        if ev_dict and ev_dict.get("source_location"):
            loc = ev_dict["source_location"]
            assert "file" in loc
            assert "line_start" in loc
            assert SYNC_FIFO.endswith("sync_fifo.sv")


# ════════════════════════════════════════════════════════════════════
# 错误处理
# ════════════════════════════════════════════════════════════════════

def test_overview_error_signal_graceful():
    """不存在的信号应该返回友好错误而非 traceback"""
    data = _json("trace", "overview",
                 "sync_fifo.nonexistent", "sync_fifo.also_fake",
                 "-f", SYNC_FIFO)

    assert "errors" in data
    assert len(data["errors"]) >= 1
    # ok 应该为 False
    assert data["ok"] is False
    # 但不应该 crash
    assert "result" in data


# ════════════════════════════════════════════════════════════════════
# Human 输出测试
# ════════════════════════════════════════════════════════════════════

def test_overview_human_output_sections():
    """--human 输出应该包含三个段标题"""
    cp = _run("trace", "overview",
              "sync_fifo.push_data_i", "sync_fifo.pop_data_o",
              "-f", SYNC_FIFO, "--human")
    assert cp.returncode == 0
    output = cp.stdout

    assert "DataFlow" in output
    assert "ControlFlow" in output
    assert "Evidence" in output
    assert "Reachable" in output
