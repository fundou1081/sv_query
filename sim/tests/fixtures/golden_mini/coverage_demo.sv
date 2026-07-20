`timescale 1ns/1ps
// [V6 Golden Test 2026-07-20] Coverage example
// - SVA property for some signals but not all
// - 1 covergroup with bins
// - Exercises use case D (--show-coverage)
module coverage_demo(
    input  clk,
    input  [3:0] sel,
    output [3:0] y
);
    reg [3:0] state_q;
    reg [3:0] other_q;  // <- no SVA / covergroup -> should be 🚨

    always @(posedge clk) begin
        case (sel)
            4'd0: state_q <= 4'd0;
            4'd1: state_q <= 4'd1;
            default: state_q <= 4'd2;
        endcase
        other_q <= other_q + 1;
    end

    assign y = state_q;

    // SVA: cover state_q transitions
    property p_state_change;
        @(posedge clk) $changed(state_q);
    endproperty
    assert property (p_state_change);

    // Covergroup: cover sel values
    covergroup cg_sel @(posedge clk);
        cp_sel: coverpoint sel {
            bins b0 = {4'd0};
            bins b1 = {4'd1};
            bins b2 = {4'd2};
            bins b3 = {[4'd3:4'd15]};
        }
    endgroup
    cg_sel cg_inst = new();
endmodule
