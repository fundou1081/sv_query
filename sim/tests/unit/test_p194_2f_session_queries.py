"""P194.2f — session coverage for instances/scope/verify_claim/verify_consistency."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _scheduler(tmp_path) -> "object":
    from sv_query.graph_session import GraphSession
    os.environ["SVQ_CACHE_DIR"] = str(tmp_path / "cache")
    return GraphSession(filelist=FIXTURE)


def test_instances_and_scope_use_the_same_graph(tmp_path):
    gs = _scheduler(tmp_path)
    listed = gs.instances()
    assert listed["count"] > 0
    path = listed["instances"][0]["full_path"]
    scope = gs.scope(path)
    assert scope["scope"] == path
    assert scope["module_type"]
    assert isinstance(scope["signals"], list)
    assert gs.graph_nodes()["total"] > 0


def test_verify_claim_and_consistency(tmp_path):
    from sv_query.graph_session import GraphSession

    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    gs = GraphSession(file=str(sv))
    assert gs.verify_claim(
        {"type": "driver", "signal": "top.y", "driver": "top.a"})["status"] == "verified"
    assert gs.verify_claim(
        {"type": "path", "from": "top.a", "to": "top.y"})["status"] == "verified"
    report = _scheduler(tmp_path).verify_consistency(checks=["connection"])
    assert set(report) >= {"verified", "coverage_complete", "unknown_checks"}
    assert report["unknown_checks"] == []


def test_stdio_serves_new_ops(tmp_path):
    env = {**os.environ, "SVQ_CACHE_DIR": str(tmp_path / "cache")}
    proc = subprocess.Popen(
        [sys.executable, "run_cli.py", "session", "--serve", "--filelist", FIXTURE],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=env,
    )
    requests = [
        {"op": "instances"},
        {"op": "scope", "path": "Scheduler_minimal.SourceA_dut"},
        {"op": "verify_consistency", "checks": ["connection"]},
    ]
    stdout, stderr = proc.communicate(
        "".join(json.dumps(r) + "\n" for r in requests), timeout=120)
    assert proc.returncode == 0, stderr[-400:]
    lines = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    assert [line["op"] for line in lines] == [r["op"] for r in requests]
    assert all(line["ok"] is True for line in lines)
