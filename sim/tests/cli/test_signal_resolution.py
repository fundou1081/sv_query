"""[iter_329 / PLAN P33.1] canonical signal identity + not_found/ambiguous。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = """
module child(input logic a, output logic y);
  assign y = a;
endmodule
module top(input logic a, output logic y);
  child u(.a(a), .y());
  assign y = a;
endmodule
"""


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def _json(tmp_path: Path, *args):
    p = tmp_path / "t.sv"
    p.write_text(SRC)
    r = _run(*args, "--file", str(p), "--json", "--no-cache")
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_exact_resolution(tmp_path):
    d = _json(tmp_path, "trace", "fanin", "top.y")
    s = d["result"]["signals"][0]
    assert d["ok"] is True
    assert s["resolution"] == "exact"
    assert s["resolved_signal"] == "top.y"


def test_relative_unique_resolution(tmp_path):
    d = _json(tmp_path, "trace", "fanout", "u.a")
    s = d["result"]["signals"][0]
    assert d["ok"] is True
    assert s["resolution"] == "relative"
    assert s["resolved_signal"] == "top.u.a"
    assert s["resolved_signal"].endswith(".a")


def test_ambiguous_lists_candidates(tmp_path):
    d = _json(tmp_path, "trace", "fanin", "a")
    assert d["ok"] is False
    err = d["errors"][0]
    assert err["error_code"] == "E_SIGNAL_AMBIGUOUS"
    s = d["result"]["signals"][0]
    assert s["resolution"] == "ambiguous"
    assert set(s["candidates"]) >= {"top.a", "top.u.a"}


def test_not_found_is_explicit(tmp_path):
    d = _json(tmp_path, "trace", "fanout", "top.nope")
    assert d["ok"] is False
    assert d["errors"][0]["error_code"] == "E_SIGNAL_NOT_FOUND"
    s = d["result"]["signals"][0]
    assert s["resolution"] == "not_found"
    assert s["resolved_signal"] is None
    assert s["count"] == 0


def test_impact_and_evidence_share_resolution(tmp_path):
    for cmd in (("trace", "impact"), ("trace", "evidence")):
        d = _json(tmp_path, *cmd, "top.nope")
        assert d["ok"] is False
        assert d["errors"][0]["error_code"] == "E_SIGNAL_NOT_FOUND"
        assert d["result"]["signals"][0]["resolution"] == "not_found"


def test_batch_partial_failure_keeps_good_signal(tmp_path):
    d = _json(tmp_path, "trace", "fanin", "--batch", "top.y,top.nope")
    assert d["ok"] is False
    sigs = d["result"]["signals"]
    assert sigs[0]["resolution"] == "exact"
    assert sigs[1]["resolution"] == "not_found"
    assert d["result"]["failed_signals"] == 1


def test_bit_base_fallback_keeps_bit_query(tmp_path):
    d = _json(tmp_path, "trace", "fanin", "top.y[3]")
    s = d["result"]["signals"][0]
    assert d["ok"] is True
    assert s["resolution"] == "bit_base_fallback"
    assert s["resolved_signal"] == "top.y[3]"
