"""P198.5 — CLI and GraphSession bit-query parity for shift fanin/fanout."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _fixture(tmp_path: Path) -> Path:
    sv = tmp_path / "shift.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [9:0] y);\n"
        "  assign y = a << 4'd2;\n"
        "endmodule\n")
    return sv


def _cli(*args: str) -> dict:
    p = subprocess.run([sys.executable, "run_cli.py", *args, "--json", "--compact",
                        "--no-cache"], cwd=ROOT, capture_output=True, text=True,
                       timeout=120)
    assert p.returncode == 0, p.stderr[-400:]
    return json.loads(p.stdout)["result"]


def test_cli_session_bit_fanin_parity(tmp_path):
    from sv_query.graph_session import GraphSession

    sv = _fixture(tmp_path)
    cli = _cli("drivers", "top.y[2]", "--file", str(sv))["signals"][0]
    session = GraphSession(file=str(sv)).drivers("top.y[2]")
    assert session["count"] == cli["count"] == 1
    assert [d["id"] for d in session["drivers"]] == [d["id"] for d in cli["drivers"]]


def test_cli_session_bit_fanout_parity(tmp_path):
    from sv_query.graph_session import GraphSession

    sv = _fixture(tmp_path)
    cli = _cli("loads", "top.a[0]", "--file", str(sv))["signals"][0]
    session = GraphSession(file=str(sv)).loads("top.a[0]")
    assert session["count"] == cli["count"]
    assert {d["id"] for d in session["loads"]} == {d["id"] for d in cli["loads"]}
