"""[iter_346 / PLAN P45] 模拟 waveform path 端到端联调。

覆盖: $root / interface / modport / generate / struct member / bit parent。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "waveform_end_to_end.sv"
PATHS = [
    "$root.top.clk",
    "top.genblk1[0].x",
    "top.gen_if.y",
    "top.u_if.data",
    "top.u_prod.m.data",
    "top.p.a",
    "top.gen_sig[3]",
    "top.not_here",
]


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=120, cwd=str(ROOT))


def test_manifest_end_to_end(tmp_path):
    f = tmp_path / "paths.txt"
    f.write_text("\n".join(PATHS))
    r = _run("trace", "manifest", "--paths-file", str(f), "-f", str(FIXTURE), "--json")
    assert r.returncode == 0, r.stderr[-500:]
    d = json.loads(r.stdout)
    assert d["result"]["total"] == len(PATHS)
    assert d["result"]["found"] == len(PATHS) - 1
    assert d["result"]["failed"] == 1
    by_path = {e["waveform_path"]: e for e in d["result"]["entries"]}

    clk = by_path["$root.top.clk"]
    assert clk["found"] is True
    assert clk["lookup"]["canonical"] == "top.clk"

    gen = by_path["top.genblk1[0].x"]
    assert gen["lookup"]["resolution"] == "exact"

    named = by_path["top.gen_if.y"]
    assert named["found"] is True

    iface = by_path["top.u_if.data"]
    assert "top.u_prod.m.data" in iface["lookup"]["aliases"]

    modport = by_path["top.u_prod.m.data"]
    assert "top.u_if.data" in modport["lookup"]["aliases"]

    member = by_path["top.p.a"]
    assert member["profile"]["type"]["known"] is True
    assert member["profile"]["type"]["member_of"] == "pair_t"

    bit = by_path["top.gen_sig[3]"]
    assert bit["lookup"]["resolution"] == "bit_parent"
    assert bit["profile"]["bit"]["select"] == "3"

    missing = by_path["top.not_here"]
    assert missing["found"] is False
    assert missing["profile"] is None
