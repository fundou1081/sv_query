"""[P76] interactive-debug follow-ups: canonical path / unmodeled control / class hints."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEEP = "examples/interactive_debug/deep_chain.sv"
RAND = "examples/interactive_debug/rand_coverage.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args, "--json"], capture_output=True,
                          text=True, timeout=60, cwd=str(ROOT))


def test_paths_canonical_chooses_maximal_variant():
    r = _run("paths", "top.din", "top.dout", "-f", DEEP,
             "--directed", "--canonical")
    assert r.returncode == 0, r.stderr[-300:]
    d = json.loads(r.stdout)
    assert d["canonical"] is True
    assert d["canonical_policy"] == "max_nodes_then_lexicographic"
    # P158.1: ternary select is a control edge, not a data segment.
    assert d["candidate_count"] == 1
    assert d["hop_count"] == 10
    assert d["path"][2] == "top.u_mid.u_stage.d"
    assert d["path"][3] == "top.u_mid.u_stage.u_leaf.d"


def test_controlflow_reads_port_ternary():
    r = _run("controlflow", "analyze", "top.u_mid.u_stage.u_leaf.d", "-f", DEEP)
    assert r.returncode == 0, r.stderr[-300:]
    res = json.loads(r.stdout)["result"]
    assert res["condition_status"] == "complete"
    assert any(c["expr"] == "sel" for d in res["conditioned_drivers"]
               for c in d["conditions"])


def test_controlflow_without_edges_is_unknown(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text("module top(input a, b, output y); assign y = a; endmodule\n")
    r = _run("controlflow", "analyze", "top.nope", "-f", str(p))
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["ok"] is False
    assert "signal not found" in data["error"]


def test_class_relative_name_and_instance_scope_hints():
    r = _run("trace", "constraints", "p.addr", "-f", RAND)
    assert r.returncode != 0
    d = json.loads(r.stdout)
    assert "top.e.p.addr" in d["hint"]
    assert d["suggestions"]

    r = _run("scope", "top.e", "-f", RAND)
    assert r.returncode != 0
    d = json.loads(r.stdout)
    assert "class instance" in d["errors"][0]["hint"]

    r = _run("trace", "coverpoints", "p.addr", "-f", RAND)
    assert r.returncode == 0
    d = json.loads(r.stdout)["result"]
    assert d["count"] == 0
    assert "top.e.p.addr" in d["hint"]
