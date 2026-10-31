"""[iter_335 / PLAN P39.1] waveform full-path lookup。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYNC = ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv"
GEN = ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_27_generate_loop.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def _lookup(tmp_path: Path, *paths: str, fixture=SYNC):
    f = tmp_path / "paths.txt"
    f.write_text("\n".join(paths))
    r = _run("trace", "lookup", "--paths-file", str(f), "-f", str(fixture), "--json")
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_exact_root_and_bit_parent(tmp_path):
    d = _lookup(tmp_path, "sync_fifo.data_out", "$root.sync_fifo.clk",
                "sync_fifo.data_out[3]")
    items = d["result"]["paths"]
    assert items[0]["canonical"] == "sync_fifo.data_out"
    assert items[0]["resolution"] == "exact"
    assert items[1]["canonical"] == "sync_fifo.clk"
    assert items[2]["resolution"] == "bit_parent"
    assert items[2]["canonical"] == "sync_fifo.data_out"
    assert items[2]["bit_suffix"] == "[3]"


def test_not_found_is_strict(tmp_path):
    d = _lookup(tmp_path, "sync_fifo.nope")
    item = d["result"]["paths"][0]
    assert item["found"] is False
    assert item["resolution"] == "not_found"
    assert item["canonical"] is None
    assert d["result"]["failed"] == 1


def test_generate_path(tmp_path):
    d = _lookup(tmp_path, "generate_loop.gen_accum[0].prod", fixture=GEN)
    item = d["result"]["paths"][0]
    assert item["found"] is True
    assert item["canonical"] == "generate_loop.gen_accum[0].prod"
