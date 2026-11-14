"""P171.7: dataflow timing_risk must carry an explicit heuristic model label."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_dataflow_reports_risk_model():
    p = subprocess.run(
        [sys.executable, str(ROOT / "run_cli.py"), "dataflow", "analyze",
         "top.data", "top.dout", "-f", str(ROOT / "sim/test_simple.sv"),
         "--json", "-q"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    )
    result = json.loads(p.stdout)["result"]
    assert result["timing_risk"] in {"safe", "low", "medium", "high", "critical"}
    assert result["risk_model"] == "heuristic_v1_uncalibrated"
