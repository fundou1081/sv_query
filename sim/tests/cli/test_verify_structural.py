"""[iter_363 / PLAN P61] verify structural findings。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BAD = """
module leaf(input a, b, c, d, output y);
  assign y = a & b & c & d;
endmodule
module top(input a, b, c, d, output y0, y1);
  leaf u0(.a(a), .b(b), .c(c), .d(d), .y(y0));
  leaf u1(.a(b), .y(y1));
endmodule
"""
CLEAN = """
module leaf(input a, b, output y);
  assign y = a & b;
endmodule
module top(input a, b, c, d, output y0, y1);
  leaf u0(.a(a), .b(b), .y(y0));
  leaf u1(.a(c), .b(d), .y(y1));
endmodule
"""


def _run(tmp_path: Path, src: str, *args: str):
    sv = tmp_path / "t.sv"
    sv.write_text(src)
    return subprocess.run(
        ["sv_query", "verify", "structural", "-f", str(sv), *args, "--json"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )


def _data(tmp_path: Path, src: str, *args: str) -> dict:
    r = _run(tmp_path, src, *args)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)


def test_structural_missing_port(tmp_path):
    d = _data(tmp_path, BAD)
    f = d["result"]["findings"]
    assert len(f) == 3
    assert {x["check"] for x in f} == {"symmetry.port_set"}
    assert {x["actual"]["missing_instances"][0] for x in f} == {"top.u1"}
    assert all(x["confidence"] == "medium" for x in f)
    assert all(x["seeds"] and x["subgraph"]["seeds"] for x in f)


def test_structural_clean_symmetric(tmp_path):
    d = _data(tmp_path, CLEAN)
    assert d["result"]["findings"] == []
    assert d["result"]["checks"][0]["status"] == "pass"
    assert d["result"]["verified"] is True
    assert d["result"]["coverage_complete"] is True
    assert d["result"]["coverage"]["groups_checked"] == 1


def test_structural_no_comparable_groups_is_unknown(tmp_path):
    d = _data(tmp_path, "module top(input a, output y); assign y = a; endmodule")
    assert d["result"]["checks"][0]["status"] == "unknown"
    assert d["result"]["verified"] is False
    assert d["result"]["unknown_checks"] == ["symmetry"]
    assert d["result"]["coverage"]["groups_checked"] == 0


def test_structural_max_findings_truncation(tmp_path):
    d = _data(tmp_path, BAD, "--max-findings", "2")
    assert d["result"]["total"] == 2
    assert d["result"]["truncated"] is True
    assert d["result"]["coverage_complete"] is False
    assert d["result"]["partial_checks"] == ["symmetry"]
    assert d["result"]["verified"] is False


def test_structural_subgraph_spec_is_runnable(tmp_path):
    d = _data(tmp_path, BAD)
    f = d["result"]["findings"][0]
    sv = tmp_path / "t.sv"
    cmd = ["sv_query", "graph", "subgraph", *f["subgraph"]["seeds"],
           "-f", str(sv), "--depth", str(f["subgraph"]["depth"]),
           "--direction", f["subgraph"]["direction"],
           "--edge-kinds", ",".join(f["subgraph"]["edge_kinds"]), "--json"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-500:]
    assert json.loads(r.stdout)["ok"] is True
