"""P194.3 — stable Python query facade and lazy package exports."""
from __future__ import annotations

import subprocess
import sys

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


def test_query_client_executes_multiple_ops(tmp_path):
    from sv_query import open_query

    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    with open_query(file=str(sv)) as client:
        assert client.execute({"op": "graph_nodes"})["result"]["total"] == 2
        assert client.execute(
            {"op": "verify_claim", "claim": {"type": "driver",
                                             "signal": "top.y", "driver": "top.a"}}
        )["result"]["status"] == "verified"


def test_query_client_close_is_idempotent_and_guarded(tmp_path):
    from sv_query import QueryClient

    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    client = QueryClient(file=str(sv))
    client.close()
    client.close()
    with pytest.raises(RuntimeError, match="closed"):
        client.execute({"op": "graph_nodes"})


def test_package_import_does_not_eagerly_load_engine():
    code = (
        "import sys, sv_query; "
        "assert 'sv_query.trace' not in sys.modules, 'engine eagerly imported'; "
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_deprecation_policy_document_is_present():
    text = (ROOT / "docs/dev/API_FACADE.md").read_text(encoding="utf-8")
    assert "QueryClient" in text
    assert "DeprecationWarning" in text
    assert "trace.*" in text
