`timescale 1ns/1ps
// [Golden Testcase 5] SUBMODULE — chain crosses submodule boundary
// Expected: 0 anomalies (port crossings are valid)
module top (
    input  wire clk_i,
    input  wire [7:0] data_i,
    output wire [7:0] data_o
);
    wire [7:0] sub_out;
    sub u_sub (.a_i(data_i), .b_o(sub_out));
    assign data_o = sub_out;
endmodule
