"""
test_localparam_driver_filter.py
================================
[Regression 2026-07-15] Verify localparam/parameter do NOT appear as DRIVER
edges in trace_fanin output.

History:
- Fix F (2026-7-14): Filter NamedValueExpression with symbol.kind=Parameter
- Fix F.5 (2026-7-15): Extend filter to IdentifierNameSyntax (Syntax AST)
  via module.body.lookupName()

Both fixes are needed because pyslang returns DIFFERENT AST node types
for the same identifier depending on context:
- Normal reference: NamedValueExpression (Semantic, has .symbol)
- Used as case-item pattern AND procedural RHS: IdentifierNameSyntax (Syntax, no .symbol)

This test exercises both paths with minimal SV that reproduces the bug.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import pytest
from trace.unified_tracer import UnifiedTracer
from trace.core.query.signal import SignalTracer


def _build_tracer(source: str, name: str = "test"):
    """Helper: build tracer from inline SV source."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
        # Wrap source in a module so pyslang accepts it
        f.write(source)
        f.flush()
        path = f.name
    try:
        tracer = UnifiedTracer(files=[path])
        graph = tracer.build_graph()
        return tracer, graph
    finally:
        os.unlink(path)


def _fanin_drivers(tracer, signal: str, module: str = None):
    """Helper: return list of driver ids from trace_fanin."""
    st = tracer._signal_tracer
    drivers = st.trace_fanin(signal, module, depth=1)
    return [d.id for d in drivers]


# =============================================================================
# Path 1: NamedValueExpression (Fix F) - simple always block with localparam RHS
# =============================================================================

class TestLocalparamRHSInSimpleAlways:
    """When localparam is RHS in a plain always block (no case).
    
    AST is NamedValueExpression. Fix F's .symbol check works.
    """

    SOURCE = """
    module simple(
        input wire clk,
        output reg [3:0] result
    );
        localparam S0 = 4'd5;
        always @(posedge clk) begin
            result <= S0;
        end
    endmodule
    """

    def test_simple_always_localparam_rhs_excluded(self):
        tracer, graph = _build_tracer(self.SOURCE, "simple")
        drivers = _fanin_drivers(tracer, "simple.result")
        assert "simple.S0" not in drivers, \
            f"S0 (localparam) should NOT be a driver, got: {drivers}"


# =============================================================================
# Path 2: IdentifierNameSyntax (Fix F.5) - case item pattern + localparam RHS
# =============================================================================

class TestLocalparamInCaseItemRHS:
    """When localparam is used as BOTH case-item pattern AND case-item body RHS.

    This is the path that pyslang returns IdentifierNameSyntax (Syntax AST)
    which doesn't have .symbol attribute. Fix F.5 adds module.body.lookupName
    fallback to resolve it.

    This is the EXACT pattern from picorv32.v line 1612:
        case (cpu_state)
            cpu_state_trap: cpu_state <= cpu_state_trap;
    """

    SOURCE = """
    module case_min(
        input  wire        clk,
        input  wire [7:0]  cpu_state,
        output reg         trap
    );
        localparam cpu_state_trap = 8'b10000000;
        always @(posedge clk) begin
            case (cpu_state)
                cpu_state_trap: trap <= cpu_state_trap;
                default:       trap <= 1'b0;
            endcase
        end
    endmodule
    """

    def test_case_item_pattern_and_rhs_localparam_excluded(self):
        tracer, graph = _build_tracer(self.SOURCE, "case_min")
        drivers = _fanin_drivers(tracer, "case_min.trap")
        assert "case_min.cpu_state_trap" not in drivers, \
            f"cpu_state_trap (localparam) should NOT be a driver, got: {drivers}"

    def test_case_item_lhs_only_localparam_excluded(self):
        """localparam appears ONLY as case pattern (RHS is literal).
        This is handled by Fix F alone (no Fix F.5 needed).
        """
        source = """
        module pattern_only(
            input  wire        clk,
            input  wire [1:0]  sel,
            output reg [3:0]   result
        );
            localparam S0 = 2'b00;
            always @(posedge clk) begin
                case (sel)
                    S0: result <= 4'd0;
                    default: result <= 4'd15;
                endcase
            end
        endmodule
        """
        tracer, _ = _build_tracer(source, "pattern_only")
        drivers = _fanin_drivers(tracer, "pattern_only.result")
        assert "pattern_only.S0" not in drivers, \
            f"S0 (localparam) should NOT be a driver, got: {drivers}"


# =============================================================================
# Negative control: literal RHS should STILL appear (sanity check)
# =============================================================================

class TestLiteralRHSStillAppears:
    """Literal values like 4'd15 are CONST, not Parameter.
    They SHOULD appear as drivers (or as CONST nodes).
    """

    SOURCE = """
    module literal_test(
        input  wire        clk,
        output reg [3:0]   result
    );
        always @(posedge clk) begin
            result <= 4'd15;
        end
    endmodule
    """

    def test_literal_rhs_appears_as_driver(self):
        tracer, _ = _build_tracer(self.SOURCE, "literal_test")
        drivers = _fanin_drivers(tracer, "literal_test.result")
        # The literal 4'd15 should be a driver (as CONST or some signal)
        # We don't check exact form, just that something is there
        assert len(drivers) > 0, "Literal RHS should produce at least one driver"


# =============================================================================
# Negative control: real signal RHS should appear (sanity check)
# =============================================================================

class TestSignalRHSStillAppears:
    """A real reg/wire RHS should still appear as driver.
    """

    SOURCE = """
    module signal_rhs(
        input  wire        clk,
        input  wire [3:0]  data_in,
        output reg [3:0]   result
    );
        reg [3:0] state;
        always @(posedge clk) begin
            state   <= data_in;
            result  <= state;
        end
    endmodule
    """

    def test_signal_rhs_appears_as_driver(self):
        tracer, _ = _build_tracer(self.SOURCE, "signal_rhs")
        drivers = _fanin_drivers(tracer, "signal_rhs.result")
        assert "signal_rhs.state" in drivers, \
            f"state (real reg) should be a driver, got: {drivers}"


# =============================================================================
# Path 3: Continuous assign with ternary localparam RHS (the remaining leak)
# 
# This is the SECOND branch of the same bug Fix F/F.5 tries to solve.
# _handle_normal_assign goes through _signal_visitor.get_signals_with_conditions
# which returns string tuples, not AST nodes. The compile-time filter doesn't apply.
#
# Per docs/CODE_DISCIPLINE_FIX_COMPLETENESS.md, this MUST be fixed (no known
# limitations). Test below asserts the CORRECT behavior; will fail until fixed.
# =============================================================================

class TestLocalparamInContinuousAssignTernary:
    """Localparam in continuous-assign ternary branch must be excluded.

    Reproducer:
        assign result = sel ? LOCALPARAM : OTHER;

    Where LOCALPARAM is declared with `localparam`.
    """

    SOURCE = """
    module assign_ternary(
        input  wire [1:0] sel,
        output wire [3:0] result
    );
        localparam S0 = 4'd5;
        localparam S1 = 4'd7;
        assign result = (sel == 2'b00) ? S0 :
                        (sel == 2'b01) ? S1 : 4'd15;
    endmodule
    """

    def test_ternary_localparam_in_continuous_assign_excluded(self):
        """Both S0 and S1 (localparams) MUST NOT appear as drivers."""
        tracer, _ = _build_tracer(self.SOURCE, "assign_ternary")
        drivers = _fanin_drivers(tracer, "assign_ternary.result")
        assert "assign_ternary.S0" not in drivers, \
            f"S0 (localparam) should NOT be a driver, got: {drivers}"
        assert "assign_ternary.S1" not in drivers, \
            f"S1 (localparam) should NOT be a driver, got: {drivers}"

    def test_ternary_non_localparam_branches_preserved(self):
        """sel (port) and 4'd15 (literal) SHOULD still appear."""
        tracer, _ = _build_tracer(self.SOURCE, "assign_ternary")
        drivers = _fanin_drivers(tracer, "assign_ternary.result")
        # sel should still be a driver (it's a real port)
        assert "assign_ternary.sel" in drivers, \
            f"sel (port) should be a driver, got: {drivers}"
        # The literal 4'd15 should be a driver (CONST)
        has_const_15 = any("1111" in d for d in drivers)
        assert has_const_15, \
            f"4'd15 literal should be a driver (as CONST), got: {drivers}"
