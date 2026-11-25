"""P194.2b — graph-only commands use the graph cache with explicit status."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _run(*args: str, cache: Path) -> dict:
    env = dict(os.environ, SVQ_CACHE_DIR=str(cache))
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *args, "--filelist", FIXTURE, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def test_graph_nodes_cold_then_hit_then_no_cache(tmp_path):
    cold = _run("graph", "nodes", cache=tmp_path)
    warm = _run("graph", "nodes", cache=tmp_path)
    assert cold["params"]["cache"]["status"] == "miss"
    assert warm["params"]["cache"]["status"] == "hit"
    assert warm["params"]["cache"]["capabilities"] == ["graph", "mig"]
    assert [n["id"] for n in cold["result"]["nodes"]] == [n["id"] for n in warm["result"]["nodes"]]

    off = _run("graph", "nodes", "--no-cache", cache=tmp_path)
    assert off["params"]["cache"]["status"] == "disabled"
    assert len(off["result"]["nodes"]) == len(cold["result"]["nodes"])


def test_graph_edges_share_same_graph_cache(tmp_path):
    nodes = _run("graph", "nodes", cache=tmp_path)
    edges = _run("graph", "edges", cache=tmp_path)
    assert nodes["params"]["cache"]["key"] == edges["params"]["cache"]["key"]
    assert edges["params"]["cache"]["status"] == "hit"
    assert len(edges["result"]["edges"]) > 0
