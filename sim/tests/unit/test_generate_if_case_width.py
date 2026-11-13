"""[iter_356 / PLAN P55] generate if/case 常场景 width 强化。"""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "generate_if_case_width.sv"


def _build(target: str):
    tr = UnifiedTracer(sources={"t.sv": FIXTURE.read_text()}, log_level="ERROR")
    return tr, tr.build_graph(use_cache=False, target_module=target)


def test_generate_if_active_branch_width():
    _, g = _build("top_if0")
    assert g.get_node("top_if0.g.u.i").width == (7, 0)
    assert g.get_node("top_if0.g.u.r").width == (7, 0)
    assert g.get_node("top_if0.g.u.o").width == (7, 0)
    assert "top_if0.other.u.i" not in g.nodes()


def test_generate_case_active_branch_width():
    _, g = _build("top_case1")
    assert g.get_node("top_case1.g1.u.i").width == (3, 0)
    assert g.get_node("top_case1.g1.u.r").width == (3, 0)
    assert "top_case1.g0.u.i" not in g.nodes()
    assert "top_case1.gd.u.i" not in g.nodes()


def test_generate_if_inactive_literal_branch_not_materialized():
    src = """
module leaf #(parameter W = 4) (input [W-1:0] i, output [W-1:0] o);
  assign o = i;
endmodule
module top_if1 #(parameter MODE = 1) (input [15:0] a, output [15:0] y);
  localparam W = 8;
  generate
    if (MODE == 0) begin: never
      leaf #(.W(2)) u(.i(a[1:0]), .o(y[1:0]));
    end else begin: chosen
      leaf #(.W(W)) u(.i(a[W-1:0]), .o(y[W-1:0]));
    end
  endgenerate
endmodule
"""
    tr = UnifiedTracer(sources={"t.sv": src}, log_level="ERROR")
    g = tr.build_graph(use_cache=False, target_module="top_if1")
    assert g.get_node("top_if1.chosen.u.i").width == (7, 0)
    assert "top_if1.never.u.i" not in g.nodes()
