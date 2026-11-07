"""[P85] neighborhood runner: envelope parse + semantic alias scoring."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "tools" / "benchmark" / "run_neighborhood.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_neighborhood", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_extract_envelope_prefers_complete_answer():
    m = _load()
    text = (
        'tool output {"block": "packet.c_order"}\n'
        '{"task_id": "x", "answer": '
        '{"rand_vars": ["packet.addr", "packet.len", "packet.mode", "packet.payload"]}, '
        '"queries": []}'
    )
    d = m._extract_json(text)
    assert d["task_id"] == "x"
    assert d["answer"]["rand_vars"][0] == "packet.addr"


def test_semantic_accepts_instance_aliases_but_requires_payload():
    m = _load()
    task = next(t for t in m.TASKS if t["id"] == "complex_constraints")
    good = {
        "rand_vars": ["top.e.p.addr", "top.e.p.len", "top.e.p.mode", "top.e.p.payload"],
        "constraints": [{"id": "c_len"}, {"id": "c_mode"}, {"id": "c_order"}],
        "condition_vars": ["top.e.p.mode"], "both_addr_len_block": "c_order",
        "inherited": ["c_len"],
    }
    assert m.score_answer(task, good)["semantic"] is True
    bad = {
        "rand_vars": ["packet.addr", "packet.len", "packet.mode"],
        "constraints": ["c_len", "c_mode", "c_order"],
        "condition_vars": ["packet.mode"], "both_addr_len_block": "c_order",
        "inherited": ["c_len"],
    }
    assert m.score_answer(task, bad)["semantic"] is False
