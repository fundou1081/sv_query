"""[P86] shared canonical + semantic scoring."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "tools" / "benchmark" / "scoring.py"


def _load():
    spec = importlib.util.spec_from_file_location("bench_scoring", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_direct_canonical_only():
    m = _load()
    task = {"id": "axi", "ground_truth": {"drivers": ["top.a"], "count": 1}}
    s = m.score_answer(task, {"drivers": ["top.a"], "count": 1})
    assert s["canonical"] is True
    assert s["semantic"] is None


def test_constraint_source_alias_semantic_only():
    m = _load()
    task = {"id": "complex_constraints", "ground_truth": {
        "rand_vars": ["packet.addr", "packet.len", "packet.mode", "packet.payload"],
        "constraints": ["packet.c_len", "packet.c_mode", "packet.c_order"],
        "condition_vars": ["packet.mode"],
        "both_addr_len_block": "packet.c_order",
        "inherited": ["packet.c_len"],
    }}
    ans = {
        "rand_vars": ["top.e.p.addr", "top.e.p.len", "top.e.p.mode", "top.e.p.payload"],
        "constraints": [{"id": "base_item::c_len"}, {"id": "packet::c_mode"},
                        {"id": "packet::c_order"}],
        "condition_vars": ["top.e.p.mode"], "both_addr_len_block": "base::c_order",
        "inherited": ["base_item::c_len"],
    }
    s = m.score_answer(task, ans)
    assert s["canonical"] is False
    assert s["semantic"] is True


def test_mux_source_signal_alias_semantic_only():
    m = _load()
    task = {"id": "mux_neighborhood", "ground_truth": {
        "mux_nodes": ["top.u.lo.ternary_sel[0]", "top.u.hi.ternary_sel[0]",
                      "top.u.y.ternary_sel[1]"],
        "selects": ["top.u.sel[0]", "top.u.sel[1]"],
        "data_sources": ["top.u.a", "top.u.b", "top.u.c", "top.u.d"],
        "register": "top.q",
    }}
    ans = {
        "mux_nodes": ["top.u.lo", "top.u.hi", "top.u.y"],
        "selects": ["top.sel[0]", "top.sel[1]"],
        "data_sources": ["top.a", "top.b", "top.c", "top.d"],
        "register": "top.q",
    }
    s = m.score_answer(task, ans)
    assert s["canonical"] is False
    assert s["semantic"] is True


def test_semantic_missing_rand_var_fails():
    m = _load()
    task = {"id": "complex_constraints", "ground_truth": {}}
    ans = {"rand_vars": ["packet.addr", "packet.len", "packet.mode"],
           "constraints": ["c_len", "c_mode", "c_order"],
           "condition_vars": ["packet.mode"], "both_addr_len_block": "c_order",
           "inherited": ["c_len"]}
    assert m.semantic_score(task, ans)[0] is False
