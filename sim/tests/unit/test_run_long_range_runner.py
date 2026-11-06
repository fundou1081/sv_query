"""[P81] long-range runner: design mapping / workspace isolation / JSON parse."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "tools" / "benchmark" / "run_long_range.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_long_range", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_design_mapping():
    m = _load()
    assert m._design("axi_araddr_neighbors") == "axi"
    assert m._design("serv_clk_path") == "serv"
    assert m._design("pico_mem_valid_fanout") == "pico"


def test_extract_json_from_fenced_block():
    m = _load()
    d = m._extract_json('thinking\n```json\n{"task_id":"x","answer":{"count":1}}\n```')
    assert d == {"task_id": "x", "answer": {"count": 1}}


def test_workspace_filelist_is_local(tmp_path):
    m = _load()
    if not (Path("/tmp/lr_pilot/axi")).is_dir():
        pytest.skip("pilot source not available")
    fl = m._copy_design("axi", tmp_path)
    text = fl.read_text()
    assert "/tmp/lr_pilot" not in text
    assert str(tmp_path) in text
    assert (tmp_path / "axi" / "axi_adapter.v").exists()


def test_direct_query_spec_uses_depth_one():
    m = _load()
    task = {"query": {"cmd": "fanout", "signal": "x"}, "ground_truth": {"loads": []}}
    cmds = m._query_spec(task, Path("design.f"))
    assert cmds[0][:5] == ["sv_query", "loads", "x", "--depth", "1"]
    assert "--filelist" in cmds[0]


def test_fact_check_matches_pico_ground_truth(tmp_path):
    m = _load()
    import json
    tasks = json.loads((ROOT / "tools" / "benchmark" / "long_range_tasks.json").read_text())["tasks"]
    task = next(t for t in tasks if t["id"] == "pico_adapter_mem_valid_fanout")
    input_path = m._copy_design("pico", tmp_path)
    ok, detail = m._fact_check(task, input_path, tmp_path)
    assert ok, detail


def test_fact_check_serv_path(tmp_path):
    m = _load()
    import json
    tasks = json.loads((ROOT / "tools" / "benchmark" / "long_range_tasks.json").read_text())["tasks"]
    task = next(t for t in tasks if t["id"] == "serv_clk_path")
    input_path = m._copy_design("serv", tmp_path)
    ok, detail = m._fact_check(task, input_path, tmp_path)
    assert ok, detail
