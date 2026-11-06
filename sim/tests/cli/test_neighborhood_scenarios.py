"""[P84] neighborhood extraction: complex constraints + nested mux."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONS = "examples/interactive_debug/complex_constraints.sv"
MUX = "examples/interactive_debug/mux_neighborhood.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args, "--json"], capture_output=True,
                          text=True, timeout=60, cwd=str(ROOT))


def test_complex_constraint_condition_neighborhood():
    r = _run("trace", "constraints", "top.e.p.mode", "-f", CONS)
    assert r.returncode == 0, r.stderr[-300:]
    items = json.loads(r.stdout)["result"]["constraints"]
    c_mode = next(c for c in items if c["block"] == "packet.c_mode")
    assert "packet.mode" in c_mode["conditions"]
    assert "packet.len" in c_mode["vars"]

    r = _run("class", "packet", "--relations", "-f", CONS)
    rel = json.loads(r.stdout)["relations"]
    blocks = {b["id"] for b in rel["constraint_blocks"]}
    assert {"packet.c_addr", "packet.c_len", "packet.c_order",
            "packet.c_mode", "packet.c_payload"} <= blocks


def test_nested_mux_subgraph_neighborhood():
    r = _run("graph", "subgraph", "top.q", "-f", MUX,
             "--depth", "5", "--edge-kinds", "driver,connection,branch")
    assert r.returncode == 0, r.stderr[-300:]
    res = json.loads(r.stdout)["result"]
    nodes = {n["id"] for n in res["nodes"]}
    assert {
        "top.u.lo.ternary_sel[0]",
        "top.u.hi.ternary_sel[0]",
        "top.u.y.ternary_sel[1]",
        "top.u.sel[0]",
        "top.u.sel[1]",
    } <= nodes
    assert {"top.u.a", "top.u.b", "top.u.c", "top.u.d"} <= nodes

    r = _run("controlflow", "analyze", "top.u.y", "-f", MUX)
    cf = json.loads(r.stdout)["result"]
    assert cf["condition_status"] == "complete"
    assert {c["expr"] for d in cf["conditioned_drivers"] for c in d["conditions"]} == {
        "sel[1]", "!(sel[1])"
    }
