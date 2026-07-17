`timescale 1ns/1ps
// Minimal l2_distribute fixture (pattern from ventus l2_distribute.v).
// 1-to-N distribution: 1 input broadcast to N outputs with per-output valid.
// Compiles cleanly in pyslang.

module l2_distribute(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [3:0]  data_i,
    input  wire        valid_i,
    output reg  [3:0]  data_o_0,
    output reg  [3:0]  data_o_1,
    output reg  [3:0]  data_o_2,
    output reg  [3:0]  data_o_3,
    output reg         valid_o
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_o_0 <= 0; data_o_1 <= 0; data_o_2 <= 0; data_o_3 <= 0;
            valid_o  <= 0;
        end else begin
            data_o_0 <= data_i;
            data_o_1 <= data_i;
            data_o_2 <= data_i;
            data_o_3 <= data_i;
            valid_o  <= valid_i;
        end
    end
endmodule
