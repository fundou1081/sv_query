"""P198.1 — typed expression IR and strict store round-trip."""
from __future__ import annotations

import pytest

from sv_query.trace.core.expression_ir import (
    AssignmentExpr,
    Expr,
    ExpressionStore,
)


def _nested():
    a = Expr(op="SignalRef", width=8, signal="a")
    b = Expr(op="SignalRef", width=8, signal="b")
    two = Expr(op="Literal", width=4, literal="4'd2")
    shift = Expr(op="Shift", width=10, children=(a, two))
    return Expr(op="Concat", width=18, children=(shift, b))


def test_nested_expression_round_trip_and_interning():
    expr = _nested()
    store = ExpressionStore()
    eid = store.add(expr)
    assert eid == expr.expr_id
    assert len(store) == 5
    assert store.get(eid) == expr
    restored = ExpressionStore.from_dict(store.to_dict())
    assert restored.get(eid) == expr
    assert restored.to_dict() == store.to_dict()


def test_xz_literal_is_preserved_as_text():
    expr = Expr(op="Literal", width=4, literal="4'bx0z1")
    restored = Expr.from_dict(expr.to_dict())
    assert restored.literal == "4'bx0z1"
    assert "x" in restored.literal


def test_assignment_keeps_both_sides_and_condition():
    lhs = Expr(op="Concat", children=(
        Expr(op="SignalRef", signal="y_hi"), Expr(op="SignalRef", signal="y_lo")))
    rhs = Expr(op="Concat", children=(
        Expr(op="SignalRef", signal="a"), Expr(op="SignalRef", signal="b")))
    cond = Expr(op="SignalRef", signal="en")
    assignment = AssignmentExpr(lhs=lhs, rhs=rhs, condition=cond,
                                assign_type="continuous")
    restored = AssignmentExpr.from_dict(assignment.to_dict())
    assert restored == assignment
    assert restored.lhs.op == "Concat" and restored.rhs.op == "Concat"


def test_strict_errors_for_unknown_op_and_bad_store_id():
    with pytest.raises(ValueError, match="unknown op"):
        Expr(op="Bogus")
    with pytest.raises(ValueError, match="id mismatch"):
        ExpressionStore.from_dict({
            "version": 1,
            "expressions": {"expr:deadbeef": Expr(op="Literal", literal="1'b0").to_dict()},
        })
