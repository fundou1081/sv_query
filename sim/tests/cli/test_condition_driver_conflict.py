"""[iter_349 / PLAN P48] 条件化简 + driver conflict。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = """
module top(input sel, input a, b, output reg y);
  always_comb if (sel) y = a; else y = b;
endmodule
"""


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def test_if_else_is_proven_exclusive_2state(tmp_path):
    p = tmp_path / "t.sv"; p.write_text(SRC)
    r = _run("trace", "fanin", "top.y", "-f", str(p), "--json", "--no-cache")
    assert r.returncode == 0, r.stderr[-300:]
    d = json.loads(r.stdout)
    sig = d["result"]["signals"][0]
    assert {x["condition"] for x in sig["drivers"]} == {"sel", "!sel"}
    assert sig["driver_conflict"] == "proven_exclusive_2state"
    assert sig["driver_conflict_analysis"]["four_state_safe"] is False
    assert sig["drivers"][0]["condition_simplified"] in ("sel", "!sel")
