"""[iter_348 / PLAN P47] class member 语义候选（UVM testbench）。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OOP = ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_35_class_oop.sv"
ENV = ROOT / "sim" / "tests" / "fixtures" / "mixed_corpus" / "env_nested_constraint.sv"
NESTED = ROOT / "sim" / "tests" / "fixtures" / "mixed_corpus" / "param_class_nested.sv"


def _member(cls: str, member: str, fixture: Path) -> dict:
    r = subprocess.run(["sv_query", "class", cls, "--member", member,
                        "-f", str(fixture), "--json"],
                       capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_unused_member_candidate_is_listed():
    d = _member("packet", "data", OOP)
    assert d["count"] == 0
    assert d["candidate_count"] == 1
    c = d["candidates"][0]
    assert c["canonical_id"] == "top.pkt.data"
    assert c["in_graph"] is False


def test_uvm_nested_instance_member_candidate():
    d = _member("packet", "addr", ENV)
    assert d["candidate_count"] == 1
    c = d["candidates"][0]
    assert c["canonical_id"] == "top.e.p.addr"
    assert c["class_instance"] == "top.e.p"
    assert c["in_graph"] is True


def test_nested_class_member_candidate():
    d = _member("inner", "val", NESTED)
    assert d["candidate_count"] == 1
    assert d["candidates"][0]["canonical_id"] == "top.p.i.val"
    assert d["candidates"][0]["in_graph"] is True
