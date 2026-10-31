"""[iter_333 / PLAN P37.1] per-driver / per-hop evidence。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYNC = ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv"
BITSLICE = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "bitslice.sv"


def _json(*args):
    r = subprocess.run(["sv_query", *args], capture_output=True, text=True,
                       timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_fanin_per_driver_evidence():
    d = _json("trace", "fanin", "sync_fifo.reg_stage1", "-f", str(SYNC),
              "--evidence", "--json", "--no-cache")
    drivers = d["result"]["signals"][0]["drivers"]
    evs = [x["evidence"] for x in drivers if x.get("evidence")]
    assert evs
    assert {"kind", "assign_type", "condition", "expression", "file", "line"} <= set(evs[0])
    assert any(e["file"] and e["line"] for e in evs)


def test_fanout_per_load_evidence():
    d = _json("trace", "fanout", "sync_fifo.reg_stage1", "-f", str(SYNC),
              "--evidence", "--json", "--no-cache")
    loads = d["result"]["signals"][0]["loads"]
    evs = [x["evidence"] for x in loads if x.get("evidence")]
    assert evs
    assert any(e["file"] and e["line"] for e in evs)


def test_paths_per_hop_evidence():
    d = _json("paths", "top.a", "top.y", "-f", str(BITSLICE),
              "--evidence", "--json")
    assert d["found"] is True
    assert len(d["edge_evidence"]) == len(d["path"]) - 1
    assert any(e and e.get("kind") for e in d["edge_evidence"])


def test_default_output_has_no_evidence_field():
    d = _json("trace", "fanin", "sync_fifo.reg_stage1", "-f", str(SYNC),
              "--json", "--no-cache")
    assert all("evidence" not in x for x in d["result"]["signals"][0]["drivers"])
