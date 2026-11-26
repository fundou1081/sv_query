"""Recursive bit mapping over typed expression IR (P198.5).

The mapper is explicit about completeness: ``None`` means the expression cannot
be mapped (call/unknown/dynamic shift), and an empty list means known no
dependency. Callers must not turn ``None`` into a fabricated bit.
"""
from __future__ import annotations

from dataclasses import dataclass

from .concat_layout import flatten
from .expression_ir import Expr


@dataclass(frozen=True)
class SourceBit:
    signal: str
    bit: int


def _base_name(signal: str) -> str:
    name = signal.rsplit(".", 1)[-1]
    return name.split("[", 1)[0]


def _matches(name: str, wanted: str) -> bool:
    return name == wanted or _base_name(name) == _base_name(wanted)


def _shift_amount(expr: Expr) -> int | None:
    if expr.op not in ("ShiftLeft", "ShiftRight",
                       "ShiftLeftArithmetic", "ShiftRightArithmetic"):
        return None
    if not expr.children:
        return None
    literal = expr.children[1] if len(expr.children) > 1 else None
    if literal is None or literal.op != "Literal":
        return None
    try:
        text = literal.literal
        if "'" in text:
            base = text.split("'", 1)[1].lstrip("sS")
            radix = base[0].lower()
            digits = base[1:].replace("_", "")
            return int(digits, {"b": 2, "o": 8, "d": 10, "h": 16}[radix])
        return int(text, 10)
    except (ValueError, IndexError, KeyError):
        return None


def _res_signal(expr, out_bit, source_filter):
    if source_filter is not None and not _matches(expr.signal, source_filter):
        return []
    return [SourceBit(expr.signal, out_bit)]


def _res_concat(expr, out_bit, source_filter):
    segments = flatten(expr)
    if segments is None:
        return None
    for seg in segments:
        if seg.offset <= out_bit < seg.offset + seg.width:
            return _result(seg.expr, out_bit - seg.offset, source_filter)
    return None


def _res_slice(expr, out_bit, source_filter):
    if not expr.children or expr.bit_range is None:
        return None
    return _result(expr.children[0], min(expr.bit_range) + out_bit, source_filter)


def _res_cast(expr, out_bit, source_filter):
    if not expr.children:
        return None
    child = expr.children[0]
    if child.op in ("ShiftLeftArithmetic", "ShiftRightArithmetic"):
        return _result(child, out_bit, source_filter)
    if child.width is not None and out_bit >= child.width:
        if child.op == "Literal" or not (expr.signed or child.signed):
            return []  # known zero extension
        return _result(child, child.width - 1, source_filter)
    return _result(child, out_bit, source_filter)


def _res_shift(expr, out_bit, source_filter):
    amount = _shift_amount(expr)
    if amount is None or not expr.children:
        return None
    child = expr.children[0]
    left = expr.op in ("ShiftLeft", "ShiftLeftArithmetic")
    delta = out_bit - amount if left else out_bit + amount
    if (expr.op == "ShiftRightArithmetic" and child.width is not None
            and delta >= child.width):
        if child.signed:
            return _result(child, child.width - 1, source_filter)
        return []
    return _result(child, delta, source_filter)


def _res_ternary(expr, out_bit, source_filter):
    if len(expr.children) != 3:
        return None
    left = _result(expr.children[1], out_bit, source_filter)
    right = _result(expr.children[2], out_bit, source_filter)
    if left is None or right is None:
        return None
    return left + right


_RESULT_HANDLERS = {
    "SignalRef": _res_signal, "Concat": _res_concat, "Slice": _res_slice,
    "Cast": _res_cast, "ShiftLeft": _res_shift, "ShiftRight": _res_shift,
    "ShiftLeftArithmetic": _res_shift, "ShiftRightArithmetic": _res_shift,
    "Ternary": _res_ternary, "Literal": lambda *_: [],
}


def _result(expr: Expr, out_bit: int, source_filter: str | None):
    if expr.width is not None and (out_bit < 0 or out_bit >= expr.width):
        return []
    handler = _RESULT_HANDLERS.get(expr.op)
    return handler(expr, out_bit, source_filter) if handler else None


def output_source_bits(expr: Expr, out_bit: int, source: str) -> list[SourceBit] | None:
    """Bits of ``source`` that determine output bit ``out_bit``."""
    return _result(expr, out_bit, source)


def _in_signal(expr, source, bit, offset):
    return [offset + bit] if _matches(expr.signal, source) else []


def _in_concat(expr, source, bit, offset):
    segments = flatten(expr)
    if segments is None:
        return None
    out = []
    for seg in segments:
        vals = _input(seg.expr, source, bit, offset + seg.offset)
        if vals is None:
            return None
        out.extend(vals)
    return out


def _in_slice(expr, source, bit, offset):
    if not expr.children or expr.bit_range is None:
        return None
    lo, hi = min(expr.bit_range), max(expr.bit_range)
    return [offset + (bit - lo)] if lo <= bit <= hi else []


def _in_cast(expr, source, bit, offset):
    if not expr.children:
        return None
    child = expr.children[0]
    vals = _input(child, source, bit, offset)
    if vals is None:
        return None
    if not _cast_extends_sign(expr, child, vals):
        return vals
    return vals + [offset + b for b in range(child.width, expr.width)]


def _cast_extends_sign(expr, child, vals):
    return (child.width is not None and child.width - 1 in vals
            and (expr.signed or child.signed) and expr.width is not None
            and expr.width > child.width)


def _shift_sign_fill(expr, child, bit, vals, offset, amount):
    child_sign = child.width - 1 if child.width is not None else None
    if (expr.op != "ShiftRightArithmetic" or not child.signed
            or child_sign is None
            or not (bit == child_sign or child_sign in vals)):
        return []
    start = max(0, child.width - amount)
    return [offset + b for b in range(start, expr.width or child.width)]


def _in_shift(expr, source, bit, offset):
    amount = _shift_amount(expr)
    if amount is None or not expr.children:
        return None
    child = expr.children[0]
    vals = _input(child, source, bit, 0)
    if vals is None:
        return None
    left = expr.op in ("ShiftLeft", "ShiftLeftArithmetic")
    delta = amount if left else -amount
    out = [offset + v + delta for v in vals
           if expr.width is None or 0 <= v + delta < expr.width]
    out += _shift_sign_fill(expr, child, bit, vals, offset, amount)
    return out


def _in_ternary(expr, source, bit, offset):
    if len(expr.children) != 3:
        return None
    left = _input(expr.children[1], source, bit, offset)
    right = _input(expr.children[2], source, bit, offset)
    if left is None or right is None:
        return None
    return left + right


_INPUT_HANDLERS = {
    "SignalRef": _in_signal, "Concat": _in_concat, "Slice": _in_slice,
    "Cast": _in_cast, "ShiftLeft": _in_shift, "ShiftRight": _in_shift,
    "ShiftLeftArithmetic": _in_shift, "ShiftRightArithmetic": _in_shift,
    "Ternary": _in_ternary, "Literal": lambda *_: [],
}


def _input(expr: Expr, source: str, bit: int, output_offset: int = 0):
    handler = _INPUT_HANDLERS.get(expr.op)
    return handler(expr, source, bit, output_offset) if handler else None


def input_output_bits(expr: Expr, source: str, bit: int) -> list[int] | None:
    """Output bits affected by a one-bit input source."""
    return _input(expr, source, bit, 0)
