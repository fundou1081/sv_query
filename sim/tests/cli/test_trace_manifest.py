"""[iter_341 / PLAN P41.2] waveform manifest：path → canonical + profile。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYNC = ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def test_manifest_mixed_paths():
    r = _run("trace", "manifest", "--path", "sync_fifo.data_out",
             "--path", "sync_fifo.data_out[3]", "--path", "sync_fifo.nope",
             "-f", str(SYNC), "--json")
    assert r.returncode == 0, r.stderr[-300:]
    d = json.loads(r.stdout)
    assert d["result"]["total"] == 3
    assert d["result"]["found"] == 2
    assert d["result"]["failed"] == 1
    good = d["result"]["entries"][0]
    assert good["found"] is True
    assert good["lookup"]["canonical"] == "sync_fifo.data_out"
    assert good["profile"]["type"]["known"] is True
    assert good["profile"]["sequential"]["sample"] == "posedge sync_fifo.clk"


def test_manifest_bit_parent_and_missing():
    r = _run("trace", "manifest", "--path", "sync_fifo.data_out[3]",
             "--path", "sync_fifo.nope", "-f", str(SYNC), "--json")
    d = json.loads(r.stdout)
    bit = d["result"]["entries"][0]
    assert bit["lookup"]["resolution"] == "bit_parent"
    assert bit["profile"]["bit"]["select"] == "3"
    missing = d["result"]["entries"][1]
    assert missing["found"] is False
    assert missing["profile"] is None
