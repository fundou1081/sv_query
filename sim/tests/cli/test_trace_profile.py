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


def test_clock_reset_event_semantics():
    i = _profile("sync_fifo.data_out")["result"]["signals"][0]
    assert all(c["edge"] == "posedge" for c in i["clocks"])
    r = i["resets"][0]
    assert r["edge"] == "negedge"
    assert r["async"] is True
    assert r["active_low"] is True
    assert i["sequential"]["always"] is not None
    assert i["sequential"]["always"]["line"] > 0


def test_bit_fallback_metadata():
    i = _profile("sync_fifo.data_out[3]")["result"]["signals"][0]
    assert i["resolution"] == "bit_base_fallback"
    assert i["resolved_signal"] == "sync_fifo.data_out"
    assert i["bit"]["parent"] == "sync_fifo.data_out"
    assert i["bit"]["select"] == "3"
    assert i["bit"]["kind"] == "bit"
    assert i["bit"]["offset"] == 3


TYPES = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "types.sv"


def _profile_types(*signals):
    r = _run("trace", "profile", *signals, "-f", str(TYPES), "--json")
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_enum_type_metadata():
    t = _profile_types("top.st")["result"]["signals"][0]["type"]
    assert t["known"] is True
    assert t["is_enum"] is True
    assert t["name"] == "state_t"
    assert [v["name"] for v in t["enum_values"]] == ["IDLE", "RUN", "DONE"]


def test_struct_type_metadata():
    t = _profile_types("top.p")["result"]["signals"][0]["type"]
    assert t["is_struct"] is True
    assert t["bit_width"] == 8
    assert [(m["name"], m["offset"], m["width"]) for m in t["packed_members"]] == [
        ("a", 4, 4), ("b", 0, 4)]


def test_array_and_plain_type_metadata():
    arr = _profile_types("top.arr")["result"]["signals"][0]["type"]
    assert arr["known"] is True
    assert arr["is_array"] is True
    plain = _profile_types("top.y")["result"]["signals"][0]["type"]
    assert plain["known"] is True
    assert plain["name"] == "logic[7:0]"
    assert plain["packed_members"] == []


def test_sequential_stage_and_sample():
    s = _profile("sync_fifo.data_out")["result"]["signals"][0]["sequential"]
    assert s["stage_known"] is True
    assert isinstance(s["stage"], int)
    assert s["stage_source"] == "pipeline_detect"
    assert s["sample"] == "posedge sync_fifo.clk"
    assert s["sample_unknown_reason"] is None


def test_combinational_stage_unknown():
    s = _profile("sync_fifo.full")["result"]["signals"][0]["sequential"]
    assert s["stage"] is None
    assert s["stage_known"] is False
    assert s["stage_unknown_reason"] == "combinational"
    assert s["sample"] is None
    assert s["sample_unknown_reason"] == "combinational"
