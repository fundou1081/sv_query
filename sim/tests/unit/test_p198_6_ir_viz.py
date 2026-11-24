"""P198.6 — typed IR feeds viz tree and DriverInfo."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.core.expression_ir import Expr
from sv_query.trace.core.graph.viz.expression_ir_bridge import ir_to_tree
from sv_query.trace.unified_tracer import UnifiedTracer


def test_ir_to_viz_tree_preserves_ops_and_literals():
    expr = Expr(op="ShiftLeft", width=10, children=(
        Expr(op="SignalRef", width=8, signal="a"),
        Expr(op="Literal", width=4, literal="4'b10")))
    tree = ir_to_tree(expr)
    assert tree is not None and tree.root is not None
    assert tree.root.op == "ShiftLeft" and tree.root.label == "<<"
    assert [c.op for c in tree.root.children] == ["SignalRef", "Const"]
    assert tree.root.children[1].label == "4'b10"


def _tracer(tmp_path: Path):
    sv = tmp_path / "viz.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [9:0] y);\n"
        "  assign y = a << 4'd2;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer


def test_driver_info_exposes_typed_ir(tmp_path):
    tracer = _tracer(tmp_path)
    driver = tracer.trace_fanin_detailed("top.y")[0]
    assert driver.expression_ir is not None
    assert driver.expression_ir["op"] == "ShiftLeft"
    assert driver.expression_ir["children"][1]["literal"] == "4'b10"


def test_collect_ir_extracts_constants_and_calls():
    from sv_query.trace.core.graph.viz.expression_ir_bridge import collect_ir

    expr = Expr(op="ShiftLeft", width=10, children=(
        Expr(op="Call", width=8, signal="f"),
        Expr(op="Literal", width=4, literal="4'b10")))
    const, funcs = {}, {}
    collect_ir(expr, "top.y", const, funcs)
    assert const == {"top.y": ["4'b10"]}
    assert "f" in funcs


def test_driver_info_without_ir_is_none(tmp_path):
    sv = tmp_path / "proc.sv"
    sv.write_text(
        "module top(input logic clk, input logic d, output logic q);\n"
        "  always_ff @(posedge clk) q <= d;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    drivers = tracer.trace_fanin_detailed("top.q")
    assert drivers and drivers[0].expression_ir is None


def test_parsed_ir_feeds_bridge_and_collector(tmp_path):
    from sv_query.trace.core.expression_builder import build_expr
    from sv_query.trace.core.graph.viz.expression_ir_bridge import collect_ir

    sv = tmp_path / "parsed.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [9:0] y);\n"
        "  assign y = a << 4'd2;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    adapter = tracer._get_adapter()
    module = adapter.get_modules()[0]
    raw = adapter.get_assignments(module)[0].assignment
    expr = build_expr(raw.right)
    tree = ir_to_tree(expr)
    assert tree is not None and tree.root.op == "ShiftLeft"
    const, funcs = {}, {}
    collect_ir(expr, "top.y", const, funcs)
    assert const == {"top.y": ["4'b10"]}
