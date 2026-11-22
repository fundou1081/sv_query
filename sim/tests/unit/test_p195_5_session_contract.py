"""P195.5 — session docs/contract matches the actual GraphSession surface."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def test_session_contract_matches_handlers():
    from sv_query.graph_session import GraphSession
    from sv_query.session import (
        SESSION_CONTRACT,
        SESSION_QUERY_OPS,
        SESSION_UNSUPPORTED_OPS,
    )

    gs = GraphSession(filelist=FIXTURE)
    assert set(gs.handlers()) == set(SESSION_QUERY_OPS)
    assert "version" in SESSION_CONTRACT["builtin_ops"]
    assert SESSION_UNSUPPORTED_OPS == frozenset({"stats"})
    assert "verify_claim" in SESSION_QUERY_OPS
    assert set(SESSION_CONTRACT["ops"]) == set(SESSION_QUERY_OPS)


def test_capabilities_exposes_session_contract():
    from sv_query.cli._registry import to_json
    from sv_query.session import SESSION_CONTRACT

    contract = to_json()["json_contract"]["session"]
    assert contract == SESSION_CONTRACT
    assert "stdio-json-lines" == contract["transport"]


def test_stdio_stats_is_explicitly_unsupported(tmp_path):
    env = {"SVQ_CACHE_DIR": str(tmp_path), **__import__("os").environ}
    proc = subprocess.Popen(
        [sys.executable, "run_cli.py", "session", "--serve", "--filelist", FIXTURE],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=env,
    )
    stdout, stderr = proc.communicate('{"op":"stats"}\n', timeout=120)
    assert proc.returncode == 0, stderr[-400:]
    response = json.loads(stdout.strip().splitlines()[0])
    assert response["ok"] is False
    assert response["error_code"] == "E_UNSUPPORTED_OP"
