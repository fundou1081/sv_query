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
        assert ev["source_text"] == "if (rd_en) data_out <= reg_stage1;"
        assert ev["source_location"]["line_start"] == 33
        assert ev["enclosing_always"] is not None
        assert "always" in ev["enclosing_always"]["text"]
        assert ev["enclosing_if"] is not None
        assert ev["credibility_score"] == 1.0
        assert ev["is_verified"] is True

    def test_multi_statement_branch_assignment_line(self):
        ev = _evidence("sync_fifo.reg_stage1")
        assert ev["source_text"] == "if (wr_en) reg_stage1 <= push_data_i;"
        assert ev["source_location"]["line_start"] == 32
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


def test_reset_branch_falls_back_to_functional_assignment():
    fixture = PROJECT_ROOT / "sim" / "test_simple.sv"
    r = subprocess.run(
        ["sv_query", "trace", "evidence", "top.dout", "-f", str(fixture),
         "--json", "--no-cache"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    ev = json.loads(r.stdout)["result"]["signals"][0]["evidence"]
    assert ev["source_location"]["line_start"] == 19
    assert ev["source_text"] == "dout <= data;"


def test_snapshot_evidence_uses_lhs_assignment(tmp_path):
    import os
    env = dict(os.environ, SVQ_SNAPSHOT_DIR=str(tmp_path))
    save = subprocess.run(
        ["sv_query", "snapshot", "save",
         "sim/tests/integration/dataflow_fixtures/sync_fifo.sv",
         "--tag", "review", "--no-preprocess", "--json", "-q"],
        capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT), env=env)
    assert save.returncode == 0, save.stderr[-500:]
    r = subprocess.run(
        ["sv_query", "trace", "evidence", "sync_fifo.reg_stage1",
         "--from-snapshot", "review", "--json", "-q"],
        capture_output=True, text=True, timeout=120, cwd=str(tmp_path), env=env)
    assert r.returncode == 0, r.stderr[-500:]
    ev = json.loads(r.stdout)["result"]["signals"][0]["evidence"]
    assert ev["source_location"]["line_start"] == 32
    assert ev["source_text"] == "if (wr_en) reg_stage1 <= push_data_i;"
    assert ev["is_verified"] is True


def test_reset_in_else_does_not_win(tmp_path):
    src = tmp_path / "reset_last.sv"
    src.write_text(
        "module top(input clk, rst_n, en, d, output reg q);\n"
        "  always_ff @(posedge clk or negedge rst_n) begin\n"
        "    if (en) q <= d;\n"
        "    else if (!rst_n) q <= 1'b0;\n"
        "  end\n"
        "endmodule\n")
    r = subprocess.run(
        ["sv_query", "trace", "evidence", "top.q", "-f", str(src),
         "--json", "-q"], capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    ev = json.loads(r.stdout)["result"]["signals"][0]["evidence"]
    assert ev["source_location"]["line_start"] == 3
    assert ev["source_text"] == "if (en) q <= d;"


def test_comparison_is_not_assignment(tmp_path):
    src = tmp_path / "cmp.sv"
    src.write_text(
        "module top(input clk, en, d, output reg q, output reg valid);\n"
        "  always_ff @(posedge clk) begin\n"
        "    if (en) q <= d;\n"
        "    if (q == 1'b0) valid <= 1'b1;\n"
        "  end\n"
        "endmodule\n")
    r = subprocess.run(
        ["sv_query", "trace", "evidence", "top.q", "-f", str(src),
         "--json", "-q"], capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    ev = json.loads(r.stdout)["result"]["signals"][0]["evidence"]
    assert ev["source_location"]["line_start"] == 3
    assert ev["source_text"] == "if (en) q <= d;"


def test_reset_comment_does_not_defeat_functional_branch(tmp_path):
    src = tmp_path / "reset_comment.sv"
    src.write_text(
        "module top(input clk, rst_n, en, d, output reg q);\n"
        "  always_ff @(posedge clk or negedge rst_n) begin\n"
        "    if (en) q <= d;\n"
        "    else if (!rst_n) begin\n"
        "      // shift reset to zero\n"
        "      q <= 1'b0;\n"
        "    end\n"
        "  end\n"
        "endmodule\n")
    r = subprocess.run(
        ["sv_query", "trace", "evidence", "top.q", "-f", str(src),
         "--json", "-q"], capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    ev = json.loads(r.stdout)["result"]["signals"][0]["evidence"]
    assert ev["source_location"]["line_start"] == 3
    assert ev["source_text"] == "if (en) q <= d;"
