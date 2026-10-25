"""[iter_288 / PLAN P3.3] `svq audit` 十条检查的回归。

原 exp 10 条创意（docs/EXP_IDEAS.md）在 `trace.core.analysis.audit` 里重新实现，
本文件锁定每条检查的**可观察输出**（不是内部实现）：

  1 protocols            名称模式识别 AXI4
  2 handshakes           valid/ready 配对 + 依赖方向
  3 backpressure_cycles  反压环候选（本 fixture 无环）
  4 assertions           SVA 断言被提取并挂到信号
  5 coverage             covergroup + 缺口建议片段
  6 verification_gaps    高风险信号无断言/无覆盖被列出
  7 risk                 时钟信号分数高于数据信号
  8 constraints          rand 变量与约束提及判定
  9 cdc                  跨时钟域候选（clk_a → clk_b）
 10 timing               组合链长度（>=3）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.analysis import CHECKS, run_audit  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE = """
class pkt;
  rand bit [7:0] addr;
  rand bit [7:0] data;
  constraint c_addr { addr inside {[0:15]}; }
endclass

module axi_slave(input logic clk, input logic rst_n,
  input logic awvalid, output logic awready, input logic [31:0] awaddr,
  input logic wvalid, output logic wready, input logic [31:0] wdata,
  input logic bready, output logic bvalid,
  input logic arvalid, output logic arready, input logic [31:0] araddr,
  input logic rready, output logic rvalid, output logic [31:0] rdata);
  assign awready = ~awvalid;
  assign wready  = 1'b1;
  assign bvalid  = awvalid & wvalid;
  assign arready = 1'b1;
  assign rvalid  = arvalid;
  assign rdata   = araddr;

  assert property (@(posedge clk) awvalid |-> ##1 awready);

  covergroup cg_axi @(posedge clk);
    cp_awvalid: coverpoint awvalid;
  endgroup
endmodule

module cdc_src(input logic clk_a, input logic d, output logic q_a);
  always_ff @(posedge clk_a) q_a <= d;
endmodule

module cdc_dst(input logic clk_b, input logic q_a, output logic q_b);
  always_ff @(posedge clk_b) q_b <= q_a;
endmodule

module chain(input logic a, output logic e);
  wire b, c, d;
  assign b = a;
  assign c = b;
  assign d = c;
  assign e = d;
endmodule

module top(input logic clk_a, clk_b, din, output logic q_b, e);
  wire q_a_w;
  axi_slave u_axi(.clk(clk_a), .rst_n(1'b1));
  cdc_src u_src(.clk_a(clk_a), .d(din), .q_a(q_a_w));
  cdc_dst u_dst(.clk_b(clk_b), .q_a(q_a_w), .q_b(q_b));
  chain u_chain(.a(din), .e(e));
endmodule
"""


@pytest.fixture(scope="module")
def audit():
    t = UnifiedTracer(sources={"fx.sv": FIXTURE}, log_level="ERROR")
    t.build_graph()
    return run_audit(t)


def test_all_checks_present(audit):
    assert audit["checks"] == list(CHECKS)
    assert set(audit["sections"]) == set(CHECKS)
    assert audit["summary"]["checks"] == 10


def test_protocol_detected(audit):
    rows = audit["sections"]["protocols"]
    assert rows, "应识别出 AXI4 从设备"
    protos = [c["protocol"] for c in rows[0]["candidates"]]
    assert "axi4" in protos
    assert rows[0]["instance"].endswith("u_axi")


def test_handshake_pair_and_direction(audit):
    pairs = audit["sections"]["handshakes"]
    aw = next(p for p in pairs if p["prefix"] == "aw")
    assert aw["valid"].endswith("awvalid") and aw["ready"].endswith("awready")
    # awready = ~awvalid → ready 依赖 valid
    assert aw["classification"] == "ready_depends_on_valid", aw


def test_no_backpressure_cycle_in_fixture(audit):
    assert audit["sections"]["backpressure_cycles"] == []


def test_assertions_extracted(audit):
    sva = audit["sections"]["assertions"]
    assert sva["assertions"] >= 1
    assert sva["errors"] == []


def test_coverage_and_suggestions(audit):
    cov = audit["sections"]["coverage"]
    assert cov["covergroups"] >= 1
    assert cov["errors"] == []
    # 未被覆盖的握手对应给出建议片段
    assert cov["suggested"], "应给出 covergroup 建议"
    assert "covergroup" in cov["suggested"][0]["code"]


def test_verification_gaps(audit):
    gaps = audit["sections"]["verification_gaps"]
    assert gaps, "fixture 有明显无断言的关键信号"
    roles = {g["role"] for g in gaps}
    assert roles & {"clock", "valid", "ready", "reset"}
    for g in gaps:
        assert g["loads"] >= 2


def test_risk_clock_ranks_high(audit):
    rows = audit["sections"]["risk"]
    assert rows
    top_role = rows[0]["role"]
    assert top_role in ("clock", "reset"), f"时钟/复位应排最前，实际 {rows[0]}"
    clock_scores = [r["score"] for r in rows if r["role"] == "clock"]
    data_scores = [r["score"] for r in rows if r["role"] == "data"]
    if clock_scores and data_scores:
        assert max(clock_scores) > min(data_scores)


def test_constraints_cover_rand_vars(audit):
    classes = audit["sections"]["constraints"]["classes"]
    assert classes
    pkt = next(c for c in classes if c["class"] == "pkt")
    assert set(pkt["rand_vars"]) == {"addr", "data"}
    # addr 被 constraint 提及，data 没有
    assert pkt["rand_vars_without_constraint"] == ["data"]


def test_cdc_candidate(audit):
    rows = audit["sections"]["cdc"]
    assert rows, "clk_a → clk_b 应产生 CDC 候选"
    signals = {r["signal"] for r in rows}
    assert any("q_a" in s for s in signals), signals
    assert all(r["confidence"] == "heuristic" for r in rows)
    # fixture 没有同步器 → has_sync_hint 为 False
    crossing = next(r for r in rows if "q_a_w" in r["signal"])
    assert crossing["has_sync_hint"] is False
    assert "clk_a" in crossing["domains"] and "clk_b" in crossing["domains"]


def test_timing_chain(audit):
    rows = audit["sections"]["timing"]
    assert rows
    assert rows[0]["length"] >= 3
    chain = rows[0]["chain"]
    assert len(set(chain)) >= len(chain) - 1, f"链里不应有大量重复节点: {chain}"


def test_check_selection(audit):
    t = UnifiedTracer(sources={"fx.sv": FIXTURE}, log_level="ERROR")
    t.build_graph()
    partial = run_audit(t, ["protocols", "risk"])
    assert partial["checks"] == ["protocols", "risk"]
    assert set(partial["sections"]) == {"protocols", "risk"}


def test_unknown_check_raises():
    t = UnifiedTracer(sources={"a.sv": "module a; endmodule"}, log_level="ERROR")
    t.build_graph()
    with pytest.raises(ValueError, match="未知检查项"):
        run_audit(t, ["nope"])


def test_cli_json_shape(tmp_path):
    """CLI 出口形状：checks/sections/summary 三个字段，JSON 可解析。"""
    import json
    import subprocess

    out = subprocess.run(
        ["python3", str(REPO / "run_cli.py"), "audit", "--file",
         str(REPO / "sim/tests/fixtures/golden_mini/inst_demo.sv"), "--json"],
        capture_output=True, text=True, cwd=str(REPO), timeout=120,
    )
    assert out.returncode == 0, out.stderr[:300]
    data = json.loads(out.stdout)
    assert data["checks"] == list(CHECKS)
    assert "sections" in data and "summary" in data
