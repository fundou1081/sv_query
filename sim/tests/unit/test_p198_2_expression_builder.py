"""P198.2 — semantic AST -> typed expression IR builder."""
from __future__ import annotations

from pathlib import Path

import pytest

from sv_query.trace.core.expression_builder import build_expr
from sv_query.trace.core.expression_ir import AssignmentExpr
from sv_query.trace.unified_tracer import UnifiedTracer


def _assignment(tmp_path: Path, body: str) -> AssignmentExpr:
    sv = tmp_path / "expr.sv"
    sv.write_text(
        "module top(input logic [7:0] a, input logic [7:0] b, input logic en,\n"
        "           output logic [9:0] y);\n"
        f"  {body}\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    adapter = tracer._get_adapter()
    module = adapter.get_modules()[0]
    assign = adapter.get_assignments(module)[0]
    raw = assign.assignment
    return AssignmentExpr(lhs=build_expr(raw.left), rhs=build_expr(raw.right),
                          assign_type="continuous")


def _unwrap_cast(expr):
    while expr.op == "Cast" and expr.children:
        expr = expr.children[0]
    return expr


def test_builder_preserves_shift_and_sized_literal(tmp_path):
    assignment = _assignment(tmp_path, "assign y = a << 4'd2;")
    rhs = _unwrap_cast(assignment.rhs)
    assert rhs.op == "ShiftLeft"
    assert _unwrap_cast(rhs.children[0]).op == "SignalRef"
    literal = rhs.children[1]
    assert literal.op == "Literal" and literal.literal == "4'b10"


def test_builder_preserves_xz_literal_text(tmp_path):
    assignment = _assignment(tmp_path, "assign y = a << 4'dx;")
    rhs = _unwrap_cast(assignment.rhs)
    literal = rhs.children[1]
    assert literal.op == "Literal"
    assert literal.literal == "4'bxxxx"


def test_builder_keeps_both_concat_sides(tmp_path):
    assignment = _assignment(tmp_path, "assign {y[9:5], y[4:0]} = {a[7:4], b[3:0]};")
    lhs = _unwrap_cast(assignment.lhs)
    rhs = _unwrap_cast(assignment.rhs)
    assert lhs.op == "Concat"
    assert rhs.op == "Concat"
    assert [c.op for c in lhs.children] == ["Slice", "Slice"]
    assert [c.op for c in rhs.children] == ["Slice", "Slice"]


def test_builder_handles_ternary_condition(tmp_path):
    assignment = _assignment(tmp_path, "assign y = en ? a : b;")
    rhs = _unwrap_cast(assignment.rhs)
    assert rhs.op == "Ternary"
    cond, true_expr, false_expr = rhs.children
    assert cond.op == "SignalRef" and cond.signal == "en"
    assert _unwrap_cast(true_expr).signal == "a"
    assert _unwrap_cast(false_expr).signal == "b"


def test_builder_keeps_conversion_wrapper(tmp_path):
    assignment = _assignment(tmp_path, "assign y = $signed(a) >>> 4'd2;")
    rhs = _unwrap_cast(assignment.rhs)
    assert rhs.op == "ShiftRightArithmetic"
    assert rhs.children[0].op == "Cast"
    assert _unwrap_cast(rhs.children[0]).signal == "a"


def test_builder_marks_non_cast_call_as_unknown_mapping(tmp_path):
    assignment = _assignment(tmp_path, "assign y = $clog2(a);")
    rhs = _unwrap_cast(assignment.rhs)
    assert rhs.op == "Call"
    assert "bit mapping unknown" in rhs.reason


def test_builder_maps_unary_minus_and_not(tmp_path):
    assignment = _assignment(tmp_path, "assign y = -a;")
    rhs = _unwrap_cast(assignment.rhs)
    assert rhs.op == "Neg"
    assert _unwrap_cast(rhs.children[0]).signal == "a"
    not_expr = _unwrap_cast(_assignment(tmp_path, "assign y = !en;").rhs)
    assert not_expr.op == "Not"


def test_builder_captures_element_and_range_select_bit_ranges(tmp_path):
    element = _unwrap_cast(_assignment(tmp_path, "assign y = a[3];").rhs)
    assert element.op == "Slice" and element.bit_range == (3, 3)
    assert "unresolved" not in element.reason
    ranged = _unwrap_cast(_assignment(tmp_path, "assign y = a[7:4];").rhs)
    assert ranged.op == "Slice" and ranged.bit_range == (7, 4)


def test_builder_preserves_call_name_and_args(tmp_path):
    rhs = _unwrap_cast(_assignment(tmp_path, "assign y = $clog2(a);").rhs)
    assert rhs.op == "Call"
    assert rhs.signal == "$clog2"
    assert rhs.children and rhs.children[0].op == "SignalRef"


def test_builder_nested_concat_and_unsupported_kind(tmp_path):
    nested = _unwrap_cast(_assignment(tmp_path, "assign y = {a, {b, 2'b10}};").rhs)
    assert nested.op == "Concat"
    assert any(c.op == "Concat" for c in nested.children)
    unknown = _unwrap_cast(_assignment(tmp_path, "assign y = a == b;").rhs)
    assert unknown.op == "Unknown"
    assert unknown.reason


@pytest.mark.parametrize("body,expected", [
    ("assign y = a * b;", "Mul"),
    ("assign y = a / b;", "Div"),
    ("assign y = a % b;", "Mod"),
    ("assign y = a & b;", "And"),
    ("assign y = a | b;", "Or"),
    ("assign y = a ^ b;", "Xor"),
])
def test_builder_maps_binary_operator_matrix(tmp_path, body, expected):
    rhs = _unwrap_cast(_assignment(tmp_path, body).rhs)
    assert rhs.op == expected
