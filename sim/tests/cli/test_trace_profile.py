"""[iter_332 / PLAN P36.1] trace profile：波形关联元数据。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def _profile(*signals):
    args = ["trace", "profile", *signals, "-f", str(FIXTURE), "--json"]
    r = _run(*args)
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_sequential_signal_profile():
    i = _profile("sync_fifo.data_out")["result"]["signals"][0]
    assert i["resolved_signal"] == "sync_fifo.data_out"
    assert i["resolution"] == "exact"
    assert i["width"] == [7, 0]
    assert i["source"]["line"] == 20
    assert i["source"]["driver"]["line"] == 30
    assert i["clock_domains"] == ["clk"]
    assert any(r["signal"] == "sync_fifo.rst_n" for r in i["resets"])
    assert i["sequential"]["is_sequential"] is True
    assert "nonblocking" in i["sequential"]["assign_types"]
    assert i["aliases"][:2] == ["sync_fifo.data_out", "data_out"]


def test_continuous_signal_profile():
    i = _profile("sync_fifo.full")["result"]["signals"][0]
    assert i["sequential"]["is_sequential"] is False
    assert i["clock_domains"] == []
    assert i["source"]["driver"]["line"] == 23
    assert i["role"]["is_port"] is True


def test_input_port_profile():
    i = _profile("sync_fifo.push_data_i")["result"]["signals"][0]
    assert i["kind"] == "PORT_IN"
    assert i["role"]["is_port"] is True
    assert i["driver_count"] == 0
    assert i["sequential"]["is_sequential"] is False


def test_relative_name_and_unknown_signal():
    d = _profile("data_out")
    assert d["ok"] is True
    assert d["result"]["signals"][0]["resolution"] == "relative"
    d = _profile("sync_fifo.nope")
    assert d["ok"] is False
    assert d["errors"][0]["error_code"] == "E_SIGNAL_NOT_FOUND"
    assert d["result"]["signals"][0]["resolution"] == "not_found"


def test_batch_partial_profile():
    d = _profile("--batch", "sync_fifo.full,sync_fifo.nope")
    assert d["ok"] is False
    assert d["result"]["failed_signals"] == 1
    assert d["result"]["signals"][0]["resolved_signal"] == "sync_fifo.full"
    assert d["result"]["signals"][1]["resolution"] == "not_found"
