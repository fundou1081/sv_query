"""[ADD 2026-06-26 A-PR4] Generate visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR4 2026-06-26] 抽 12 @on handler 涵盖 generate/loop/foreach 等
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 1-2 min.

Handler 类别:
- Generate: CaseGenerate/IfGenerate/LoopGenerate/GenerateBlock/GenerateRegion
- Loop: ForLoopStatement/ForeachLoopStatement/LoopStatement/DoWhileStatement
- Repeat: RepeatedEventControl/RsRepeat/ForeachLoopList

Total: 12 @on handler (163 行, 11-17 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class GenerateVisitor:
    """[ADD 2026-06-26 A-PR4] 抽所有 generate/loop/foreach @on handler 到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("CaseGenerate")
    def extract_case_generate(self, node) -> SignalResult:
        """[NOT TESTED] CaseGenerate: case generate construct"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "condition", None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("IfGenerate")
    def extract_if_generate(self, node) -> SignalResult:
        """[NOT TESTED] IfGenerate: if generate construct"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, "true_body", None) or getattr(node, "body", None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, "false_body", None) or getattr(node, "else_body", None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result


    @on("LoopGenerate")
    def extract_loop_generate(self, node) -> SignalResult:
        """[NOT TESTED] LoopGenerate: loop generate construct"""
        result = SignalResult()
        init = getattr(node, "init", None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, "step", None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result


    @on("GenerateBlock")
    def extract_generate_block(self, node) -> SignalResult:
        """[NOT TESTED] GenerateBlock: generate block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result


    @on("GenerateRegion")
    def extract_generate_region(self, node) -> SignalResult:
        """[NOT TESTED] GenerateRegion: generate region"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "statements", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Continuous assignment

    @on("ForLoopStatement")
    def extract_for_loop_statement(self, node) -> SignalResult:
        """[NOT TESTED] ForLoopStatement: for loop statement"""
        result = SignalResult()
        init = getattr(node, "init", None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, "cond", None) or getattr(node, "condition", None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, "step", None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result


    @on("ForeachLoopStatement")
    def extract_foreach_loop_statement(self, node) -> SignalResult:
        """[NOT TESTED] ForeachLoopStatement: foreach loop statement"""
        result = SignalResult()
        array = getattr(node, "array", None) or getattr(node, "expr", None)
        if array:
            result = result.merge(self.extract(array))
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result


    @on("LoopStatement")
    def extract_loop_statement(self, node) -> SignalResult:
        """[NOT TESTED] LoopStatement: loop statement (for, while, do-while, repeat, foreach)"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        vars_ = getattr(node, "variables", None) or getattr(node, "declarations", None)
        if vars_ and hasattr(vars_, "__iter__"):
            for v in vars_:
                if v:
                    result = result.merge(self.extract(v))
        return result


    @on("DoWhileStatement")
    def extract_do_while_statement(self, node) -> SignalResult:
        """[NOT TESTED] DoWhileStatement: do-while statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        cond = getattr(node, "condition", None) or getattr(node, "expr", None)
        if cond:
            result = result.merge(self.extract(cond))
        return result


    @on("RepeatedEventControl")
    def extract_repeated_event_control(self, node) -> SignalResult:
        """[NOT TESTED] RepeatedEventControl: repeated event control"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "events", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("RsRepeat")
    def extract_rsrepeat(self, node) -> SignalResult:
        """[NOT TESTED] RsRepeat: Rsrepeat"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ForeachLoopList")
    def extract_foreachlooplist(self, node) -> SignalResult:
        """[NOT TESTED] ForeachLoopList: Foreachlooplist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


