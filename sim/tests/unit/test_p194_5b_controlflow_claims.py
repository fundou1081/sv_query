"""P194.5b — controlflow scope labeling and claim schema discoverability."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


def test_inline_condition_is_not_labeled_complete(tmp_path):
    sv = tmp_path / "cf.sv"
    sv.write_text(
        "module top(input logic [3:0] state_q, output logic ready_o);\n"
        "  localparam logic [3:0] TOP_IDLE = 4'd0;\n"
        "  assign ready_o = (state_q == TOP_IDLE);\n"
        "endmodule\n")
    proc = _run("controlflow", "analyze", "top.ready_o", "--file", str(sv))
    assert proc.returncode == 0, proc.stderr[-400:]
    result = json.loads(proc.stdout)["result"]
    assert result["condition_status"] == "not_modeled"
    assert result["condition_scope"] == "if_case_conditioned_drivers_only"
    assert any("not modeled" in warning for warning in result["warnings"])


def test_unconditional_assign_still_complete(tmp_path):
    sv = tmp_path / "plain.sv"
    sv.write_text(
        "module top(input logic a, output logic y); assign y = a; endmodule\n")
    proc = _run("controlflow", "analyze", "top.y", "--file", str(sv))
    assert proc.returncode == 0, proc.stderr[-400:]
    assert json.loads(proc.stdout)["result"]["condition_status"] == "complete"


def test_claim_schema_is_in_capabilities_and_compact():
    full = json.loads(_run("capabilities").stdout)["json_contract"]["claim_schema"]
    assert set(full["types"]) == {"driver", "path", "connection", "bit"}
    assert full["verdicts"] == ["verified", "contradicted", "unknown"]
    compact = json.loads(_run("capabilities", "--compact").stdout)
    assert compact["claim_types"] == ["driver", "path", "connection", "bit"]
    assert compact["claim_verdicts"] == ["verified", "contradicted", "unknown"]
