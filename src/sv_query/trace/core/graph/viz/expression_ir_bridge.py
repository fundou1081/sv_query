"""Typed semantic IR -> viz expression tree bridge (P198.6)."""
from __future__ import annotations

from typing import Any

from .expression_tree import ExpressionTree, ExprNode

_LABELS = {
    "Add": "+", "Sub": "-", "Mul": "*", "Div": "/", "Mod": "%",
    "And": "&", "Or": "|", "Xor": "^", "Not": "!", "Neg": "-",
    "ShiftLeft": "<<", "ShiftRight": ">>", "Concat": "{}",
    "Cast": "cast", "Ternary": "?:", "Slice": "[]", "Call": "call",
}


def _label(expr: Any) -> tuple[str, str]:
    if expr.op == "SignalRef":
        return expr.signal, "SignalRef"
    if expr.op == "Literal":
        return expr.literal, "Const"
    if expr.op == "Slice":
        return str(expr.bit_range or "[]"), "Slice"
    if expr.op == "Call":
        return expr.signal or "call", "Call"
    if expr.op == "Unknown":
        return expr.reason or "unknown", "Unknown"
    return _LABELS.get(expr.op, expr.op), expr.op


def ir_to_tree(expr: Any) -> ExpressionTree | None:
    if expr is None:
        return None
    if not hasattr(expr, "op"):
        raise ValueError("ir_to_tree: Expr required")
    label, op = _label(expr)
    children = []
    for child in expr.children:
        tree = ir_to_tree(child)
        if tree is not None and tree.root is not None:
            children.append(tree.root)
    width = (expr.width - 1, 0) if expr.width else None
    return ExpressionTree(root=ExprNode(op=op, label=label, width=width,
                                       children=children))


def collect_ir(expr: Any, dst_short: str, const_map: dict,
               func_info: dict) -> None:
    """Collect constants/calls from typed IR (P198.6)."""
    if expr is None:
        return
    if expr.op == "Literal":
        const_map.setdefault(dst_short, [])
        if expr.literal not in const_map[dst_short]:
            const_map[dst_short].append(expr.literal)
    if expr.op == "Call" and expr.signal:
        func_info.setdefault(expr.signal, None)
    for child in expr.children:
        collect_ir(child, dst_short, const_map, func_info)
