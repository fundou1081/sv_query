"""[P71] agent 可靠性: multi-top bit fallback + --top + explicit fields."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _setup(tmp_path: Path) -> Path:
    (tmp_path / "a.sv").write_text(
        "module top_a(input [7:0] bus, output [7:0] out); assign out = bus; endmodule\n")
    (tmp_path / "b.sv").write_text(
        "module top_b(input [7:0] bus, output [7:0] out); assign out = bus; endmodule\n")
    fl = tmp_path / "f.f"
    fl.write_text(f"{tmp_path / 'a.sv'}\n{tmp_path / 'b.sv'}\n")
    return fl


def _run(fl: Path, *args):
    return subprocess.run(["sv_query", *args, "--filelist", str(fl), "--json",
                           "--no-cache"], capture_output=True, text=True, timeout=60,
                          cwd=str(ROOT))


def test_multi_top_bit_is_flagged_not_rejected(tmp_path):
    fl = _setup(tmp_path)
    r = _run(fl, "drivers", "top_a.bus[3]")
    d = json.loads(r.stdout)
    assert r.returncode == 0
    s = d["result"]["signals"][0]
    assert s["top_modules"] == ["top_a", "top_b"]
    assert s["top_ambiguous"] is True
    assert s["bit_fallback"] is True
    assert s["resolution"] == "bit_base_fallback"


def test_bit_fallback_with_top_is_explicit(tmp_path):
    fl = _setup(tmp_path)
    r = _run(fl, "loads", "top_a.bus[3]", "--top", "top_a")
    assert r.returncode == 0, r.stderr[-300:]
    s = json.loads(r.stdout)["result"]["signals"][0]
    assert s["resolution"] == "bit_base_fallback"
    assert s["bit_fallback"] is True
    assert s["top_modules"] == ["top_a"]
    assert s["top_ambiguous"] is False


def test_covergroup_exposes_bin_names():
    r = subprocess.run(
        ["sv_query", "trace", "covergroups", "-f",
         "examples/interactive_debug/rand_coverage.sv", "--json"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    cg = json.loads(r.stdout)["result"]["covergroups"][0]
    bins = {b["name"] for cp in cg["coverpoints"] for b in cp["bin_details"]}
    assert bins == {"low", "high", "len_small", "len_large"}
