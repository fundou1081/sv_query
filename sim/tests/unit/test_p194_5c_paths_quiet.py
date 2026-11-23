"""P194.5c — session/CLI path view parity and JSON-mode quiet."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=120, env=env,
    )


def test_json_mode_is_quiet_by_default_and_verbose_restores(tmp_path):
    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    env = dict(os.environ, SVQ_CACHE_DIR=str(tmp_path / "cache"))
    quiet = _run("drivers", "top.y", "--file", str(sv), "--json", "--no-cache",
                 env=env)
    assert quiet.returncode == 0
    assert quiet.stderr == ""
    verbose = _run("drivers", "top.y", "--file", str(sv), "--json", "--no-cache",
                   "--verbose", env=env)
    assert verbose.returncode == 0
    assert verbose.stderr != ""


def test_session_paths_match_cli_for_same_direction(tmp_path):
    from sv_query.graph_session import GraphSession

    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    cli = _run("paths", "top.a", "top.y", "--file", str(sv), "--json",
               "--directed")
    assert cli.returncode == 0, cli.stderr[-400:]
    cli_data = json.loads(cli.stdout)
    session = GraphSession(file=str(sv)).paths("top.a", "top.y", directed=True)
    assert session["directed"] is True
    assert session["mode"] == "data"
    assert session["found"] == cli_data["found"]
    assert session["hop_count"] == cli_data["hop_count"]
    assert session["path"] == cli_data["path"]
