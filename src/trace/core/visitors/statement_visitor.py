"""[ADD 2026-06-27 A-PR7] Statement visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR7 2026-06-27] 抽 60 @on handler 涵盖 statement/block/event/control
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

Handler 类别:
- Statement: IfStatement/CaseStatement/RandCaseStatement/ReturnStatement/...
- Block: AlwaysBlock/AlwaysCombBlock/AlwaysFFBlock/InitialBlock/FinalBlock/SequentialBlockStatement/ParallelBlockStatement/ActionBlock
- Assign: ProceduralAssignStatement/ContinuousAssign/NonblockingAssignment/...
- Assert: ImmediateAssertStatement/ImmediateAssumeStatement/ImmediateCoverStatement/DeferredAssertion
- Event/Wait: EventControl/WaitStatement/WaitForkStatement/WaitOrderStatement/...
- Cover: Coverpoint/CoverCross/CoverageOption/CoverageBins/...
- Specify: SpecifyBlock/TimingControlStatement
- Control: JumpStatement/DisableStatement/DisableForkStatement
- Misc: NamedBlockClause/IffEventClause/EventType/TimingCheckEventArg/...

Total: 60 @on handler (~514 行, 5-13 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class StatementVisitor:
    """[ADD 2026-06-27 A-PR7] 抽所有 statement/block/event/control @on handler
    到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("EventControl")
    def extract_event_control(self, node) -> SignalResult:
        """[NOT TESTED] EventControl: @event"""
        event = getattr(node, "event", None)
        if event:
            return self.extract(event)
        return SignalResult()

    @on("EmptyStatement")
    def extract_empty_statement(self, node) -> SignalResult:
        """[NOT TESTED] EmptyStatement: empty statement"""
        return SignalResult()

    @on("ProceduralAssignStatement")
    def extract_procedural_assign_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralAssignStatement: procedural assign"""
        result = SignalResult()
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, "rvalue", None) or getattr(node, "expr", None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result

    @on("ProceduralForceStatement")
    def extract_procedural_force_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralForceStatement: procedural force"""
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()

    @on("ImplicitEventControl")
    def extract_implicit_event_control(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitEventControl: @@"""
        return SignalResult()

    @on("WaitForkStatement")
    def extract_wait_fork_statement(self, node) -> SignalResult:
        """[NOT TESTED] WaitForkStatement: wait fork"""
        return SignalResult()

    @on("WaitOrderStatement")
    def extract_wait_order_statement(self, node) -> SignalResult:
        """[NOT TESTED] WaitOrderStatement: wait order"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("ProceduralDeassignStatement")
    def extract_procedural_deassign_statement(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralDeassignStatement: procedural deassign"""
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()

    @on("RandCaseStatement")
    def extract_rand_case_statement(self, node) -> SignalResult:
        """[NOT TESTED] RandCaseStatement: rand case"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("EventType")
    def extract_event_type(self, node) -> SignalResult:
        """[NOT TESTED] EventType: event type"""
        return SignalResult()

    @on("CoverSequenceStatement")
    def extract_cover_sequence_statement(self, node) -> SignalResult:
        """[NOT TESTED] CoverSequenceStatement: cover sequence statement"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        return result

    @on("ConstraintBlock")
    def extract_constraint_block(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintBlock: constraint block"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "constraints", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("CoverageBins")
    def extract_coverage_bins(self, node) -> SignalResult:
        """[NOT TESTED] CoverageBins: coverage bins"""
        result = SignalResult()
        value = getattr(node, "value", None) or getattr(node, "expr", None)
        if value:
            result = result.merge(self.extract(value))
        return result

    @on("CoverageBinsArraySize")
    def extract_coverage_bins_array_size(self, node) -> SignalResult:
        """[NOT TESTED] CoverageBinsArraySize: coverage bins array size"""
        result = SignalResult()
        size = getattr(node, "size", None) or getattr(node, "expr", None)
        if size:
            result = result.merge(self.extract(size))
        return result

    @on("DefaultCoverageBinInitializer")
    def extract_default_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] DefaultCoverageBinInitializer: default coverage bin initializer"""
        return SignalResult()

    @on("CaseStatement")
    def extract_case_statement_stmt(self, node) -> SignalResult:
        """[NOT TESTED] CaseStatement: case statement"""
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

    @on("AssertionItemPort")
    def extract_assertion_item_port(self, node) -> SignalResult:
        """[NOT TESTED] AssertionItemPort: assertion item port"""
        return SignalResult()

    @on("Coverpoint")
    def extract_coverpoint(self, node) -> SignalResult:
        """[NOT TESTED] Coverpoint: coverpoint"""
        result = SignalResult()
        transition = getattr(node, "transition", None) or getattr(node, "expr", None)
        if transition:
            result = result.merge(self.extract(transition))
        return result

    @on("CoverCross")
    def extract_cover_cross(self, node) -> SignalResult:
        """[NOT TESTED] CoverCross: cover cross"""
        return SignalResult()

    @on("CoverageOption")
    def extract_coverage_option(self, node) -> SignalResult:
        """[NOT TESTED] CoverageOption: coverage option"""
        return SignalResult()

    @on("CoverageIffClause")
    def extract_coverage_iff_clause(self, node) -> SignalResult:
        """[NOT TESTED] CoverageIffClause: coverage iff clause"""
        expr = getattr(node, "expr", None) or getattr(node, "condition", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    @on("BlockCoverageEvent")
    def extract_block_coverage_event(self, node) -> SignalResult:
        """[NOT TESTED] BlockCoverageEvent: block coverage event"""
        return SignalResult()

    # Bad and invalid expressions
    @on("BlockingEventTriggerStatement")
    def extract_blocking_event_trigger_statement(self, node) -> SignalResult:
        """[NOT TESTED] BlockingEventTriggerStatement: blocking event trigger"""
        event = getattr(node, "event", None) or getattr(node, "expr", None)
        if event:
            return self.extract(event)
        return SignalResult()

    # Default disable declaration
    @on("ContinuousAssign")
    def extract_continuous_assign(self, node) -> SignalResult:
        """[NOT TESTED] ContinuousAssign: continuous assignment"""
        result = SignalResult()
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, "rvalue", None) or getattr(node, "expr", None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result

    @on("ReturnStatement")
    def extract_return_statement(self, node) -> SignalResult:
        """[NOT TESTED] ReturnStatement: return statement"""
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    @on("DisableStatement")
    def extract_disable_statement(self, node) -> SignalResult:
        """[NOT TESTED] DisableStatement: disable statement"""
        return SignalResult()

    # Wait statements
    @on("WaitStatement")
    def extract_wait_statement_stmt(self, node) -> SignalResult:
        """[NOT TESTED] WaitStatement: wait statement"""
        cond = getattr(node, "cond", None) or getattr(node, "expression", None)
        if cond:
            return self.extract(cond)
        return SignalResult()

    @on("RandSequenceStatement")
    def extract_rand_sequence_statement(self, node) -> SignalResult:
        """[NOT TESTED] RandSequenceStatement: rand sequence statement"""
        return SignalResult()

    # Immediate assertion statements
    @on("ImmediateAssertStatement")
    def extract_immediate_assert_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssertStatement: immediate assert statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, "action", None)
        if action:
            result = result.merge(self.extract(action))
        return result

    @on("ImmediateAssumeStatement")
    def extract_immediate_assume_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssumeStatement: immediate assume statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result

    @on("ImmediateCoverStatement")
    def extract_immediate_cover_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateCoverStatement: immediate cover statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result

    # Deferred assertion statements
    @on("ForeverStatement")
    def extract_forever_statement(self, node) -> SignalResult:
        """[NOT TESTED] ForeverStatement: forever statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("JumpStatement")
    def extract_jump_statement(self, node) -> SignalResult:
        """[NOT TESTED] JumpStatement: break, continue, return, disable statements"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "value", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # Return statement
    @on("DisableForkStatement")
    def extract_disable_fork_statement(self, node) -> SignalResult:
        """[NOT TESTED] DisableForkStatement: disable fork statement"""
        return SignalResult()

    # Wait statement
    @on("ProceduralReleaseStatement")
    def extract_procedural_release_statement(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralReleaseStatement: procedural release statement"""
        return SignalResult()

    # Event trigger statements
    @on("NonblockingEventTriggerStatement")
    def extract_nonblocking_event_trigger_statement(self, node) -> SignalResult:
        """[NOT TESTED] NonblockingEventTriggerStatement: nonblocking event trigger ->>"""
        return SignalResult()

    # Property expressions
    @on("AlwaysBlock")
    def extract_always_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysBlock: always block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AlwaysCombBlock")
    def extract_always_comb_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysCombBlock: always_comb block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AlwaysFFBlock")
    def extract_always_ff_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysFFBlock: always_ff block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AlwaysLatchBlock")
    def extract_always_latch_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysLatchBlock: always_latch block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("InitialBlock")
    def extract_initial_block(self, node) -> SignalResult:
        """[NOT TESTED] InitialBlock: initial block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("FinalBlock")
    def extract_final_block(self, node) -> SignalResult:
        """[NOT TESTED] FinalBlock: final block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("SequentialBlockStatement")
    def extract_sequential_block_statement(self, node) -> SignalResult:
        """[NOT TESTED] SequentialBlockStatement: sequential block statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("ParallelBlockStatement")
    def extract_parallel_block_statement(self, node) -> SignalResult:
        """[NOT TESTED] ParallelBlockStatement: parallel block statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("ActionBlock")
    def extract_action_block(self, node) -> SignalResult:
        """[NOT TESTED] ActionBlock: action block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("RsCodeBlock")
    def extract_rs_code_block(self, node) -> SignalResult:
        """[NOT TESTED] RsCodeBlock: randsequence code block"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("EqualsAssertionArgClause")
    def extract_equals_assertion_arg_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsAssertionArgClause: equals assertion arg clause"""
        return SignalResult()

    @on("IffEventClause")
    def extract_iff_event_clause(self, node) -> SignalResult:
        """[NOT TESTED] IffEventClause: iff event clause"""
        return SignalResult()

    @on("NamedBlockClause")
    def extract_named_block_clause(self, node) -> SignalResult:
        """[NOT TESTED] NamedBlockClause: named block clause"""
        return SignalResult()

    @on("TimingCheckEventArg")
    def extract_timing_check_event_arg(self, node) -> SignalResult:
        """[NOT TESTED] TimingCheckEventArg: timing check event arg"""
        return SignalResult()

    @on("TimingCheckEventCondition")
    def extract_timing_check_event_condition(self, node) -> SignalResult:
        """[NOT TESTED] TimingCheckEventCondition: timing check event condition"""
        return SignalResult()

    @on("IdWithExprCoverageBinInitializer")
    def extract_id_with_expr_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] IdWithExprCoverageBinInitializer: id with expr coverage bin initializer"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("SpecifyBlock")
    def extract_specify_block(self, node) -> SignalResult:
        """[NOT TESTED] SpecifyBlock: specify block"""
        return SignalResult()

    @on("TimingControlStatement")
    def extract_timing_control_statement(self, node) -> SignalResult:
        """[NOT TESTED] TimingControlStatement: timing control statement"""
        return SignalResult()

    @on("TransListCoverageBinInitializer")
    def extract_translistcoveragebininitializer(self, node) -> SignalResult:
        """[NOT TESTED] TransListCoverageBinInitializer: Translistcoveragebininitializer"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpInitialStmt")
    def extract_udpinitialstmt(self, node) -> SignalResult:
        """[NOT TESTED] UdpInitialStmt: Udpinitialstmt"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("OneStepDelay")
    def extract_onestepdelay(self, node) -> SignalResult:
        """[NOT TESTED] OneStepDelay: Onestepdelay"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("LibraryIncludeStatement")
    def extract_libraryincludestatement(self, node) -> SignalResult:
        """[NOT TESTED] LibraryIncludeStatement: Libraryincludestatement"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DeferredAssertion")
    def extract_deferredassertion(self, node) -> SignalResult:
        """[NOT TESTED] DeferredAssertion: Deferredassertion"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("CycleDelay")
    def extract_cycledelay(self, node) -> SignalResult:
        """[NOT TESTED] CycleDelay: Cycledelay"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result
