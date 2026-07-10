`timescale 1ns/1ps
// [Golden Testcase 2] X_DRIVER — wire 'orphan_wire' has no driver
// Expected: 1 X_DRIVER anomaly for 'orphan_wire'
module x_driver (
    input  wire clk_i,
    input  wire rst_ni,
    input  wire [7:0] data_i,
    output wire [7:0] data_o
);
    // X_DRIVER: 'orphan_wire' is declared but NEVER assigned/driver
    // In simulation, this would be X (undefined)
    wire [7:0] orphan_wire;

    reg [7:0] data_reg;
    always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) data_reg <= 8'h0;
        else         data_reg <= data_i;
    end

    assign data_o = data_reg + orphan_wire;  // orphan_wire drives here
endmodule
