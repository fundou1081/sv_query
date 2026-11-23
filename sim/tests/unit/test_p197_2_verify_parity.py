"""P197.2 — CLI/session claim and zero-check consistency parity."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _cli(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *args, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def _fixture(tmp_path: Path) -> Path:
    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    return sv


def test_path_claim_verdict_matches_cli(tmp_path):
    from sv_query.graph_session import GraphSession

    sv = _fixture(tmp_path)
    claim = {"type": "path", "from": "top.a", "to": "top.y",
             "nodes": ["top.a", "top.y", "top.a"]}
    cli = _cli("verify", "claim", "--file", str(sv), "--claim", json.dumps(claim))
    session = GraphSession(file=str(sv)).verify_claim(claim)
    assert cli["result"]["status"] == "contradicted"
    assert session["status"] == cli["result"]["status"]


def test_bidirectional_path_claim_parity(tmp_path):
    from sv_query.graph_session import GraphSession

    sv = _fixture(tmp_path)
    claim = {"type": "path", "from": "top.a", "to": "top.y",
             "nodes": ["top.a", "top.y"], "bidirectional": True}
    cli = _cli("verify", "claim", "--file", str(sv), "--claim", json.dumps(claim))
    session = GraphSession(file=str(sv)).verify_claim(claim)
    assert cli["result"]["status"] == "contradicted"
    assert session["status"] == "contradicted"


def test_session_zero_connection_is_unknown(tmp_path):
    from sv_query.graph_session import GraphSession

    report = GraphSession(file=str(_fixture(tmp_path))).verify_consistency(
        checks=["connection"])
    assert report["verified"] is False
    assert report["unknown_checks"] == ["connection"]
    assert report["checks"][0]["checked"] == 0
    assert report["checks"][0]["status"] == "unknown"


def test_reciprocity_zero_check_is_unknown(tmp_path):
    sv = tmp_path / "empty.sv"
    sv.write_text("module top(); endmodule\n")
    data = _cli("verify", "consistency", "--file", str(sv),
                "--checks", "reciprocity")
    result = data["result"]
    assert result["verified"] is False
    assert result["unknown_checks"] == ["reciprocity"]
    assert result["checks"][0]["checked"] == 0
