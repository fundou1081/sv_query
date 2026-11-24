"""Semantic AST -> typed expression IR builder (P198.2).

Only pyslang semantic nodes are accepted. Syntax-token expression trees remain a
display concern and are not a fallback here. Unsupported constructs become an
explicit ``Unknown`` node; they are never guessed.
"""
from __future__ import annotations

from .expression_ir import Expr

_BIN_OPS = {
    "add": "Add", "subtract": "Sub", "multiply": "Mul", "divide": "Div",
    "mod": "Mod", "binaryand": "And", "binaryor": "Or", "binaryxor": "Xor",
    "logicalshiftleft": "ShiftLeft", "logicalshiftright": "ShiftRight",
    "arithmeticshiftleft": "ShiftLeft", "arithmeticshiftright": "ShiftRight",
}
_UNARY_OPS = {
    "logicalnot": "Not", "bitwisenot": "Not", "negate": "Neg",
    "unaryminus": "Neg", "unaryplus": "",
}


def _kind(node) -> str:
    return str(getattr(node, "kind", ""))


def _type_info(node) -> tuple[int | None, bool]:
    typ = getattr(node, "type", None)
    if typ is None:
        return None, False
    raw = getattr(typ, "bitWidth", None)
    width = int(raw) if isinstance(raw, int) else None
    return width, bool(getattr(typ, "isSigned", False))


def _leaf_name(node) -> str:
    sym = getattr(node, "symbol", None)
    if sym is not None:
        name = getattr(sym, "name", None)
        if name is not None:
            return str(name)
    name = getattr(node, "name", None)
    return str(name) if name is not None else ""


def _op_name(value) -> str:
    raw = getattr(value, "name", value)
    text = str(raw)
    for part in (text.split(".")[-1], text):
        key = part.strip().lower()
        if key in _BIN_OPS:
            return _BIN_OPS[key]
        if key in _UNARY_OPS:
            return _UNARY_OPS[key]
    return ""


def _unknown(node, reason: str) -> Expr:
    width, signed = _type_info(node)
    return Expr(op="Unknown", width=width, signed=signed, reason=reason)


def _literal(node, width, signed, _resolve):
    value = getattr(node, "value", None)
    return Expr(op="Literal", width=width, signed=signed,
                literal=str(value) if value is not None else "",
                reason="" if value is not None else "literal value unavailable")


def _named(node, width, signed, resolve):
    name = _leaf_name(node)
    if resolve is not None and name:
        name = resolve(name)
    return Expr(op="SignalRef", width=width, signed=signed, signal=name,
                reason="" if name else "signal name unavailable")


def _cast(node, width, signed, resolve):
    return Expr(op="Cast", width=width, signed=signed,
                children=(build_expr(getattr(node, "operand", None),
                                     signal_resolver=resolve),))


def _binary(node, width, signed, resolve):
    op = _op_name(getattr(node, "op", None))
    if not op:
        return _unknown(node, f"unsupported binary operator {getattr(node, 'op', None)!r}")
    left = build_expr(getattr(node, "left", None), signal_resolver=resolve)
    right = build_expr(getattr(node, "right", None), signal_resolver=resolve)
    return Expr(op=op, width=width, signed=signed, children=(left, right))


def _unary(node, width, signed, resolve):
    op = _op_name(getattr(node, "op", None))
    if not op:
        return _unknown(node, f"unsupported unary operator {getattr(node, 'op', None)!r}")
    child = build_expr(getattr(node, "operand", None), signal_resolver=resolve)
    return Expr(op=op, width=width, signed=signed, children=(child,))


def _concat(node, width, signed, resolve):
    operands = getattr(node, "operands", None) or ()
    return Expr(op="Concat", width=width, signed=signed,
                children=tuple(build_expr(x, signal_resolver=resolve)
                               for x in operands))


def _conditional(node, width, signed, resolve):
    pred = getattr(node, "predicate", None)
    if pred is None:
        conditions = getattr(node, "conditions", None) or ()
        if conditions:
            pred = getattr(conditions[0], "expr", None)
    cond = build_expr(pred, signal_resolver=resolve)
    true_expr = build_expr(getattr(node, "left", None), signal_resolver=resolve)
    false_expr = build_expr(getattr(node, "right", None), signal_resolver=resolve)
    return Expr(op="Ternary", width=width, signed=signed,
                children=(cond, true_expr, false_expr))


def _select(node, width, signed, resolve):
    base = getattr(node, "value", None) or getattr(node, "left", None)
    child = build_expr(base, signal_resolver=resolve)
    msb = getattr(node, "left", None) or getattr(node, "selector", None)
    lsb = getattr(node, "right", None)
    bit_range = None
    if msb is not None and lsb is not None:
        try:
            bit_range = (int(msb.value), int(lsb.value))
        except (AttributeError, TypeError, ValueError):
            bit_range = None
    return Expr(op="Slice", width=width, signed=signed, children=(child,),
                bit_range=bit_range,
                reason="" if bit_range else "dynamic or unresolved select")


def _call(node, width, signed, resolve):
    name = str(getattr(node, "subroutineName", "") or "")
    args = getattr(node, "arguments", None) or ()
    if name in ("$signed", "$unsigned") and args:
        return Expr(op="Cast", width=width, signed=(name == "$signed"),
                    children=(build_expr(args[0], signal_resolver=resolve),))
    return Expr(op="Call", width=width, signed=signed,
                reason=f"function call {name or '<unknown>'}; bit mapping unknown")


_HANDLERS = (
    ("IntegerLiteral", _literal),
    ("NamedValue", _named),
    ("Conversion", _cast),
    ("Binary", _binary),
    ("Unary", _unary),
    ("Concatenation", _concat),
    ("Conditional", _conditional),
    ("ElementSelect", _select),
    ("RangeSelect", _select),
    ("Call", _call),
)


def build_expr(node, *, signal_resolver=None) -> Expr:
    """Build one IR node from a pyslang semantic expression.

    ``signal_resolver`` optionally rewrites a signal name (for genvar contexts).
    It is a pure callback; unresolved names are preserved.
    """
    if node is None:
        return _unknown(node, "missing semantic expression")
    kind = _kind(node)
    width, signed = _type_info(node)
    for marker, handler in _HANDLERS:
        if marker in kind:
            return handler(node, width, signed, signal_resolver)
    return _unknown(node, f"unsupported expression kind {kind!r}")
