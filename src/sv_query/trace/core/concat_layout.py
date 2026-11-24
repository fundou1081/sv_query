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
    if expr.op == "Slice":
        return None  # a slice without semantic width is unknown
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


def _subexpr(seg: Segment, lo: int, hi: int) -> Expr | None:
    """Sub-expression for relative bits [lo, hi] of a segment."""
    if lo == 0 and hi == seg.width - 1:
        return seg.expr
    expr = seg.expr
    if expr.op == "SignalRef":
        return Expr(op="Slice", width=hi - lo + 1, children=(expr,),
                    bit_range=(hi, lo))
    if expr.op == "Slice" and expr.children and expr.bit_range is not None:
        msb, lsb = expr.bit_range
        direction = 1 if msb >= lsb else -1
        start = lsb + direction * lo
        end = lsb + direction * hi
        # The graph's slice-expansion pass expects descending [hi:lo].
        # Keep the physical bits direction-correct, but always emit the
        # higher index first so per-bit expansion still happens.
        high, low = max(start, end), min(start, end)
        return Expr(op="Slice", width=hi - lo + 1,
                    children=(expr.children[0],),
                    bit_range=(high, low))
    return None  # literal/unknown subrange: caller must mark unknown


def pair(lhs: Expr, rhs: Expr) -> list[ConcatPair] | None:
    """Pair overlapping bit ranges, splitting wide/narrow segments.

    Returns None for unknown widths/unsupported subranges; the caller must emit
    an explicit unknown rather than fabricate a leaf mapping.
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
            lo, hi = max(l_lo, r_lo), min(l_hi, r_hi)
            if lo > hi:
                continue
            lsub = _subexpr(lseg, lo - lseg.offset, hi - lseg.offset)
            rsub = _subexpr(rseg, lo - rseg.offset, hi - rseg.offset)
            if lsub is None or rsub is None:
                return None
            out.append(ConcatPair(
                lhs=Segment(expr=lsub, width=hi - lo + 1, offset=lo),
                rhs=Segment(expr=rsub, width=hi - lo + 1, offset=lo)))
    return out


def signal_part(expr: Expr) -> tuple[str, tuple[int, int] | None] | None:
    """Return (base signal, optional bit range) for SignalRef/Slice."""
    if expr.op == "SignalRef" and expr.signal:
        return expr.signal, None
    if expr.op == "Slice" and expr.children:
        if expr.reason or expr.bit_range is None:
            return None  # dynamic/unresolved select is not a whole-signal source
        child = expr.children[0]
        if child.op == "SignalRef" and child.signal:
            return child.signal, expr.bit_range
    return None
