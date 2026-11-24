"""Typed semantic expression IR (P198.1).

The IR is the canonical, loss-aware representation of an expression tree. It is
intentionally independent of pyslang: the semantic builder produces these
nodes, and graph/cache/query consume them. Text forms are display-only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

IR_VERSION = 1
OPS = frozenset({
    "SignalRef", "Literal", "Concat", "Slice", "Shift", "Add", "Sub", "Mul",
    "Div", "Mod", "And", "Or", "Xor", "Not", "Neg", "Cast", "Ternary", "Call",
    "Unknown",
})


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _as_int(value: Any, *, field_name: str, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{where}: field {field_name!r} must be an integer")
    return value


def _validate_op(expr: Expr) -> None:
    if expr.op not in OPS:
        raise ValueError(f"Expr: unknown op {expr.op!r}")
    if expr.width is not None and (not isinstance(expr.width, int) or expr.width < 0):
        raise ValueError("Expr: width must be a non-negative integer or None")
    if not isinstance(expr.signed, bool):
        raise ValueError("Expr: signed must be bool")
    if not isinstance(expr.children, tuple) or any(
            not isinstance(c, Expr) for c in expr.children):
        raise ValueError("Expr: children must be a tuple[Expr, ...]")


def _validate_payload(expr: Expr) -> None:
    _validate_signal(expr)
    _validate_literal(expr)
    _validate_unknown(expr)
    _validate_bit_range(expr)


def _validate_signal(expr: Expr) -> None:
    if expr.op == "SignalRef" and not expr.signal:
        raise ValueError("Expr: SignalRef requires signal")


def _validate_literal(expr: Expr) -> None:
    if expr.op == "Literal" and not expr.literal:
        raise ValueError("Expr: Literal requires literal text")


def _validate_unknown(expr: Expr) -> None:
    if expr.op == "Unknown" and not expr.reason:
        raise ValueError("Expr: Unknown requires reason")


def _validate_bit_range(expr: Expr) -> None:
    if expr.bit_range is None:
        return
    if (not isinstance(expr.bit_range, tuple) or len(expr.bit_range) != 2
            or any(not isinstance(v, int) for v in expr.bit_range)):
        raise ValueError("Expr: bit_range must be (msb, lsb)")


def _validate_source(expr: Expr) -> None:
    if not isinstance(expr.source_line, int) or expr.source_line < 0:
        raise ValueError("Expr: source_line must be non-negative")


@dataclass(frozen=True)
class Expr:
    """One immutable expression node.

    ``literal`` is canonical SystemVerilog text (for example ``4'b10x``), not an
    int, so X/Z is never silently coerced to zero. ``width is None`` means the
    semantic width was unavailable; bit mapping must treat it as unknown.
    """

    op: str
    width: int | None = None
    signed: bool = False
    children: tuple[Expr, ...] = ()
    signal: str = ""
    literal: str = ""
    bit_range: tuple[int, int] | None = None
    reason: str = ""
    source_line: int = 0

    def __post_init__(self) -> None:
        _validate_op(self)
        _validate_payload(self)
        _validate_source(self)

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "width": self.width,
            "signed": self.signed,
            "children": [c.to_dict() for c in self.children],
            "signal": self.signal,
            "literal": self.literal,
            "bit_range": list(self.bit_range) if self.bit_range else None,
            "reason": self.reason,
            "source_line": self.source_line,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Expr:
        if not isinstance(data, dict):
            raise ValueError("Expr.from_dict: node must be an object")
        allowed = {"op", "width", "signed", "children", "signal", "literal",
                   "bit_range", "reason", "source_line"}
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"Expr.from_dict: unknown fields {sorted(extra)}")
        op = data.get("op")
        if not isinstance(op, str):
            raise ValueError("Expr.from_dict: op must be a string")
        children_raw = data.get("children", [])
        if not isinstance(children_raw, list):
            raise ValueError("Expr.from_dict: children must be a list")
        bit_raw = data.get("bit_range")
        bit_range = None
        if bit_raw is not None:
            if not isinstance(bit_raw, list) or len(bit_raw) != 2:
                raise ValueError("Expr.from_dict: bit_range must be [msb, lsb]")
            bit_range = (_as_int(bit_raw[0], field_name="bit_range[0]", where="Expr"),
                         _as_int(bit_raw[1], field_name="bit_range[1]", where="Expr"))
        line = data.get("source_line", 0)
        if not isinstance(line, int) or line < 0:
            raise ValueError("Expr.from_dict: source_line must be non-negative")
        return cls(
            op=op,
            width=data.get("width"),
            signed=bool(data.get("signed", False)),
            children=tuple(cls.from_dict(c) for c in children_raw),
            signal=data.get("signal", ""),
            literal=data.get("literal", ""),
            bit_range=bit_range,
            reason=data.get("reason", ""),
            source_line=line,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict()).encode()).hexdigest()[:16]

    @property
    def expr_id(self) -> str:
        return f"expr:{self.fingerprint()}"


@dataclass(frozen=True)
class AssignmentExpr:
    lhs: Expr
    rhs: Expr
    condition: Expr | None = None
    assign_type: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.lhs, Expr) or not isinstance(self.rhs, Expr):
            raise ValueError("AssignmentExpr: lhs/rhs must be Expr")
        if self.condition is not None and not isinstance(self.condition, Expr):
            raise ValueError("AssignmentExpr: condition must be Expr or None")
        if not isinstance(self.assign_type, str):
            raise ValueError("AssignmentExpr: assign_type must be a string")

    def to_dict(self) -> dict:
        return {
            "lhs": self.lhs.to_dict(),
            "rhs": self.rhs.to_dict(),
            "condition": self.condition.to_dict() if self.condition else None,
            "assign_type": self.assign_type,
        }

    @classmethod
    def from_dict(cls, data: Any) -> AssignmentExpr:
        if not isinstance(data, dict):
            raise ValueError("AssignmentExpr.from_dict: object required")
        allowed = {"lhs", "rhs", "condition", "assign_type"}
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"AssignmentExpr.from_dict: unknown fields {sorted(extra)}")
        if "lhs" not in data or "rhs" not in data:
            raise ValueError("AssignmentExpr.from_dict: lhs and rhs required")
        cond = data.get("condition")
        return cls(
            lhs=Expr.from_dict(data["lhs"]),
            rhs=Expr.from_dict(data["rhs"]),
            condition=Expr.from_dict(cond) if cond is not None else None,
            assign_type=data.get("assign_type", ""),
        )


@dataclass
class ExpressionStore:
    """Interned expression DAG. Keys are stable ``expr:<hash>`` ids."""

    _by_id: dict[str, Expr] = field(default_factory=dict)

    def add(self, expr: Expr) -> str:
        if not isinstance(expr, Expr):
            raise ValueError("ExpressionStore.add: Expr required")
        for child in expr.children:
            self.add(child)
        eid = expr.expr_id
        existing = self._by_id.get(eid)
        if existing is not None and existing != expr:
            raise ValueError("ExpressionStore: fingerprint collision")
        self._by_id[eid] = expr
        return eid

    def get(self, expr_id: str) -> Expr:
        try:
            return self._by_id[expr_id]
        except KeyError:
            raise KeyError(f"ExpressionStore: unknown expression {expr_id!r}") from None

    def __len__(self) -> int:
        return len(self._by_id)

    def to_dict(self) -> dict:
        return {"version": IR_VERSION,
                "expressions": {eid: expr.to_dict() for eid, expr in sorted(self._by_id.items())}}

    @classmethod
    def from_dict(cls, data: Any) -> ExpressionStore:
        if not isinstance(data, dict):
            raise ValueError("ExpressionStore.from_dict: object required")
        if data.get("version") != IR_VERSION:
            raise ValueError(f"ExpressionStore.from_dict: unsupported version {data.get('version')!r}")
        raw = data.get("expressions")
        if not isinstance(raw, dict):
            raise ValueError("ExpressionStore.from_dict: expressions must be an object")
        store = cls()
        for eid, node in raw.items():
            if not isinstance(eid, str):
                raise ValueError("ExpressionStore.from_dict: expression id must be a string")
            expr = Expr.from_dict(node)
            if expr.expr_id != eid:
                raise ValueError(
                    f"ExpressionStore.from_dict: id mismatch for {eid!r} "
                    f"(canonical {expr.expr_id!r})")
            store.add(expr)
        return store
