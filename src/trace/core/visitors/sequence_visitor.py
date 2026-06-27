"""[ADD 2026-06-27 A-PR11] Sequence visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR11 2026-06-27] 抽 13 @on handler 涵盖 assertion sequence expressions
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

Handler 类别:
- Compound: AndSequenceExpr/OrSequenceExpr/IntersectSequenceExpr/ThroughoutSequenceExpr/WithinSequenceExpr
- Repetition: SequenceRepetition
- Delay: DelayedSequenceExpr/DelayedSequenceElement
- Match: FirstMatchSequenceExpr/SequenceMatchList
- Clocking: ClockingSequenceExpr
- Simple: SimpleSequenceExpr/ParenthesizedSequenceExpr

Total: 13 @on handler (~141 行, 8-12 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class SequenceVisitor:
    """[ADD 2026-06-27 A-PR11] 抽所有 assertion sequence expression @on handler
    到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("SequenceRepetition")
    def extract_sequence_repetition(self, node) -> SignalResult:
        """[NOT TESTED] SequenceRepetition: seq[*1:3]"""
        seq = getattr(node, "sequence", None) or getattr(node, "operand", None)
        if seq:
            return self.extract(seq)
        return SignalResult()

    @on("AndSequenceExpr")
    def extract_and_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] AndSequenceExpr: and sequence expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("OrSequenceExpr")
    def extract_or_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] OrSequenceExpr: or sequence expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("FirstMatchSequenceExpr")
    def extract_first_match_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] FirstMatchSequenceExpr: first_match sequence expression"""
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            return self.extract(seq)
        return SignalResult()

    @on("ClockingSequenceExpr")
    def extract_clocking_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ClockingSequenceExpr: clocking sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, "clock", None)
        if clock:
            result = result.merge(self.extract(clock))
        return result

    @on("WithinSequenceExpr")
    def extract_within_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] WithinSequenceExpr: within sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        within = getattr(node, "within", None) or getattr(node, "expr2", None)
        if within:
            result = result.merge(self.extract(within))
        return result

    @on("ThroughoutSequenceExpr")
    def extract_throughout_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ThroughoutSequenceExpr: throughout sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        throughout = getattr(node, "throughout", None) or getattr(node, "expr2", None)
        if throughout:
            result = result.merge(self.extract(throughout))
        return result

    @on("SimpleSequenceExpr")
    def extract_simple_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimpleSequenceExpr: simple sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            return self.extract(seq)
        return result

    @on("DelayedSequenceExpr")
    def extract_delayed_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] DelayedSequenceExpr: delayed sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        return result

    @on("DelayedSequenceElement")
    def extract_delayed_sequence_element(self, node) -> SignalResult:
        """[NOT TESTED] DelayedSequenceElement: delayed sequence element"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("SequenceMatchList")
    def extract_sequence_match_list(self, node) -> SignalResult:
        """[NOT TESTED] SequenceMatchList: sequence match list"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("IntersectSequenceExpr")
    def extract_intersect_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] IntersectSequenceExpr: intersect sequence expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("ParenthesizedSequenceExpr")
    def extract_parenthesized_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedSequenceExpr: parenthesized sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            return self.extract(seq)
        return result

