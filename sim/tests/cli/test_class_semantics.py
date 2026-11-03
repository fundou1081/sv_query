"""[iter_365 / PLAN P63] class/constraint/covergroup CLI。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT / "sim" / "tests" / "fixtures" / "mixed_corpus" / "env_nested_constraint.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args, "--json"], capture_output=True,
                          text=True, timeout=90, cwd=str(ROOT))


def _json(*args):
    r = _run(*args)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)


def test_class_relations_constraints_and_covergroups():
    packet = _json("class", "packet", "--relations", "-f", str(FIX))["relations"]
    blocks = {b["id"]: b for b in packet["constraint_blocks"]}
    assert blocks["packet.c_addr"]["vars"] == ["packet.addr"]
    assert blocks["packet.c_addr"]["expr_count"] == 1

    env = _json("class", "tb_env", "--relations", "-f", str(FIX))["relations"]
    cgs = {cg["name"]: cg for cg in env["covergroups"]}
    assert cgs["cg_env"]["in_class"] == "tb_env"
    assert cgs["cg_env"]["coverpoints"] == ["cp_p"]


def test_trace_constraints_type_and_instance():
    type_q = _json("trace", "constraints", "packet.addr", "-f", str(FIX))
    assert type_q["result"]["count"] == 1
    assert type_q["result"]["constraints"][0]["block"] == "packet.c_addr"

    inst_q = _json("trace", "constraints", "top.e.p.addr", "-f", str(FIX))
    assert inst_q["result"]["resolved"] == "top.e.p.addr"
    assert inst_q["result"]["constraints"][0]["vars"] == ["packet.addr"]


def test_trace_constraints_unknown_is_error():
    r = _run("trace", "constraints", "packet.nope", "-f", str(FIX))
    assert r.returncode != 0
    assert json.loads(r.stdout)["ok"] is False


def test_trace_covergroups_list():
    d = _json("trace", "covergroups", "-f", str(FIX))
    assert d["result"]["count"] == 1
    cg = d["result"]["covergroups"][0]
    assert cg["name"] == "cg_env" and cg["in_class"] == "tb_env"
    assert cg["coverpoints"][0]["signal"] == "p.addr"


def test_trace_coverpoints_reverse():
    d = _json("trace", "coverpoints", "top.e.p.addr", "-f", str(FIX))
    assert d["result"]["count"] == 1
    m = d["result"]["matches"][0]
    assert (m["covergroup"], m["coverpoint"], m["instance"]) == (
        "cg_env", "cp_p", "top.e")


def test_trace_covergroup_sampling_and_rand():
    d = _json("trace", "covergroup", "cg_env", "--instance", "top.e", "-f", str(FIX))
    sample = d["result"]["samples"][0]
    assert sample["sampled"] == ["top.e.p.addr"]
    assert sample["drivers"] == ["top.din"]

    r = _json("trace", "covergroup", "cg_env", "--instance", "top.e",
              "--rand", "-f", str(FIX))
    link = r["result"]["links"][0]
    assert link["property"] == "top.e.p.addr"
    assert link["constraints"][0]["block"] == "packet.c_addr"


def test_trace_covergroup_unknown_is_error():
    r = _run("trace", "covergroup", "nope", "-f", str(FIX))
    assert r.returncode != 0
    assert json.loads(r.stdout)["ok"] is False
