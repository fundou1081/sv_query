`timescale 1ns/1ps
// Simple leaf pipeline module (compiles cleanly in pyslang)
module leaf_pipeline(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        data_i,
    output reg         data_o
);
    reg stage1_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) stage1_q <= 0;
        else stage1_q <= data_i;
    end
    assign data_o = stage1_q;
endmodule

module leaf_adder(
    input  wire [7:0]  a,
    input  wire [7:0]  b,
    output reg  [7:0]  sum
);
    always @(*) sum = a + b;
endmodule
