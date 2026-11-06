"""[P77] port-map ternary -> OP_TERNARY + BRANCH_* subgraph."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEEP = "examples/interactive_debug/deep_chain.sv"
TARGET = "top.u_mid.u_stage.u_leaf.d"


def _run(*args):
    env = os.environ.copy()
    env["SVQ_CACHE_DIR"] = tempfile.mkdtemp(prefix="svq-porttern-")
    return subprocess.run(["sv_query", *args, "--json"], capture_output=True,
                          text=True, timeout=60, cwd=str(ROOT), env=env)


def test_port_ternary_creates_op_node():
    r = _run("graph", "nodes", "-f", DEEP, "--kind", "OP_TERNARY")
    assert r.returncode == 0, r.stderr[-300:]
    ids = [n["id"] for n in json.loads(r.stdout)["result"]["nodes"]]
    assert ids == [f"{TARGET}.ternary_sel"], ids


def test_port_ternary_controlflow_is_complete():
    r = _run("controlflow", "analyze", TARGET, "-f", DEEP)
    assert r.returncode == 0, r.stderr[-300:]
    res = json.loads(r.stdout)["result"]
    assert res["condition_status"] == "complete"
    assert any(c["expr"] == "sel" for d in res["conditioned_drivers"]
               for c in d["conditions"])


def test_port_ternary_fanin_has_conditional_driver():
    r = _run("trace", "fanin", TARGET, "-f", DEEP, "--depth", "1")
    assert r.returncode == 0, r.stderr[-300:]
    sig = json.loads(r.stdout)["result"]["signals"][0]
    by_id = {d["id"]: d for d in sig["drivers"]}
    assert "top.u_mid.u_stage.d" in by_id
    assert "sel" in by_id["top.u_mid.u_stage.d"]["condition"]
