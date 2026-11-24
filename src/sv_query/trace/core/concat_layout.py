"""Concat LHS/RHS bit-layout pairing (P198.4).

The old concat handler zipped leaf names, which loses width/orientation for
nested concat and slices. This module flattens typed IR into LSB-offset
segments and pairs them by bit range.
"""
from __future__ import annotations

from dataclasses import dataclass

from .expression_ir import Expr


@dataclass(frozen=True)
class Segment:
    expr: Expr
    width: int
    offset: int  # absolute bit offset from the LSB of this side


@dataclass(frozen=True)
class ConcatPair:
    lhs: Segment
    rhs: Segment


def _segment_width(expr: Expr) -> int | None:
    if expr.width is not None:
        return expr.width
    if expr.op == "Slice" and expr.children:
        return expr.children[0].width
    return None


def _flat_width(expr: Expr) -> int | None:
    if expr.op == "Concat":
        widths = [_flat_width(c) for c in expr.children]
        if not widths or any(w is None or w <= 0 for w in widths):
            return None
        return sum(widths)  # type: ignore[arg-type]
    return _segment_width(expr)


def flatten(expr: Expr) -> list[Segment] | None:
    """Flatten MSB-first concat into LSB-offset segments.

    ``None`` means width/orientation is unknown; callers must not guess.
    """
    out: list[Segment] = []

    def walk(node: Expr, base: int) -> bool:
        if node.op != "Concat":
            width = _segment_width(node)
            if width is None or width <= 0:
                return False
            out.append(Segment(expr=node, width=width, offset=base))
            return True
        widths = [_flat_width(c) for c in node.children]
        if not widths or any(w is None or w <= 0 for w in widths):
            return False
        cursor = base + sum(widths)  # type: ignore[arg-type]
        for child, width in zip(node.children, widths, strict=True):
            cursor -= width  # type: ignore[operator]
            if not walk(child, cursor):
                return False
        return True

    if not walk(expr, 0):
        return None
    return sorted(out, key=lambda s: s.offset)


def pair(lhs: Expr, rhs: Expr) -> list[ConcatPair] | None:
    """Pair lhs/rhs segments by absolute bit range.

    Returns None for unknown/ mismatched widths, so callers can emit explicit
    unknown instead of inventing a leaf mapping.
    """
    left = flatten(lhs)
    right = flatten(rhs)
    if left is None or right is None:
        return None
    if sum(s.width for s in left) != sum(s.width for s in right):
        return None
    out = []
    for lseg in left:
        l_lo, l_hi = lseg.offset, lseg.offset + lseg.width - 1
        for rseg in right:
            r_lo, r_hi = rseg.offset, rseg.offset + rseg.width - 1
            if l_lo == r_lo and l_hi == r_hi:
                out.append(ConcatPair(lhs=lseg, rhs=rseg))
                break
        else:
            return None
    return out


def signal_part(expr: Expr) -> tuple[str, tuple[int, int] | None] | None:
    """Return (base signal, optional bit range) for SignalRef/Slice."""
    if expr.op == "SignalRef" and expr.signal:
        return expr.signal, None
    if expr.op == "Slice" and expr.children:
        child = expr.children[0]
        if child.op == "SignalRef" and child.signal:
            return child.signal, expr.bit_range
    return None
