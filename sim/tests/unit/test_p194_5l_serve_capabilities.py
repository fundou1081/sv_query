"""P194.5l — `session --serve` supports capabilities alongside graph ops."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_serve_capabilities_and_graph_nodes(tmp_path):
    sv = tmp_path / "serve.sv"
    sv.write_text(
        "module top(input logic a, output logic y);\n"
        "  assign y = a;\n"
        "endmodule\n")
    requests = [
        {"op": "capabilities", "compact": True},
        {"op": "graph_nodes", "match": "top.y"},
        {"op": "version"},
    ]
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "session", "--serve", "-f", str(sv)],
        cwd=ROOT, input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    rows = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert [r["op"] for r in rows] == ["capabilities", "graph_nodes", "version"]
    assert all(r["ok"] is True for r in rows), rows
    assert rows[0]["result"]["schema_version"] == "1"
    assert any(n["id"].endswith("top.y") for n in rows[1]["result"]["nodes"])
