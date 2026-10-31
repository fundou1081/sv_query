"""[iter_327 / PLAN P32] trace evidence 稳定性。

- always_ff/comb 驱动：source_text 是真正的 LHS 赋值行（不是 if 条件行）
- enclosing_always + enclosing_if 都存在
- continuous assign：source_location/source_text/enclosing_assign 一致
- 无 driver 的输入端口：字段稳定为空（不伪造证据）
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = PROJECT_ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv"


def _evidence(sig: str) -> dict:
    r = subprocess.run(
        ["sv_query", "trace", "evidence", sig, "-f", str(FIXTURE),
         "--json", "--no-cache"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    d = json.loads(r.stdout)
    return d["result"]["signals"][0]["evidence"]


class TestEvidenceStability:
    def test_always_assignment_line(self):
        ev = _evidence("sync_fifo.data_out")
        assert ev["source_text"] == "data_out  <= 8'd0;"
        assert ev["source_location"]["line_start"] == 30
        assert ev["enclosing_always"] is not None
        assert "always" in ev["enclosing_always"]["text"]
        assert ev["enclosing_if"] is not None
        assert ev["credibility_score"] == 1.0
        assert ev["is_verified"] is True

    def test_continuous_assign_line(self):
        ev = _evidence("sync_fifo.full")
        assert ev["source_text"] == "assign full = 1'b0;"
        assert ev["source_location"]["line_start"] == 23
        assert ev["enclosing_assign"] is not None
        assert "assign full" in ev["enclosing_assign"]["text"]

    def test_port_without_driver_is_empty(self):
        ev = _evidence("sync_fifo.push_data_i")
        assert ev["source_location"] is None
        assert ev["source_text"] == ""
        assert ev["enclosing_always"] is None
        assert ev["enclosing_assign"] is None
        assert ev["credibility_score"] == 0.0
