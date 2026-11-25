"""P198.4 — concat sides pair by bit layout, not leaf zip."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.core.concat_layout import flatten, pair
from sv_query.trace.core.expression_ir import Expr
from sv_query.trace.unified_tracer import UnifiedTracer


def _ref(name: str, width: int = 1) -> Expr:
    return Expr(op="SignalRef", width=width, signal=name)


def test_layout_pairs_nested_concat_by_lsb_offset():
    lhs = Expr(op="Concat", width=3, children=(
        _ref("y2"), Expr(op="Concat", width=2, children=(_ref("y1"), _ref("y0")))))
    rhs = Expr(op="Concat", width=3, children=(
        _ref("a"), Expr(op="Concat", width=2, children=(_ref("b"), _ref("c")))))
    assert [s.expr.signal for s in flatten(lhs)] == ["y0", "y1", "y2"]
    assert [(p.lhs.expr.signal, p.rhs.expr.signal) for p in pair(lhs, rhs)] == [
        ("y0", "c"), ("y1", "b"), ("y2", "a")]


def test_width_mismatch_has_no_layout_pairing():
    lhs = Expr(op="Concat", width=2, children=(_ref("a"), _ref("b")))
    rhs = Expr(op="Concat", width=1, children=(_ref("c"),))
    assert pair(lhs, rhs) is None


def _graph(tmp_path: Path, body: str):
    sv = tmp_path / "concat.sv"
    sv.write_text(
        "module top(input logic [3:0] a, input logic [3:0] b, input logic c,\n"
        "           output logic [1:0] y0, output logic [1:0] y1);\n"
        f"  {body}\n  endmodule\n")
    return UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()


def test_graph_concat_pairs_individual_lhs_segments(tmp_path):
    graph = _graph(tmp_path, "assign {y1, y0} = {a[1:0], b[1:0]};")
    pairs = {(e.src, e.dst) for (_, _), edges in graph._edge_data.items()
             for e in edges if e.assign_type == "continuous"}
    assert ("top.a[1:0]", "top.y1") in pairs
    assert ("top.b[1:0]", "top.y0") in pairs
    assert not any(dst.startswith("top.{") for _, dst in pairs)


def test_graph_concat_slices_keep_ranges(tmp_path):
    graph = _graph(tmp_path, "assign {y1[1:0], y0[1:0]} = {a[3:2], b[1:0]};")
    pairs = {(e.src, e.dst) for (_, _), edges in graph._edge_data.items()
             for e in edges if e.assign_type == "continuous"}
    assert ("top.a[3:2]", "top.y1[1:0]") in pairs
    assert ("top.b[1:0]", "top.y0[1:0]") in pairs


def test_graph_width_mismatch_is_explicit_unknown_without_aggregate(tmp_path):
    graph = _graph(tmp_path, "assign {y1, y0} = {a, b, c};")
    targets = {e.dst for (_, _), edges in graph._edge_data.items()
               for e in edges if e.assign_type == "continuous"}
    assert not any(dst.startswith("top.{") for dst in targets)
    assert any(u["kind"] == "concat_layout" for u in graph.unknowns)


def test_graph_dynamic_select_segment_is_unknown(tmp_path):
    sv = tmp_path / "dyn.sv"
    sv.write_text(
        "module top(input logic [3:0] a, input logic [1:0] idx,\n"
        "           output logic y0, output logic y1);\n"
        "  assign {y1, y0} = {a[idx], a[0]};\n"
        "endmodule\n")
    graph = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()
    assert any("concat" in u["kind"] for u in graph.unknowns)
    assert graph.get_edge("top.a", "top.y1") is None


def test_graph_literal_segment_is_not_silently_dropped(tmp_path):
    graph = _graph(tmp_path, "assign {y1, y0} = {a[1:0], 2'b10};")
    assert any(u["kind"] == "concat_segment_unknown" for u in graph.unknowns)


def test_graph_concat_edges_carry_ir_refs(tmp_path):
    graph = _graph(tmp_path, "assign {y1, y0} = {a[1:0], b[1:0]};")
    edge = graph._edge_data_for_dst("top.y1")[0]
    assert edge.expr_id and edge.assignment_id
    assert edge.assignment_id in graph.assignments


def test_mixed_segmentation_splits_wide_rhs(tmp_path):
    sv = tmp_path / "mixed.sv"
    sv.write_text(
        "module top(input logic [1:0] a, output logic y0, output logic y1);\n"
        "  assign {y1, y0} = {a[1:0]};\n"
        "endmodule\n")
    graph = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()
    pairs = {(e.src, e.dst) for (_, _), edges in graph._edge_data.items()
             for e in edges if e.assign_type == "continuous"}
    assert ("top.a[1]", "top.y1") in pairs
    assert ("top.a[0]", "top.y0") in pairs


def test_slice_without_width_is_unknown():
    expr = Expr(op="Slice", width=None, children=(
        Expr(op="SignalRef", width=4, signal="a"),), bit_range=None)
    assert flatten(expr) is None


def test_descending_packed_concat_maps_correct_bits(tmp_path):
    sv = tmp_path / "desc.sv"
    sv.write_text(
        "module top(input logic [0:1] a, input logic [0:1] b,\n"
        "           output logic [0:3] y);\n"
        "  assign {y[0:3]} = {a[0:1], b[0:1]};\n"
        "endmodule\n")
    graph = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()
    pairs = {(e.src, e.dst) for (_, _), edges in graph._edge_data.items()
             for e in edges if e.assign_type == "continuous"}
    assert ("top.a[0:1]", "top.y[0:1]") in pairs
    assert ("top.b[0:1]", "top.y[2:3]") in pairs
    assert ("top.a[0]", "top.y[0]") in pairs
    assert ("top.a[1]", "top.y[1]") in pairs
    assert ("top.b[0]", "top.y[2]") in pairs
    assert ("top.b[1]", "top.y[3]") in pairs


def test_single_bit_slice_lhs_concat_has_refs(tmp_path):
    sv = tmp_path / "bits.sv"
    sv.write_text(
        "module top(input logic [3:0] a, output logic [3:0] y);\n"
        "  assign {y[3], y[2], y[1], y[0]} = {a[3], a[2], a[1], a[0]};\n"
        "endmodule\n")
    graph = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR").build_graph()
    referenced = {e.assignment_id for (_, _), edges in graph._edge_data.items()
                  for e in edges if e.assignment_id}
    assert referenced == set(graph.assignments)
    for bit in range(4):
        edge = graph._edge_data_for_dst(f"top.y[{bit}]")[0]
        assert edge.expr_id and edge.assignment_id


def test_descending_multi_bit_split_expands_per_bit(tmp_path):
    from sv_query.trace.unified_tracer import UnifiedTracer
    sv = tmp_path / "dsplit.sv"
    sv.write_text(
        "module top(input logic [2:0] a, input logic b, output logic [3:0] y);\n"
        "  assign {y[3], y[2:0]} = {a[2:0], b};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    graph = tracer.build_graph()
    assert {r.id for r in tracer.trace_fanin("top.y[1]")} == {"top.a[0]"}
    assert {r.id for r in tracer.trace_fanin("top.y[2]")} == {"top.a[1]"}
    assert {r.id for r in tracer.trace_fanin("top.y[3]")} == {"top.a[2]"}
    assert graph is not None


def test_descending_wide_rhs_keeps_per_bit_fanin(tmp_path):
    from sv_query.trace.unified_tracer import UnifiedTracer
    sv = tmp_path / "wide.sv"
    sv.write_text(
        "module top(input logic [3:0] a, output logic [1:0] y0,\n"
        "           output logic [1:0] y1);\n"
        "  assign {y1, y0} = {a[3:0]};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    assert {r.id for r in tracer.trace_fanin("top.y0[0]")} == {"top.a[0]"}
    assert {r.id for r in tracer.trace_fanin("top.y0[1]")} == {"top.a[1]"}
    assert {r.id for r in tracer.trace_fanin("top.y1[0]")} == {"top.a[2]"}
    assert {r.id for r in tracer.trace_fanin("top.y1[1]")} == {"top.a[3]"}
