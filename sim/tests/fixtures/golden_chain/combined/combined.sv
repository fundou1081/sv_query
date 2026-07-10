`timescale 1ns/1ps
// [Golden Testcase 4] COMBINED — X_DRIVER + DANGLING pattern
// Real RTL scenario: dead code chain where undriven wires feed a chain that has no consumer.
//
// Expected anomalies:
//   - isolated_a: X_DRIVER (no driver, but feeds chain)
//   - isolated_b: X_DRIVER (no driver, but feeds chain)
//   - chain_wire: DANGLING (driven by isolated_a/b but never read)
module combined (
    input  wire clk_i,
    input  wire rst_ni,
    input  wire [7:0] data_i,
    output wire [7:0] data_o
);
    reg [7:0] data_reg;
    always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) data_reg <= 8'h0;
        else         data_reg <= data_i;
    end

    // Dead code chain: undriven wires → chain_wire → nothing
    wire [7:0] isolated_a;
    wire [7:0] isolated_b;
    wire [7:0] chain_wire;
    assign chain_wire = isolated_a | isolated_b;

    assign data_o = data_reg;
endmodule
