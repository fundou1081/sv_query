"""P199.1 — every fanin surface uses the shared data-edge policy."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *args, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def _fixture(tmp_path: Path) -> Path:
    sv = tmp_path / "clock_data.sv"
    sv.write_text(
        "module top(input logic clk, input logic [2:0] d, output reg [31:0] q);\n"
        "  always @(posedge clk) q[14:12] <= d;\n"
        "endmodule\n")
    return sv


def test_drivers_depth1_excludes_clock(tmp_path):
    sv = _fixture(tmp_path)
    data = _run("drivers", "top.q[14:12]", "-f", str(sv), "--depth", "1")
    ids = {x["id"] for x in data["result"]["signals"][0]["drivers"]}
    assert "top.d" in ids
    assert "top.clk" not in ids


def test_verify_driver_rejects_clock(tmp_path):
    sv = _fixture(tmp_path)
    data = _run(
        "verify", "claim", "--claim",
        '{"type":"driver","signal":"top.q[14:12]","driver":"top.clk"}',
        "-f", str(sv))
    assert data["result"]["status"] == "contradicted"


def test_recursive_fanin_also_excludes_clock(tmp_path):
    sv = _fixture(tmp_path)
    data = _run("drivers", "top.q[14:12]", "-f", str(sv))
    ids = {x["id"] for x in data["result"]["signals"][0]["drivers"]}
    assert "top.clk" not in ids


def test_snapshot_evidence_ignores_clock_only_edges(tmp_path):
    from sv_query.cli.core.semantic.trace_evidence import _snapshot_edge_evidence
    from sv_query.trace.core.graph.contracts import is_data_edge
    from sv_query.trace.core.graph.models import (
        EdgeKind,
        NodeKind,
        SignalGraph,
        SourceLocation,
        TraceEdge,
        TraceNode,
    )

    graph = SignalGraph()
    graph.add_trace_node(TraceNode(id="top.clk", name="clk", module="top",
                                   kind=NodeKind.PORT_IN, width=(0, 0)))
    graph.add_trace_node(TraceNode(id="top.q", name="q", module="top",
                                   kind=NodeKind.REG, width=(0, 0)))
    edge = TraceEdge(src="top.clk", dst="top.q", kind=EdgeKind.CLOCK,
                     source_location=SourceLocation(
                         file="x.sv", line_start=2, line_end=2, column=0))
    graph.add_trace_edge(edge)
    assert is_data_edge(edge) is False
    assert _snapshot_edge_evidence(graph, "top.q") is None
